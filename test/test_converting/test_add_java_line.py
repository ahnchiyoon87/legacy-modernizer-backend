import json
import unittest
import sys
import os
import logging

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from convert.add_service_line_range import find_service_line_ranges


# * 로그 레벨 설정
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logging.getLogger('asyncio').setLevel(logging.ERROR)

for logger in ['asyncio', 'anthropic', 'langchain', 'urllib3', 'anthropic._base_client', 
               'anthropic._client', 'langchain_core', 'langchain_anthropic', 'uvicorn', 'fastapi']:
    logging.getLogger(logger).setLevel(logging.CRITICAL)


# * Java 코드의 라인 범위를 찾는 테스트
class TestJavaLineRangeExtraction(unittest.IsolatedAsyncioTestCase):
    async def test_find_java_line_ranges(self):
        try:

            # * test_results.json 파일에서 service_class_name 읽기
            with open('test/test_converting/test_results.json', 'r', encoding='utf-8') as f:
                service_classes = json.load(f).get('service_class_name', {})


            # * 각 서비스 클래스에 대해 Java 라인 범위 찾기 테스트
            for object_name, service_class_name in service_classes.items():
                queries = await find_service_line_ranges(object_name, service_class_name)
                self.assertTrue(len(queries) > 0, f"Java 라인 범위를 찾지 못했습니다: {object_name}")
                
        except Exception as e:
            self.fail(f"테스트 실패: {str(e)}")


if __name__ == '__main__':
    unittest.main()