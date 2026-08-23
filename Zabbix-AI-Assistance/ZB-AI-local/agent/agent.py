import json
import re
from typing import Any, Dict, Optional

import requests
from langchain_core.prompts import ChatPromptTemplate

from agent.llm import get_llm
from agent.prompt import SUMMARY_PROMPT
from config.settings import LLM_API_KEY, LLM_BASE_URL
from memory.memory import get_memory
from tools.es_tool import search_zabbix_docs_tool
from tools.zabbix_tool import zabbix_api_tool
from utils.logger import setup_logger

logger = setup_logger()

'''
def _extract_host_hint(question: str) -> str:
    patterns = [
        r"\b(stg[a-zA-Z0-9._-]+)\b",
        r"\b([a-zA-Z0-9.-]+\.[a-zA-Z0-9.-]+\.[a-zA-Z0-9.-]+)\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, question)
        if match:
            return match.group(1)

    return ""
''' 
''' 
def _detect_intent(question: str) -> str:
    q = question.lower()

    if "tag" in q:
        return "host_tags"
    if "template" in q:
        return "host_templates"
    if "enable" in q or "disable" in q or "status" in q:
        return "host_status"
    if "problem" in q:
        return "problem_lookup"
    if "host" in q:
        return "host_lookup"

    return "general"
''' 

def _strip_code_fences(text: str) -> str:
    cleaned = text.strip()

    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    return cleaned.strip()


def _parse_plan_content(content: str) -> Dict[str, Any]:
    cleaned = _strip_code_fences(content)

    try:
        parsed = json.loads(cleaned)
    except Exception:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise ValueError(f"Planner did not return JSON: {content}")
        parsed = json.loads(match.group(0))

    if not isinstance(parsed, dict):
        raise ValueError(f"Planner returned non-object JSON: {parsed}")

    return parsed


def _normalize_plan(plan: Any) -> Dict[str, Any]:
    if isinstance(plan, dict):
        return {
            "jsonrpc": plan.get("jsonrpc", "2.0"),
            "method": plan.get("method"),
            "params": plan.get("params", {}) or {},
            "id": plan.get("id", 1),
            "auth": plan.get("auth"),
            "explanation": plan.get("explanation", ""),
            "raw_plan": plan,
        }

    return {
        "jsonrpc": getattr(plan, "jsonrpc", "2.0"),
        "method": getattr(plan, "method", None),
        "params": getattr(plan, "params", {}) or {},
        "id": getattr(plan, "id", 1),
        "auth": getattr(plan, "auth", None),
        "explanation": getattr(plan, "explanation", ""),
        "raw_plan": plan,
    }


def _is_too_generic(question: str, plan_data: Dict[str, Any]) -> bool:
    q = question.lower()
    method = (plan_data.get("method") or "").strip()
    params = plan_data.get("params") or {}

    if any(word in q for word in ["host", "tags", "template", "enable", "disable", "status"]):
        if method == "host.get" and not params:
            return True

    return False


def build_plan_with_llm(question: str, docs_context: str) -> Dict[str, Any]:
    if not LLM_API_KEY or not LLM_BASE_URL:
        raise ValueError("LLM_API_KEY or LLM_BASE_URL is missing from environment.")

    url = f"{LLM_BASE_URL.rstrip('/')}/chat/completions"
    #host_hint = _extract_host_hint(question)
    #intent_hint = _detect_intent(question)
    #use this detected intent: {intent_hint}
    #use this detected host hint: {host_hint if host_hint else "none"}

    prompt = f"""
    generate right zabbix api call for question "{question}"
    and use this doc context:

    {docs_context}

    only return the api call without any explanation.
    """

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        #"model": "gpt-5.1-codex",
        "model": "e2open-chat-default",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0,
    }

    logger.info("Calling planner LLM directly with raw prompt...")
    response = requests.post(url, json=payload, headers=headers, timeout=60)
    response.raise_for_status()

    data = response.json()
    content = data["choices"][0]["message"]["content"]

    logger.info(f"Raw planner output: {content}")

    plan = _parse_plan_content(content)
    return _normalize_plan(plan)


class ZabbixAssistant:
    def __init__(self):
        self.llm = get_llm()
        self.memory = get_memory()

        self.summary_chain = (
            ChatPromptTemplate.from_messages([
                ("system", SUMMARY_PROMPT),
                (
                    "human",
                    "Chat history:\n{chat_history}\n\n"
                    "Retrieved docs context:\n{docs_context}\n\n"
                    "Planned API call:\n{api_plan}\n\n"
                    "Raw Zabbix response:\n{api_result}\n\n"
                    "User question:\n{question}"
                )
            ])
            | self.llm
        )

    def _history_to_text(self) -> str:
        history = self.memory.load_memory_variables({}).get("chat_history", [])
        if not history:
            return "No prior history."

        lines = []
        for msg in history[-10:]:
            role = getattr(msg, "type", "message").upper()
            content = getattr(msg, "content", "")
            lines.append(f"{role}: {content}")

        return "\n".join(lines)

    def invoke(self, question: str) -> Dict[str, Any]:
        logger.info("Starting assistant pipeline")
        logger.info(f"Question: {question}")

        chat_history_text = self._history_to_text()
        logger.info("Loaded chat history")

        logger.info("Searching ES docs...")
        docs_context = search_zabbix_docs_tool.invoke({
            "query": question,
            "top_k": 4
        })

        if not docs_context:
            docs_context = "No documentation context found."

        logger.info("ES search completed")

        logger.info("Planning API call...")
        plan_data = build_plan_with_llm(question, docs_context)

        logger.info(f"Planned method: {plan_data.get('method')}")
        logger.info(f"Planned params: {plan_data.get('params')}")

        if _is_too_generic(question, plan_data):
            logger.warning("Generic plan detected, retrying planner once")

            retry_question = (
                f"{question}\n\n"
                "The previous plan was too generic. "
                "Return a more specific minimal Zabbix API call. "
                "Do not return empty params for a specific host-related question."
            )

            plan_data = build_plan_with_llm(retry_question, docs_context)

            logger.info(f"Replanned method: {plan_data.get('method')}")
            logger.info(f"Replanned params: {plan_data.get('params')}")

        logger.info("Calling Zabbix API...")
        api_result = zabbix_api_tool.invoke({
            "method": plan_data["method"],
            "params": plan_data.get("params", {})
        })
        logger.info("Zabbix API call completed")

        api_result_str = json.dumps(api_result, indent=2, ensure_ascii=False)
        if len(api_result_str) > 12000:
            logger.warning(f"API result too large ({len(api_result_str)} chars), truncating")
            api_result_str = api_result_str[:12000]

        logger.info("Summarizing result...")
        summary_msg = self.summary_chain.invoke({
            "question": question,
            "chat_history": chat_history_text,
            "docs_context": docs_context,
            "api_plan": plan_data,
            "api_result": api_result_str
        })
        logger.info("Summary generated")

        answer = summary_msg.content if hasattr(summary_msg, "content") else str(summary_msg)

        self.memory.save_context(
            {"input": question},
            {"output": answer}
        )

        logger.info("Pipeline finished successfully")

        return {
            "answer": answer,
            "docs_context": docs_context,
            "api_plan": plan_data,
            "api_result": api_result
        }


def create_agent():
    return ZabbixAssistant()