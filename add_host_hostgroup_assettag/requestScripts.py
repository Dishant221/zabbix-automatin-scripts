REQUIRED_TAGS_CHECK = {
    "SFID", 
    "JID", 
    "USER", 
    "SOLUTION", 
    "SuppressedBy"
}

missingvalues = {
    'SFID', 
    'SOLUTION', 
    'JID', 
    'USER', 
    'SuppressedBy', 
    'Hub', 
    'CustomerCategory'
}

import requests
import json

api_url = "http://192.168.65.130/zabbix/api_jsonrpc.php"
ACCESS_TOKEN ="REDACTED"

headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json-rpc"  # Optional, depending on API requirements
    }

missingdict = {keys : "" for keys in REQUIRED_TAGS_CHECK & missingvalues}
#print(missingdict)


tag={'SOLUTION': '', 'SuppressedBy': '', 'SFID': '', 'JID': '', 'USER': ''}

#result = {key for key, value in missingdict.items() }
method = 'host.update' 
# Convert missingdict to the expected format
tags_array = [{"tag": key, "value": value} for key, value in missingdict.items()]

print(tags_array)

param = {
    "hostid": 10685,
    "tags": tags_array
}

param = {
                "hostid": 10685,
                "tags": tags_array
            }

payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": param,
        
        "id": 1,
    }

response = requests.post(api_url, headers=headers, json=payload)
result = response.json()
if "error" in result:
    raise Exception(f"Zabbix API error: {result['error']}")
else:
    print(result["result"])
