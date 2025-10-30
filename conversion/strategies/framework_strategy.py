import json
from typing import AsyncGenerator, Any
from .base_strategy import ConversionStrategy


class FrameworkConversionStrategy(ConversionStrategy):
    """프레임워크 변환 전략 (Spring Boot, FastAPI 등)"""
    
    def __init__(self, target_framework: str = "springboot"):
        self.target_framework = target_framework.lower()
    
    async def convert(self, file_names: list, orchestrator: Any, **kwargs) -> AsyncGenerator[bytes, None]:
        """
        프레임워크 변환을 수행합니다.
        
        Args:
            file_names: 변환할 파일 목록
            orchestrator: ServiceOrchestrator 인스턴스
            **kwargs: 추가 매개변수
        """
        if self.target_framework == "springboot":
            async for chunk in orchestrator.convert_to_springboot(file_names):
                yield chunk
        elif self.target_framework == "fastapi":
            # TODO: FastAPI 변환 로직 구현
            yield json.dumps({"error": "FastAPI conversion not implemented yet"}).encode('utf-8')
        else:
            yield json.dumps({"error": f"Unsupported framework: {self.target_framework}"}).encode('utf-8')
