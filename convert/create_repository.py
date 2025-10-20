from collections import defaultdict
import logging
import textwrap
from prompt.convert_repository_prompt import convert_repository_code
from understand.neo4j_connection import Neo4jConnection
from util.exception import ConvertingError
from util.utility_tool import convert_to_camel_case, convert_to_pascal_case, save_file, build_java_base_path, build_variable_index, extract_used_variable_nodes


MAX_TOKENS = 2000  # LLM 처리를 위한 배치당 최대 토큰 수

# JPA Repository 인터페이스 템플릿
JPA_TEMPLATE = """package com.example.{project_name}.repository;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.data.rest.core.annotation.RepositoryRestResource;
import com.example.{project_name}.entity.{entity_pascal_name};
import java.time.*;

@RepositoryRestResource(collectionResourceRel = "{entity_camel_name}s", path = "{entity_camel_name}s")
public interface {entity_pascal_name}Repository extends JpaRepository<{entity_pascal_name}, Long> {{
{merged_methods}
}}"""


# ----- Repository 생성 관리 클래스 -----
class RepositoryGenerator:
    """
    레거시 SQL 쿼리(DML)를 분석하여 Spring Data JPA Repository 인터페이스를 자동 생성하는 클래스
    Neo4j에서 DML 노드(SELECT, INSERT, UPDATE, DELETE)와 변수 정보를 조회하고,
    LLM을 활용하여 JPA Repository 메서드로 변환합니다.
    """

    def __init__(self, project_name: str, user_id: str, api_key: str, locale: str = 'ko'):
        """
        RepositoryGenerator 초기화
        
        Args:
            project_name: 프로젝트 이름
            user_id: 사용자 식별자
            api_key: LLM API 키
            locale: 언어 설정 (기본값: 'ko')
        """
        self.project_name = project_name
        self.user_id = user_id
        self.api_key = api_key
        self.locale = locale
        self.save_path = build_java_base_path(project_name, user_id, 'repository')

    async def generate(self) -> tuple:
        """
        Repository 인터페이스 생성의 메인 진입점
        Neo4j에서 DML 노드와 변수 정보를 조회하고, 배치 단위로 LLM 변환을 수행하여
        JPA Repository 인터페이스 파일을 생성합니다.
        
        Returns:
            tuple: (used_query_methods, global_variables, sequence_methods, repository_list)
                - used_query_methods (dict): {라인범위: 메서드코드} 매핑
                - global_variables (list): 전역 변수 정보 리스트
                - sequence_methods (list): 시퀀스 관련 메서드 목록
                - repository_list (list): 생성된 Repository 정보 리스트
        """
        logging.info("Repository Interface 생성을 시작합니다.")
        connection = Neo4jConnection()
        
        try:
            # Neo4j에서 DML 노드 및 변수 정보 조회
            table_dml_results, var_results = await connection.execute_queries([
                f"""MATCH (n {{user_id: '{self.user_id}', project_name: '{self.project_name}'}})
                    WHERE n:SELECT OR n:UPDATE OR n:DELETE OR n:INSERT OR n:MERGE
                    AND NOT EXISTS {{ MATCH (p)-[:PARENT_OF]->(n) WHERE p:SELECT OR p:UPDATE OR p:DELETE OR p:INSERT OR p:MERGE }}
                    OPTIONAL MATCH (n)-[:FROM|WRITES]->(t:Table {{user_id: '{self.user_id}', project_name: '{self.project_name}'}})
                    WITH t, collect(n) as dml_nodes WHERE t IS NOT NULL
                    RETURN t, dml_nodes""",
                f"""MATCH (v:Variable {{user_id: '{self.user_id}', project_name: '{self.project_name}'}})
                    RETURN v, v.scope as scope"""
            ])

            # 변수를 Local/Global로 분리
            local_vars = []
            self.global_vars = []
            for var in var_results:
                if var['scope'] == 'Global':
                    v_node = var['v']
                    self.global_vars.append({
                        'name': v_node['name'],
                        'type': v_node.get('type', 'Unknown'),
                        'role': v_node.get('role', ''),
                        'scope': 'Global',
                        'value': v_node.get('value', '')
                    })
                else:
                    local_vars.append(var)
            
            # 변수 인덱스 생성
            self.var_index = build_variable_index(local_vars)
            
            # 결과 컨테이너 초기화
            self.all_used_query_methods = {}
            self.all_sequence_methods = set()
            self.aggregated_query_methods = {}

            # 모든 DML 노드를 한 번에 처리
            all_dml_nodes = [node for result in table_dml_results if (dml_nodes := result.get('dml_nodes')) for node in dml_nodes]
            if all_dml_nodes:
                await self._process_dml_nodes(all_dml_nodes)

            # Repository 파일 생성
            repository_list = await self._save_repository_files()
            
            logging.info("모든 Repository Interface 생성이 완료되었습니다.\n")
            return self.all_used_query_methods, self.global_vars, list(self.all_sequence_methods), repository_list

        except Exception as e:
            logging.error(f"Repository Interface 생성 중 오류: {str(e)}")
            raise ConvertingError(f"Repository Interface 생성 중 오류: {str(e)}")
        finally:
            await connection.close()

    # ----- 내부 처리 메서드 -----

    async def _process_dml_nodes(self, dml_nodes: list) -> None:
        """
        DML 노드를 배치 단위로 처리하여 Repository 메서드 생성
        결과는 클래스 속성에 직접 누적됩니다.
        
        Args:
            dml_nodes: 처리할 DML 노드 리스트
        """
        current_tokens = 0
        batch_codes = []
        batch_vars = defaultdict(list)

        for node in dml_nodes:
            # 필수 필드 체크
            if 'token' not in node or 'startLine' not in node:
                continue
            
            # DML 코드 추출
            code = node.get('summarized_code') or node.get('node_code', '')
            
            # 관련 변수 추출
            var_nodes, var_tokens = await extract_used_variable_nodes(node['startLine'], self.var_index)
            total = current_tokens + node['token'] + var_tokens

            # 배치 토큰 한도 초과 시 즉시 처리
            if batch_codes and total >= MAX_TOKENS:
                await self._flush_batch(batch_codes, batch_vars)
                batch_codes, batch_vars, current_tokens = [], defaultdict(list), 0

            # 배치에 추가
            batch_codes.append(code)
            for k, v in var_nodes.items():
                batch_vars[k].extend(v)
            current_tokens = total

        # 마지막 남은 배치 처리
        if batch_codes:
            await self._flush_batch(batch_codes, batch_vars)

    async def _flush_batch(self, codes: list, vars_dict: dict) -> None:
        """
        배치를 LLM으로 변환하고 결과를 클래스 속성에 즉시 누적
        
        Args:
            codes: DML 코드 리스트
            vars_dict: 변수 정보 딕셔너리
        """
        analysis_data = convert_repository_code(codes, vars_dict, len(codes), self.global_vars, self.api_key, self.locale)
        
        # 메서드를 Entity별로 그룹화하여 누적
        for method in analysis_data['analysis']:
            method_code = method['method']
            entity_name = convert_to_pascal_case(method['tableName'].split('.')[-1])
            
            self.aggregated_query_methods.setdefault(entity_name, []).append(method_code)
            
            # 라인 범위별 메서드 매핑
            for r in method['range']:
                self.all_used_query_methods[f"{r['startLine']}~{r['endLine']}"] = method_code
        
        # 시퀀스 메서드 누적
        if seq := analysis_data.get('seq_method'):
            self.all_sequence_methods.update(seq)

    async def _save_repository_files(self) -> list:
        """
        Entity별로 Repository 인터페이스 파일 생성
        
        Returns:
            list: 생성된 Repository 정보 리스트
        """
        if not self.aggregated_query_methods:
            return []
        
        results = []
        for entity_name, methods in self.aggregated_query_methods.items():
            camel_name = convert_to_camel_case(entity_name)
            repo_name = f"{entity_name}Repository"
            
            # 메서드 병합
            merged = '\n\n'.join(
                textwrap.indent(m.strip().replace('\n\n', '\n'), '    ') 
                for m in methods
            )
            
            # 템플릿 적용
            code = JPA_TEMPLATE.format(
                project_name=self.project_name,
                entity_pascal_name=entity_name,
                entity_camel_name=camel_name,
                merged_methods=merged
            )
            
            # 파일 저장 및 결과 누적
            await save_file(code, f"{repo_name}.java", self.save_path)
            results.append({"repositoryName": repo_name, "code": code})
        
        return results
