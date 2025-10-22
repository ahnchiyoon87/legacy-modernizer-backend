import logging
import textwrap
from prompt.convert_controller_prompt import convert_controller_method_code
from util.exception import ConvertingError, GenerateTargetError
from util.utility_tool import save_file, build_java_base_path


# ----- 상수 정의 -----
CODE_PLACEHOLDER = "CodePlaceHolder"
SKIP_NODE_TYPE = "FUNCTION"


# ----- 컨트롤러 매니저 (싱글톤 패턴) -----
class ControllerManager:
    """
    컨트롤러 메서드 누적 및 파일 저장 관리
    - 여러 프로시저의 메서드를 하나의 Controller 파일에 병합
    """
    _instances = {}  # {(user_id, object_name): ControllerManager}
    
    def __init__(self, controller_skeleton: str, controller_class_name: str, 
                 user_id: str, project_name: str):
        self.controller_skeleton = controller_skeleton
        self.controller_class_name = controller_class_name
        self.user_id = user_id
        self.project_name = project_name
        self.methods = []  # 메서드 누적
    
    @classmethod
    def get_instance(cls, object_name: str, controller_skeleton: str, controller_class_name: str,
                     user_id: str, project_name: str):
        """싱글톤 인스턴스 가져오기"""
        key = (user_id, object_name)
        if key not in cls._instances:
            cls._instances[key] = cls(controller_skeleton, controller_class_name, user_id, project_name)
        return cls._instances[key]
    
    @classmethod
    def clear_instance(cls, user_id: str, object_name: str):
        """인스턴스 초기화 (파일 처리 후)"""
        key = (user_id, object_name)
        if key in cls._instances:
            del cls._instances[key]
    
    def add_method(self, method_code: str):
        """메서드 추가"""
        if method_code and method_code.strip():
            self.methods.append(method_code)
    
    async def save_controller_file(self):
        """누적된 메서드를 Controller 파일로 저장"""
        try:
            merged_methods = '\n\n'.join(self.methods)
            completed = self.controller_skeleton.replace(
                CODE_PLACEHOLDER,
                textwrap.indent(merged_methods.strip(), '    ')
            )
            
            await save_file(
                content=completed,
                filename=f"{self.controller_class_name}.java",
                base_path=build_java_base_path(self.project_name, self.user_id, 'controller')
            )
            
            logging.info(f"\n💾 Controller 파일 저장 완료: {self.controller_class_name}.java")
            logging.info(f"   경로: {build_java_base_path(self.project_name, self.user_id, 'controller')}")
            
        except Exception as e:
            logging.error(f"❌ 컨트롤러 파일 저장 실패: {str(e)}")
            raise GenerateTargetError(f"컨트롤러 파일 저장 중 오류: {str(e)}")


# ----- 컨트롤러 생성 클래스 -----
class ControllerGenerator:
    """
    컨트롤러 메서드 생성
    - LLM을 통한 컨트롤러 메서드 생성
    - FUNCTION 타입 스킵
    """
    __slots__ = (
        'method_signature', 'procedure_name', 'object_name', 'command_class_variable',
        'command_class_name', 'node_type', 'merge_method_code', 'api_key', 'locale'
    )

    def __init__(self, method_signature: str, procedure_name: str, object_name: str,
                 command_class_variable: str, command_class_name: str,
                 node_type: str, merge_method_code: str, api_key: str, locale: str):
        self.method_signature = method_signature
        self.procedure_name = procedure_name
        self.object_name = object_name
        self.command_class_variable = command_class_variable
        self.command_class_name = command_class_name
        self.node_type = node_type
        self.merge_method_code = merge_method_code
        self.api_key = api_key
        self.locale = locale

    # ----- 공개 메서드 -----

    def generate(self, controller_skeleton: str) -> str:
        """
        컨트롤러 메서드 생성
        
        Args:
            controller_skeleton: 컨트롤러 템플릿 (LLM 프롬프트용)
        
        Returns:
            str: 병합된 컨트롤러 메서드 코드
        """
        # FUNCTION 타입 스킵
        if self.node_type == SKIP_NODE_TYPE:
            logging.info(f"[{self.object_name}] {self.procedure_name} FUNCTION 타입 스킵\n")
            return self.merge_method_code

        logging.info(f"  📌 Controller 메서드: {self.procedure_name}")

        # LLM으로 메서드 생성 및 병합
        result = convert_controller_method_code(
            self.method_signature,
            self.procedure_name,
            self.command_class_variable,
            self.command_class_name,
            controller_skeleton,
            self.api_key,
            self.locale
        )

        merged = f"{self.merge_method_code}\n\n{result['method']}"

        logging.info(f"  ✅ {self.procedure_name} 메서드 생성 완료")
        return merged


# ----- 컨트롤러 파일 저장 -----
async def generate_controller_class(
    controller_skeleton: str,
    controller_class_name: str,
    merge_controller_method_code: str,
    user_id: str,
    project_name: str
) -> str:
    """
    컨트롤러 클래스 파일 생성
    
    Args:
        controller_skeleton: 컨트롤러 클래스 템플릿
        controller_class_name: 클래스 이름
        merge_controller_method_code: 메서드 코드
        user_id: 사용자 ID
        project_name: 프로젝트 이름
    
    Returns:
        str: 생성된 컨트롤러 코드
    
    Raises:
        GenerateTargetError: 파일 생성 중 오류
    """
    try:
        # 코드 완성
        completed = controller_skeleton.replace(
            CODE_PLACEHOLDER,
            textwrap.indent(merge_controller_method_code.strip(), '    ')
        )

        # 파일 저장
        await save_file(
            content=completed,
            filename=f"{controller_class_name}.java",
            base_path=build_java_base_path(project_name, user_id, 'controller')
        )

        logging.info(f"[{controller_class_name}] 컨트롤러 파일 생성 완료\n")
        return completed

    except Exception as e:
        err_msg = f"컨트롤러 파일 생성 중 오류: {str(e)}"
        logging.error(err_msg)
        raise GenerateTargetError(err_msg)


# ----- 진입점 함수 -----
def start_controller_processing(
    method_signature: str,
    procedure_name: str,
    command_class_variable: str,
    command_class_name: str,
    node_type: str,
    controller_skeleton: str,
    controller_class_name: str,
    object_name: str,
    user_id: str,
    project_name: str,
    api_key: str,
    locale: str
):
    """
    컨트롤러 메서드 생성 및 매니저에 추가
    
    Args:
        method_signature: 서비스 메서드 시그니처
        procedure_name: 프로시저 이름
        command_class_variable: Command 필드 목록
        command_class_name: Command 클래스 이름
        node_type: 노드 타입
        controller_skeleton: 컨트롤러 템플릿
        controller_class_name: Controller 클래스 이름
        object_name: 객체 이름
        user_id: 사용자 ID
        project_name: 프로젝트 이름
        api_key: LLM API 키
        locale: 로케일
    
    Returns:
        None (매니저에 메서드 추가)
    
    Raises:
        ConvertingError: 생성 중 오류 발생 시
    """
    try:
        # 매니저 인스턴스 가져오기
        manager = ControllerManager.get_instance(
            object_name, controller_skeleton, controller_class_name,
            user_id, project_name
        )
        
        # FUNCTION 타입은 스킵
        if node_type == SKIP_NODE_TYPE:
            logging.info(f"  ⏭️  {procedure_name} FUNCTION 타입 스킵")
            return
        
        logging.info(f"  📌 Controller 메서드: {procedure_name}")
        
        # LLM으로 메서드 생성
        result = convert_controller_method_code(
            method_signature,
            procedure_name,
            command_class_variable,
            command_class_name,
            controller_skeleton,
            api_key,
            locale
        )
        
        # 매니저에 메서드 추가
        manager.add_method(result['method'])
        
        logging.info(f"  ✅ {procedure_name} 메서드 생성 완료")

    except ConvertingError:
        raise
    except Exception as e:
        err_msg = f"컨트롤러 메서드 생성 중 오류: {str(e)}"
        logging.error(err_msg)
        raise ConvertingError(err_msg)


# ----- 컨트롤러 파일 저장 함수 -----
async def finalize_controller(user_id: str, object_name: str):
    """
    컨트롤러 파일 최종 저장 및 인스턴스 정리
    
    Args:
        user_id: 사용자 ID
        object_name: 객체 이름
    
    Raises:
        ConvertingError: 저장 중 오류 발생 시
    """
    try:
        logging.info("\n" + "="*80)
        logging.info(f"🎯 STEP 5: Controller 파일 저장 - {object_name}")
        logging.info("="*80)
        
        key = (user_id, object_name)
        if key in ControllerManager._instances:
            manager = ControllerManager._instances[key]
            await manager.save_controller_file()
            ControllerManager.clear_instance(user_id, object_name)
            
            logging.info("\n" + "-"*80)
            logging.info(f"✅ STEP 5 완료: Controller 저장 완료")
            logging.info("-"*80 + "\n")
        else:
            logging.warning(f"⚠️ Controller 매니저 인스턴스를 찾을 수 없습니다: {object_name}")
    
    except Exception as e:
        err_msg = f"컨트롤러 파일 저장 중 오류: {str(e)}"
        logging.error(err_msg)
        raise ConvertingError(err_msg)
