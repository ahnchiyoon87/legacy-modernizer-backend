"""
임시 테스트 스텁: 기존 Understanding 파이프라인 전체 테스트를
`temp.analysis_async_refactor.Analyzer` 대상으로도 수행할 수 있도록 복제한 파일입니다.

실제 환경에서 사용하려면 Neo4j, LLM API 등의 외부 의존성을 동일하게 준비해야 합니다.
"""

import asyncio
import os
from pathlib import Path

import pytest
import pytest_asyncio

import importlib
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# 리팩터 Analyzer를 강제로 사용하도록 교체합니다.
sys.modules["understand.analysis"] = importlib.import_module("temp.analysis_async_refactor")

# 한글 로그가 깨지지 않도록 UTF-8 인코딩을 강제합니다.
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from service.service import ServiceOrchestrator
from understand.neo4j_connection import Neo4jConnection


TEST_USER_ID = "KO_TestSession"
TEST_PROJECT_NAME = "HOSPITAL_MANAGEMENT"
TEST_API_KEY = os.getenv("LLM_API_KEY")
TEST_DB_NAME = "test"
TEST_LOCALE = "ko"
TEST_DBMS = "postgres"

TEST_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / TEST_USER_ID / TEST_PROJECT_NAME


@pytest.fixture(scope="module")
def test_data_exists():
    assert TEST_DATA_DIR.exists(), f"테스트 데이터 디렉토리가 없습니다: {TEST_DATA_DIR}"
    src_dir = TEST_DATA_DIR / "src"
    assert src_dir.exists(), f"src 디렉토리가 없습니다: {src_dir}"

    sp_files = []
    for folder in src_dir.iterdir():
        if folder.is_dir():
            for sql_file in folder.glob("*.sql"):
                sp_files.append((folder.name, sql_file.name))

    assert sp_files, f"SP 파일이 없습니다: {src_dir}"
    return TEST_DATA_DIR, sp_files


@pytest_asyncio.fixture
async def real_neo4j():
    original_db = Neo4jConnection.DATABASE_NAME
    Neo4jConnection.DATABASE_NAME = TEST_DB_NAME

    conn = Neo4jConnection()
    await conn.execute_queries([
        f"MATCH (n {{user_id: '{TEST_USER_ID}', project_name: '{TEST_PROJECT_NAME}'}}) DETACH DELETE n"
    ])

    yield conn

    await conn.close()
    Neo4jConnection.DATABASE_NAME = original_db


@pytest.mark.asyncio
async def test_complete_understanding_pipeline_against_temp_copy(test_data_exists, real_neo4j):
    if not TEST_API_KEY:
        pytest.skip("LLM_API_KEY가 설정되지 않았습니다")

    _, sp_files = test_data_exists

    orchestrator = ServiceOrchestrator(
        user_id=TEST_USER_ID,
        api_key=TEST_API_KEY,
        locale=TEST_LOCALE,
        project_name=TEST_PROJECT_NAME,
        dbms=TEST_DBMS
    )

    events = []
    async for chunk in orchestrator.understand_project(sp_files):
        events.append(chunk)

    assert events, "Understanding 파이프라인 이벤트가 없습니다"

