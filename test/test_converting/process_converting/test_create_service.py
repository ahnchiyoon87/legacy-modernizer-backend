import asyncio
import json
import logging
import os
import re
import sys
import unittest
import aiofiles
import tiktoken

logging.basicConfig(level=logging.INFO)
logging.getLogger('asyncio').setLevel(logging.ERROR)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from test_converting.converting_prompt.service_prompt import convert_code
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
from cypher.neo4j_connection import Neo4jConnection


# * 인코더 설정 및 파일 이름 및 변수 초기화 
encoder = tiktoken.get_encoding("cl100k_base")
fileName = None
procedure_variables = []
service_skeleton = None

# 역할 : 전달받은 이름을 전부 소문자로 전환하는 함수입니다,
# 매개변수 : 
#   - fileName : 스토어드 프로시저 파일의 이름
# 반환값 : 전부 소문자로 전환된 프로젝트 이름
def convert_to_lower_case_no_underscores(fileName):
    return fileName.replace('_', '').lower()


# 역할: 각 노드의 스토어드 프로시저 코드의 첫 라인에서 식별되는 키워드로 타입을 얻어냅니다
# 매개변수: 
#      - code : 특정 노드의 스토어드 프로시저 코드
# 반환값: 식별된 키워드
def identify_first_line_keyword(code):
    try:
        first_line = code.split('\n')[0]   
        
        # * '숫자: 숫자:' 형태 이후의 첫 단어를 기준으로 키워드를 식별합니다.
        pattern = r"\d+:\s*\d+:\s*(DECLARE|SELECT|INSERT|UPDATE|DELETE|EXECUTE IMMEDIATE|CREATE OR REPLACE PROCEDURE|IF|FOR|COMMIT|MERGE|WHILE)\b"
        match = re.search(pattern, first_line)

        if match:
            first_keyword = match.group(1)
            return "OPERATION" if first_keyword == "EXECUTE IMMEDIATE" else first_keyword
        return "ASSIGN"
    except Exception:
        logging.exception("Error occurred while identifying first line keyword(understanding)")
        raise


# 역할: 주어진 스토어드 프로시저 코드의 토큰의 개수를 계산하는 함수입니다.
# 매개변수: 
#      - code - 토큰을 계산할 스토어드 프로시저
# 반환값: 계산된 토큰의 수
def count_tokens_in_text(code):
    
    if code == "": return 0

    try:
        # * 코드를 토큰화하고 토큰의 개수를 반환합니다.
        tokens = encoder.encode(code)
        return len(tokens)
    except Exception:
        logging.exception("Unexpected error occurred during token counting(converting)")
        raise


# 역할: 주어진 범위에서 startLine과 endLine을 추출해서 스토어드 프로시저 코드를 잘라내는 함수입니다.
# 매개변수: 
#     - file_content : 스토어드 프로시저 파일 전체 내용
#     - start_line : 시작 라인 번호
#     - end_line : 끝 라인 번호
# 반환값: 범위에 맞게 추출된 스토어드 프로시저 코드.
def extract_node_code(file_content, start_line, end_line):
    try:
        # * 지정된 라인 번호를 기준으로 코드를 추출합니다.
        extracted_lines = file_content[start_line-1:end_line]          


        # * 추출된 라인들을 하나의 문자열로 연결합니다.
        return ''.join(extracted_lines)
    except Exception:
        logging.exception("Error occurred while extracting node code")
        raise


# 역할: 전달된 노드의 스토어드 프로시저 코드에서 자식이 있을 경우 자식 부분을 요약합니다.
# 매개변수: 
#   file_content - 스토어드 프로시저 파일 전체 내용
#   node - (시작 라인, 끝 라인, 코드, 자식)을 포함한 노드 정보
# 반환값: 자식 코드들이 요약 처리된 노드 코드
def extract_and_summarize_code(file_content, node):

    def summarize_code(start_line, end_line, children):

        # * 시작 라인과 끝 라인을 기준으로 스토어드 프로시저 코드 라인을 추출합니다.
        code_lines = file_content[start_line-1:end_line]
        summarized_code = []
        last_end_line = start_line - 1


        # * 각 자식 노드에 대해 코드를 추출한 뒤, 요약 처리를 반복합니다.
        for child in children:
            before_child_code = code_lines[last_end_line-start_line+1:child['startLine']-start_line]
            summarized_code.extend([f"{i+last_end_line+1}: {line}" for i, line in enumerate(before_child_code)])
            summarized_code.append(f"{child['startLine']}: ... code ...\n")
            last_end_line = child['endLine']
        

        # * 마지막 자식 노드의 끝나는 지점 이후부터 노드의 끝나는 지점까지의 코드를 추가합니다
        after_last_child_code = code_lines[last_end_line-start_line+1:]
        summarized_code.extend([f"{i+last_end_line+1}: {line}" for i, line in enumerate(after_last_child_code)])
        return ''.join(summarized_code)
    
    try:

        # * 자식 노드가 없는 경우, 해당 노드의 코드만을 추출합니다.
        if not node.get('children'):
            code_lines = file_content[node['startLine']-1:node['endLine']]
            return ''.join([f"{i+node['startLine']}: {line}" for i, line in enumerate(code_lines)])
        else:
            # * 자식 노드가 있는 경우, summarize_code 함수를 호출하여 요약 처리합니다.
            return summarize_code(node['startLine'], node['endLine'], node.get('children', []))
    except Exception:
        logging.exception("during summarize code unexpected error occurred(converting)")
        raise


# 역할: 현재 스케줄에서 시작하여 스택에 있는 모든 스케줄을 역순으로 검토하면서 필요한 스토어드 프로시저 코드를 조합합니다.
# 매개변수: 
#      - current_schedule (dict): 현재 처리 중인 스케줄 정보
#      - schedule_stack (list): 처리된 스케줄들의 스택
# 반환값: 분석에 사용될 스토어드 프로시저 코드
def create_focused_code(current_schedule, schedule_stack):
    try:
        focused_code = current_schedule["code"]
        current_start_line = current_schedule["startLine"]


        # * 스택을 역순으로 검토하면서 스토어드 프로시저 코드를 조합합니다.
        for schedule in reversed(schedule_stack):
            placeholder = f"{current_start_line}: ... code ..."
            if placeholder in schedule["code"]:

                # * 현재 스케줄의 시작 라인을 플레이스홀더로 사용하여 실제 스토어드 프로시저 코드로 교체합니다.
                focused_code = schedule["code"].replace(placeholder, focused_code, 1)
                current_start_line = schedule["startLine"]

        return focused_code

    except Exception:
        logging.exception("An error occurred while creating focused code(converting)")
        raise


# 역할: 전달된 스토어드 프로시저 코드에서 불필요한 정보를 제거합니다.
# 매개변수: 
#      - code : 스토어드 프로시저 코드
# 반환값: 불필요한 정보가 제거된 스토어드 프로시저 코드.
def remove_unnecessary_information(code):
    try:
        if code == "": return code 


        # * 모든 주석을 제거합니다.
        code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
        code = re.sub(r'--.*$', '', code, flags=re.MULTILINE)
        # code = re.sub(r'^[\d\s:]*$', '', code, flags=re.MULTILINE)
        return code
    
    except Exception:
        logging.exception("Error during code placeholder removal(converting)")
        raise


# 역할: 해당 노드에서 사용된 변수노드를 가져오는 메서드입니다.
# 매개변수: 
#      - node_id : 노드의 고유 식별자.
# 반환값: 노드에서 사용된 변수 노드의 목록.
async def fetch_variable_nodes(node_id):
    
    try:
        # * 변수 노드를 가져오는 사이퍼쿼리를 준비한 뒤, 퀴리 실행하여, 가져온 정보를 추출합니다
        query = [f"MATCH (v:Variable) WHERE v.role_{node_id} IS NOT NULL RETURN v"]
        connection = Neo4jConnection()  
        variable_nodes = await connection.execute_queries(query) 
        variable_node_list = [node['v']['name'] for node in variable_nodes[0]]
        logging.info("\nSuccess received Variable Nodes from Neo4J\n")
        await connection.close()
        return variable_node_list

    except Exception:
        logging.exception("Error during bring variable node from neo4j(converting)")
        raise


# 역할 : Service 클래스 파일 생성하는 함수
# 매개변수 :
#   - service_name : 생성된 서비스 클래스 이름
#   - service_code : 생성된 서비스 클래스 코드
#   - LLM_count : 호출된 LLM 횟수
async def create_service_file(service_name, LLM_count, service_code):
    service_directory = os.path.join('test', 'test_converting', 'converting_result', 'service')
    os.makedirs(service_directory, exist_ok=True)
    service_file_path = os.path.join(service_directory, f"service{LLM_count}.txt")
    
    async with aiofiles.open(service_file_path, 'w', encoding='utf-8') as file:
        await file.write(service_code)
    
    logging.info(f"\nSuccess Create {service_name}{LLM_count} Java File\n")


# 역할: Service 클래스를 생성하기 위해 분석을 시작하는 함수입니다.
# 매개변수: 
#   data - 분석할 데이터 구조(ANTLR)
#   file_content - 분석할 스토어드 프로시저 파일의 내용.
#   jpa_method_list - 사용된 JPA 메서드 목록.
#   procedure_variable - 프로시저 선언부에서 선언된 변수 정보(입력 매개변수).
# 반환값 : 없음
async def analysis(data, file_content, jpa_method_list, procedure_variable):
    schedule_stack = []               # 스케줄 스택
    variable_list = {}                # 특정 노드에서 사용된 변수 목록
    jpa_query_methods = []            # 특정 노드에서 사용된 JPA 쿼리 메서드 목록
    clean_code= None                  # 불필요한 정보(주석)가 제거된 코드
    focused_code = ""                 # 전체적인 스토어드 프로시저 코드의 틀
    service_code = None               # 서비스 클래스 코드
    total_token_count = 0             # 토큰 수
    LLM_count = 0                     # LLM 호출 횟수
    node_token_count = 0              # 노드에 대한 토큰 사이즈
    statement_flag = 0                # 구문을 구분하는 플래그 (0 : 자식이 없는 단일 구문, 1: 자식이 있지만 토큰이 작은 구문, 2: 자식이 있지만 토큰이 매우 큰 구문, 3: converting에 쓸모 없는 구문 )
    parent_id_flag = 0                # 부모의 시작라인을 저장하는 변수로, 부모 노드에 대한 처리가 끝났는지 판단
    child_done_flag = 0               # 자식 노드에 대한 처리 여부를 나타내는 플래그 (0 : 자식이 아직 처리되지 않았음, 1: 모든 자식을 처리 했음)
    start_summarzied_flag = 0         # 요약에 대한 필요성을 나타내는 플래그 (0 : 요약할 필요없음, 1: 요약이 필요함)
    logging.info("\n Start creating a service class \n")


    # 역할: llm에게 분석할 스토어드 프로시저 코드를 전달한 뒤, 해당 결과를 바탕으로 Service를 생성합니다.
    # 반환값 : Service 클래스 파일
    async def process_analysis_results():
        nonlocal clean_code, total_token_count, LLM_count, focused_code, service_code
        
        try:
            # * 정리된 코드를 분석합니다(llm에게 전달)
            analysis_result = convert_code(clean_code, service_code, variable_list, jpa_query_methods, procedure_variables, fileName)
            LLM_count += 1


            # * 분석 결과 각각의 데이터를 추출하고, 필요한 변수를 초기화합니다 
            service_code = analysis_result['code']


            # * 서비스 클래스를 파일로 생성하고 SERVICE 틀을 초기화 합니다.
            if start_summarzied_flag != 1:
                await create_service_file(analysis_result['name'], LLM_count, analysis_result['code'])
                service_code = service_skeleton


            # * 다음 분석 주기를 위해 필요한 변수를 초기화합니다
            focused_code = ""
            clean_code = None
            total_token_count = 0
            variable_list.clear()

        except Exception:
            logging.exception("An error occurred during analysis results processing(converting)")
            raise
    

    # 역할: 토큰 수가 최대치를 초과할 경우, service 생성을 위해 처리하는 메서드를 호출합니다
    async def signal_for_process_analysis():
        try:
            analysis_task = asyncio.create_task(process_analysis_results())
            await asyncio.gather(analysis_task)
            
        except Exception:
            logging.exception(f"An error occurred during signal_for_process_analysis(converting)")
            raise


    # 역할: 재귀적으로 노드를 순회하며 구조를 탐색하고, 필요한 데이터를 처리하여 서비스 클래스를 생성하는 함수입니다.
    # 매개변수: 
    #   node - 분석할 노드.
    #   schedule_stack - 스케줄들의 스택.
    #   parent_id - 현재 노드의 부모 노드 ID.
    #   jpa_method_list - 사용된 JPA 메서드 목록.
    #   procedure_variable - 프로시저 선언부에서 사용된 변수 정보.
    # 반환값: 없음
    async def traverse(node, schedule_stack, jpa_method_list, procedure_variable, parent_id):
        nonlocal focused_code, total_token_count, clean_code, service_code, node_token_count, statement_flag, parent_id_flag, child_done_flag, start_summarzied_flag


        # * 순회를 시작하기에 앞서 필요한 정보를 초기화하고 준비합니다.
        summarized_code = extract_and_summarize_code(file_content, node)
        statementType = "ROOT" if node['startLine'] == 0 else ("DECLARE" if node['type'] == "DECLARE" else identify_first_line_keyword(summarized_code))
        children = node.get('children', [])
        is_parent_done = (child_done_flag == 1 or start_summarzied_flag == 1) and parent_id_flag >= parent_id
        current_schedule = {
            "startLine": node['startLine'],
            "endLine": node['endLine'],
            "code": summarized_code,
            "child": children,
        }


        # * 부모 노드에 대한 처리가 끝났을 경우, 플래그 변수들을 다시 초기화 합니다. 
        if is_parent_done:
            statement_flag = 0
            child_done_flag = 0
            if start_summarzied_flag == 1:
                start_summarzied_flag = 0


        # * 각 노드의 토큰 수와 전체적인 토큰 수를 계산합니다. 만약 이 노드의 부모 노드가 이미 처리되었다면, 이 노드는 건너뛰고 토큰 수를 계산하지 않습니다.
        if statementType not in {"OPERATION","CREATE OR REPLACE PROCEDURE", "ROOT", "DECLARE"} and child_done_flag != 1:
            node_code = remove_unnecessary_information(extract_node_code(file_content, node['startLine'], node['endLine']))
            clean_code = remove_unnecessary_information(focused_code)
            node_token_count = count_tokens_in_text(node_code)
            total_token_count = count_tokens_in_text(clean_code)
            total_token_count += node_token_count


        # * 토큰 수를 검사하여 분석 여부를 결정합니다.
        if (node_token_count >=1000 and clean_code) or (total_token_count >= 1200 and clean_code):
            signal_task = asyncio.create_task(signal_for_process_analysis())
            await asyncio.gather(signal_task)


        # * 현재 스토어드 프로시저 노드가 어떤 종류인지 플래그로 구분
        if statementType not in {"OPERATION", "DECLARE"} and not children:
            statement_flag = 0
        elif child_done_flag == 0 and statementType in {"IF", "WHILE", "FOR"} and node_token_count <= 1000:
            statement_flag = 1
            child_done_flag = 1
            parent_id_flag = parent_id
        elif statementType in {"IF", "WHILE", "FOR"} and node_token_count >= 1000:
            statement_flag = 2
            start_summarzied_flag = 1
            parent_id_flag = parent_id
        else:
            statement_flag = 3


        # * 플래그 변수 상태에 따라서 어떻게 분석할 코드를 선택할지를 결정
        if statement_flag == 0 and child_done_flag == 0 and start_summarzied_flag != 1:
            focused_code += "\n" + node_code
        elif statement_flag == 1 and child_done_flag == 1 and start_summarzied_flag != 1:
            focused_code += "\n" + node_code
        elif statement_flag == 2 and start_summarzied_flag == 0:
            schedule_stack.append(current_schedule)


        # * 자식을 가지고 있는 부모 노드가 매우 큰 경우, 요약을 진행  
        if start_summarzied_flag == 1:
            if focused_code == "":
                focused_code = schedule_stack[-1]['code']
            else:
                placeholder = f"{node['startLine']}: ... code ..."
                focused_code = focused_code.replace(placeholder, summarized_code, 1)
 

        # * 해당 노드에서 사용된 변수 노드 목록을 가져옵니다
        if statementType not in {"OPERATION","CREATE OR REPLACE PROCEDURE", "ROOT", "DECLARE"}:
            variable_nodes = await fetch_variable_nodes(node['startLine'])
            variable_list[f"startLine:{node['startLine']} endLine:{node['endLine']}"] = variable_nodes


        # * 현재 노드가 자식이 있는 경우, 해당 자식을 순회하면서 traverse함수를 (재귀적으로) 호출하고 처리합니다
        for child in children:
            node_explore_task = asyncio.create_task(traverse(child, schedule_stack, jpa_method_list, procedure_variable, node['startLine']))
            await asyncio.gather(node_explore_task)


    try:
        # * traverse 함수를 호출하여, 노드 순회를 시작합니다
        start_analysis_task = asyncio.create_task(traverse(data, schedule_stack , jpa_method_list, procedure_variable, 0))
        await asyncio.gather(start_analysis_task)


        # TODO 마지막 노드그룹에 대한 처리를 합니다
        if focused_code is not None:
            pass
        logging.info("\nLLM 호출 횟수 : " + str(LLM_count))

    except Exception:
        logging.exception("An error occurred during the analysis process(converting)")
        raise


# 역할: 스토어드 프로시저 파일과 ANTLR 분석 파일을 읽어서 분석을 시작하는 메서드입니다.
# 매개변수: 
#   fileName - 스토어드 프로시저 파일 이름
# 반환값: 없음 
async def start_service_processing(sp_fileName):
    
    # * 테스트에 필요한 데이터 준비 
    service_skeleton_code = """
package com.example.pbcac120calcsuipstd.service;

import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import com.example.pbcac120calcsuipstd.command.OgadwCommand;
import org.springframework.beans.factory.annotation.Autowired;
import java.util.List;
import org.springframework.transaction.annotation.Transactional;

@RestController
@Transactional
public class OgadwService {

    @PostMapping(path="/calculate")
    public void calculate(@RequestBody OgadwCommand command) {
    }
}
    """

  
    jpa_method_list = [
            {"19~22": "List<Employee> findByEmployeeId(@Param(\"p_employee_id\") Long pEmployeeId);"},
            {"26~30": "List<WorkLog> findByEmployeeIdAndWorkDateBetween(@Param(\"p_employee_id\") Long pEmployeeId)"},
            {"37~42": "List<LeaveRecords> findUnpaidLeaveDays(@Param(\"p_employee_id\") Long pEmployeeId)"}
    ]

    procedure_variable = {
            "procedureParameters": [
                "p_TL_APL_ID IN VARCHAR2",
                "p_TL_ACC_ID IN VARCHAR2",
                "p_APPYYMM IN VARCHAR2",
                "p_WORK_GBN IN VARCHAR2",
                "p_WORK_DTL_GBN IN VARCHAR2",
                "p_INSR_CMPN_CD IN VARCHAR2",
                "p_WORK_EMP_NO IN VARCHAR2",
                "p_RESULT OUT VARCHAR2",
            ]
    }
    
    # * 전역 변수 초기화
    global fileName, procedure_variables, service_skeleton
    fileName = convert_to_lower_case_no_underscores(sp_fileName)
    procedure_variables = list(procedure_variable["procedureParameters"])
    service_skeleton = service_skeleton_code


    # * 분석에 필요한 파일 경로 설정
    base_dir = os.path.dirname(__file__)  
    analysis_file_path = os.path.abspath(os.path.join(base_dir, '..', '..', '..', 'cypher', 'analysis', f'{sp_fileName}.json'))
    sql_file_path = os.path.abspath(os.path.join(base_dir, '..', '..', '..', 'cypher', 'sql', f'{sp_fileName}.txt'))
    

    # * 분석에 필요한 파일들(스토어드 프로시저, ANTLR 분석)의 내용을 읽습니다
    async with aiofiles.open(analysis_file_path, 'r', encoding='utf-8') as analysis_file, aiofiles.open(sql_file_path, 'r', encoding='utf-8') as sql_file:
        analysis_data, sql_content = await asyncio.gather(analysis_file.read(), sql_file.readlines())
        analysis_data = json.loads(analysis_data)


    # * 읽어들인 데이터를 바탕으로 분석 메서드를 호출합니다.
    await analysis(analysis_data, sql_content, jpa_method_list, procedure_variable)


# 서비스 생성을 위한 테스트 모듈입니다.
class TestAnalysisMethod(unittest.IsolatedAsyncioTestCase):
    async def test_create_service(self):
        await start_service_processing("P_B_CAC120_CALC_SUIP_STD")


if __name__ == "__main__":
    unittest.main()