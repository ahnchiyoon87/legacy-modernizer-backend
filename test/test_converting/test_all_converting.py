import unittest
import sys
import os
import logging
import asyncio

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from service.service import generate_spring_boot_project

# 로그 레벨을 INFO로 설정
logging.basicConfig(level=logging.INFO)
logging.getLogger('asyncio').setLevel(logging.ERROR)


class TestGenerateSpringBootProject(unittest.IsolatedAsyncioTestCase):
    async def test_generate_spring_boot_project(self):
        
        # * 테스트할 파일 이름 설정
        test_filename = "P_B_CAC120_CALC_SUIP_STD"

        try:
            # * generate_spring_boot_project 메서드 호출 및 결과 확인
            async for step_result in generate_spring_boot_project(test_filename):
                
                # * 각 단계의 결과를 로깅
                logging.info(f"Step result: {step_result}")
                if step_result == "convert-error":
                    raise Exception("변환 중 오류 발생")
        except Exception as e:
            self.fail(f"Spring Boot 프로젝트 생성 중 예외 발생: {str(e)}")

if __name__ == '__main__':
    unittest.main()