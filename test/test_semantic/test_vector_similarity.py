import unittest
import sys
import os
import logging
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from understand.neo4j_connection import Neo4jConnection
from semantic.vectorizer import vectorize_text

logging.basicConfig(level=logging.INFO)

class TestVectorSimilarity(unittest.IsolatedAsyncioTestCase):

    async def test_find_similar_nodes(self):
        
        conn = Neo4jConnection()
        
        try:
            # 테스트할 검색 텍스트
            search_text = "TpxSalaryService 클래스에서 calculateDeduction 메서드를 찾을 수 없습니다. 116번 라인에서 calculateDeduction(String, Long) 메서드를 호출하고 있으나, 이 메서드가 클래스 내에 정의되어 있지 않습니다. 실제 정의된 메서드명과 일치하도록 메서드 호출부를 수정해야 합니다. TpxSalaryService 클래스에서 급여 공제액을 계산하는 메서드의 실제 이름을 확인하여 호출부를 수정하세요."
            
            # 검색 텍스트를 벡터화
            search_vector = vectorize_text(search_text)
            
            # Neo4j 쿼리 실행
            nodes = await conn.search_similar_nodes(
                search_vector=search_vector,
                similarity_threshold=0.5,
                limit=10
            )

            # 결과 출력 및 검증
            print("\n=== 유사도 검색 결과 ===")
            print(f"검색어: {search_text}\n")
            
            for node in nodes:
                print(f"유사도: {node['similarity']:.4f}")
                print(f"노드 이름: {node['name']}")
                print(f"요약: {node['summary']}\n")
                print(f"자바 파일 내용: {node['java_code']}\n")

            self.assertTrue(len(nodes) > 0, "검색 결과가 없습니다")
        
        finally:
            await conn.close()

if __name__ == '__main__':
    unittest.main()