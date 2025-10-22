import logging
import os
import warnings
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase
from util.exception import Neo4jError

# Neo4j notification warnings 무시
warnings.filterwarnings('ignore', category=DeprecationWarning, module='neo4j')
warnings.filterwarnings('ignore', message='.*Received notification from DBMS server.*')

# Neo4j 로거 레벨 조정 (notification 경고 숨기기)
logging.getLogger('neo4j.notifications').setLevel(logging.ERROR)

# 환경변수 미리 로드 (모듈 레벨에서 한번만)
load_dotenv()

class Neo4jConnection:
    """Neo4j 비동기 연결 관리 및 쿼리 실행"""

    __slots__ = ('_Neo4jConnection__driver',)
    
    # 클래스 상수
    DATABASE_NAME = "neo4j"
    DEFAULT_URI = "bolt://localhost:7687"
    DEFAULT_USER = "neo4j"
    DEFAULT_PASSWORD = "neo4j"

    def __init__(self):
        """환경변수에서 연결 정보를 읽어 드라이버 초기화"""
        uri = os.getenv("NEO4J_URI", self.DEFAULT_URI)
        user = os.getenv("NEO4J_USER", self.DEFAULT_USER)
        password = os.getenv("NEO4J_PASSWORD", self.DEFAULT_PASSWORD)
        self.__driver = AsyncGraphDatabase.driver(uri, auth=(user, password))

    async def close(self):
        """데이터베이스 연결 종료"""
        await self.__driver.close()



    async def execute_queries(self, queries: list) -> list:
        """사이퍼 쿼리를 순차 실행하고 결과 반환 (최적화: 리스트 컴프리헨션 불가, await 필요)"""
        try:
            results = []
            async with self.__driver.session(database=self.DATABASE_NAME) as session:
                for query in queries:
                    query_result = await session.run(query)
                    results.append(await query_result.data())
            return results
        except Exception as e:
            error_msg = f"Cypher Query를 실행하여, 노드 및 관계를 생성하는 도중 오류가 발생: {str(e)}"
            logging.exception(error_msg)
            raise Neo4jError(error_msg)
    
    
    # 클래스 상수로 쿼리 캐싱
    _DEFAULT_GRAPH_QUERY = """
        UNWIND $pairs as target
        MATCH (n)-[r]->(m)
        WHERE NOT n:Variable AND NOT n:PACKAGE_VARIABLE
          AND NOT m:Variable AND NOT m:PACKAGE_VARIABLE
          AND n.user_id = $user_id AND m.user_id = $user_id
          AND ((n:Table OR (n.folder_name = target.folder_name AND n.file_name = target.file_name))
               AND (m:Table OR (m.folder_name = target.folder_name AND m.file_name = target.file_name)))
        RETURN DISTINCT n, r, m
    """

    async def execute_query_and_return_graph(self, user_id: str, file_names: list, custom_query: str | None = None) -> dict:
        """노드/관계를 조회하여 그래프 딕셔너리로 반환 (최적화: 병렬 처리)"""
        try:
            pairs = [{"folder_name": f, "file_name": s} for f, s in file_names]
            params = {"user_id": user_id, "pairs": pairs}

            async with self.__driver.session(database=self.DATABASE_NAME) as session:
                result = await session.run(custom_query or self._DEFAULT_GRAPH_QUERY, params)
                graph = await result.graph()

                # 딕셔너리 키 상수화 (반복 생성 방지)
                return {
                    "Nodes": [
                        {
                            "Node ID": node.element_id,
                            "Labels": list(node.labels),
                            "Properties": dict(node),
                        }
                        for node in graph.nodes
                    ],
                    "Relationships": [
                        {
                            "Relationship ID": rel.element_id,
                            "Type": rel.type,
                            "Properties": dict(rel),
                            "Start Node ID": rel.start_node.element_id,
                            "End Node ID": rel.end_node.element_id,
                        }
                        for rel in graph.relationships
                    ]
                }
            
        except Exception as e:
            error_msg = f"Neo4J에서 그래프 객체 형태로 결과를 반환하는 도중 문제가 발생: {str(e)}"
            logging.exception(error_msg)
            raise Neo4jError(error_msg)
        

    # 클래스 상수로 쿼리 캐싱
    _NODE_EXISTS_QUERY = """
        UNWIND $pairs as target
        MATCH (n)
        WHERE n.user_id = $user_id
          AND n.folder_name = target.folder_name
          AND n.file_name = target.file_name
        RETURN COUNT(n) > 0 AS exists
    """

    async def node_exists(self, user_id: str, file_names: list) -> bool:
        """노드 존재 여부 확인 (최적화: 쿼리 캐싱)"""
        try:
            pairs = [{"folder_name": f, "file_name": s} for f, s in file_names]
            params = {"pairs": pairs, "user_id": user_id}

            async with self.__driver.session(database=self.DATABASE_NAME) as session:
                result = await session.run(self._NODE_EXISTS_QUERY, params)
                return (await result.single())["exists"]
            
        except Exception as e:
            error_msg = f"노드 존재 여부 확인 중 오류 발생: {str(e)}"
            logging.exception(error_msg)
            raise Neo4jError(error_msg)