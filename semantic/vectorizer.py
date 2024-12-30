import logging
from sentence_transformers import SentenceTransformer
from util.exception import VectorizeError

model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

# 'all-MiniLM-L6-v2' 모델은:
# - 384 차원의 벡터 생성
# - 다국어 지원
# - 문장의 의미를 잘 포착
def vectorize_text(text):
    try:
        vector = model.encode(text)  # text -> 384차원 벡터로 변환
        return vector  # shape: (384,)
    except Exception as e:
        err_msg = f"텍스트 벡터화 중 오류가 발생했습니다: {str(e)}"
        logging.error(err_msg)
        raise VectorizeError(err_msg)