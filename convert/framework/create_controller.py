import logging
import textwrap
import json
from util.exception import ConvertingError
from util.utility_tool import save_file, build_rule_based_path, convert_to_camel_case, convert_to_pascal_case
from util.rule_loader import RuleLoader


# ----- 상수 정의 -----
CODE_PLACEHOLDER = "CodePlaceHolder"
SKIP_NODE_TYPE = "FUNCTION"


# ----- 컨트롤러 생성 클래스 -----
class ControllerGenerator:
    """
    컨트롤러 인터페이스 생성
    - 여러 프로시저의 메서드를 하나의 Controller로 통합
    - Generator 방식으로 통일
    """
    __slots__ = (
        'project_name', 'user_id', 'api_key', 'locale', 'rule_loader', 'save_path'
    )

    def __init__(self, project_name: str, user_id: str, api_key: str, locale: str = 'ko', target_lang: str = 'java'):
        """
        ControllerGenerator 초기화
        
        Args:
            project_name: 프로젝트 이름
            user_id: 사용자 식별자
            api_key: LLM API 키
            locale: 언어 설정
            target_lang: 타겟 언어
        """
        self.project_name = project_name
        self.user_id = user_id
        self.api_key = api_key
        self.locale = locale
        self.rule_loader = RuleLoader(target_lang=target_lang)
        self.save_path = build_rule_based_path(project_name, user_id, target_lang, 'controller')

    async def _generate_skeleton(self, controller_class_name: str, object_name: str, 
                                service_class_name: str, exist_command_class: bool) -> str:
        """
        Controller Skeleton (기본 틀) 생성
        
        Args:
            controller_class_name: Controller 클래스명
            object_name: 객체 이름
            service_class_name: Service 클래스명
            exist_command_class: Command 클래스 존재 여부
        
        Returns:
            str: Skeleton 코드
        """
        skeleton_data = self.rule_loader.execute(
            role_name='controller_skeleton',
            inputs={
                'controller_class_name': controller_class_name,
                'project_name': self.project_name,
                'object_name': object_name,
                'service_class_name': service_class_name,
                'exist_command_class': exist_command_class,
                'locale': self.locale
            },
            api_key=self.api_key
        )
        
        return skeleton_data.get('code', '')
    
    async def generate(self, object_name: str, service_class_name: str, exist_command_class: bool,
                      service_creation_info: list) -> tuple[str, str]:
        """
        Controller 클래스 생성 (Skeleton + 메서드)
        
        Args:
            object_name: 객체 이름
            service_class_name: Service 클래스 이름 (import용)
            exist_command_class: Command 클래스 존재 여부
            service_creation_info: Service 메서드 정보 리스트
        
        Returns:
            tuple: (controller_class_name, controller_code)
        """
        logging.info("\n" + "="*80)
        logging.info(f"🌐 STEP 4: Controller 생성 - {object_name}")
        logging.info("="*80)
        
        # Controller Skeleton 생성
        pascal_name = convert_to_pascal_case(object_name)
        camel_name = convert_to_camel_case(object_name)
        controller_class_name = f"{pascal_name}Controller"
        
        # Service 클래스명 (전달받거나 기본값)
        service_class_name = service_class_name or f"{pascal_name}Service"
        
        # Controller Skeleton 생성
        controller_skeleton = await self._generate_skeleton(
            controller_class_name, object_name, service_class_name, exist_command_class
        )
        
        # 각 프로시저별 메서드 생성
        controller_methods = []
        
        for svc in service_creation_info:
            method_sig = svc['method_signature']
            proc_name = svc['procedure_name']
            cmd_var = svc['command_class_variable']
            cmd_name = svc['command_class_name']
            node_type = svc['node_type']
            
            # FUNCTION 타입 스킵
            if node_type == SKIP_NODE_TYPE:
                logging.info(f"  ⏭️  {proc_name} FUNCTION 타입 스킵")
                continue
            
            logging.info(f"  📌 Controller 메서드: {proc_name}")
            
            # LLM으로 메서드 생성 (Rule 파일 사용)
            result = self.rule_loader.execute(
                role_name='controller',
                inputs={
                    'method_signature': method_sig,
                    'procedure_name': proc_name,
                    'command_class_variable': json.dumps(cmd_var, ensure_ascii=False, indent=2),
                    'command_class_name': cmd_name,
                    'controller_skeleton': controller_skeleton,
                    'locale': self.locale
                },
                api_key=self.api_key
            )
            
            controller_methods.append(result['method'])
            logging.info(f"  ✅ {proc_name} 메서드 생성 완료")
        
        # Controller 파일 조립 및 저장
        merged_methods = '\n\n'.join(controller_methods)
        completed = controller_skeleton.replace(
            'CodePlaceHolder',
            textwrap.indent(merged_methods.strip(), '    ')
        )
        
        await save_file(
            content=completed,
            filename=f"{controller_class_name}.java",
            base_path=self.save_path
        )
        
        logging.info(f"\n💾 Controller 파일 저장 완료: {controller_class_name}.java")
        logging.info(f"   경로: {self.save_path}")
        
        logging.info("\n" + "-"*80)
        logging.info(f"✅ STEP 4 완료: Controller 생성 완료")
        logging.info("-"*80 + "\n")
        
        return controller_class_name, completed


# ----- 진입점 함수 -----
def start_controller_skeleton_processing(
    object_name: str,
    exist_command_class: bool,
    project_name: str,
    service_class_name: str = None,
    target_lang: str = 'java'
) -> tuple[str, str]:
    """
    컨트롤러 스켈레톤 생성 시작 (호환성을 위한 함수)
    
    Args:
        object_name: 패키지/객체 이름
        exist_command_class: Command 클래스 존재 여부
        project_name: 프로젝트 이름
        service_class_name: Service 클래스 이름 (import용)
        target_lang: 타겟 언어
    
    Returns:
        tuple: (controller_skeleton, controller_class_name)
    
    Raises:
        ConvertingError: 생성 중 오류 발생 시
    """
    try:
        pascal_name = convert_to_pascal_case(object_name)
        camel_name = convert_to_camel_case(object_name)
        controller_class_name = f"{pascal_name}Controller"
        
        # Service 클래스명 (전달받거나 기본값)
        service_class_name = service_class_name or f"{pascal_name}Service"
        
        # Rule 파일 기반 스켈레톤 생성
        rule_loader = RuleLoader(target_lang=target_lang)
        controller_skeleton = rule_loader.render_prompt(
            'controller_skeleton',
            {
                'controller_class_name': controller_class_name,
                'project_name': project_name,
                'object_name': object_name,
                'service_class_name': service_class_name,
                'exist_command_class': exist_command_class,
                'locale': 'ko'
            }
        )
        
        logging.info(f"[{object_name}] 컨트롤러 스켈레톤 생성 완료\n")
        return controller_skeleton, controller_class_name

    except Exception as e:
        err_msg = f"컨트롤러 스켈레톤 생성 중 오류: {str(e)}"
        logging.error(err_msg)
        raise ConvertingError(err_msg)
