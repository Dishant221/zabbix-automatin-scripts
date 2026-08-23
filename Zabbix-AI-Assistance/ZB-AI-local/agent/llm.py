from langchain_openai import ChatOpenAI
from config.settings import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL


def get_llm():
    return ChatOpenAI(
        #model=LLM_MODEL,
        model="e2open-chat-default",
        temperature=0,
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY
    )