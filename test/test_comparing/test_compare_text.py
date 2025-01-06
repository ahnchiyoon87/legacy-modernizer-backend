import json
import os
import sys
from unittest import IsolatedAsyncioTestCase
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from prompt.generate_compare_text_prompt import generate_compare_text

class TestCompareText(IsolatedAsyncioTestCase):

    async def test_compare_text(self):

        base_path = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
        
        try:
            with open(os.path.join(base_path, 'result_java_given_when_then_case1.json'), encoding='utf-8') as f1, \
                 open(os.path.join(base_path, 'result_plsql_given_when_then_case1.json'), encoding='utf-8') as f2, \
                 open(os.path.join(base_path, 'compare_result_case1.json'), encoding='utf-8') as f3:
                
                result = generate_compare_text(
                    java_result=json.load(f1),
                    plsql_result=json.load(f2),
                    compare_result=json.load(f3)
                )
                
                print("\n=== 테스트 비교 분석 결과 ===")
                print(result)
                print("==========================\n")

        except Exception as e:
            self.fail(f"테스트 실패: {str(e)}")

if __name__ == '__main__':
    unittest.main()