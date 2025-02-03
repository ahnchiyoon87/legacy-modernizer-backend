import asyncio
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from compare.result_compare import execute_maven_commands

async def test_execute_maven_commands():

    # 테스트할 클래스 이름 리스트 정의 (실제 테스트 클래스 이름과 동일)
    test_classes = [
        "TpxUpdateSalaryDeduct100kTest"
    ]

    # 테스트에 사용될 프로시저 로그 정의
    plsql_gwt_log = {
        "given": [
            {
                "operation": "c",
                "table": "TPJ_EMPLOYEE",
                "data": {
                    "DEPT_CODE": "DEV001",
                    "EMP_KEY": "EMP001",
                    "EMP_NAME": "이정규",
                    "REGULAR_YN": "Y"
                }
            },
            {
                "operation": "c",
                "table": "TPJ_SALARY",
                "data": {
                    "EMP_KEY": "EMP001",
                    "AMOUNT": 1000000,
                    "PAY_DATE": "2024-12-13",
                    "SAL_KEY": "SAL001"
                }
            }
        ],
        "when": {
            "procedure": "TPX_UPDATE_SALARY.TPX_UPDATE_SALARY",
            "parameters": {
                "pEmpKey": "EMP001",
                "pEmpName": "이정규",
                "pDeptCode": "DEV001",
                "pBaseAmount": 1000000,
                "pPayDate": "2024-12-13",
                "pRegularYn": "Y"
            }
        },
        "then": [
            {
                "operation": "u",
                "table": "TPJ_SALARY",
                "data": {
                    "SAL_KEY": "SAL001",
                    "EMP_KEY": "EMP001",
                    "PAY_DATE": "2024-12-13 09:00:00",
                    "AMOUNT": 900000
                }
            }
        ]
    }

    # 세션 아이디 정의
    session_uuid = "525f343f-006e-455d-9e52-9825170c2088"

    # execute_maven_commands 함수 호출
    async for result in execute_maven_commands(test_classes, plsql_gwt_log, session_uuid):
        print(result)

# asyncio.run을 사용하여 비동기 함수 실행
if __name__ == "__main__":
    asyncio.run(test_execute_maven_commands())