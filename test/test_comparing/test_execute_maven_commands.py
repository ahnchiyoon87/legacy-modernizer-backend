import asyncio
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from compare.result_compare import execute_maven_commands

async def test_execute_maven_commands():

    # 테스트할 클래스 이름 리스트 정의 (실제 테스트 클래스 이름과 동일)
    test_classes = [
        "TpjSalaryDeduct100KAmountTest"
    ]

    # execute_maven_commands 함수 호출
    await execute_maven_commands(test_classes)

# asyncio.run을 사용하여 비동기 함수 실행
if __name__ == "__main__":
    asyncio.run(test_execute_maven_commands())