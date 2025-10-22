import logging
from util.exception import ConvertingError
from util.utility_tool import convert_to_camel_case, convert_to_pascal_case


# ----- 상수 정의 -----
CODE_PLACEHOLDER = "CodePlaceHolder"


# ----- 컨트롤러 스켈레톤 생성 클래스 -----
class ControllerSkeletonGenerator:
    """
    컨트롤러 클래스 기본 구조 생성
    - Spring Boot RestController 템플릿 생성
    - Command 클래스 존재 여부에 따른 import 처리
    """
    __slots__ = ('exist_command_class', 'project_name', 'controller_class_name', 'camel_name', 'pascal_name')

    def __init__(self, object_name: str, exist_command_class: bool, project_name: str):
        self.exist_command_class = exist_command_class
        self.project_name = project_name
        self.pascal_name = convert_to_pascal_case(object_name)
        self.camel_name = convert_to_camel_case(object_name)
        self.controller_class_name = f"{self.pascal_name}Controller"

    # ----- 공개 메서드 -----

    def generate(self) -> tuple[str, str]:
        """
        컨트롤러 스켈레톤 생성
        
        Returns:
            tuple: (controller_skeleton, controller_class_name)
        """
        # Command import (조건부)
        command_import = (
            f"import com.example.{self.project_name}.command.{self.camel_name}.*;\n"
            if self.exist_command_class else ""
        )

        # 컨트롤러 템플릿
        skeleton = f"""package com.example.{self.project_name}.controller;

{command_import}import com.example.{self.project_name}.service.{self.pascal_name}Service;
import org.springframework.web.bind.annotation.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.transaction.annotation.Transactional;
import java.util.*;

@RestController
@RequestMapping("/{self.camel_name}")
public class {self.controller_class_name} {{

    @Autowired
    private {self.pascal_name}Service {self.camel_name}Service;

{CODE_PLACEHOLDER}
}}"""

        return skeleton, self.controller_class_name


# ----- 진입점 함수 -----
def start_controller_skeleton_processing(
    object_name: str,
    exist_command_class: bool,
    project_name: str
) -> tuple[str, str]:
    """
    컨트롤러 스켈레톤 생성 시작
    
    Args:
        object_name: 패키지/객체 이름
        exist_command_class: Command 클래스 존재 여부
        project_name: 프로젝트 이름
    
    Returns:
        tuple: (controller_skeleton, controller_class_name)
    
    Raises:
        ConvertingError: 생성 중 오류 발생 시
    """
    try:
        generator = ControllerSkeletonGenerator(object_name, exist_command_class, project_name)
        skeleton, class_name = generator.generate()
        
        logging.info(f"[{object_name}] 컨트롤러 스켈레톤 생성 완료\n")
        return skeleton, class_name

    except Exception as e:
        err_msg = f"컨트롤러 스켈레톤 생성 중 오류: {str(e)}"
        logging.error(err_msg)
        raise ConvertingError(err_msg)
