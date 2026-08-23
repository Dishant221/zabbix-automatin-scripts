import json
import requests

from typing import Any, Dict, Optional
from langchain_core.tools import StructuredTool

from config.settings import ZABBIX_URL, ZABBIX_TOKEN
from utils.logger import setup_logger

logger = setup_logger()


def zabbix_api(
    method: str,
    params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:

    logger.info(f"Zabbix method: {method}")
    logger.info(f"Zabbix params: {params}")

    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params or {},
        "id": 1
    }

    logger.info("========================================")
    logger.info("ZABBIX REQUEST PAYLOAD")
    logger.info(json.dumps(payload, indent=2))
    logger.info("========================================")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ZABBIX_TOKEN}"
    }

    try:

        response = requests.post(
            ZABBIX_URL,
            json=payload,
            headers=headers,
            timeout=60
        )

        logger.info(f"Zabbix HTTP status: {response.status_code}")

        try:

            data = response.json()

            result_count = 0

            if isinstance(data, dict):

                if "result" in data:

                    if isinstance(data["result"], list):
                        result_count = len(data["result"])

                    elif isinstance(data["result"], dict):
                        result_count = 1

            logger.info(f"Zabbix result count: {result_count}")

            response_str = json.dumps(data)

            logger.info(
                f"Zabbix response size: {len(response_str)} chars"
            )

            logger.info("========================================")
            logger.info("RAW ZABBIX RESPONSE")
            logger.info(response_str[:5000])
            logger.info("========================================")

            return data

        except Exception as json_error:

            logger.exception("JSON parse failed")

            return {
                "error": str(json_error),
                "raw_text": response.text[:5000]
            }

    except Exception as e:

        logger.exception("Zabbix API failed")

        return {
            "error": str(e)
        }


zabbix_api_tool = StructuredTool.from_function(
    func=zabbix_api,
    name="zabbix_api",
    description="Call the Zabbix JSON-RPC API"
)