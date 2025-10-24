"""
util_core.py - 레거시 모더나이저 유틸리티 모듈

이 모듈은 Legacy-modernizer 프로젝트의 핵심 유틸리티 함수들을 제공합니다.
파일 처리, 문자열 변환, 토큰 계산, 코드 변환 등의 기능을 포함합니다.
"""

import os
import logging
import json
import aiofiles
import tiktoken
from collections import defaultdict
from typing import Optional, Dict, List, Tuple, Any, Union

from util.exception import UtilProcessingError

# tiktoken 인코더 초기화
ENCODER = tiktoken.get_encoding("cl100k_base")

#==============================================================================
# 파일 처리 유틸리티
#==============================================================================

async def save_file(content: str, filename: str, base_path: Optional[str] = None) -> str:
    """파일을 비동기적으로 저장 (최적화: 경로 결합 최소화)"""
    try:
        os.makedirs(base_path, exist_ok=True)
        file_path = os.path.join(base_path, filename)
        
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as file:
            await file.write(content)
        
        logging.info(f"파일 저장 성공: {file_path}")
        return file_path
        
    except Exception as e:
        err_msg = f"파일 저장 중 오류 발생: {str(e)}"
        logging.error(err_msg)
        raise UtilProcessingError(err_msg)


#==============================================================================
# 경로 유틸리티
#==============================================================================

# 모듈 레벨 캐싱 (반복 계산 방지)
_WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def build_rule_based_path(project_name: str, user_id: str, target_lang: str, role_name: str, **kwargs) -> str:
    """
    Rule 파일 기반 저장 경로 생성 (다중 언어 지원)
    
    Args:
        project_name: 프로젝트 이름
        user_id: 사용자 식별자
        target_lang: 타겟 언어 (java, python 등)
        role_name: Rule 파일명 (entity, service 등)
        **kwargs: 추가 변수 (dir_name 등)
    
    Returns:
        str: 저장 경로
    """
    from util.rule_loader import RuleLoader
    
    # Rule 파일에서 path 정보 로드
    rule_loader = RuleLoader(target_lang=target_lang)
    rule_info = rule_loader._load_role_file(role_name)
    relative_path = rule_info.get('path', '.')
    
    # 변수 치환 ({project_name}, {dir_name} 등)
    format_vars = {'project_name': project_name, **kwargs}
    relative_path = relative_path.format(**format_vars)
    
    # 전체 경로 생성
    docker_ctx = os.getenv('DOCKER_COMPOSE_CONTEXT')
    base_dir = docker_ctx if docker_ctx else _WORKSPACE_DIR
    base_path = os.path.join(base_dir, 'target', target_lang, user_id, project_name)
    
    return os.path.join(base_path, relative_path)


#==============================================================================
# 문자열 변환 유틸리티
#==============================================================================

def convert_to_pascal_case(snake_str: str) -> str:
    """스네이크 케이스를 파스칼 케이스로 변환 (최적화: 조건 개선)"""
    try:
        if not snake_str:
            return ""
        if '_' not in snake_str:
            return snake_str[0].upper() + snake_str[1:]
        return ''.join(word.capitalize() for word in snake_str.split('_'))
    except Exception as e:
        err_msg = f"파스칼 케이스 변환 중 오류 발생: {str(e)}"
        logging.error(err_msg)
        raise UtilProcessingError("파스칼 케이스 변환 중 오류 발생")


def convert_to_camel_case(snake_str: str) -> str:
    """스네이크 케이스를 카멜 케이스로 변환 (최적화: 빈 체크)"""
    try:
        if not snake_str:
            return ""
        words = snake_str.split('_')
        return words[0].lower() + ''.join(word.capitalize() for word in words[1:])
    except Exception as e:
        err_msg = f"카멜 케이스 변환 중 오류 발생: {str(e)}"
        logging.error(err_msg)
        raise UtilProcessingError("카멜 케이스 변환 중 오류 발생")


def convert_to_upper_snake_case(camel_str: str) -> str:
    """파스칼/카멜 케이스를 대문자 스네이크 케이스로 변환 (최적화: 리스트 사용)"""
    try:
        if not camel_str:
            return ""
        
        result = [camel_str[0].upper()]
        for char in camel_str[1:]:
            if char.isupper():
                result.append('_')
                result.append(char)
            else:
                result.append(char.upper())
        
        return ''.join(result)
    except Exception as e:
        err_msg = f"대문자 스네이크 케이스 변환 중 오류 발생: {str(e)}"
        logging.error(err_msg)
        raise UtilProcessingError("대문자 스네이크 케이스 변환 중 오류 발생")


def add_line_numbers(plsql: List[str]) -> Tuple[str, List[str]]:
    """PL/SQL 코드에 라인 번호 추가 (최적화: enumerate 인덱스 조정)"""
    try:
        numbered_lines = [f"{i}: {line}" for i, line in enumerate(plsql, start=1)]
        return "".join(numbered_lines), numbered_lines
    except Exception as e:
        err_msg = f"코드에 라인번호를 추가하는 도중 문제가 발생했습니다: {str(e)}"
        logging.error(err_msg)
        raise UtilProcessingError(err_msg)


#==============================================================================
# 스키마/테이블 파싱 & 정규화 유틸리티
#==============================================================================
def parse_table_identifier(qualified_table_name: str) -> tuple[str, str, str | None]:
    """'SCHEMA.TABLE@DBLINK'에서 (schema, table, dblink) 추출 (최적화: 조건 개선)"""
    if not qualified_table_name:
        return '', '', None
    
    text = qualified_table_name.strip()
    left, _, link = text.partition('@')
    s, _, t = left.partition('.')
    
    return (s.strip() if t else ''), (t.strip() if t else left.strip()), (link.strip() or None)

#==============================================================================
# 코드 분석 및 변환 유틸리티
#==============================================================================

def calculate_code_token(code: Union[str, Dict, List]) -> int:
    """코드 토큰 길이 계산 (최적화: 중복 제거)"""
    try:
        text_json = json.dumps(code, ensure_ascii=False)
        return len(ENCODER.encode(text_json))
    except Exception as e:
        err_msg = f"토큰 계산 도중 문제가 발생: {str(e)}"
        logging.error(err_msg)
        raise UtilProcessingError(err_msg)


def build_variable_index(local_variable_nodes: List[Dict]) -> Dict:
    """변수 노드를 startLine 기준으로 인덱싱 (최적화: split 최소화)"""
    index = {}
    for variable_node in local_variable_nodes:
        node_data = variable_node.get('v', {})
        var_name = node_data.get('name')
        if not var_name:
            continue
        
        var_info = f"{node_data.get('type', 'Unknown')}: {var_name}"
        
        for key in node_data:
            if '_' in key:
                parts = key.split('_')
                if len(parts) == 2 and all(p.isdigit() for p in parts):
                    start_line = int(parts[0])
                    entry = index.setdefault(start_line, {'nodes': defaultdict(list), 'tokens': None})
                    entry['nodes'][f"{start_line}~{int(parts[1])}"].append(var_info)
    return index


async def extract_used_variable_nodes(startLine: int, local_variable_nodes: List[Dict]) -> Tuple[Dict, int]:
    """특정 라인에서 사용된 변수 추출 (최적화: 타입 체크 개선)"""
    try:
        # 인덱스면 그대로 사용, 리스트면 인덱스 생성
        var_index = (local_variable_nodes if isinstance(local_variable_nodes, dict) 
                     else build_variable_index(local_variable_nodes))
        
        if entry := var_index.get(startLine):
            var_nodes = entry['nodes']
            if entry['tokens'] is None:
                entry['tokens'] = calculate_code_token(var_nodes)
            return var_nodes, entry['tokens']
        return {}, 0
    
    except UtilProcessingError:
        raise
    except Exception as e:
        err_msg = f"사용된 변수 노드를 추출하는 도중 오류가 발생했습니다: {str(e)}"
        logging.error(err_msg)
        raise UtilProcessingError(err_msg)


async def collect_variables_in_range(local_variable_nodes: List[Dict], start_line: int, end_line: int) -> List[Dict]:
    """범위 내 변수 수집 (최적화: 딕셔너리 구조 개선)"""
    try:
        unique = {}
        for variable_node in local_variable_nodes:
            node_data = variable_node.get('v', {})
            var_name = node_data.get('name')
            if not var_name or var_name in unique:
                continue
            
            for range_key in node_data:
                if '_' in range_key:
                    parts = range_key.split('_')
                    if len(parts) == 2 and all(p.isdigit() for p in parts):
                        v_start, v_end = int(parts[0]), int(parts[1])
                        if start_line <= v_start and v_end <= end_line:
                            unique[var_name] = {'type': node_data.get('type', 'Unknown'), 'name': var_name}
                            break
        return list(unique.values())
    except Exception as e:
        err_msg = f"변수 범위 수집 중 오류가 발생했습니다: {str(e)}"
        logging.error(err_msg)
        raise UtilProcessingError(err_msg)

async def extract_used_query_methods(start_line: int, end_line: int, 
                                   jpa_method_list: Dict, 
                                   used_jpa_method_dict: Dict) -> Dict:
    """범위 내 JPA 메서드 수집 (최적화: 직접 업데이트)"""
    try:
        for range_key, method in jpa_method_list.items():
            method_start, method_end = map(int, range_key.split('~'))
            if start_line <= method_start and method_end <= end_line:
                used_jpa_method_dict[range_key] = method
        return used_jpa_method_dict
        
    except Exception as e:
        err_msg = f"JPA 쿼리 메서드를 추출하는 도중 오류가 발생했습니다: {str(e)}"
        logging.error(err_msg)
        raise UtilProcessingError(err_msg)