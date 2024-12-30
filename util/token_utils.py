import json
from json import encoder
import logging
import tiktoken

from util.exception import TokenCountError
encoder = tiktoken.get_encoding("cl100k_base")


# 역할: 전달된 코드의 토큰 길이를 계산하는 유틸리티 함수입니다.
# 매개변수: 
#   - code : 토큰 수를 계산할 코드 문자열 (dict, list 등 다양한 타입 가능)
# 반환값: 
#   - len(text_json) : JSON으로 변환된 코드의 토큰 수
def calculate_code_token(code):
    
    try:
        text_json = json.dumps(code, ensure_ascii=False)
        return len(encoder.encode(text_json))

    except Exception as e:
        err_msg = f"토큰 계산 도중 문제가 발생: {str(e)}"
        logging.error(err_msg)
        raise TokenCountError(err_msg)
