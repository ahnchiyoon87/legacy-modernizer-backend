import logging
import os
from openai import OpenAI
import numpy as np
from util.exception import VectorizeError
from langchain.globals import set_llm_cache
from langchain_community.cache import SQLiteCache

# OpenAI 클라이언트 초기화
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
db_path = os.path.join(os.path.dirname(__file__), 'langchain.db')
set_llm_cache(SQLiteCache(database_path=db_path))


# 역할 : 텍스트를 OpenAI의 text-embedding-3-small 모델을 사용하여 벡터로 변환하는 함수
#
# 매개변수 : 
#   - text (str): 벡터화할 텍스트 문자열
#                 예: "정규직 직원의 급여 계산 로직"
#
# 반환값 : 
#   - numpy.ndarray: 1536차원의 벡터로 변환된 텍스트
#                    예: [0.123, -0.456, ..., 0.789]
def vectorize_text(text):
    try:
        # * OpenAI API를 사용하여 텍스트 임베딩 생성
        response = client.embeddings.create(
            model="text-embedding-3-large",
            input=text
        )
        
        # * 벡터 추출
        vector = np.array(response.data[0].embedding)
        return vector
        
    except Exception as e:
        err_msg = f"텍스트 벡터화 중 오류가 발생했습니다: {str(e)}"
        logging.error(err_msg)
        raise VectorizeError(err_msg)