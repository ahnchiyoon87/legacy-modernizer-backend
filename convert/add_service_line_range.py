from understand.neo4j_connection import Neo4jConnection
from util.exception import ExtractJavaLineError, Neo4jError
from util.file_utils import read_target_file
import logging


# 역할 : 서비스 파일에서 Java 코드 블록의 시작과 끝 라인을 찾는 함수
#
# 매개변수 :
#   - object_name: 오브젝트 이름
#   - procedure_name: 프로시저 이름
#   - service_class_name: 서비스 클래스 이름
#
# 반환값 :
#   - tuple[int, int]: (시작 라인, 끝 라인)
async def find_service_line_ranges(object_name: str, service_class_name: str) -> list[str]:
    try:
        # * 파일 내용 읽기
        file_content = read_target_file(service_class_name, "service")
        file_lines = file_content.splitlines()
        
        # * Neo4j에서 Java 코드 조회
        java_nodes = await get_java_node(object_name)
        
        # * Cypher 쿼리를 저장할 리스트
        update_queries = []
        
        # * 각 Java 코드 블록에 대해 위치 찾기
        for node in java_nodes:
            node_data = node['n'] 
            java_code = node_data['java_code']
            start_line = node_data['startLine']
            end_line = node_data['endLine']
            
            if not java_code:
                continue
                
            # * 코드 라인 정규화
            java_lines = [line.strip() for line in java_code.splitlines() if line.strip()]
            java_first_line = java_lines[0]
            
            # * 파일에서 코드 블록 찾기
            for i, line in enumerate(file_lines, 1):
                if line.strip() != java_first_line:
                    continue
                    
                # * 전체 블록 매칭 확인
                is_match = True
                current_line = i
                
                for java_line in java_lines[1:]:

                    # * 빈 줄 건너뛰기
                    while current_line < len(file_lines) and not file_lines[current_line].strip():
                        current_line += 1
                        
                    # * 라인 매칭 실패 시 중단
                    if current_line >= len(file_lines) or file_lines[current_line].strip() != java_line:
                        is_match = False
                        break
                        
                    current_line += 1
                
                if is_match:
                    query = f"""
                        MATCH (n)
                        WHERE n.object_name = '{object_name}'
                        AND n.startLine = {start_line}
                        AND n.endLine = {end_line}
                        SET n.java_range = '{i}~{current_line - 1}'
                    """
                    update_queries.append(query)
                    break
        
        if not update_queries:
            logging.info(f"일치하는 Java 코드를 찾을 수 없습니다: {service_class_name}")
            
        return update_queries       
    
    except Exception as e:
        error_msg = f"일치하는 Java 코드를 찾을 수 없습니다: {service_class_name}, 에러: {e}"
        logging.error(error_msg)
        raise ExtractJavaLineError(error_msg)
    


# 역할 : Neo4j에서 Java 코드 조회
#
# 매개변수 :
#   - object_name: 오브젝트 이름
#
# 반환값 :
#   - dict: Java 코드와 라인 정보가 포함된 노드
async def get_java_node(object_name: str) -> list[dict]:
    try:
        connection = Neo4jConnection()
        query = [f"""
            MATCH (n)
            WHERE n.object_name = '{object_name}'
            AND n.java_code IS NOT NULL
            AND NOT n:EXCEPTION
            RETURN n
            ORDER BY n.startLine
        """]
        nodes = await connection.execute_queries(query)
        return nodes[0]
    
    except Exception as e:
        error_msg = f"Neo4j에서 Java 코드를 조회하는 도중 오류가 발생했습니다: {str(e)}"
        logging.error(error_msg)
        raise Neo4jError(error_msg)
    finally:
        await connection.close()
