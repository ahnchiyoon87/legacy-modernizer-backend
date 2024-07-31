from langchain_anthropic import ChatAnthropic
from langchain.prompts import PromptTemplate
from langchain_community.cache import SQLiteCache
from langchain.globals import set_llm_cache
from langchain.schema.runnable import RunnablePassthrough
from langchain_core.output_parsers import JsonOutputParser
import os
import json

# Anthropic API 키 설정
os.environ["ANTHROPIC_API_KEY"] = os.getenv("ANTHROPIC_API_KEY")

# SQLite 캐시 설정
db_path = os.path.join(os.path.dirname(__file__), 'langchain.db')
set_llm_cache(SQLiteCache(database_path=db_path))

# ChatAnthropic 모델 초기화
llm = ChatAnthropic(model="claude-3-5-sonnet-20240620")

prompt = PromptTemplate.from_template(
"""
당신은 클린 아키텍처 원칙을 따르는 스프링부트 기반의 자바 애플리케이션을 개발하는 소프트웨어 엔지니어입니다. 주어진 JSON 형식의 테이블 데이터를 기반으로 자바 Entity 클래스를 생성하는 작업을 맡았습니다.

테이블 데이터(JSON)입니다:
{table_json_data}

테이블 데이터(JSON)을 Entity 클래스로 전환할 때, 아래를 참고하여 작업하세요:
1. 각 테이블(JSON) 객체는 하나의 Entity 클래스로 변환되어야 합니다.
2. 각 테이블(JSON) 객체의 'name'은 파스칼 표기법을 적용한 클래스 이름으로 사용됩니다. (예: B_Plcy_Month -> BPlcyMonth)
3. 클래스의 이름과 'entityName'은 복수형이 아닌 단수형으로 표현하세요. (예: Employees -> Employee)
4. 'fields' 배열의 각 항목은 카멜 표기법을 적용한 클래스의 속성으로 사용됩니다. (예: B_Plcy_Month -> bPlcyMonth)
5. 각 속성은 적절한 자바 데이터 타입과 함께 private 접근 제한자를 가집니다. (데이터 타입의 경우, 되도록이면 int 대신 long을 사용하세요.)

아래는 자바 Entity 클래스의 기본 구조입니다:
package com.example.{project_name}.entity;

import jakarta.persistence.*;
import lombok.Data;
import java.time.LocalDate

@Entity
@Table(name = "TableName")
@Data
public class EntityName {{
    @Id
    @GeneratedValue(strategy = GenerationType.AUTO)
    private Long id;
    private DataType fieldName1;
    private DataType fieldName2;
    ...
}}

아래는 결과 예시로, 부가 설명 없이 결과만을 포함하여, 다음 JSON 형식으로 반환하세요:
{{
    "analysis": [
        {{
            "entityName": "EntityName",
            "code": "Java Code"
        }}
    ]
}}
"""
)

def convert_entity_code(table_data, spFile_name):
    table_json_data = json.dumps(table_data)

    chain = (
        RunnablePassthrough()
        | prompt
        | llm
        | JsonOutputParser()
    )
    result = chain.invoke({"table_json_data": table_json_data, "project_name": spFile_name})
    return result

# 테스트용 JSON 데이터
test_json_data = [
  {
    "name": "B_Plcy_Month",
    "fields": [
      {"name": "B_Plcy_Month", "type": "VARCHAR(6)"},
      {"name": "B_Plcy_Strt_Dt", "type": "DATE"},
      {"name": "B_Plcy_End_Dt", "type": "DATE"}
    ]
  }
]

# 함수 실행 및 결과 출력
result = convert_entity_code(test_json_data, "example")
print(json.dumps(result, indent=2))