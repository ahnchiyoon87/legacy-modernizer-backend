"""
오류 수정 메인 스크립트
- 컴파일 오류 발생 시 변환된 코드를 자동으로 수정하고 재병합
"""

import logging
import asyncio
from typing import Optional
from error_fix.error_parser import parse_error_message
from error_fix.block_finder import find_converting_node, find_block_by_line_number, get_block_with_children
from error_fix.code_fixer import fix_code_with_llm
from error_fix.code_merger import merge_fixed_code
from understand.neo4j_connection import Neo4jConnection
from util.utility_tool import escape_for_cypher
from convert.dbms.create_dbms_skeleton import start_dbms_skeleton
from util.exception import ConvertingError

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def fix_conversion_error(
    error_messages: list[str] | str,
    folder_name: str,
    file_name: str,
    procedure_name: str,
    user_id: str,
    project_name: str,
    api_key: str,
    locale: str = "ko",
    conversion_type: str = "dbms",
    target: str = "oracle",
    additional_context: str | None = None
) -> str:
    """
    컴파일 오류들을 수정하고 변환된 코드를 재병합합니다.
    
    Args:
        error_messages: 컴파일 오류 메시지 리스트 또는 단일 메시지
                       (예: ["ORA-00942: ... at line 10", "ORA-00904: ... at line 15"])
        folder_name: 폴더명
        file_name: 파일명
        procedure_name: 프로시저명
        user_id: 사용자 ID
        project_name: 프로젝트명
        api_key: LLM API 키
        locale: 언어 설정
        conversion_type: 변환 타입 ("dbms" 또는 "framework")
        target: 타겟 (예: "oracle", "java")
        additional_context: 추가 컨텍스트 정보 (예: 테이블 정보, 지시사항 등)
                           예시: "테이블명은 PATIENT_INFO입니다. 컬럼명은 snake_case를 사용하세요."
        
    Returns:
        수정 및 병합된 최종 코드
    """
    try:
        # 단일 오류 메시지를 리스트로 변환
        if isinstance(error_messages, str):
            error_messages = [error_messages]
        
        if not error_messages:
            raise ConvertingError("오류 메시지가 없습니다.")
        
        logger.info(f"🔍 총 {len(error_messages)}개의 오류를 처리합니다.")
        
        # 1. CONVERTING 노드 찾기 (한 번만)
        logger.info("🔍 CONVERTING 노드 검색 중...")
        converting_node = await find_converting_node(
            folder_name=folder_name,
            file_name=file_name,
            procedure_name=procedure_name,
            user_id=user_id,
            project_name=project_name,
            conversion_type=conversion_type,
            target=target
        )
        
        if not converting_node:
            raise ConvertingError(
                f"CONVERTING 노드를 찾을 수 없습니다: "
                f"{folder_name}/{file_name}/{procedure_name}"
            )
        
        logger.info("✅ CONVERTING 노드 찾음")
        
        # 2. 각 오류를 순차적으로 처리
        processed_errors = []
        for idx, error_message in enumerate(error_messages, 1):
            logger.info(f"\n{'='*80}")
            logger.info(f"📝 오류 {idx}/{len(error_messages)} 처리 중...")
            logger.info(f"{'='*80}")
            
            # 2-1. 오류 메시지 파싱
            error_info = parse_error_message(error_message)
            if not error_info:
                logger.warning(f"⚠️ 오류 메시지 파싱 실패, 건너뜀: {error_message}")
                continue
            
            error_number = error_info.get('error_number')
            error_code = error_info.get('error_code', 'UNKNOWN')
            error_msg = error_info.get('error_message', error_message)
            line_number = error_info.get('line_number')
            
            logger.info(f"✅ 오류 정보: {error_code} (라인: {line_number})")
            
            # 2-2. 오류 라인 번호를 포함하는 블록 찾기 (자식 우선)
            if not line_number:
                logger.warning(f"⚠️ 라인 번호 추출 실패, 건너뜀: {error_message}")
                continue
            
            logger.info(f"🔍 오류 라인 {line_number}을 포함하는 블록 검색 중...")
            error_block = await find_block_by_line_number(
                folder_name=folder_name,
                file_name=file_name,
                procedure_name=procedure_name,
                user_id=user_id,
                project_name=project_name,
                conversion_type=conversion_type,
                target=target,
                line_number=line_number
            )
            
            if not error_block:
                logger.warning(f"⚠️ 라인 {line_number}을 포함하는 블록을 찾을 수 없음, 건너뜀")
                continue
            
            logger.info(
                f"✅ 오류 블록 찾음: 라인 {error_block.get('start_line')}~{error_block.get('end_line')}"
            )
            
            # 2-3. 블록 정보 가져오기
            block_start = error_block.get('start_line')
            block_end = error_block.get('end_line')
            block_info = await get_block_with_children(
                folder_name=folder_name,
                file_name=file_name,
                procedure_name=procedure_name,
                user_id=user_id,
                project_name=project_name,
                conversion_type=conversion_type,
                target=target,
                block_start_line=block_start,
                block_end_line=block_end
            )
            
            target_block = block_info.get('block')
            if not target_block:
                logger.warning(f"⚠️ 블록 정보를 가져올 수 없음, 건너뜀")
                continue
            
            # 2-4. LLM으로 코드 수정
            original_code = target_block.get('original_code', '')
            converted_code = target_block.get('converted_code', '')
            block_start_line = target_block.get('start_line')
            
            logger.info(f"🤖 LLM을 통한 코드 수정 중... (오류: {error_code})")
            fixed_code = await fix_code_with_llm(
                original_code=original_code,
                converted_code=converted_code,
                error_message=error_msg,
                error_code=error_code,
                error_number=error_number,
                start_line=block_start_line,
                api_key=api_key,
                locale=locale,
                conversion_type=conversion_type,
                target=target,
                additional_context=additional_context
            )
            
            # 2-5. Neo4j에 수정된 코드 업데이트
            logger.info("💾 Neo4j에 수정된 코드 저장 중...")
            await update_block_code(
                folder_name=folder_name,
                file_name=file_name,
                procedure_name=procedure_name,
                user_id=user_id,
                project_name=project_name,
                start_line=block_start,
                end_line=block_end,
                fixed_code=fixed_code
            )
            
            logger.info(f"✅ 오류 {idx} 처리 완료: {error_code}")
            processed_errors.append({
                'error_code': error_code,
                'line_number': line_number,
                'block': f"{block_start}~{block_end}"
            })
        
        if not processed_errors:
            raise ConvertingError("처리된 오류가 없습니다.")
        
        logger.info(f"\n{'='*80}")
        logger.info(f"✅ 총 {len(processed_errors)}개의 오류 처리 완료")
        logger.info(f"{'='*80}\n")
        
        # 3. 모든 오류 처리 완료 후 스켈레톤 생성 및 병합 (1번만)
        logger.info("🔧 스켈레톤 코드 생성 중...")
        skeleton_code = await start_dbms_skeleton(
            folder_name=folder_name,
            file_name=file_name,
            procedure_name=procedure_name,
            project_name=project_name,
            user_id=user_id,
            api_key=api_key,
            locale=locale,
            target_dbms=target
        )
        
        # 4. 코드 병합
        logger.info("🔗 코드 병합 중...")
        merged_code = await merge_fixed_code(
            folder_name=folder_name,
            file_name=file_name,
            procedure_name=procedure_name,
            user_id=user_id,
            project_name=project_name,
            conversion_type=conversion_type,
            target=target,
            skeleton_code=skeleton_code
        )
        
        logger.info("✅ 모든 오류 수정 및 코드 병합 완료!")
        return merged_code
        
    except Exception as e:
        logger.error(f"❌ 오류 수정 실패: {str(e)}")
        raise ConvertingError(f"오류 수정 중 오류: {str(e)}")


async def update_block_code(
    folder_name: str,
    file_name: str,
    procedure_name: str,
    user_id: str,
    project_name: str | None,
    start_line: int,
    end_line: int,
    fixed_code: str
) -> None:
    """
    Neo4j의 CONVERSION_BLOCK 노드에 수정된 코드를 업데이트합니다.
    """
    connection = Neo4jConnection()
    try:
        project_condition = f", project_name: '{escape_for_cypher(project_name)}'" if project_name else ""
        escaped_code = escape_for_cypher(fixed_code)
        
        query = f"""
            MATCH (block:CONVERSION_BLOCK {{
                folder_name: '{escape_for_cypher(folder_name)}',
                file_name: '{escape_for_cypher(file_name)}',
                procedure_name: '{escape_for_cypher(procedure_name)}',
                user_id: '{escape_for_cypher(user_id)}'{project_condition},
                start_line: {start_line},
                end_line: {end_line}
            }})
            SET block.converted_code = '{escaped_code}',
                block.updated_at = datetime()
        """
        
        await connection.execute_queries([query])
    finally:
        await connection.close()


# CLI 진입점
async def main():
    """
    CLI에서 실행할 때 사용하는 메인 함수
    예: python -m error_fix.main
    
    하드코딩된 변수들을 수정하여 사용하세요.
    """
    # ============================================
    # 하드코딩된 설정값 (여기를 수정하세요)
    # ============================================
    
    # 컴파일 오류 메시지들 (여러 개 가능)
    error_messages = [
        "ORA-00942: table or view does not exist at line 10",
        # "ORA-00904: invalid identifier at line 15",  # 추가 오류가 있으면 주석 해제
    ]
    
    # 필수 정보
    folder_name = "HOSPITAL_RECEPTION"
    file_name = "SP_HOSPITAL_RECEPTION.sql"
    procedure_name = "TPX_HOSPITAL_RECEPTION"
    user_id = "KO_TestSession"
    project_name = "HOSPITAL_MANAGEMENT"
    api_key = "your-api-key-here"  # API 키를 여기에 입력하세요
    
    # 선택 정보 (기본값 사용 시 변경 불필요)
    locale = "ko"
    conversion_type = "dbms"
    target = "oracle"
    
    # 추가 컨텍스트 (필요시 사용)
    additional_context = None
    # additional_context = """
    # 테이블 정보:
    # - 테이블명: PATIENT_INFO (대문자 사용)
    # - 컬럼명: snake_case 사용
    # 
    # 지시사항:
    # - 모든 테이블 참조 시 스키마명을 명시하세요
    # """
    
    # ============================================
    # 실행
    # ============================================
    
    try:
        fixed_code = await fix_conversion_error(
            error_messages=error_messages,
            folder_name=folder_name,
            file_name=file_name,
            procedure_name=procedure_name,
            user_id=user_id,
            project_name=project_name,
            api_key=api_key,
            locale=locale,
            conversion_type=conversion_type,
            target=target,
            additional_context=additional_context
        )
        
        print("\n" + "="*80)
        print("✅ 수정된 코드:")
        print("="*80)
        print(fixed_code)
        print("="*80)
        
    except Exception as e:
        import sys
        print(f"❌ 오류: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

