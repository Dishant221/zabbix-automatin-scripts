import requests
import json
import sys


ZABBIX_URL = "http://192.168.65.130/zabbix//api_jsonrpc.php" 
ZABBIX_API_TOKEN = "REDACTED"  

HEADERS = {
    "Content-Type": "application/json-rpc",
    "Authorization": f"Bearer {ZABBIX_API_TOKEN}"
}

def call_zabbix_api(method, params):
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1
    }
    response = requests.post(ZABBIX_URL, headers=HEADERS, json=payload)
    data = response.json()
    if "error" in data:
        raise Exception(f"❌ Zabbix API Error: {data['error']}")
    return data["result"]

def get_host_id(hostname):
    result = call_zabbix_api("host.get", {"filter": {"host": [hostname]}})
    return result[0]["hostid"] if result else None

def add_suppressByTag(hostId,tag,hostname):
    result = call_zabbix_api('host.get',{
        "hostid": hostId,
        "tags":{
            "tag":tag,
            "value" : ""
        }

    })
    print(json.dumps(result, indent=4))



if __name__ == "__main__":

    hostname = sys.argv[1]

    hostid = get_host_id(hostname)
    
    try:
        get_host_without_suppressedByTag(hostid)
    except Exception as e:
        print(str(e))

{
    "jsonrpc": "2.0",
    "method": "host.get",
    "params": {
        "output": ["hostid"],
        "selectTags": "extend",
        "evaltype": 0,
        "tags": [
            {
                "tag": "host-name",
                "value": "linux-server",
                "operator": 1
            }
        ]
    },
    "id": 1
}