import os
import json
import logging
from langchain.globals import set_llm_cache
from langchain_community.cache import SQLiteCache
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import JsonOutputParser
from langchain.prompts import PromptTemplate
from langchain.schema.runnable import RunnablePassthrough

from util.exception import LLMCallError

db_path = os.path.join(os.path.dirname(__file__), 'langchain.db')
set_llm_cache(SQLiteCache(database_path=db_path))
llm = ChatAnthropic(model="claude-3-5-sonnet-20241022", max_tokens=8000, temperature=0.0)
prompt = PromptTemplate.from_template(
"""
당신은 Java 컴파일 오류 로그를 분석하는 전문가입니다. 컴파일 오류 로그를 분석하여 오류의 원인과 오류가 발생한 위치를 정확히 파악하여 설명하는 텍스트를 생성해야 합니다.
오류가 발생한 위치를 찾도록 하는 것이 중요합니다. 또한 어떤 파일에 오류가 발생했는지도 찾도록 하는 것이 중요합니다.
어떤 파일에서 어떤 함수나 동작을 수행하려고 했는지 해당 함수나 동작이 어떤 기능인지를 설명해주세요.


[분석할 데이터]
Java 컴파일 오류 로그:
{error_log}


[필수 분석 항목]
1. 구체적인 오류 내용: 컴파일러가 보고한 오류 메시지와 그 의미를 설명
2. 오류가 발생한 컨텍스트: 
   - 어떤 클래스의 어떤 메서드에서 오류가 발생했는지
   - 실제 오류가 발생한 메서드와 이를 호출한 상위 메서드를 구분하여 설명
   - 해당 코드가 수행하려던 작업은 무엇인지 설명
   - 관련된 다른 객체들과 그들의 메서드 호출 식별:
     * 다른 서비스 객체의 메서드 호출 (예: userService.createUser())
     * 리포지토리 인터페이스의 메서드 호출 (예: userRepository.findById())
     * 엔티티 클래스 객체 사용 (예: User user = new User())
3. 문제 해결을 위해 확인이 필요한 파일 유형:
   - Repository: JPA 리포지토리 관련 문제
   - Entity: 엔티티 클래스 정의 및 매핑 문제
   - Command: 커맨드 객체 관련 문제
   - Controller: API 엔드포인트 및 요청 처리 문제
   - Service: 비즈니스 로직 처리 문제
   - Configuration: 설정 파일(application.yml, pom.xml 등) 관련 문제
4. 문제 해결을 위한 구체적인 방법: 코드 수정 예시를 포함한 실질적인 해결 방안 제시
5. 라인 번호는 처리 규칙 : 
   - 오류가 단일 라인에서 발생한 경우: "42~42" 형식으로 표시
   - 동일한 오류라도 연속되지 않은 라인은 별도로 처리 (예: "7~7", "107~107")
   - 연속된 라인에서 동일한 오류가 발생한 경우, 하나의 error_items로 처리 (예 : "17~18")
   - error_location 필드에는 항상 "시작행~종료행" 형식 사용


[패키지 이름 추출 규칙]
- 파일명에서 'Service', 'Command', 'Controller', 'Repository', 'Entity' 등의 접두어를 제거
- 파일명이 'TPJ_'로 시작하면 'TPJ_' 이후의 텍스트를 패키지명으로 사용
- 파일명이 'TPX_'로 시작하면 'TPX_' 이후의 텍스트를 패키지명으로 사용
- 예시: 'TpjUser.java' -> 'TPJ_USER'
        'TpxOrderCommand.java' -> 'TPX_ORDER'
        'TpxUpdateService.java' -> 'TPX_UPDATE'
        'TpxDeleteController.java' -> 'TPX_DELETE'


[메서드 관련 오류 분석 우선순위]
"메서드를 찾을 수 없음" 오류가 발생한 경우:
- 이는 항상 호출하는 메서드명이 실제 정의된 메서드명과 일치하지 않아서 발생하는 문제입니다
- 절대로 새로운 메서드를 추가하라고 제안하지 마세요
- 대신 호출하는 메서드명을 실제 정의된 메서드명과 일치하도록 수정하는 방법을 안내하세요
- error_method에는 실제 오류가 발생한 메서드명을 지정하세요 (상위 메서드가 아님). 
- 만약 메서드 관련 오류가 아닌 경우(예: 변수 초기화 오류, 구문 오류 등)에는 error_method를 "none"으로 지정하세요


[관련 객체 분석]
오류 컨텍스트에서 다음 객체들의 사용을 식별하고 분석하세요:
1. 서비스 객체:
   - 다른 서비스 클래스의 메서드를 호출하는 경우 (예: orderService.processOrder())
   - 해당 서비스 객체의 이름도 추출 -> OrderService
2. 리포지토리 객체:
   - JPA 리포지토리 인터페이스의 메서드 호출 (예: orderRepository.save())
   - 사용된 리포지토리의 이름도 추출 -> OrderRepository
3. 엔티티 객체:
   - 엔티티 클래스의 인스턴스 생성이나 사용 (예: Order order = new Order())
   - 관련 엔티티의 이름도 추출 -> Order
(주의! : 관련 엔티티가 없는 경우 "none" 지정)


[예시]
error_text: "신규 사용자 등록 처리 중 오류가 발생했습니다. UserService 클래스의 registerNewUser 메서드 내에서 호출된 createUser 메서드에서 파라미터 순서가 잘못 지정되었습니다. createUser 메서드는 사용자 이름(String)과 나이(Integer) 순으로 입력받도록 설계되었으나, 실제로는 나이와 이름 순으로 전달되어 타입 불일치가 발생했습니다. createUser(userName, userAge) 형태로 파라미터 순서를 수정하여 문제를 해결할 수 있습니다."
error_location: "42~43"
error_file: "UserService.java"
error_method: "createUser"
required_files: "Service"
package_name: "TPX_USER_UPDATE"
related_objects: "OrderService"


주의사항:
- 각 항목은 오류에 대한 설명(error_text), 발생 위치(error_location), 파일명(error_file), 메서드명(error_method)을 포함합니다
- 오류가 하나만 있는 경우 배열에는 하나의 객체만 포함됩니다.


[출력 형식]
부가 설명 없이 결과만을 포함하여, 다음 JSON 형식으로 반환하세요:
{{
    "error_items": [
        {{
            "error_text": "오류 내용",
            "error_location": "라인번호~라인번호",
            "error_file": "파일명",
            "error_method": "실제 오류가 발생한 메서드명",
            "required_files": "확인해야 할 파일 유형",
            "package_name": "패키지명",
            "related_objects": "관련 객체명"
        }},
        {{
            "error_text": "오류 내용",
            "error_location": "라인번호~라인번호",
            "error_file": "파일명",
            "error_method": "메서드명",
            "required_files": "확인해야 할 파일 유형",
            "package_name": "패키지명",
            "related_objects": "관련 객체명"
        }}
    ]
}}
"""
)


def generate_error_log(error_log: str) -> str:
    try:
        chain = (
            RunnablePassthrough()
            | prompt
            | llm
            | JsonOutputParser()
        )
        
        result = chain.invoke({
            "error_log": error_log
        })
        
        return result
    except Exception as e:
        err_msg = f"컴파일 오류 로그 생성 중 오류가 발생했습니다: {str(e)}"
        logging.error(err_msg)
        raise LLMCallError(err_msg)