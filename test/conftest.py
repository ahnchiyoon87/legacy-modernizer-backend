"""
pytest 설정 파일 - 모든 테스트에 공통 적용되는 설정
"""
import logging
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

# 로깅 설정 (테스트 실행 시 내부 로직의 logging 출력을 보기 위함)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S',
    force=True  # 기존 로깅 설정을 덮어쓰기
)

# pytest 경고 필터링은 pytest.ini에서 처리

