import json
import logging
import os
from langchain.globals import set_llm_cache
from langchain_community.cache import SQLiteCache
from langchain.prompts import PromptTemplate
from langchain.schema.runnable import RunnablePassthrough
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from util.exception  import LLMCallError
from langchain_core.output_parsers import JsonOutputParser


db_path = os.path.join(os.path.dirname(__file__), 'langchain.db')
set_llm_cache(SQLiteCache(database_path=db_path))
llm = ChatAnthropic(model="claude-3-5-sonnet-20240620", max_tokens=8000)

prompt = PromptTemplate.from_template(
"""
당신은 Oracle PL/SQL 전문가이며 데이터베이스 분석가입니다. 
주어진 Stored Procedure Code를 상세히 분석하여 코드의 구조, 데이터 흐름, 그리고 테이블 관계를 파악하는 작업을 수행합니다.


분석할 Stored Procedure Code:
{code}


분석할 Stored Procedure Code의 범위 목록:
{ranges}


[SECTION 1] 반드시 지켜야할 주의사항
===============================================
1. 범위 준수
   - 분석할 Stored Procedure Code의 범위 개수는 {count}개입니다
   - 반드시 'analysis'는 정확히 {count}개의 요소를 가져야 합니다
   - 각 범위는 독립적으로 분석되어야 합니다
   - 지정된 라인 범위 내의 Stored Procedure Code만 분석합니다.
   - 범위를 벗어난 코드는 절대 분석하지 않습니다

2. 테이블 명명 규칙
   - 테이블의 별칭은 제외합니다 (예: FROM EMPLOYEE E → EMPLOYEE)
   - 스키마 이름은 제외합니다 (예: HR.EMPLOYEE → EMPLOYEE)
   - 오직 순수한 테이블 이름만 사용합니다
   - 대소문자는 원본 그대로 유지합니다

3. 변수와 컬럼 구분
   - 테이블의 컬럼이 'variables' 목록에 포함되지 않도록 합니다.
   - 테이블의 컬럼과 변수는 명확하게 구분되어야 합니다.

4. 정보 누락 처리
   - 식별되지 않는 정보에 대해서는 빈 사전{{}} 또는 빈 리스트로 []으로 반환합니다
   - 테이블의 컬럼 타입을 식별할 수 없는 경우 문맥에 맞는 적절한 타입을 추정하여 넣습니다

   
[SECTION 2] 범위별 상세 분석 지침
===============================================
1. 코드 역할과 동작 분석
   - 코드의 역할과 동작을 2-3줄로 상세하게 설명하세요:
   - 어떤 비즈니스 로직을 수행하는지
   - 어떤 데이터를 처리하고 어떤 결과를 생성하는지
   - 주요 처리 단계나 중요한 로직은 무엇인지
   - 주석이 있다면 주석을 참고하여 작성하세요.

2. 변수 식별 및 분류
   A. 일반 변수 식별
      - 'v', 'v_' 접두사: 일반 변수
      - 'p', 'p_' 접두사: 매개변수
      - 'i', 'i_' 접두사: 입력 매개변수
      - 'o', 'o_' 접두사: 출력 매개변수
   
   B. 특수 변수 식별
      - %ROWTYPE 변수: 테이블/뷰의 전체 구조
      - %TYPE 변수: 특정 컬럼의 타입
      - 커서 변수: 결과 집합 참조
   
   C. 변수 타입 분석
      - 각 변수의 정확한 데이터 타입 식별
      - 사용자 정의 타입 포함
      - 복합 데이터 타입(레코드, 컬렉션 등) 포함


3. 프로시저/함수 호출 분석
   A. 외부 패키지 호출
      - 형식: 'PACKAGE_NAME.PROCEDURE_NAME()'
      - 다른 패키지의 프로시저/함수 호출
      - 시스템 패키지 호출
   
   B. 내부 호출
      - 형식: 'PROCEDURE_NAME()'
      - 현재 패키지 내 프로시저 호출
      - 로컬 함수 호출
   
   C. 호출 순서
      - 모든 호출을 발생 순서대로 'calls' 배열에 저장
      - 중복 호출도 포함
      - 조건부 호출도 포함

      
[SECTION 3] 전체 코드 분석 지침
===============================================   
1. SQL CRUD 작업 분석
   A. INSERT 작업
      - 'INSERT INTO' 구문 식별
      - 'MERGE INTO'의 INSERT 부분 식별
      - 대상 테이블 순서대로 기록
   
   B. UPDATE 작업
      - 'UPDATE' 구문 식별
      - 'MERGE INTO'의 UPDATE 부분 식별
      - 대상 테이블 순서대로 기록
   
   C. SELECT 작업
      - 'FROM' 절의 테이블 식별
      - 서브쿼리 내 테이블 포함
      - 인라인 뷰 내 테이블 포함

2. 테이블 구조 분석
   A. 컬럼 식별
      - CRUD 문에서 사용된 모든 컬럼 추출
      - 각 컬럼의 데이터 타입 식별
      - WHERE 절과 조인 조건의 컬럼 포함
   
   B. 테이블별 정리
      - 각 테이블별로 사용된 컬럼 그룹화
      - 컬럼의 데이터 타입 명시
      - 누락된 컬럼 없이 완전한 목록 작성

3. 테이블 관계 분석
   A. 조인 관계 파악
      - 명시적 조인 관계 (JOIN 키워드)
      - 암시적 조인 관계 (WHERE 절)
      - 서브쿼리 내 조인 관계
   
   B. 관계 표현
      - source: 조인 왼쪽(기준) 테이블
      - target: 조인 오른쪽(참조) 테이블
      - 다중 조인의 경우 모든 관계 포함

      
[SECTION 4] JSON 출력 형식
===============================================
식별된 정보만 담아서 json 형식으로 나타내고, 주석이나 부가 설명은 피해주세요:
{{
    "analysis": [
        {{
            "startLine": startLine,
            "endLine": endLine,
            "summary": "summary of the code",
            "tableNames": ["tableName1", "tableName2"],
            "calls": ["procedure1", "function1", "package1"], 
            "variables": ["type:variable1", "type:variable2"]
        }}
    ],
    "Tables": {{
        "tableName1": ["type:field1", "type:field2"], 
        "tableName2": []
    }},
    "tableReference": [{{"source": "tableName1", "target": "tableName2"}}]
}}
""")

# 역할 : 주어진 스토어드 프로시저 코드  분석하여, 사이퍼쿼리 생성에 필요한 정보 받습니다
# 매개변수: 
#   - sp_code: 분석할 스토어드 프로시저 코드 
#   - context_ranges : 분석할 스토어드 프로시저 코드의 범위 
#   - context_range_count : 분석할 스토어드 프로시저 범위의 개수(결과 개수 유지를 위함)
# 반환값 : 
#   - parsed_content : JSON으로 파싱된 llm의 분석 결과
def understand_code(sp_code, context_ranges, context_range_count):
    try:
        ranges_json = json.dumps(context_ranges)

        chain = (
            RunnablePassthrough()
            | prompt
            | llm
        )

        json_parser = JsonOutputParser()
        result = chain.invoke({"code": sp_code, "ranges": ranges_json, "count": context_range_count})
        # TODO 여기서 최대 출력 토큰만 4096이 넘은 경우 처리가 필요
        json_parsed_content = json_parser.parse(result.content)
        logging.info(f"토큰 수: {result.usage_metadata}")     
        return json_parsed_content
    
    except Exception:
        err_msg = "Understanding 과정에서 LLM 호출하는 도중 오류가 발생했습니다."
        logging.error(err_msg, exc_info=False)
        raise LLMCallError(err_msg)