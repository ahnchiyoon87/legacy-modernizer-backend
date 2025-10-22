import logging
from util.exception import ConvertingError
from util.utility_tool import save_file, build_java_base_path


# ----- Main 클래스 템플릿 -----
MAIN_TEMPLATE = """package com.example.{project_name};

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class {class_name} {{

    public static void main(String[] args) {{
        SpringApplication.run({class_name}.class, args);
    }}

}}
"""


# ----- Main 클래스 생성 관리 클래스 -----
class MainClassGenerator:
    """
    Spring Boot 애플리케이션의 메인 클래스를 자동 생성하는 클래스
    프로젝트명을 기반으로 Application 클래스를 생성합니다.
    """
    __slots__ = ('project_name', 'class_name', 'file_name', 'save_path')

    def __init__(self, project_name: str, user_id: str):
        """
        MainClassGenerator 초기화
        
        Args:
            project_name: 프로젝트 이름
            user_id: 사용자 식별자
        """
        self.project_name = project_name
        self.class_name = f"{project_name.capitalize()}Application"
        self.file_name = f"{self.class_name}.java"
        self.save_path = build_java_base_path(project_name, user_id)

    async def generate(self) -> str:
        """
        Main 클래스 생성의 메인 진입점
        Spring Boot Application 클래스를 생성하고 파일로 저장합니다.
        
        Returns:
            str: 생성된 메인 클래스 코드
        
        Raises:
            ConvertingError: 메인 클래스 생성 중 오류 발생 시
        """
        logging.info("메인 클래스 생성을 시작합니다.")
        
        try:
            # 템플릿 적용
            main_code = MAIN_TEMPLATE.format(project_name=self.project_name, class_name=self.class_name)
            
            # 파일 저장
            await save_file(main_code, self.file_name, self.save_path)
            
            logging.info("메인 클래스가 생성되었습니다.\n")
            return main_code
        
        except Exception as e:
            logging.error(f"메인 클래스 생성 중 오류: {str(e)}")
            raise ConvertingError(f"메인 클래스 생성 중 오류: {str(e)}")
