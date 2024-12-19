import json
import logging
import os
from langchain.globals import set_llm_cache
from langchain_community.cache import SQLiteCache
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import JsonOutputParser
from langchain.prompts import PromptTemplate
from langchain.schema.runnable import RunnablePassthrough
from util.exception import LLMCallError
import openai

db_path = os.path.join(os.path.dirname(__file__), 'langchain.db')
set_llm_cache(SQLiteCache(database_path=db_path))

api_key = os.getenv("OPENAI_API_KEY")
if api_key is None:
    raise ValueError("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")

# llm = ChatOpenAI(api_key=api_key, model_name="gpt-4o")
llm = ChatAnthropic(model="claude-3-5-sonnet-20241022", max_tokens=8000, temperature=0.1)


prompt = PromptTemplate.from_template(
"""
당신은 PL/SQL 프로시저와 함수의 동작을 분석하고 요약하는 전문가입니다.
주어진 코드 분석 요약들을 바탕으로 전체 프로시저/함수의 핵심 기능을 간단명료하게 설명해주세요.

분석된 요약 내용:
{summaries}

[분석 규칙]
===============================================
1. 핵심 기능 파악
   - 프로시저/함수가 수행하는 주요 작업
   - 입력과 출력의 흐름
   - 중요한 비즈니스 로직

2. 요약 방식
   - 3~4줄로 간단하게 정리
   - 기술적인 용어는 최소화
   - 비즈니스 관점에서 이해하기 쉽게 설명

[JSON 출력 형식]
===============================================
주석이나 부가설명 없이 다음 JSON 형식으로만 결과를 반환하세요:
{{
    "summary": "프로시저/함수의 흐름을 요약한 문장"
}}
"""
)

def understand_summary(summaries):
    try:
        chain = (
            RunnablePassthrough()
            | prompt
            | llm
            | JsonOutputParser()
        )
        result = chain.invoke({"summaries": summaries})
        return result
    except Exception:
        err_msg = "Understanding 과정에서 요약 관련 LLM 호출하는 도중 오류가 발생했습니다."
        logging.error(err_msg, exc_info=False)
        raise LLMCallError(err_msg)