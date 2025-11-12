import json
import logging
import os
from typing import Any, Dict
from langchain_core.globals import set_llm_cache
from langchain_community.cache import SQLiteCache
from util.llm_client import get_llm
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableConfig
from util.llm_audit import invoke_with_audit
from util.exception import LLMCallError

db_path = os.path.join(os.path.dirname(__file__), 'langchain.db')
set_llm_cache(SQLiteCache(database_path=db_path))

# PostgreSQL → Oracle 변환 프롬프트
postgres_to_oracle_prompt = PromptTemplate.from_template(
"""
당신은 PostgreSQL Stored Procedure를 Oracle Stored Procedure로 변환하는 전문가입니다.
주어진 PostgreSQL 코드를 Oracle 문법에 맞게 정확하게 변환합니다.

사용자 언어 설정: {locale}

[입력 데이터]
===========================================
PostgreSQL SP 코드:
{source_code}

ANTLR 분석 결과 (JSON):
{antlr_data}


[변환 원칙]
===========================================
PostgreSQL의 의미와 로직을 그대로 유지하면서 Oracle 문법으로만 변환하세요.

[핵심 변환 규칙]
===========================================

1. 기본 구조
   - CREATE OR REPLACE PROCEDURE/FUNCTION 구문 유지
   - BEGIN...END 블록 구조 유지
   - 변수는 DECLARE 섹션에 선언 (Oracle 표준)

2. CURSOR 변환
   - PostgreSQL의 `FOR rec IN SELECT ... LOOP`는 Oracle 명시적 CURSOR로 변환
   - CURSOR 선언 + OPEN/FETCH/CLOSE 구조 사용
   - 예시: FOR rec IN (SELECT ...) LOOP → CURSOR cur IS SELECT ...; OPEN cur; LOOP FETCH...

3. 날짜/시간 함수 변환
   - `date_trunc('month', NOW())` → `TRUNC(SYSDATE, 'MM')`
   - `INTERVAL '1 month'` → `ADD_MONTHS()` 또는 `LAST_DAY()`
   - `current_date` → `SYSDATE` (필요시 TRUNC 적용)

4. 주요 함수 변환
   - `COALESCE()` → `NVL()`
   - `SUBSTRING()` → `SUBSTR()`
   - 자동 형변환 주의 (Oracle은 더 엄격함)

5. 제어 구조 (대부분 동일)
   - IF-ELSE, LOOP 등은 동일하게 유지

6. 출력 형식
   - 완전히 실행 가능한 Oracle 코드
   - 주석 보존, 들여쓰기 유지
   - 프로시저 끝에 슬래시(/) 추가


[JSON 출력 형식]
===========================================
다음 JSON 형식으로 반환하세요:
{{
   "converted_code": "변환된 Oracle SP 코드",
   "summary": "주요 변환 사항 설명"
}}
"""
)


def convert_postgres_to_oracle(source_code: str, antlr_data: str, api_key: str, locale: str = 'ko') -> dict:
    """
    PostgreSQL SP를 Oracle SP로 변환
    
    Args:
        source_code: PostgreSQL SP 소스 코드
        antlr_data: ANTLR 분석 결과 JSON
        api_key: LLM API 키
        locale: 언어 설정
    
    Returns:
        dict: {"converted_code": "...", "summary": "..."}
    """
    try:
        llm = get_llm(max_tokens=8192, api_key=api_key)
        
        chain = (
            RunnablePassthrough()
            | postgres_to_oracle_prompt
            | llm
        )

        payload = {
            "source_code": source_code,
            "antlr_data": antlr_data,
            "locale": locale
        }

        raw_result = invoke_with_audit(
            chain,
            payload,
            prompt_name="prompt/convert_dbms_prompt.py",
            input_payload=payload,
            metadata={"type": "dbms_conversion"},
            config=RunnableConfig(
                prompt_type="convert_postgres_to_oracle"
            )
        )

        return _parse_json_response(raw_result)
        
    except Exception as e:
        err_msg = f"PostgreSQL to Oracle 변환 중 LLM 호출 오류: {str(e)}"
        logging.error(err_msg)
        raise LLMCallError(err_msg)


def _parse_json_response(raw_result: Any) -> Dict[str, Any]:
    """
    LLM 응답을 JSON dict로 변환
    
    Args:
        raw_result: LLM 응답 객체
    
    Returns:
        Dict[str, Any]: 파싱된 JSON
    """
    try:
        if isinstance(raw_result, dict):
            return raw_result

        content = raw_result.content if hasattr(raw_result, "content") else raw_result

        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    text_parts.append(str(item["text"]))
                else:
                    text_parts.append(str(item))
            content = "\n".join(text_parts)

        if not isinstance(content, str):
            content = str(content)

        parsed = json.loads(content)

        if isinstance(parsed, list):
            if parsed and isinstance(parsed[0], dict):
                return parsed[0]
            raise ValueError("JSON 리스트 형식은 지원되지 않습니다.")

        if not isinstance(parsed, dict):
            raise ValueError("JSON 객체 형식만 지원됩니다.")

        return parsed

    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        raise LLMCallError(f"LLM JSON 응답 파싱 실패: {exc}") from exc
