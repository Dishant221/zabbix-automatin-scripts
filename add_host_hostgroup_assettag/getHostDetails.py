import csv
import requests
import json
import sys
import logging


DEV_ZABBIX_TOKEN = 'REDACTED'
DEV_ZABBIX_URL = 'https://monitor.staging.e2open.com/zabbix/api_jsonrpc.php'


HEADERS = headers = {
        "Authorization": f"Bearer {DEV_ZABBIX_TOKEN}",
        "Content-Type": "application/json-rpc"  # Optional, depending on API requirements
    }



def zabbix_api(method, params):
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        
        "id": 1,
    }
    response = requests.post(DEV_ZABBIX_URL, headers=HEADERS, json=payload)
    result = response.json()
    if "error" in result:
        raise Exception(f"Zabbix API error: {result['error']}")
    return result["result"]

def main():
     result = zabbix_api("host.get", 
         {
            "filter": {
              "host": [
                "stg4384.sjcus.prod.e2open.com"
                    ]
                },
                "selectInventory": "extend"
             } )
     print(json.dumps(result, indent=4))
        


if __name__ == "__main__":
    main()
