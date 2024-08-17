import logging
import os
import re
import sys
import unittest
import tiktoken

logging.basicConfig(level=logging.INFO)
logging.getLogger('asyncio').setLevel(logging.ERROR)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from test_converting.converting_prompt.parent_skeleton_prompt import convert_parent_skeleton
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


# TODO 레이블 대문자 변경 필요!!
# 역할: 해당 노드에서 사용된 변수노드를 가져오는 메서드입니다.
# 매개변수: 
#      - node_id : 노드의 고유 식별자.
#      - variable_dict : 변수 리스트
# 반환값: 노드에서 사용된 변수 노드의 목록.
async def fetch_variable_nodes(node_id, variable_dict):
    try:
        query = [f"MATCH (v:Variable) WHERE v.role_{node_id} IS NOT NULL RETURN v.id, v.name, v"]
        connection = Neo4jConnection()
        variable_nodes = await connection.execute_queries(query)
        
        
        # * 전달된 변수 정보 데이터를 이용해서 사용하게 쉽게 재구성 
        for node in variable_nodes[0]:
            var_name = node['v']['name']
            role_start = node['v'][f'role_{node_id}']


            # * 역할 설명 정규화 (예: "저장합니다", "저장함", "저장됨" -> "저장")
            normalized_role = re.sub(r'합니다$|함$|됨$', '', role_start).strip()


            # * 중복된 역할 제거 후 리스트에 추가
            if var_name not in variable_dict:
                variable_dict[var_name] = {normalized_role}
            else:
                variable_dict[var_name].add(normalized_role)


        logging.info("\nSuccessfully received variable nodes from Neo4J\n")
        await connection.close()
        return variable_dict

    except Exception:
        logging.exception("Error during fetching variable nodes from Neo4J (converting)")
        raise


# 역할 : 노드를 업데이트할 쿼리를 실행하여 노드에 Java 속성을 추가하는 함수입니다.
# 매개변수 :
#   - node_update_query : 노드를 업데이트할 쿼리 리스트
async def process_node_update_java_properties(node_update_query):

    # * Neo4j 연결 생성 및 쿼리 실행
    connection = Neo4jConnection()
    await connection.execute_queries(node_update_query)
    logging.info(f"\nSuccessfully updated node properties\n")
    await connection.close()


# 역할 : 사이즈가 매우 큰 부모 노드를 처리하는 함수입니다.
# 매개변수 :
#   - start_line : 노드의 시작 라인
#   - summarized_code : 자식 노드의 요약 처리된 코드
async def process_over_size_node(start_line, summarized_code):

    # * 노드 업데이트 쿼리를 저장할 리스트
    node_update_query = []


    # * 요약된 코드를 분석하여 결과를 가져옵니다
    analysis_result = convert_parent_skeleton(summarized_code)
    logging.info(f"\nSuccessfully Converted Parent Node\n")
    service_code = analysis_result['code']


    # * Neo4j 데이터베이스에서 해당 노드의 Java 코드를 업데이트하는 쿼리 생성
    query = f"MATCH (n) WHERE n.startLine = {start_line} SET n.java_code = '{service_code.replace('\n', '\\n').replace("'", "\\'")}'"
    node_update_query.append(query)     


    # * 생성된 쿼리를 실행하는 함수를 호출
    await process_node_update_java_properties(node_update_query)


# 역할: llm에게 분석할 스토어드 프로시저 코드를 전달한 뒤, 해당 결과를 바탕으로 Service를 생성합니다.
# 매개변수:
#   - convert_sp_code : 스토어드 프로시저 코드
#   - total_tokens : 총 토큰 수
#   - variable_dict : 변수 리스트
#   - context_range : 컨텍스트 범위
# 반환값: 
#   - convert_sp_code : 초기화된 스토어드 프로시저 코드
#   - total_tokens : 초기화된 총 토큰 수
#   - variable_dict : 초기화된 변수 리스트
#   - context_range : 컨텍스트 범위
async def process_converting(convert_sp_code, total_tokens, variable_dict, context_range):
    
    try:
        # * 노드 업데이트 쿼리를 저장할 리스트 및 범위 개수
        node_update_query = []
        range_count = len(context_range)

        # * 정리된 코드를 분석합니다(llm에게 전달)
        analysis_result = convert_code(convert_sp_code, service_skeleton, variable_dict, procedure_variables, context_range, range_count)
        logging.info(f"\nsuccessfully converted code\n")


        # * 분석 결과 각각의 데이터를 추출하고, 필요한 변수를 초기화합니다 
        for result in analysis_result['analysis']:
            start_line = result['range']['startLine']
            service_code = result['code']
            query = f"MATCH (n) WHERE n.startLine = {start_line} SET n.java_code = '{service_code.replace('\n', '\\n').replace("'", "\\'")}'"
            node_update_query.append(query)        
        

        # * 노드 업데이트 쿼리를 실행하는 메서드를 호출 
        await process_node_update_java_properties(node_update_query)


        # * 다음 분석 주기를 위해 필요한 변수를 초기화합니다
        convert_sp_code = ""
        total_tokens = 0
        context_range.clear()
        variable_dict.clear()

        return (convert_sp_code, total_tokens, variable_dict, context_range)


    except Exception:
        logging.exception("An error occurred during analysis results processing(converting)")
        raise



# 역할: 실제 서비스를 생성하는 함수입니다.
# 매개변수: 
#   node_data_list - 노드와 관계에 대한 정보가 담긴 리스트
# 반환값: 없음 
async def process_service_class(node_data_list):

    variable_dict = {}                    # 변수의 역할 및 이름을 저장하는 딕셔너리
    context_range = []                    # 분석할 컨텍스트 범위를 저장하는 리스트
    total_tokens = 0                      # 총 토큰 수
    start_node_tokens = 0                 # 시작 노드의 토큰 수 
    over_size_parent_startLine = 0        # 토큰이 초과된 부모 노드의 시작 라인
    nomal_size_parent_startLine = 0       # 토큰이 초과되지 않는 부모 노드의 시작 라인
    next_parent_node_start_line = 0       # 처리 완료된 부모의 다음 노드의 시작라인
    statement_flag = 0                    # 구문 유형을 나타내는 플래그
    node_processed = 0                    # 이미 처리된 노드 상태를 저장하는 플래그
    convert_sp_code = ""                  # converting할 프로시저 코드를 저장하는 변수


    # * 비즈니스 로직과 관련된 모든 노드 순회
    for result in node_data_list:
        node_start = result['n']
        relationship = result['r']
        node_end = result['m']
        relationship_name = relationship[1]
        print("-" * 40) 
        print(f"시작 노드: {node_start['startLine']}, ({node_start['name']}), {node_start['endLine']}, tokens: {node_start['token']}")
        print(f"관계: {relationship_name}")
        print(f"종료 노드: {node_end['startLine']}, ({node_end['name']}), {node_end['endLine']}, tokens: {node_end['token']}")


        # * 부모 노드에 대한 처리가 끝났는지, 모든 자식들의 처리가 끝났는지, 이미 처리된 부모 노드에서 새로운 부모 노드가 발견되었는지, 이미 처리된 자식노드인지 검토
        all_child_traversed = next_parent_node_start_line !=0 and next_parent_node_start_line == node_start['startLine']
        if all_child_traversed: print("모든 자식 노드 순회 완료, 다음 부모 노드 시작라인 초기화\n"); next_parent_node_start_line = 0
        oversized_parent_processed = over_size_parent_startLine == node_start['startLine'] and relationship_name == "NEXT"
        normal_size_parent_processed = nomal_size_parent_startLine == node_start['startLine'] and relationship_name == "NEXT"
        child_node_already_processed = next_parent_node_start_line !=0 and next_parent_node_start_line != node_start['startLine'] and relationship_name == "NEXT"
        encountered_inner_parent_node = next_parent_node_start_line !=0 and next_parent_node_start_line != node_start['startLine'] and relationship_name == "PARENT_OF"


        # * 이미 처리된 자식 노드에 대한 중복 처리 방지
        if child_node_already_processed: print(f"이미 처리된 자식 노드 : [{node_start['startLine']}, {node_end['startLine']}] 에 대한 중복 처리\n"); continue


        # * (사이즈가 작은)부모 노드가 중복처리 되는 경우를 방지하고, 변수값을 초기화 합니다.
        if normal_size_parent_processed:
            print(f"토큰이 작은 부모 노드 : [{node_start['startLine']}] 에 대한 중복 방지\n")
            context_range.append({"startLine": node_start['startLine'], "endLine": node_start['endLine']})
            next_parent_node_start_line = node_end['startLine']
            nomal_size_parent_startLine = 0
            node_processed = 0
            continue
        

        # * (사이즈가 큰)부모 노드가 중복처리 되는 경우를 방지하고, 변수값을 초기화합니다.
        if oversized_parent_processed:
            print(f"토큰이 큰 부모 노드 : [{node_start['startLine']}] 에 대한 중복 방지\n")
            next_parent_node_start_line = node_end['startLine']
            over_size_parent_startLine = 0
            continue        


        # * 이미 처리된 노드 상태거나, 부모 노드 안에 다른 부모노드를 만나지 않았다면, 총 토큰 수 검사를 진행합니다.
        if node_processed == 0 and not encountered_inner_parent_node:
            if over_size_parent_startLine == 1 or nomal_size_parent_startLine == 1:
                total_tokens_to_check = total_tokens + node_end['token']
                print(f"자식 노드의 토큰 검사 : [{total_tokens} + {node_end['token']}] \n")
            else:
                total_tokens_to_check = total_tokens + node_start['token']
                print(f"단일 노드 및 크기가 작은 부모 노드 토큰 검사 : [{total_tokens} + {node_start['token']}]\n")

            if total_tokens_to_check >= 1200:
                print(f"토큰 수 : [{total_tokens_to_check}], 토큰 초과 converting 진행합니다.\n")
                (convert_sp_code, total_tokens, variable_dict, context_range) = await process_converting(convert_sp_code, total_tokens, variable_dict, context_range)
                total_tokens_to_check = 0
        else:
            print("모든 자식이 처리가 완료되었으므로, 토큰 검사를 건너뜁니다.\n")


        # * 각 노드의 타입에 따라서 플래그를 설정합니다.
        if relationship_name == "PARENT_OF":
            if start_node_tokens > 1000:                                   # 토큰을 초과하는 부모 노드의 경우, 각 종 플래그를 설정합니다
                statement_flag = 2                                         # 부모 노드에 대한 순회가 끝났다는 것을 알아채기 위해 부모 노드의 시작라인을 기억합니다.
                over_size_parent_startLine = node_start['startLine']
            elif encountered_inner_parent_node:                            # 이미 처리된 부모 노드에서 또 다른 부모 노드를 만났을 때, 플래그를 5로 설정합니다
                statement_flag = 5
            elif start_node_tokens <= 1000 and not node_processed:         # 토큰을 초과하지 않는 부모 노드의 경우, 각 종 플래그를 초기화합니다.
                statement_flag = 1                                         # node_processed를 1로 하여, 자식 노드들에 대한 처리가 이미 다 끝났다는 것을 알립니다.
                node_processed = 1                                         # 부모 노드에 대한 순회가 끝났다는 것을 알아채기 위해 부모 노드의 시작라인을 기억합니다. 
                nomal_size_parent_startLine = node_start['startLine']
            else:                                                          # 이미 node_processed가 1인 노드의 경우 플래그를 3으로 설정합니다.
                statement_flag = 3         
        else:                                                              # 단일 노드의 경우, 플래그를 4로 설정합니다
            statement_flag = 4  
        print(f"구문 타입 설정 : {statement_flag}\n")


        # * 총 토큰 수를 업데이트합니다.
        if node_processed == 1 and statement_flag == 1:                     # 토큰을 초과하지 않는 부모 노드의 경우, 부모 노드의 토큰 수를 더합니다.
            total_tokens += node_start['token']
            print(f"부모 노드 토큰 : {node_start['token']} 추가됨, 총 토큰: {total_tokens}\n")
        elif statement_flag == 2:                                           # 토큰을 초과하는 부모 노드의 경우, 자식 노드의 토큰 수를 더합니다.
            total_tokens += node_end['token']
            print(f"자식 노드 토큰 : {node_end['token']} 추가됨, 총 토큰: {total_tokens}\n")
        elif statement_flag == 3 or statement_flag == 5:                    # 이미 처리된 노드이거나, 이미 처리된 부모 노드에서 다른 부모 노드를 만났을 경우, 넘어갑니다. 
            print("이미 처리된 자식 노드로, 토큰 추가 없습니다.\n")
        else:                                                               # 단일 노드의 경우, 자기 자신 토큰 수를 더합니다.
            total_tokens += node_start['token']
            print(f"토큰 추가: 단일 노드 토큰 {node_start['token']} 추가됨, 총 토큰: {total_tokens}\n")


        # * 플래그 값에 따라서 라인 및 분석할 context_range를 할당합니다.
        start_line = node_start['startLine'] if statement_flag == 4 else node_end['startLine']
        end_line = node_start['endLine'] if statement_flag == 4 else node_end['endLine']
        context_range.append({"startLine": start_line, "endLine": end_line})
        print(f"분석할 범위를 저장 : [{start_line}, {end_line}]\n")


        # * 플래그 값에 따라서 converting할 스토어드 프로시저 코드를 추가
        if statement_flag == 2:
            await process_over_size_node(start_line, node_end['summarized_code'])
            print("부모 노드의 토큰이 초과하여 별도 처리를 진행합니다.\n")
        elif statement_flag not in [3, 5]:
            node_code = node_start['node_code'] if statement_flag in [1, 4] else node_end['node_code']
            node_type = "부모 노드 또는 단일 노드" if statement_flag in [1, 4] else "자식 노드"
            print(f"{node_type} 코드 추가: {node_code}\n")
            convert_sp_code += f"\n{node_code}"
        else:
            print("이미 처리된 자식 노드로 추가 코드 필요 없음.\n")


        # * 변수 노드를 가져옵니다
        # TODO 수정 필요 한번에 다 들고와서 정리하는게 더 빠름, 부모 노드의 경우 node_end로 기준을 해야하므로 두번 호출해야함.. 어쩔수없음 -> 최적화 필요
        if node_processed == 1:
            print(f"부모 노드에서 사용된 변수 조회 : {node_start['startLine']}라인")
            variable_dict = await fetch_variable_nodes(node_start['startLine'], variable_dict)
        start_line = node_end['startLine'] if relationship_name == "PARENT_OF" else node_start['startLine']
        print(f"단일 및 자식 노드에서 사용된 변수 조회 : {start_line}라인\n")
        variable_dict = await fetch_variable_nodes(start_line, variable_dict)


# 역할: 서비스를 생성하기 위한 데이터를 준비하는 함수입니다.
# 매개변수: 
#   sp_fileName - 스토어드 프로시저 파일 이름
# 반환값: 없음 
async def start_service_processing(sp_fileName):
    
    # * 서비스 스켈레톤
    service_skeleton_code = """
@RestController
public class OgadwService {{
    @PostMapping(path="/calculate")
    public void calculate(@RequestBody OgadwCommand command) {{
            //Here is business logic 
    }}

}}
    """

    # * Command 클래스의 변수
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
    

    # * 전역 변수 초기화(프로시저 파일, command_class 변수, 서비스 틀)
    global fileName, procedure_variables, service_skeleton
    fileName = convert_to_lower_case_no_underscores(sp_fileName)
    procedure_variables = list(procedure_variable["procedureParameters"])
    service_skeleton = service_skeleton_code

    # * Neo4j 연결 생성
    connection = Neo4jConnection() 
    
    try:
        # * 노드와 관계를 가져오는 쿼리 
        # TODO 레이블을 대문자로 변경 필요 
        query = [
            """
            MATCH (n)-[r]->(m)
            WHERE NOT (
                n:ROOT OR n:Variable OR n:DECLARE OR n:Table OR n:CREATE_PROCEDURE_BODY OR n:OPERATION OR
                m:ROOT OR m:Variable OR m:DECLARE OR m:Table OR m:CREATE_PROCEDURE_BODY OR m:OPERATION
            )
            RETURN n, r, m
            """
        ]
        
        
        # * 쿼리 실행
        results = await connection.execute_queries(query)
        

        # * 결과를 함수로 전달
        await process_service_class(results[0])


    except Exception as e:
        print(f"An error occurred from neo4j for service creation: {e}")
    finally:
        await connection.close() 


# 서비스 생성을 위한 테스트 모듈입니다.
class TestAnalysisMethod(unittest.IsolatedAsyncioTestCase):
    async def test_create_service(self):
        await start_service_processing("P_B_CAC120_CALC_SUIP_STD")


if __name__ == "__main__":
    unittest.main()