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
당신은 Java와 PLSQL 테스트 결과 분석 전문가입니다. 두 시스템의 테스트 결과 차이를 분석하여 문제의 맥락을 정확히 설명하는 텍스트를 생성해야 합니다.

[분석할 데이터]
1. Java 테스트 결과:
{java_result}

2. PLSQL 테스트 결과:
{plsql_result}

3. 비교 결과:
{compare_result}

[생성할 텍스트 요구사항]
1. 다음 정보를 반드시 포함하여 하나의 문장으로 작성하세요:
   - 실행된 프로시저명
   - 관련된 업무 규칙 (근태 상태, 직원 유형 등)
   - 기준값과 결과값의 관계 파악
   - 연관된 테이블들의 관계성

2. 문맥 파악에 중점을 두어 작성하세요:
   - 단순한 테이블명/필드명 나열이 아닌 비즈니스 로직 설명
   - 차이가 발생한 이유를 추론할 수 있는 맥락 포함
   - 구체적인 수치 정보 포함

3. 텍스트는 다음과 유사한 형식으로 작성하세요:
"[프로시저명]에서 [조건/상태]인 [대상]의 [동작] 로직 차이 발생. [기준값] 기준으로 Java는 [결과1], PLSQL은 [결과2]로 [처리됨/계산됨/집계됨]."
* 예) TPX_UPDATE_SALARY 프로시저에서 결근(AB) 상태인 정규직(REGULAR_YN='Y') 직원의 급여(AMOUNT) 차감액 계산 로직 차이 발생. 기본급 1000000원 기준으로 Java는 500000원, PLSQL은 900000원으로 계산됨.

[주의사항]
- 불필요한 기술적 용어는 제외하고 비즈니스 맥락에 집중
- 모든 관련 정보를 하나의 자연스러운 문장으로 통합
- 벡터 검색에 효과적인 키워드들이 자연스럽게 포함되도록 작성


[출력 형식]
부가 설명 없이 결과만을 포함하여, 다음 JSON 형식으로 반환하세요:
{{
    "compare_text": "content"
}}
"""
)


def generate_compare_text(java_result: dict, plsql_result: dict, compare_result: dict) -> str:
    try:
        chain = (
            RunnablePassthrough()
            | prompt
            | llm
            | JsonOutputParser()
        )
        
        result = chain.invoke({
            "java_result": json.dumps(java_result, indent=2, ensure_ascii=False),
            "plsql_result": json.dumps(plsql_result, indent=2, ensure_ascii=False),
            "compare_result": json.dumps(compare_result, indent=2, ensure_ascii=False)
        })
        
        return result
    except Exception as e:
        err_msg = f"비교 텍스트 생성 중 오류가 발생했습니다: {str(e)}"
        logging.error(err_msg)
        raise LLMCallError(err_msg)