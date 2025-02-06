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


각 오류는 다음 정보를 포함해야 합니다:
1. 구체적인 오류 내용: 컴파일러가 보고한 오류 메시지와 그 의미를 설명
2. 오류가 발생한 컨텍스트: 
   - 어떤 클래스의 어떤 메서드에서 오류가 발생했는지
   - 오류가 발생한 메서드명
   - 해당 코드가 수행하려던 작업은 무엇인지 설명
3. 문제 해결을 위한 구체적인 방법: 코드 수정 예시를 포함한 실질적인 해결 방안 제시


[메서드 관련 오류 분석 우선순위]
"메서드를 찾을 수 없음" 오류가 발생한 경우:
- 이는 항상 호출하는 메서드명이 실제 정의된 메서드명과 일치하지 않아서 발생하는 문제입니다
- 절대로 새로운 메서드를 추가하라고 제안하지 마세요
- 대신 호출하는 메서드명을 실제 정의된 메서드명과 일치하도록 수정하는 방법을 안내하세요


"메서드 호출 시 파라미터 관련 오류":
   a) 파라미터 순서 오류
   b) 파라미터 타입 불일치
   c) 파라미터 개수 불일치

   
[예시]
error_text: "신규 사용자 등록 처리 중 오류가 발생했습니다. UserService 클래스의 registerNewUser 메서드에서 사용자 기본 정보(이름, 나이)를 데이터베이스에 저장하는 createUser 메서드를 호출하는 과정에서, 파라미터 순서가 잘못 지정되었습니다. createUser 메서드는 사용자 이름(String)과 나이(Integer) 순으로 입력받도록 설계되었으나, 실제로는 나이와 이름 순으로 전달되어 타입 불일치가 발생했습니다. createUser(userName, userAge) 형태로 파라미터 순서를 수정하여 문제를 해결할 수 있습니다."
error_location: 42
error_file: "UserService.java"
error_method: "registerNewUser"


주의사항:
- error_items 배열에는 발견된 오류 개수만큼의 객체가 포함됩니다
- 각 항목은 오류에 대한 설명(error_text), 발생 위치(error_location), 파일명(error_file), 메서드명(error_method)을 포함합니다
- 오류가 하나만 있는 경우 배열에는 하나의 객체만 포함됩니다


[출력 형식]
부가 설명 없이 결과만을 포함하여, 다음 JSON 형식으로 반환하세요:
{{
    "error_items": [
        {{
            "error_text": "오류 내용",
            "error_location": 라인 번호,
            "error_file": "파일명",
            "error_method": "메서드명"
        }},
        {{
            "error_text": "오류 내용",
            "error_location": 라인 번호,
            "error_file": "파일명",
            "error_method": "메서드명"
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