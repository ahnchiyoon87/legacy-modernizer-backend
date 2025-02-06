import logging
import re
from sentence_transformers import SentenceTransformer
from util.exception import VectorizeError

model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

# # 'all-MiniLM-L6-v2' 모델은:
# # - 384 차원의 벡터 생성
# # - 다국어 지원
# # - 문장의 의미를 잘 포착
# def vectorize_text(text):
#     try:
#         # 1. 메서드/함수 이름 추출
#         file_names = re.findall(r'([A-Za-z]\w+)(?:\.java|\.py)\s+파일', text)
#         class_names = re.findall(r'([A-Za-z]\w+)(?:\s+클래스)', text)
#         method_names = re.findall(r'([A-Za-z]\w+)(?:\s+(?:메서드|함수))', text)
        
#         # 2. 메서드 이름 강조만 적용
#         emphasized_text = text
#         identifiers = file_names + class_names + method_names
#         if identifiers:
#             emphasized_part = ' '.join([f"{name}" * 5 for name in identifiers])
#             emphasized_text = f"{emphasized_part} {text}"
        
#         # 3. 벡터화
#         vector = model.encode(emphasized_text)
#         return vector
        
#     except Exception as e:
#         err_msg = f"텍스트 벡터화 중 오류가 발생했습니다: {str(e)}"
#         logging.error(err_msg)
#         raise VectorizeError(err_msg)
    


# import logging
# from sentence_transformers import SentenceTransformer
# from util.exception import VectorizeError

# model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

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