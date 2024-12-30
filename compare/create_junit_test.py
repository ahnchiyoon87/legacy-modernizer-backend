import logging
import os
from prompt.generate_junit_test_prompt import generate_test_code
from util.exception import GenerateJunitError

TEST_PATH = 'target/java/demo/src/test/java/com/example/demo'

# 역할 : JUnit 테스트 코드를 생성하는 함수
#
# 매개변수 : 
#   - given_when_then_log : 주어진 로그 데이터
#   - table_names : 테이블 이름 리스트
#   - package_name : 패키지 이름
#   - procedure_name : 프로시저 이름
#
# 반환값 : 
#   - str : 생성된 테스트 코드 파일 이름
async def create_junit_test(given_when_then_log: dict, table_names: list, package_name: str, procedure_name: str):
    try:
        test_result = generate_test_code(
            table_names,
            package_name,
            procedure_name,
            procedure_info=given_when_then_log.get("when"),
            given_log=given_when_then_log.get("given"),
            then_log=given_when_then_log.get("then")
        )
        

        # * 생성된 테스트 코드를 파일로 저장
        parent_workspace_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        test_file_path = os.path.join(parent_workspace_dir, TEST_PATH, f"{test_result['className']}.java")
        
        os.makedirs(os.path.dirname(test_file_path), exist_ok=True)
        with open(test_file_path, "w", encoding="utf-8") as f:
            f.write(test_result['testCode'])
        
        return test_result['className']
    
    except Exception as e:
        err_msg = f"Junit 테스트 코드 작성 중 오류가 발생했습니다: {str(e)}"
        logging.error(err_msg)
        raise GenerateJunitError(err_msg)
    