# custom_llm_client.py : 포스코 llm class

import requests
from typing import Any, Optional, Dict, List, Union
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.language_models import BaseChatModel
from langchain_core.outputs import ChatResult, ChatGeneration


class PoscoLLMClient(BaseChatModel):
    """포스코 전용 LLM 래퍼 (간단 스텁).

    - invoke(input) 메서드만 제공하며 현재는 빈 문자열을 반환합니다.
    - 실제 HTTP 호출 로직은 추후 구현 예정입니다.
    """
    api_key: str
    base_url: str
    model: str
    temperature: float = 0.1
    max_tokens: Optional[int] = None
    timeout: Optional[int] = 60
    verify_ssl: bool = False

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        timeout: int = 60,
        verify_ssl: bool = False,
    ):
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            verify_ssl=verify_ssl,
        )

    def _llm_type(self) -> str:
        return "posco-chat-model(p-gpt)"

    def _convert_messages(self, messages: List[BaseMessage]) -> List[Dict[str, str]]:
        out = []
        for message in messages:
            if isinstance(message, HumanMessage):
                role = "user"
            elif isinstance(message, SystemMessage):
                role = "system"
            elif isinstance(message, AIMessage):
                role = "assistant"
            else:
                role = "user"
            out.append({"role": role, "content": message.content})
        return out

    def _generate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None) -> ChatResult:
        headers = {
            "accept": "*/*",
            "Authorization": f"Bearer {self.api_key}",
            "content-type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": self._convert_messages(messages),
            "temperature": self.temperature,
        }
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens
        if stop:
            payload["stop"] = stop

        resp = requests.post(self.base_url, headers=headers, json=payload, timeout=self.timeout, verify=self.verify_ssl)
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "").lower()
        if "application/json" in content_type:
            data = resp.json()
            content = (
                data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            )
        else:
            content = resp.text.strip()

        ai_msg = AIMessage(content=content)
        return ChatResult(generations=[ChatGeneration(message=ai_msg)])

    def invoke(self, prompt_value: Any, config: Optional[Dict[str, str]] = None) -> str:
        text = getattr(prompt_value, "to_string", lambda: str(prompt_value))()

        if config:
            self.temperature = config.get("temperature", self.temperature)
            self.max_tokens = config.get("max_tokens", self.max_tokens)
        
        messages = List[BaseMessage] = [
            SystemMessage(content="너는 도움을 주는 시스템이야. 사용자의 질문/말을 보고 답을 해."),
            HumanMessage(content=text),
        ]

        result = self._generate(messages, stop=config.get("stop") if config else None)
        return result.generations[0].message.content

    def _call_(self, prompt_value: Any, **config: Any) -> str:
        return self.invoke(prompt_value, config)