import unittest
import sys
import os
import logging

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from service.service import initialize_docker_environment

# 로그 레벨을 INFO로 설정
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

class TestDockerComposeYml(unittest.IsolatedAsyncioTestCase):
    
    async def test_initialize_docker_environment(self):
        try:
            # 테스트용 데이터
            user_id = "3c667f5b-6bde-4c1f-b3e9-bfb0a5396d52"
            orm_type = "jpa"
            package_names = ["TPX_EMPLOYEE", "TPX_SALARY", "TPX_ATTENDANCE", "TPX_MAIN"]
            
            # 함수 실행
            await initialize_docker_environment(user_id, orm_type, package_names)
            
            # 오류가 발생하지 않았다면 테스트 성공
            self.assertTrue(True)
                
        except Exception as e:
            self.fail(f"도커 환경 초기화 중 예외 발생: {str(e)}")

if __name__ == '__main__':
    unittest.main()