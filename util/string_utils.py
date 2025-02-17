import logging
from util.exception import AddLineNumError, StringConversionError


# 역할: 스네이크 케이스 형식의 문자열을 자바 클래스명으로 사용할 수 있는 파스칼 케이스로 변환합니다.
# 
# 매개변수: 
#   - snake_case_input: 변환할 스네이크 케이스 문자열 (예: employee_payroll, user_profile_service)
# 
# 반환값: 
#   - 파스칼 케이스로 변환된 문자열 (예: snake_case_input이 'employee_payroll'인 경우 -> 'EmployeePayroll')
def convert_to_pascal_case(snake_str: str) -> str:
    try:
        if '_' not in snake_str:
            return snake_str
        
        return ''.join(word.capitalize() for word in snake_str.split('_'))
    except Exception as e:
        err_msg = f"파스칼 케이스 변환 중 오류 발생: {str(e)}"
        logging.error(err_msg)
        raise StringConversionError("파스칼 케이스 변환 중 오류 발생")


# 역할: 스네이크 케이스 형식의 문자열을 자바 클래스명으로 사용할 수 있는 카멜 케이스로 변환합니다.
#
# 매개변수: 
#   - snake_str: 변환할 스네이크 케이스 문자열 (예: user_profile_service)
#
# 반환값: 
#   - 카멜 케이스로 변환된 문자열 (예: userProfileService)
def convert_to_camel_case(snake_str: str) -> str:
    try:
        words = snake_str.split('_')
        return words[0].lower() + ''.join(word.capitalize() for word in words[1:])
    except Exception as e:
        err_msg = f"카멜 케이스 변환 중 오류 발생: {str(e)}"
        logging.error(err_msg)
        raise StringConversionError("카멜 케이스 변환 중 오류 발생")
    

# 역할: 파스칼 케이스나 카멜 케이스 형식의 문자열을 대문자 스네이크 케이스로 변환합니다.
#
# 매개변수: 
#   - camel_str: 변환할 파스칼/카멜 케이스 문자열 (예: 'UserProfileService' 또는 'userProfileService')
#
# 반환값: 
#   - 대문자 스네이크 케이스로 변환된 문자열 (예: 'USER_PROFILE_SERVICE')
def convert_to_upper_snake_case(camel_str: str) -> str:
    try:
        if not camel_str:  # None이거나 빈 문자열인 경우
            return ""
        
        # 첫 번째 대문자 앞에는 '_'를 추가하지 않음
        result = camel_str[0].upper()
        
        # 나머지 문자들을 순회하면서 대문자를 '_대문자'로 변환
        for char in camel_str[1:]:
            if char.isupper():
                result += '_' + char
            else:
                result += char.upper()
                
        return result
    except Exception as e:
        err_msg = f"대문자 스네이크 케이스 변환 중 오류 발생: {str(e)}"
        logging.error(err_msg)
        raise StringConversionError("대문자 스네이크 케이스 변환 중 오류 발생")


# 역할: PL/SQL 코드의 각 라인에 번호를 추가하여 코드 추적과 디버깅을 용이하게 합니다.
#
# 매개변수: 
#   - plsql : 원본 PL/SQL 코드 (라인 단위 리스트)
#
# 반환값: 
#   - numbered_plsql : 각 라인 앞에 번호가 추가된 PL/SQL 코드
#   - numbered_lines : 각 라인 앞에 번호가 추가된 라인 리스트
def add_line_numbers(plsql):
    try: 
        # * 각 라인에 번호를 추가합니다.
        numbered_lines = [f"{index + 1}: {line}" for index, line in enumerate(plsql)]
        numbered_plsql = "".join(numbered_lines)
        return numbered_plsql, numbered_lines
    except Exception as e:
        err_msg = f"전달된 스토어드 프로시저 코드에 라인번호를 추가하는 도중 문제가 발생했습니다: {str(e)}"
        logging.error(err_msg)
        raise AddLineNumError(err_msg)