"""Understanding 분석 파이프라인 성능 측정 스크립트.

이 스크립트는 기존 `understand.analysis.Analyzer`와
`temp.analysis_async_refactor.Analyzer`를 선택적으로 적용하여
동일한 입력에 대한 처리 시간을 비교할 수 있도록 준비합니다.

실행 전/후로 LangChain 캐시(`langchain.db*`)를 정리하여
프롬프트 응답 캐시가 결과에 영향을 주지 않도록 할 수 있습니다.
각 버전은 별도의 프로세스로 실행하세요.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import os
import sys
import time
from pathlib import Path
from types import ModuleType
from typing import Iterable, List, Sequence, Tuple


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _clear_langchain_cache(verbose: bool = False) -> None:
    """프로젝트 내에 생성된 LangChain SQLite 캐시 파일을 제거합니다."""
    removed: List[Path] = []
    for db_file in BACKEND_ROOT.rglob("langchain.db*"):
        try:
            db_file.unlink()
            removed.append(db_file)
        except FileNotFoundError:
            continue
        except OSError as exc:
            if verbose:
                print(f"캐시 삭제 실패: {db_file} ({exc})")

    if verbose:
        if removed:
            print("삭제된 캐시 파일:")
            for path in removed:
                try:
                    rel_path = path.relative_to(PROJECT_ROOT)
                except ValueError:
                    rel_path = path
                print(f"  - {rel_path}")
        else:
            print("삭제할 LangChain 캐시 파일이 없습니다.")


def _load_file_pairs(args: argparse.Namespace) -> Sequence[Tuple[str, str]]:
    """분석 대상 파일 목록을 로드합니다."""
    if args.file_pairs:
        data_path = Path(args.file_pairs).resolve()
        payload = json.loads(data_path.read_text(encoding="utf-8"))
        return [(folder, file) for folder, file in payload]

    base_dir = PROJECT_ROOT / "data" / args.user_id / args.project_name / "src"
    if not base_dir.exists():
        raise FileNotFoundError(f"분석 대상 src 디렉터리가 없습니다: {base_dir}")

    pairs: List[Tuple[str, str]] = []
    for folder in sorted(base_dir.iterdir()):
        if folder.is_dir():
            for sql_file in sorted(folder.glob("*.sql")):
                pairs.append((folder.name, sql_file.name))

    if not pairs:
        raise FileNotFoundError(f"SQL 파일을 찾을 수 없습니다: {base_dir}")

    return pairs


async def _reset_neo4j(user_id: str, project_name: str, database: str | None) -> None:
    """비교 실행 전 기존 그래프 데이터를 정리합니다."""
    from understand.neo4j_connection import Neo4jConnection

    original_db = Neo4jConnection.DATABASE_NAME
    if database:
        Neo4jConnection.DATABASE_NAME = database

    try:
        conn = Neo4jConnection()
        try:
            await conn.execute_queries([
                f"MATCH (n {{user_id: '{user_id}', project_name: '{project_name}'}}) DETACH DELETE n"
            ])
        finally:
            await conn.close()
    finally:
        Neo4jConnection.DATABASE_NAME = original_db


def _prepare_service_module(variant: str) -> ModuleType:
    """선택한 Analyzer 변형을 사용하도록 service 모듈을 로드합니다."""
    if variant not in {"original", "refactor"}:
        raise ValueError("variant는 original 또는 refactor 중 하나여야 합니다.")

    for name in ["service.service", "understand.analysis"]:
        if name in sys.modules:
            del sys.modules[name]

    if variant == "refactor":
        ref_module = importlib.import_module("temp.analysis_async_refactor")
        sys.modules["understand.analysis"] = ref_module

    return importlib.import_module("service.service")


def _override_postprocess_if_needed(service_module: ModuleType, variant: str) -> None:
    """리팩터 모드에서는 postprocess를 비활성화하고, 오리지널은 기본 동작을 유지합니다."""
    orchestrator_cls = getattr(service_module, "ServiceOrchestrator", None)
    if orchestrator_cls is None:
        return

    if variant == "refactor":
        async def _skip_postprocess(self, connection, folder_name, file_name, file_pairs):
            return None

        setattr(orchestrator_cls, "_postprocess_file", _skip_postprocess)

async def _run_understanding(
    variant: str,
    files: Sequence[Tuple[str, str]],
    user_id: str,
    api_key: str,
    locale: str,
    project_name: str,
    dbms: str,
    neo4j_db: str | None,
) -> dict:
    """선택한 Analyzer로 Understanding 파이프라인을 실행하고 통계를 반환합니다."""
    service_module = _prepare_service_module(variant)
    _override_postprocess_if_needed(service_module, variant)
    orchestrator = service_module.ServiceOrchestrator(
        user_id=user_id,
        api_key=api_key,
        locale=locale,
        project_name=project_name,
        dbms=dbms,
    )

    from understand.neo4j_connection import Neo4jConnection
    original_db = Neo4jConnection.DATABASE_NAME
    if neo4j_db:
        Neo4jConnection.DATABASE_NAME = neo4j_db

    try:
        start = time.perf_counter()
        event_count = 0
        async for _chunk in orchestrator.understand_project(list(files)):
            event_count += 1
        elapsed = time.perf_counter() - start
    finally:
        Neo4jConnection.DATABASE_NAME = original_db

    return {
        "variant": variant,
        "elapsed_seconds": elapsed,
        "event_count": event_count,
        "files": len(files),
    }


async def main_async(args: argparse.Namespace) -> None:
    if args.clear_cache:
        _clear_langchain_cache(verbose=True)

    files = _load_file_pairs(args)
    if args.reset_neo4j:
        await _reset_neo4j(args.user_id, args.project_name, args.neo4j_db)

    if not args.api_key:
        raise RuntimeError("LLM_API_KEY 환경 변수가 설정되어 있지 않습니다.")

    result = await _run_understanding(
        variant=args.variant,
        files=files,
        user_id=args.user_id,
        api_key=args.api_key,
        locale=args.locale,
        project_name=args.project_name,
        dbms=args.dbms,
        neo4j_db=args.neo4j_db,
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Understanding 성능 비교 실행기")
    parser.add_argument("variant", choices=["original", "refactor"], help="사용할 Analyzer 버전")
    parser.add_argument("--user-id", default="KO_TestSession")
    parser.add_argument("--project-name", default="HOSPITAL_MANAGEMENT")
    parser.add_argument("--locale", default="ko")
    parser.add_argument("--dbms", default="postgres")
    parser.add_argument("--neo4j-db", default=None, help="Neo4j 데이터베이스명(옵션)")
    parser.add_argument("--file-pairs", help="분석 대상 (folder, file) JSON 경로")
    parser.add_argument("--clear-cache", action="store_true", help="LangChain 캐시 제거 후 실행")
    parser.add_argument("--reset-neo4j", action="store_true", help="실행 전 Neo4j 데이터 초기화")
    return parser


def main(argv: Iterable[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.api_key = os.getenv("LLM_API_KEY", "")

    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        print("사용자에 의해 중단되었습니다.")


if __name__ == "__main__":
    main()

