"""
Understanding 파이프라인을 단일 테스트로 검증/비교합니다.

환경 변수 `UNDERSTANDING_VARIANT`로 실행 대상을 제어할 수 있습니다.
- `legacy`   : 레거시 Analyzer만 실행
- `refactor` : 리팩터 Analyzer만 실행 (기본값)
- `compare`  : 두 버전을 순차 실행하여 성능 지표(시간, 이벤트 수)를 출력

실제 환경에서 사용하려면 Neo4j, LLM API 등의 외부 의존성을 동일하게 준비해야 합니다.
"""

from __future__ import annotations

import importlib
import os
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List

import pytest
import pytest_asyncio


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# 한글 로그가 깨지지 않도록 UTF-8 인코딩을 강제합니다.
os.environ.setdefault("PYTHONIOENCODING", "utf-8")


TEST_USER_ID = "KO_TestSession"
TEST_PROJECT_NAME = "HOSPITAL_MANAGEMENT"
TEST_API_KEY = os.getenv("LLM_API_KEY")
TEST_DB_NAME = "test"
TEST_LOCALE = "ko"
TEST_DBMS = "postgres"

TEST_DATA_DIR = PROJECT_ROOT.parent / "data" / TEST_USER_ID / TEST_PROJECT_NAME

VARIANT_ENV_KEY = "UNDERSTANDING_VARIANT"
DEFAULT_VARIANT = "refactor"
VALID_VARIANTS = {"legacy", "refactor", "compare"}


def _determine_variants() -> tuple[List[str], bool]:
    """환경 변수 설정을 읽어 실행할 Analyzer 버전을 결정합니다."""
    env_value = os.getenv(VARIANT_ENV_KEY, DEFAULT_VARIANT).lower()
    if env_value not in VALID_VARIANTS:
        raise ValueError(
            f"환경 변수 {VARIANT_ENV_KEY} 값이 올바르지 않습니다: {env_value} (허용: {', '.join(sorted(VALID_VARIANTS))})"
        )

    if env_value == "compare":
        return ["legacy", "refactor"], True
    return [env_value], False


def _clear_import_cache():
    """동적 import 전 cached 모듈을 제거하여 변형 간 간섭을 막습니다."""
    for name in ("service.service", "understand.analysis"):
        sys.modules.pop(name, None)


def _load_service_orchestrator(variant: str):
    """지정된 버전에 해당하는 ServiceOrchestrator 클래스를 반환합니다."""
    if variant == "legacy":
        legacy_module = importlib.import_module("legacy.understand.analysis")
        sys.modules["understand.analysis"] = legacy_module
    else:
        # 리팩터 버전은 메인 모듈이므로 단순 import 만 수행
        importlib.import_module("understand.analysis")

    service_module = importlib.import_module("service.service")
    return service_module.ServiceOrchestrator


async def _clear_graph(connection, user_id: str, project_name: str):
    """테스트 독립성을 확보하기 위해 지정 사용자/프로젝트 데이터를 삭제합니다."""
    await connection.execute_queries([
        f"MATCH (n {{user_id: '{user_id}', project_name: '{project_name}'}}) DETACH DELETE n"
    ])


def _load_sp_files(data_dir: Path) -> List[tuple[str, str]]:
    """테스트용 SP 파일 목록을 폴더/파일 튜플 형태로 불러옵니다."""
    src_dir = data_dir / "src"
    if not data_dir.exists():
        raise AssertionError(f"테스트 데이터 디렉토리가 없습니다: {data_dir}")
    if not src_dir.exists():
        raise AssertionError(f"src 디렉토리가 없습니다: {src_dir}")

    sp_files: List[tuple[str, str]] = []
    for folder in sorted(src_dir.iterdir()):
        if folder.is_dir():
            for sql_file in sorted(folder.glob("*.sql")):
                sp_files.append((folder.name, sql_file.name))

    if not sp_files:
        raise AssertionError(f"SP 파일이 없습니다: {src_dir}")
    return sp_files


@pytest_asyncio.fixture
async def real_neo4j():
    """테스트용 Neo4j 연결을 생성하고 종료 후 복구합니다."""
    from understand.neo4j_connection import Neo4jConnection

    original_db = Neo4jConnection.DATABASE_NAME
    Neo4jConnection.DATABASE_NAME = TEST_DB_NAME

    conn = Neo4jConnection()
    await _clear_graph(conn, TEST_USER_ID, TEST_PROJECT_NAME)

    try:
        yield conn
    finally:
        await conn.close()
        Neo4jConnection.DATABASE_NAME = original_db


def _run_summary_log(results: Iterable[Dict[str, float | int | str]]):
    """비교 실행 결과를 읽기 좋은 로그 형식으로 출력합니다."""
    lines = ["\n[UNDERSTANDING TEST RESULT]"]
    for item in results:
        lines.append(
            (
                f"  - variant={item['variant']} "
                f"elapsed={item['elapsed_seconds']:.2f}s "
                f"events={item['event_count']} "
                f"files={item['files']}"
            )
        )
    print("\n".join(lines))


@pytest.mark.asyncio
async def test_understanding_pipeline(real_neo4j):
    """환경 설정에 따라 레거시/리팩터 Analyzer를 실행하고 결과를 비교합니다."""
    if not TEST_API_KEY:
        pytest.skip("LLM_API_KEY가 설정되지 않았습니다")

    variants, compare_mode = _determine_variants()
    sp_files = _load_sp_files(TEST_DATA_DIR)

    results: List[Dict[str, float | int | str]] = []

    for variant in variants:
        orchestrator_cls = _load_service_orchestrator(variant)
        orchestrator = orchestrator_cls(
            user_id=TEST_USER_ID,
            api_key=TEST_API_KEY,
            locale=TEST_LOCALE,
            project_name=TEST_PROJECT_NAME,
            dbms=TEST_DBMS,
        )

        await _clear_graph(real_neo4j, TEST_USER_ID, TEST_PROJECT_NAME)

        start = time.perf_counter()
        event_count = 0
        async for _chunk in orchestrator.understand_project(list(sp_files)):
            event_count += 1
        elapsed = time.perf_counter() - start

        results.append(
            {
                "variant": variant,
                "elapsed_seconds": elapsed,
                "event_count": event_count,
                "files": len(sp_files),
            }
        )

        assert event_count > 0, f"{variant} 파이프라인에서 이벤트가 생성되지 않았습니다"

        _clear_import_cache()

    _run_summary_log(results)

    if compare_mode:
        # 비교 모드에서는 두 결과가 모두 생성되었는지 확인
        assert len(results) == 2, "compare 모드에서는 두 결과가 생성되어야 합니다"

