import logging
from util.exception import ConvertingError
from util.utility_tool import save_file, build_rule_based_path
from util.rule_loader import RuleLoader


# ----- Main 클래스 생성 관리 클래스 -----
class MainClassGenerator:
    """
    애플리케이션의 메인/진입점 클래스를 자동 생성하는 클래스
    타겟 언어에 맞게 Main 클래스를 생성합니다.
    - Java: Spring Boot Application 클래스
    - Python: FastAPI 앱 인스턴스 생성 파일
    """
    __slots__ = ('project_name', 'class_name', 'file_name', 'save_path', 'target_lang', 'rule_loader')

    def __init__(self, project_name: str, user_id: str, target_lang: str = 'java'):
        """
        MainClassGenerator 초기화
        
        Args:
            project_name: 프로젝트 이름
            user_id: 사용자 식별자
            target_lang: 타겟 언어 (java, python)
        """
        self.project_name = project_name
        self.target_lang = target_lang
        self.rule_loader = RuleLoader(target_lang=target_lang)
        
        if target_lang == 'java':
            self.class_name = f"{project_name.capitalize()}Application"
            self.file_name = f"{self.class_name}.java"
        else:  # python
            self.class_name = "main"
            self.file_name = "main.py"
        
        self.save_path = build_rule_based_path(project_name, user_id, target_lang, 'main')

    async def generate(self) -> str:
        """
        Main 클래스 생성의 메인 진입점
        타겟 언어에 맞는 Application 진입점 클래스를 생성하고 파일로 저장합니다.
        
        Returns:
            str: 생성된 메인 클래스 코드
        
        Raises:
            ConvertingError: 메인 클래스 생성 중 오류 발생 시
        """
        logging.info(f"[{self.target_lang.upper()}] 메인 클래스 생성을 시작합니다.")
        
        try:
            # Rule 파일에서 템플릿 로드 및 렌더링
            variables = {
                'project_name': self.project_name,
                'class_name': self.class_name
            }
            main_code = self.rule_loader.render_prompt('main', variables)
            
            # 파일 저장
            await save_file(main_code, self.file_name, self.save_path)
            
            logging.info(f"메인 클래스가 생성되었습니다.\n")
            return main_code
        
        except Exception as e:
            logging.error(f"메인 클래스 생성 중 오류: {str(e)}")
            raise ConvertingError(f"메인 클래스 생성 중 오류: {str(e)}")
