from zabbix_utils import ZabbixAPI
import json
import request

serverUrl = "http://192.168.65.130/zabbix/api_jsonrpc.php"
#user = 'Admin'
#passW = 'zabbix'

serverToken = 'REDACTED'



api = ZabbixAPI(url=serverUrl)
api.login(token=serverToken)

allHost = api.hostgroup.get(output="extend", filter={"name": ["Linux servers", "Training/Servers", "Zabbix servers"]})
allHost =json.dumps(allHost, indent=4)
print(allHost)

'''
users = api.user.get(
    output=['userid','name']
)

for user in users:
    print(user['name'])
'''
