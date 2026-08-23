import requests

# --- Zabbix Configuration ---
ZABBIX_URL = "https://monitor.dev.e2open.com/zabbix/api_jsonrpc.php"  # Change to your Zabbix server URL
ZABBIX_API_TOKEN = "REDACTED"  # Replace with your actual API token

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

def get_host_groups_by_hostname(hostname):
    result = call_zabbix_api("host.get", {
        "filter": {"host": [hostname]},
        "output": ["hostid", "host"],
        "selectGroups": ["groupid", "name"]
    })

    if not result:
        raise Exception(f"❌ Host '{hostname}' not found.")

    host = result[0]
    host_groups = host.get("groups", [])

    if not host_groups:
        print(f"ℹ️ Host '{hostname}' does not belong to any host group.")
    else:
        print(f"✅ Host groups for '{hostname}':")
        for group in host_groups:
            print(f"  - {group['name']} (ID: {group['groupid']})")

# --- Main Execution ---
if __name__ == "__main__":
    hostname_input = input("Enter hostname: ").strip()
    try:
        get_host_groups_by_hostname(hostname_input)
    except Exception as e:
        print(str(e))
