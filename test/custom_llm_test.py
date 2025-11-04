from langchain_core.prompts import PromptTemplate
from pathlib import Path
import sys
sys.path.append(0, str(Path(__file__).resolve().parents[1]))
from util.llm_client import get_llm

template = """
너는 도움을 주는 시스템이야. 사용자의 질문/말을 보고 답을 해.

질문: {question}
"""

prompt = PromptTemplate(
    input_variables=["question"],
    template=template,
)

api_key = os.getenv("LLM_API_KEY")
llm = get_llm(api_key=api_key, is_custom_llm=True, company_name="")

chain= prompt | llm
response = chain.invoke({"question": "안녕하세요?"})
print("=== 커스텀 LLM 테스트 ===")
print(f"답변: {response}")