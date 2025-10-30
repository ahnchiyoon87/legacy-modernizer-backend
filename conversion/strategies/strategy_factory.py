from .base_strategy import ConversionStrategy
from .framework_strategy import FrameworkConversionStrategy
from .dbms_strategy import DbmsConversionStrategy


class StrategyFactory:
    """전략 패턴 팩토리 클래스"""
    
    @staticmethod
    def create_strategy(conversion_type: str, **kwargs) -> ConversionStrategy:
        """
        변환 타입에 따라 적절한 전략을 생성합니다.
        
        Args:
            conversion_type: 변환 타입 ("framework" 또는 "dbms")
            **kwargs: 전략 생성에 필요한 추가 매개변수
            
        Returns:
            ConversionStrategy: 생성된 전략 인스턴스
            
        Raises:
            ValueError: 지원하지 않는 변환 타입인 경우
        """
        conversion_type = conversion_type.lower()
        
        if conversion_type == "framework":
            target_framework = kwargs.get('target_framework', 'springboot')
            return FrameworkConversionStrategy(target_framework)
            
        elif conversion_type == "dbms":
            source_dbms = kwargs.get('source_dbms', 'postgres')
            target_dbms = kwargs.get('target_dbms', 'oracle')
            return DbmsConversionStrategy(source_dbms, target_dbms)
            
        else:
            raise ValueError(f"Unsupported conversion type: {conversion_type}")
    
    @staticmethod
    def get_supported_conversion_types() -> dict:
        """
        지원하는 변환 타입 목록을 반환합니다.
        
        Returns:
            dict: 지원하는 변환 타입과 옵션들
        """
        return {
            "framework": {
                "springboot": "Java Spring Boot",
                "fastapi": "Python FastAPI (TODO)"
            },
            "dbms": {
                "postgres_to_oracle": "PostgreSQL → Oracle",
                "oracle_to_postgres": "Oracle → PostgreSQL (TODO)"
            }
        }
