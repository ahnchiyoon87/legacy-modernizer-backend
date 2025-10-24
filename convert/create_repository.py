from collections import defaultdict
import logging
import textwrap
import json
from understand.neo4j_connection import Neo4jConnection
from util.exception import ConvertingError
from util.utility_tool import convert_to_camel_case, convert_to_pascal_case, save_file, build_rule_based_path, build_variable_index, extract_used_variable_nodes
from util.rule_loader import RuleLoader


MAX_TOKENS = 1000  # LLM 처리를 위한 배치당 최대 토큰 수


# ----- Repository 생성 관리 클래스 -----
class RepositoryGenerator:
    """
    레거시 SQL 쿼리(DML)를 분석하여 Spring Data JPA Repository 인터페이스를 자동 생성하는 클래스
    1단계: Repository Skeleton (기본 틀) 생성
    2단계: DML을 배치 단위로 처리하여 JPA 메서드 생성
    3단계: Skeleton과 메서드 병합
    """
    __slots__ = ('project_name', 'user_id', 'api_key', 'locale', 'save_path', 
                 'global_vars', 'var_index', 'all_used_query_methods', 
                 'all_sequence_methods', 'aggregated_query_methods', 'rule_loader')

    def __init__(self, project_name: str, user_id: str, api_key: str, locale: str = 'ko', target_lang: str = 'java'):
        """
        RepositoryGenerator 초기화
        
        Args:
            project_name: 프로젝트 이름
            user_id: 사용자 식별자
            api_key: LLM API 키
            locale: 언어 설정 (기본값: 'ko')
            target_lang: 타겟 언어 (기본값: 'java')
        """
        self.project_name = project_name
        self.user_id = user_id
        self.api_key = api_key
        self.locale = locale
        self.rule_loader = RuleLoader(target_lang=target_lang)
        self.save_path = build_rule_based_path(project_name, user_id, target_lang, 'repository')

    async def generate(self) -> tuple:
        """
        Repository 인터페이스 생성의 메인 진입점
        1. Skeleton 생성 (테이블당 1회)
        2. DML을 배치 단위로 처리하여 메서드 생성
        3. Skeleton과 메서드 병합
        
        Returns:
            tuple: (used_query_methods, global_variables, sequence_methods, repository_list)
        """
        logging.info("Repository Interface 생성을 시작합니다.")
        connection = Neo4jConnection()
        
        logging.info("\n" + "="*80)
        logging.info("🗄️  STEP 2: Repository Interface 생성 시작")
        logging.info("="*80)
        
        try:
            # Neo4j에서 DML 노드 및 변수 정보 조회
            logging.info("📊 Neo4j에서 DML 노드 및 변수 조회 중...")
            table_dml_results, var_results = await connection.execute_queries([
                f"""MATCH (n {{user_id: '{self.user_id}', project_name: '{self.project_name}'}})
                    WHERE n:SELECT OR n:UPDATE OR n:DELETE OR n:MERGE
                    AND NOT EXISTS {{ MATCH (p)-[:PARENT_OF]->(n) WHERE p:SELECT OR p:UPDATE OR p:DELETE OR p:MERGE }}
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

            # Repository 파일 생성
            logging.info(f"💾 Repository 파일 생성 중...")
            repository_list = await self._generate_repositories(table_dml_results)
            
            logging.info("\n" + "-"*80)
            logging.info(f"✅ STEP 2 완료: {len(repository_list)}개 Repository 생성 완료")
            logging.info(f"   - JPA 쿼리 메서드: {len(self.all_used_query_methods)}개")
            logging.info(f"   - 시퀀스 메서드: {len(self.all_sequence_methods)}개")
            logging.info("-"*80 + "\n")
            return self.all_used_query_methods, self.global_vars, list(self.all_sequence_methods), repository_list

        except Exception as e:
            logging.error(f"Repository Interface 생성 중 오류: {str(e)}")
            raise ConvertingError(f"Repository Interface 생성 중 오류: {str(e)}")
        finally:
            await connection.close()

    # ----- 내부 처리 메서드 -----

    async def _generate_repositories(self, table_dml_results: list) -> list:
        """
        테이블별로 Repository 생성
        1. Skeleton 생성
        2. DML을 배치 단위로 처리하여 메서드 생성
        3. 병합
        
        Args:
            table_dml_results: 테이블별 DML 노드 결과
        
        Returns:
            list: 생성된 Repository 정보 리스트
        """
        results = []
        
        for result in table_dml_results:
            if not (dml_nodes := result.get('dml_nodes')):
                continue
            
            table_node = result['t']
            table_name = table_node['name']
            entity_name = convert_to_pascal_case(table_name)
            camel_name = convert_to_camel_case(entity_name)
            repo_name = f"{entity_name}Repository"
            
            try:
                logging.info(f"   📝 {repo_name} 생성 중...")
                
                # 1단계: Skeleton 생성
                skeleton = await self._generate_skeleton(entity_name, camel_name, table_name)
                
                # 2단계: DML을 배치 단위로 처리하여 메서드 생성
                await self._process_dml_nodes_for_entity(entity_name, dml_nodes)
                
                # 3단계: Skeleton과 메서드 병합
                merged_methods = self.aggregated_query_methods.get(entity_name, [])
                if merged_methods:
                    methods_code = '\n\n'.join(
                        textwrap.indent(m.strip(), '    ') for m in merged_methods
                    )
                    # Skeleton의 CodePlaceHolder를 메서드로 치환
                    code = skeleton.replace('CodePlaceHolder', methods_code)
                else:
                    code = skeleton
                
                # 파일 저장
                await save_file(code, f"{repo_name}.java", self.save_path)
                results.append({"repositoryName": repo_name, "code": code})
                logging.info(f"   ✓ {repo_name} 생성 완료")
                
            except Exception as e:
                logging.error(f"Entity '{entity_name}' Repository 생성 중 오류: {str(e)}")
                continue
        
        return results

    async def _generate_skeleton(self, entity_name: str, camel_name: str, table_name: str) -> str:
        """
        Repository Skeleton (기본 틀) 생성
        
        Args:
            entity_name: Entity 클래스명
            camel_name: Entity camelCase명
            table_name: 원본 테이블명
        
        Returns:
            str: Skeleton 코드
        """
        skeleton_data = self.rule_loader.execute(
            role_name='repository_skeleton',
            inputs={
                'entity_name': entity_name,
                'entity_camel_name': camel_name,
                'table_name': table_name,
                'project_name': self.project_name,
                'locale': self.locale
            },
            api_key=self.api_key
        )
        
        return skeleton_data.get('code', '')

    async def _process_dml_nodes_for_entity(self, entity_name: str, dml_nodes: list) -> None:
        """
        Entity의 DML 노드를 배치 단위로 처리
        
        Args:
            entity_name: Entity 클래스명
            dml_nodes: DML 노드 리스트
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
                await self._flush_batch(entity_name, batch_codes, batch_vars)
                batch_codes, batch_vars, current_tokens = [], defaultdict(list), 0

            # 배치에 추가
            batch_codes.append(code)
            for k, v in var_nodes.items():
                batch_vars[k].extend(v)
            current_tokens = total

        # 마지막 남은 배치 처리
        if batch_codes:
            await self._flush_batch(entity_name, batch_codes, batch_vars)

    async def _flush_batch(self, entity_name: str, codes: list, vars_dict: dict) -> None:
        """
        배치를 LLM으로 변환하고 결과를 클래스 속성에 즉시 누적
        
        Args:
            entity_name: Entity 클래스명
            codes: DML 코드 리스트
            vars_dict: 변수 정보 딕셔너리
        """
        # Role 파일 기반 프롬프트 실행
        analysis_data = self.rule_loader.execute(
            role_name='repository',
            inputs={
                'entity_name': entity_name,
                'repository_nodes': json.dumps(codes, ensure_ascii=False, indent=2),
                'used_variable_nodes': json.dumps(vars_dict, ensure_ascii=False, indent=2),
                'count': len(codes),
                'global_variable_nodes': json.dumps(self.global_vars, ensure_ascii=False, indent=2),
                'locale': self.locale
            },
            api_key=self.api_key
        )
        
        # 메서드를 Entity별로 그룹화하여 누적
        for method in analysis_data.get('analysis', []):
            method_code = method['method']
            
            self.aggregated_query_methods.setdefault(entity_name, []).append(method_code)
            
            # 라인 범위별 메서드 매핑
            for r in method.get('range', []):
                self.all_used_query_methods[f"{r['startLine']}~{r['endLine']}"] = method_code
        
        # 시퀀스 메서드 누적
        if seq := analysis_data.get('seq_method'):
            self.all_sequence_methods.update(seq)
