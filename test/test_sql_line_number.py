#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQL 파일 라인 번호 추가 스크립트
지정된 경로의 SQL 파일들을 읽어서 라인 번호를 추가한 형태로 출력/저장합니다.
"""

import sys
from pathlib import Path
from typing import List, Optional


def add_line_numbers_to_sql(file_path: Path, output_path: Optional[Path] = None) -> str:
    """
    SQL 파일을 읽어서 라인 번호를 추가한 형태로 변환
    
    Args:
        file_path: 읽을 SQL 파일 경로
        output_path: 출력 파일 경로 (None이면 콘솔 출력만)
    
    Returns:
        str: 라인 번호가 추가된 SQL 내용
    """
    try:
        # 파일 읽기 (UTF-8, BOM 처리)
        with open(file_path, 'rb') as f:
            raw_content = f.read()
        
        content = raw_content.decode('utf-8', errors='ignore')
        if content.startswith('\ufeff'):
            content = content[1:]
        
        # 라인 번호 추가
        lines = content.splitlines(keepends=True)
        numbered_lines = []
        
        for line_num, line in enumerate(lines, start=1):
            # 라인 끝 문자가 있으면 그대로 유지, 없으면 추가
            if line.endswith('\n') or line.endswith('\r\n'):
                numbered_line = f"{line_num}: {line}"
            else:
                numbered_line = f"{line_num}: {line}\n"
            
            numbered_lines.append(numbered_line)
        
        result = ''.join(numbered_lines)
        
        # 파일로 저장 (옵션)
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(result)
            print(f"✓ 저장 완료: {output_path}")
        
        return result
        
    except FileNotFoundError:
        print(f"❌ 파일을 찾을 수 없습니다: {file_path}")
        return ""
    except Exception as e:
        print(f"❌ 오류 발생: {file_path} - {str(e)}")
        return ""


def process_directory(directory_path: Path, output_dir: Optional[Path] = None) -> None:
    """
    디렉토리 내 모든 SQL 파일 처리
    
    Args:
        directory_path: SQL 파일이 있는 디렉토리 경로
        output_dir: 출력 디렉토리 (None이면 콘솔 출력만)
    """
    if not directory_path.exists():
        print(f"❌ 디렉토리가 존재하지 않습니다: {directory_path}")
        return
    
    if not directory_path.is_dir():
        print(f"❌ 디렉토리가 아닙니다: {directory_path}")
        return
    
    # .sql 파일 찾기
    sql_files = list(directory_path.glob("*.sql"))
    
    if not sql_files:
        print(f"⚠️  SQL 파일을 찾을 수 없습니다: {directory_path}")
        return
    
    print(f"📂 디렉토리: {directory_path}")
    print(f"📄 발견된 SQL 파일: {len(sql_files)}개\n")
    print("=" * 80)
    
    for sql_file in sorted(sql_files):
        print(f"\n📄 파일: {sql_file.name}")
        print("-" * 80)
        
        if output_dir:
            output_file = output_dir / f"{sql_file.stem}_numbered.sql"
            result = add_line_numbers_to_sql(sql_file, output_file)
        else:
            result = add_line_numbers_to_sql(sql_file)
            # 콘솔 출력 (처음 50줄만)
            lines = result.splitlines()
            for line in lines[:50]:
                print(line)
            if len(lines) > 50:
                print(f"\n... (총 {len(lines)}줄, 처음 50줄만 표시)")
        
        print("-" * 80)


def main():
    """메인 함수"""
    # 기본 경로 (사용자 지정)
    default_path = Path(r"C:\uEngine\Legacy-modernizer\data\TestSession_4\test\src\sample")
    
    # 명령줄 인자 처리
    if len(sys.argv) > 1:
        target_path = Path(sys.argv[1])
    else:
        target_path = default_path
    
    # 출력 디렉토리 (옵션)
    output_dir = None
    if len(sys.argv) > 2:
        output_dir = Path(sys.argv[2])
    
    print("=" * 80)
    print("SQL 파일 라인 번호 추가 스크립트")
    print("=" * 80)
    print()
    
    # 파일인지 디렉토리인지 확인
    if target_path.is_file() and target_path.suffix.lower() == '.sql':
        # 단일 파일 처리
        print(f"📄 파일 처리: {target_path}")
        print("-" * 80)
        
        if output_dir:
            output_file = output_dir / f"{target_path.stem}_numbered.sql"
            result = add_line_numbers_to_sql(target_path, output_file)
        else:
            result = add_line_numbers_to_sql(target_path)
            # 콘솔 출력
            print(result)
        
    elif target_path.is_dir():
        # 디렉토리 처리
        process_directory(target_path, output_dir)
    else:
        print(f"❌ 유효하지 않은 경로입니다: {target_path}")
        print(f"   파일(.sql) 또는 디렉토리를 지정해주세요.")
        return
    
    print("\n" + "=" * 80)
    print("✅ 처리 완료")
    print("=" * 80)


if __name__ == '__main__':
    main()

