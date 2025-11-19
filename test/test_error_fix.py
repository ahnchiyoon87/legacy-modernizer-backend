"""
오류 수정 기능 테스트
- 컴파일 오류 발생 시 변환된 코드를 자동으로 수정하고 재병합하는 기능 테스트
"""

import pytest
import asyncio
import os
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from error_fix.main import fix_conversion_error
from error_fix.error_parser import parse_error_message
from error_fix.block_finder import find_converting_node, find_block_by_line_number
from understand.neo4j_connection import Neo4jConnection


# ==================== 설정 ====================

TEST_USER_ID = "KO_TestSession"
TEST_PROJECT_NAME = "HOSPITAL_MANAGEMENT"
TEST_API_KEY = os.getenv("LLM_API_KEY")
TEST_LOCALE = "ko"
TEST_CONVERSION_TYPE = "dbms"
TEST_TARGET = "oracle"

# 테스트 대상 파일
TEST_FOLDER_NAME = "HOSPITAL_RECEPTION"
TEST_FILE_NAME = "SP_HOSPITAL_RECEPTION.sql"
TEST_PROCEDURE_NAME = "TPX_HOSPITAL_RECEPTION"


# ==================== Fixtures ====================

@pytest.fixture(scope="module")
def test_config():
    """테스트 설정"""
    return {
        "user_id": TEST_USER_ID,
        "project_name": TEST_PROJECT_NAME,
        "api_key": TEST_API_KEY,
        "locale": TEST_LOCALE,
        "conversion_type": TEST_CONVERSION_TYPE,
        "target": TEST_TARGET,
        "folder_name": TEST_FOLDER_NAME,
        "file_name": TEST_FILE_NAME,
        "procedure_name": TEST_PROCEDURE_NAME
    }


# ==================== 테스트 케이스 ====================

class TestErrorParser:
    """오류 메시지 파서 테스트"""
    
    def test_parse_oracle_error(self):
        """Oracle 오류 메시지 파싱"""
        error_msg = "ORA-00942: table or view does not exist at line 10"
        result = parse_error_message(error_msg)
        
        assert result is not None
        assert result['error_code'] == 'ORA-00942'
        assert result['error_number'] == 942
        assert result['line_number'] == 10
        assert 'table or view does not exist' in result['error_message']
    
    def test_parse_oracle_error_no_line(self):
        """라인 번호 없는 Oracle 오류"""
        error_msg = "ORA-00942: table or view does not exist"
        result = parse_error_message(error_msg)
        
        assert result is not None
        assert result['error_code'] == 'ORA-00942'
        assert result['error_number'] == 942
        assert result['line_number'] is None
    
    def test_parse_sql_server_error(self):
        """SQL Server 오류 메시지 파싱"""
        error_msg = "Msg 102, Level 15, State 1, Line 5, Invalid syntax"
        result = parse_error_message(error_msg)
        
        assert result is not None
        assert result['error_code'] == 'SQL-102'
        assert result['error_number'] == 102
        assert result['line_number'] == 5
    
    def test_parse_invalid_error(self):
        """잘못된 형식의 오류 메시지"""
        error_msg = "Some random error message"
        result = parse_error_message(error_msg)
        
        # 파싱 실패 시 None 또는 기본값 반환
        # 실제 구현에 따라 다를 수 있음
        assert result is None or isinstance(result, dict)


class TestBlockFinder:
    """블록 찾기 테스트"""
    
    @pytest.mark.asyncio
    async def test_find_converting_node(self, test_config):
        """CONVERTING 노드 찾기"""
        if not test_config["api_key"]:
            pytest.skip("LLM_API_KEY 환경변수가 설정되지 않았습니다")
        
        converting_node = await find_converting_node(
            folder_name=test_config["folder_name"],
            file_name=test_config["file_name"],
            procedure_name=test_config["procedure_name"],
            user_id=test_config["user_id"],
            project_name=test_config["project_name"],
            conversion_type=test_config["conversion_type"],
            target=test_config["target"]
        )
        
        # CONVERTING 노드가 존재하는 경우에만 테스트
        if converting_node:
            assert converting_node is not None
            assert converting_node.get('folder_name') == test_config["folder_name"]
            assert converting_node.get('file_name') == test_config["file_name"]
            assert converting_node.get('procedure_name') == test_config["procedure_name"]
        else:
            pytest.skip("CONVERTING 노드가 존재하지 않습니다. 먼저 변환을 수행하세요.")
    
    @pytest.mark.asyncio
    async def test_find_block_by_line_number(self, test_config):
        """라인 번호로 블록 찾기"""
        if not test_config["api_key"]:
            pytest.skip("LLM_API_KEY 환경변수가 설정되지 않았습니다")
        
        # 테스트용 라인 번호 (실제 존재하는 라인 번호로 변경 필요)
        test_line_number = 10
        
        block = await find_block_by_line_number(
            folder_name=test_config["folder_name"],
            file_name=test_config["file_name"],
            procedure_name=test_config["procedure_name"],
            user_id=test_config["user_id"],
            project_name=test_config["project_name"],
            conversion_type=test_config["conversion_type"],
            target=test_config["target"],
            line_number=test_line_number
        )
        
        # 블록이 존재하는 경우에만 테스트
        if block:
            assert block is not None
            assert block.get('start_line') <= test_line_number
            assert block.get('end_line') >= test_line_number
            assert 'converted_code' in block
            assert 'original_code' in block
        else:
            pytest.skip(f"라인 {test_line_number}을 포함하는 블록이 없습니다.")


class TestErrorFix:
    """오류 수정 통합 테스트"""
    
    @pytest.mark.asyncio
    async def test_fix_single_error(self, test_config):
        """단일 오류 수정 테스트"""
        if not test_config["api_key"]:
            pytest.skip("LLM_API_KEY 환경변수가 설정되지 않았습니다")
        
        # 테스트용 오류 메시지 (실제 컴파일 오류로 변경 필요)
        error_messages = [
            "ORA-00942: table or view does not exist at line 10"
        ]
        
        try:
            fixed_code = await fix_conversion_error(
                error_messages=error_messages,
                folder_name=test_config["folder_name"],
                file_name=test_config["file_name"],
                procedure_name=test_config["procedure_name"],
                user_id=test_config["user_id"],
                project_name=test_config["project_name"],
                api_key=test_config["api_key"],
                locale=test_config["locale"],
                conversion_type=test_config["conversion_type"],
                target=test_config["target"]
            )
            
            assert fixed_code is not None
            assert len(fixed_code) > 0
            assert isinstance(fixed_code, str)
            
        except Exception as e:
            # CONVERTING 노드가 없거나 블록을 찾을 수 없는 경우는 스킵
            if "CONVERTING 노드를 찾을 수 없습니다" in str(e) or "블록을 찾을 수 없습니다" in str(e):
                pytest.skip(f"테스트 전제조건 미충족: {str(e)}")
            else:
                raise
    
    @pytest.mark.asyncio
    async def test_fix_multiple_errors(self, test_config):
        """여러 오류 한번에 수정 테스트"""
        if not test_config["api_key"]:
            pytest.skip("LLM_API_KEY 환경변수가 설정되지 않았습니다")
        
        # 테스트용 오류 메시지들 (실제 컴파일 오류로 변경 필요)
        error_messages = [
            "ORA-00942: table or view does not exist at line 10",
            "ORA-00904: invalid identifier at line 15"
        ]
        
        try:
            fixed_code = await fix_conversion_error(
                error_messages=error_messages,
                folder_name=test_config["folder_name"],
                file_name=test_config["file_name"],
                procedure_name=test_config["procedure_name"],
                user_id=test_config["user_id"],
                project_name=test_config["project_name"],
                api_key=test_config["api_key"],
                locale=test_config["locale"],
                conversion_type=test_config["conversion_type"],
                target=test_config["target"]
            )
            
            assert fixed_code is not None
            assert len(fixed_code) > 0
            assert isinstance(fixed_code, str)
            
        except Exception as e:
            # CONVERTING 노드가 없거나 블록을 찾을 수 없는 경우는 스킵
            if "CONVERTING 노드를 찾을 수 없습니다" in str(e) or "블록을 찾을 수 없습니다" in str(e):
                pytest.skip(f"테스트 전제조건 미충족: {str(e)}")
            else:
                raise
    
    @pytest.mark.asyncio
    async def test_fix_with_additional_context(self, test_config):
        """추가 컨텍스트를 포함한 오류 수정 테스트"""
        if not test_config["api_key"]:
            pytest.skip("LLM_API_KEY 환경변수가 설정되지 않았습니다")
        
        error_messages = [
            "ORA-00942: table or view does not exist at line 10"
        ]
        
        additional_context = """
        테이블 정보:
        - 테이블명: PATIENT_INFO (대문자 사용)
        - 스키마: HOSPITAL_SCHEMA
        
        지시사항:
        - 모든 테이블 참조 시 스키마명을 명시하세요
        """
        
        try:
            fixed_code = await fix_conversion_error(
                error_messages=error_messages,
                folder_name=test_config["folder_name"],
                file_name=test_config["file_name"],
                procedure_name=test_config["procedure_name"],
                user_id=test_config["user_id"],
                project_name=test_config["project_name"],
                api_key=test_config["api_key"],
                locale=test_config["locale"],
                conversion_type=test_config["conversion_type"],
                target=test_config["target"],
                additional_context=additional_context
            )
            
            assert fixed_code is not None
            assert len(fixed_code) > 0
            
        except Exception as e:
            if "CONVERTING 노드를 찾을 수 없습니다" in str(e) or "블록을 찾을 수 없습니다" in str(e):
                pytest.skip(f"테스트 전제조건 미충족: {str(e)}")
            else:
                raise


# ==================== 실행 ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

