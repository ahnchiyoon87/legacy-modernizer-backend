"""
설정 파일 생성 모듈
- Rule 파일 기반 다중 언어 지원
- 성능 최적화 (캐싱, 슬롯)
- 메모리 효율성 (지연 로딩)
- 가독성 (명확한 구조)
"""

import os
import logging
from typing import Dict, List, Any, Tuple
from util.exception import ConvertingError
from util.utility_tool import save_file, build_rule_based_path
from util.rule_loader import RuleLoader


class ConfigFilesGenerator:
    """
    Rule 파일 기반 설정 파일 생성기
    
    특징:
    - 다중 언어 지원 (java, python, typescript 등)
    - 다중 설정 파일 지원 (pom.xml, .env, requirements.txt 등)
    - 성능 최적화 (캐싱, 슬롯)
    - 메모리 효율성 (지연 로딩)
    """
    
    __slots__ = (
        'project_name', 'user_id', 'target_lang', 'rule_loader', 
        'base_path', '_config_cache'
    )
    
    def __init__(self, project_name: str, user_id: str, target_lang: str = 'java'):
        """
        ConfigFilesGenerator 초기화
        
        Args:
            project_name: 프로젝트 이름
            user_id: 사용자 식별자
            target_lang: 타겟 언어 (java, python, typescript 등)
        """
        self.project_name = project_name
        self.user_id = user_id
        self.target_lang = target_lang
        self.rule_loader = RuleLoader(target_lang=target_lang)
        
        # 경로 설정 (Rule 파일 기반)
        self.base_path = build_rule_based_path(project_name, user_id, target_lang, 'config')
        
        # 캐시 초기화 (지연 로딩)
        self._config_cache = None
    
    def _load_config_rule(self) -> Dict[str, Any]:
        """
        Rule 파일에서 설정 정보 로드 (캐싱)
        
        Returns:
            Dict: 설정 파일 정보
        """
        if self._config_cache is None:
            try:
                self._config_cache = self.rule_loader._load_role_file('config')
            except FileNotFoundError:
                raise ConvertingError(f"설정 파일 Rule을 찾을 수 없습니다: rules/{self.target_lang}/config.yaml")
            except Exception as e:
                raise ConvertingError(f"설정 파일 Rule 로드 실패: {str(e)}")
        
        return self._config_cache
    
    def _build_file_path(self, file_info: Dict[str, str]) -> str:
        """
        파일 저장 경로 생성 (Rule 파일 기반)
        
        Args:
            file_info: 파일 정보 (filename, path)
            
        Returns:
            str: 전체 파일 경로
        """
        relative_path = file_info.get('path', '.')
        return os.path.join(self.base_path, relative_path)
    
    def _get_default_variables(self) -> Dict[str, str]:
        """
        언어별 기본 변수 설정
        
        Returns:
            Dict: 기본 변수값
        """
        defaults = {
            'project_name': self.project_name,
            'db_username': 'user',
            'db_password': 'password'
        }
        
        # 언어별 기본값 설정
        if self.target_lang == 'java':
            defaults.update({
                'db_driver': 'oracle.jdbc.driver.OracleDriver',
                'db_url': 'jdbc:oracle:thin:@localhost:1521:xe',
                'db_username': 'system'
            })
        elif self.target_lang == 'python':
            defaults.update({
                'db_driver': 'postgresql',
                'db_url': 'postgresql://localhost:5432/dbname',
                'db_username': 'postgres'
            })
        
        return defaults
    
    def _render_template(self, file_info: Dict[str, str], variables: Dict[str, str]) -> str:
        """
        Jinja2 템플릿 렌더링
        
        Args:
            file_info: 파일 정보
            variables: 변수값
            
        Returns:
            str: 렌더링된 템플릿
        """
        try:
            from jinja2 import Template
            
            template_content = file_info['template']
            template = Template(template_content)
            return template.render(**variables)
            
        except Exception as e:
            raise ConvertingError(f"템플릿 렌더링 실패 ({file_info['filename']}): {str(e)}")
    
    async def _save_config_file(self, file_info: Dict[str, str], content: str) -> None:
        """
        설정 파일 저장
        
        Args:
            file_info: 파일 정보
            content: 파일 내용
        """
        try:
            file_path = self._build_file_path(file_info)
            filename = file_info['filename']
            
            await save_file(content, filename, file_path)
            logging.info(f"설정 파일 생성 완료: {filename}")
            
        except Exception as e:
            raise ConvertingError(f"설정 파일 저장 실패 ({file_info['filename']}): {str(e)}")
    
    async def generate(self) -> Dict[str, str]:
        """
        설정 파일 생성 메인 진입점
        
        Returns:
            Dict[str, str]: 생성된 파일명과 내용의 매핑
            
        Raises:
            ConvertingError: 설정 파일 생성 중 오류 발생 시
        """
        logging.info(f"{self.target_lang} 설정 파일 생성을 시작합니다.")
        
        try:
            # Rule 파일에서 설정 정보 로드
            config_rule = self._load_config_rule()
            config_files = config_rule.get('config_files', [])
            
            if not config_files:
                raise ConvertingError(f"설정 파일 정보가 없습니다: rules/{self.target_lang}/config.yaml")
            
            # 기본 변수 설정
            variables = self._get_default_variables()
            
            # 결과 저장용
            results = {}
            
            # 각 설정 파일 생성
            for file_info in config_files:
                try:
                    # 템플릿 렌더링
                    content = self._render_template(file_info, variables)
                    
                    # 파일 저장
                    await self._save_config_file(file_info, content)
                    
                    # 결과 저장
                    results[file_info['filename']] = content
                    
                except Exception as e:
                    logging.error(f"설정 파일 생성 실패 ({file_info.get('filename', 'unknown')}): {str(e)}")
                    raise ConvertingError(f"설정 파일 생성 실패: {str(e)}")
            
            logging.info(f"{self.target_lang} 설정 파일 생성이 완료되었습니다. ({len(results)}개 파일)")
            return results
            
        except ConvertingError:
            raise
        except Exception as e:
            logging.error(f"설정 파일 생성 중 예상치 못한 오류: {str(e)}")
            raise ConvertingError(f"설정 파일 생성 중 오류: {str(e)}")
    
    def get_supported_languages(self) -> List[str]:
        """
        지원되는 언어 목록 반환
        
        Returns:
            List[str]: 지원되는 언어 목록
        """
        return ['java', 'python', 'typescript', 'go', 'csharp']
    
    def get_config_files_info(self) -> Dict[str, List[str]]:
        """
        언어별 설정 파일 정보 반환
        
        Returns:
            Dict[str, List[str]]: 언어별 설정 파일 목록
        """
        return {
            'java': ['pom.xml', 'application.properties'],
            'python': ['.env', 'requirements.txt', 'config.py'],
            'typescript': ['package.json', '.env', 'tsconfig.json'],
            'go': ['go.mod', 'go.sum', '.env'],
            'csharp': ['*.csproj', 'appsettings.json']
        }


# ----- 편의 함수 -----

async def create_config_files(project_name: str, user_id: str, target_lang: str = 'java') -> Dict[str, str]:
    """
    설정 파일 생성 편의 함수
    
    Args:
        project_name: 프로젝트 이름
        user_id: 사용자 식별자
        target_lang: 타겟 언어
        
    Returns:
        Dict[str, str]: 생성된 파일명과 내용의 매핑
    """
    generator = ConfigFilesGenerator(project_name, user_id, target_lang)
    return await generator.generate()


# ----- 메인 실행 (테스트용) -----
if __name__ == "__main__":
    import asyncio
    
    async def test():
        # Java 설정 파일 생성 테스트
        java_results = await create_config_files("test-project", "user123", "java")
        print("Java 설정 파일:", list(java_results.keys()))
        
        # Python 설정 파일 생성 테스트
        python_results = await create_config_files("test-project", "user123", "python")
        print("Python 설정 파일:", list(python_results.keys()))
    
    asyncio.run(test())