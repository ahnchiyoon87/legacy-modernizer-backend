import os
import logging
import aiofiles
import tiktoken
from prompt.service_skeleton_prompt import convert_controller_method_code, convert_function_code, convert_method_skeleton_code
from prompt.command_prompt import convert_command_code
from understand.neo4j_connection import Neo4jConnection
from util.exception import ConvertingError, ExtractCodeError, HandleResultError, LLMCallError, Neo4jError, ProcessResultError, SaveFileError, SkeletonCreationError, TraverseCodeError

encoder = tiktoken.get_encoding("cl100k_base")
JAVA_PATH = 'java/demo/src/main/java/com/example/demo'


# 역할: 스네이크 케이스 형식의 문자열을 자바 클래스명으로 사용할 수 있는 파스칼 케이스로 변환합니다.
#      예시) user_profile_service -> UserProfileService
# 매개변수: 
#   - snake_case_input: 변환할 스네이크 케이스 문자열
#                      (예: employee_payroll, user_profile_service)
# 반환값: 
#   - 파스칼 케이스로 변환된 문자열
#     (예: snake_case_input이 'employee_payroll'인 경우 -> 'EmployeePayroll')
def convert_to_pascal_case(snake_str: str) -> str:
    return ''.join(word.capitalize() for word in snake_str.split('_'))


# 역할: 스프링부트 서비스 클래스의 기본 골격을 생성합니다.
#      서비스 클래스에는 필요한 리포지토리 의존성과 기본 어노테이션이 포함됩니다.
# 매개변수: 
#   - object_name: 서비스 클래스명의 기반이 될 패키지 이름 (스네이크 케이스)
#                       (예: employee_management)
#   - required_entities: 서비스에서 사용할 엔티티 클래스명 목록
#                       (예: ['Employee', 'Department'])
# 반환값: 
#   - template: 생성된 서비스 클래스 코드 문자열
#   - service_class_name: 생성된 서비스 클래스명 (예: EmployeeManagementService)
async def create_service_skeleton(object_name: str, entity_name_list: list) -> str:
    try:
        # * 1. 파스칼 케이스로 변환하여 서비스 클래스명 생성 
        service_class_name = convert_to_pascal_case(object_name) + "Service"
        
        # * 2. 서비스 클래스 템플릿 생성
        service_class_template = f"""package com.example.testjava.service;

{chr(10).join(f'import com.example.testjava.entity.{entity};' for entity in entity_name_list)}
{chr(10).join(f'import com.example.testjava.repository.{entity}Repository;' for entity in entity_name_list)}
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.beans.factory.annotation.Autowired;
import java.time.LocalDate;
import java.util.List;
import org.springframework.http.ResponseEntity;
import org.springframework.transaction.annotation.Transactional;

@RestController
@Transactional
public class {service_class_name} {{

{chr(10).join(f'    @Autowired\n    private {entity}Repository {entity[0].lower()}{entity[1:]}Repository;' for entity in entity_name_list)}
CodePlaceHolder1
}}"""

        return service_class_template, service_class_name

    except Exception:
        err_msg = "서비스 클래스 골격을 생성하는 도중 문제가 발생했습니다."
        logging.error(err_msg, exc_info=False)
        raise ExtractCodeError(err_msg)


# 역할: 프로시저/함수에 대한 커맨드 클래스와 서비스 메서드의 구현 코드를 생성합니다.
# 매개변수: 
#   - method_info: 메서드 생성에 필요한 상세 정보
#                 (프로시저명, 지역변수, 반환코드 등을 포함하는 딕셔너리)
#   - parameter_info: 입력 매개변수 관련 정보
#                    (파라미터 타입, 이름 등을 포함하는 딕셔너리)
#   - node_type: 대상 노드의 유형
#                (FUNCTION/PROCEDURE/CREATE_PROCEDURE_BODY)
# 반환값: 
#   - command_fields: 커맨드 클래스에 정의된 필드 정보 (함수인 경우 None)
#   - method_name: 생성된 서비스 메서드명
#   - method_code: 생성된 메서드 구현 코드
async def create_method_and_command(method_skeleton_data, parameter_data, node_type):

    try:
        command_class_variable = None
        if node_type != 'FUNCTION':
            # * 커맨드 클래스 생성에 필요한 정보를 받습니다.
            analysis_command = convert_command_code(parameter_data)  
            command_class_name = analysis_command['commandName']
            command_class_code = analysis_command['command']
            command_class_variable = analysis_command['command_class_variable']              

            # * 컨트롤러 메서드 틀 생성에 필요한 정보를 받습니다.
            analysis_method_skeleton = convert_controller_method_code(method_skeleton_data, command_class_name)  
            method_skeleton_name = analysis_method_skeleton['methodName']
            method_skeleton_code = analysis_method_skeleton['method']
            
            # * command 클래스 파일로 생성합니다.
            await save_java_file(command_class_name, command_class_code)
        else:
            # * 일반 메서드 틀 생성에 필요한 정보를 받습니다.
            analysis_function = convert_function_code(method_skeleton_data, parameter_data)  
            method_skeleton_name = analysis_function['methodName']
            method_skeleton_code = analysis_function['method']

        return command_class_variable, method_skeleton_name, method_skeleton_code

    except (LLMCallError, HandleResultError):
        raise
    except Exception:
        err_msg = "메서드 틀을 생성하는 과정에서 결과 처리 준비 처리를 하는 도중 문제가 발생했습니다."
        logging.error(err_msg, exc_info=False)
        raise ProcessResultError(err_msg)


# 역할: 생성된 자바 소스 코드를 지정된 디렉토리에 파일로 저장합니다.
#      환경(Docker/로컬)에 따라 적절한 저장 경로를 선택합니다.
# 매개변수: 
#   - class_name: 저장할 자바 클래스명 (확장자 제외)
#   - source_code: 저장할 자바 소스 코드 내용
#   - target_directory: 저장할 하위 디렉토리 이름 
# 반환값: 없음
async def save_java_file(class_name: str, source_code: str) -> None:

    try:
        # * 1. 환경변수에 따른 기본 디렉토리 경로 설정
        base_directory = os.getenv('DOCKER_COMPOSE_CONTEXT')
        if base_directory:
            # * Docker 환경인 경우의 경로
            java_directory = os.path.join(base_directory, JAVA_PATH, 'command')
        else:
            # * 로컬 환경인 경우의 경로
            parent_workspace_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            java_directory = os.path.join(parent_workspace_dir, JAVA_PATH, 'command')
        
        # * 2. 저장 디렉토리가 없으면 생성
        os.makedirs(java_directory, exist_ok=True)
        
        # * 3. Java 파일 생성 및 코드 작성
        file_path = os.path.join(java_directory, f"{class_name}.java")
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as file:
            await file.write(source_code)
            
    except Exception:
        err_msg = "서비스 골격 및 커맨드 클래스 파일을 저장하는 도중 오류가 발생했습니다."
        logging.error(err_msg, exc_info=False)
        raise SaveFileError(err_msg)



# 역할: Neo4j 데이터베이스에서 프로시저 정보를 조회하여 서비스 클래스와 관련 코드를 생성합니다.
#      프로시저별로 필요한 커맨드 클래스와 서비스 메서드를 생성하고 조합합니다.
# 매개변수: 
#   - required_entities: 서비스에서 사용할 엔티티 클래스명 목록
#                       (예: ['Employee', 'Department'])
#   - service_base_name: 서비스 클래스명의 기반이 될 객체 이름
#                       (예: employee_management)
# 반환값: 
#   - service_components: 생성된 서비스 구성요소 목록 (커맨드 클래스, 메서드 등)
#   - service_template: 서비스 클래스의 기본 템플릿 코드
#   - service_class_name: 생성된 서비스 클래스명
async def start_service_skeleton_processing(entity_name_list, object_name):
    
    connection = Neo4jConnection()  
    logging.info(f"[{object_name}] 서비스 틀 생성을 시작합니다.")
    procedure_groups = {}
    service_creation_info = []

    try:

        # TODO 프로시저 스펙에 있는 전역변수는 서비스 클래스의 필드로 되어야함
        query = [
            f"""
            MATCH (v:Variable)-[:SCOPE]-(p)
            WHERE (p:PROCEDURE OR p:CREATE_PROCEDURE_BODY OR p:FUNCTION)
            AND v.object_name = '{object_name}'
            AND p.object_name = '{object_name}'
            OPTIONAL MATCH (p)-[:PARENT_OF]->(d:DECLARE)
            WHERE d.object_name = '{object_name}'
            OPTIONAL MATCH (p)-[:PARENT_OF]->(r:RETURN)
            WHERE r.object_name = '{object_name}'
            WITH v, p, d, r, CASE 
                WHEN p:FUNCTION THEN 'FUNCTION'
                WHEN p:PROCEDURE THEN 'PROCEDURE'
                WHEN p:CREATE_PROCEDURE_BODY THEN 'CREATE_PROCEDURE_BODY'
            END as node_type
            RETURN v, p, d, r, node_type
            """
        ]

        nodes = await connection.execute_queries(query)  
        
        # * 프로시저별로 데이터 구조화
        for item in nodes[0]:
            proc_name = item['p'].get('procedure_name', '')
            
            # * 새로운 프로시저인 경우 딕셔너리 초기화
            if proc_name not in procedure_groups:
                procedure_groups[proc_name] = {
                    'parameters': [], 
                    'declaration': item['p'].get('declaration', ''),  
                    'local_variables': item['d'].get('node_code', '') if item['d'] else '', 
                    'return_code': item['r'].get('node_code', '') if item['r'] else '', 
                    'node_type': item['node_type']
                }
            
            # * 프로시저 입력 매개변수 정보 추가
            variable = {
                'type': item['v']['type'],
                'name': item['v']['name']
            }
            procedure_groups[proc_name]['parameters'].append(variable)


        # * 서비스 클래스의 틀을 생성합니다.
        service_skeleton, service_name = await create_service_skeleton(object_name, entity_name_list)
    

        # * 커맨드 클래스 및 메서드 틀 생성을 위한 데이터를 구성합니다.
        for proc_name, proc_data in procedure_groups.items():
            
            # * 메서드 틀 생성을 위한 데이터 구성
            method_skeleton_data = {
                'procedure_name': proc_name,
                'local_variables': proc_data['local_variables'],
                'return_code': proc_data['return_code'],
                'node_type': proc_data['node_type']
            }

            # * 커맨드 클래스 생성을 위한 데이터 구성
            parameter_data = {
                'parameters': proc_data['parameters'],
                'procedure_name': proc_name
            }

            # * 각 프로시저별 커맨드 클래스, 메서드 틀 생성을 진행합니다.
            command_class_variable, method_skeleton_name, method_skeleton_code = await create_method_and_command(
                method_skeleton_data, 
                parameter_data, 
                proc_data['node_type']
            )

            # * 결과를 딕셔너리로 구성하여 리스트에 추가
            service_creation_info.append({
                'service_skeleton': service_skeleton,
                'service_class_name': service_name,
                'command_class_variable': command_class_variable,
                'method_skeleton_name': method_skeleton_name,
                'method_skeleton_code': method_skeleton_code,
                'procedure_name': proc_name
            })

        logging.info(f"[{object_name}] {len(service_creation_info)}개의 커맨드 클래스 및 메서드 골격을 생성했습니다.\n")
        return service_creation_info, service_skeleton, service_name

    except (ConvertingError, Neo4jError, SaveFileError):
        raise
    except Exception:
        err_msg = "서비스 골격 클래스를 생성하기 위해 데이터를 준비하는 도중 문제가 발생했습니다."
        logging.error(err_msg, exc_info=False)
        raise SkeletonCreationError(err_msg)
    finally:
        await connection.close()
