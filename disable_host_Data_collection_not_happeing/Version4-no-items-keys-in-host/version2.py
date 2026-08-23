from pyzabbix import ZabbixAPI, ZabbixAPIException
import logging
import os
import json
import time


keys = ['system.uptime','agent.ping','system.localtime']
HISTORY_LIMIT = 10 

ZABBIX_URL = "https://monitor.dev.e2open.com/zabbix"
ZABBIX_API_TOKEN = "REDACTED"

def connect():
    
    zapi = ZabbixAPI(ZABBIX_URL)
    zapi.session.headers.update({"Authorization": f"Bearer {ZABBIX_API_TOKEN}"})
    zapi.auth = ZABBIX_API_TOKEN
    return zapi


def get_item_history(zapi, item_id, value_type, limit=HISTORY_LIMIT):
    """Fetch recent history records for a single item."""
    try:
        now = int(time.time())
        # use a 3-hour window for history
        three_hours_ago = now - 3 * 3600
        history = zapi.history.get(
            output='extend',
            itemids=item_id,
            time_from=three_hours_ago,
            time_till=now,
            history=value_type,
            sortfield='clock',
            sortorder='DESC',
            limit=limit
        )
        return history
    except Exception as e:
        print(f"Failed to fetch history for item {item_id}: {e}")
        return []
    

def filter_golive_hosts(hosts):
    filtered_hosts = []
    for host in hosts:
        groups = host.get('groups', [])
        for group in groups:
            if all(group['name'].upper().startswith('GO-LIVE')):
                filtered_hosts.append(host)
    return filtered_hosts


def get_all_hosts(zapi):
    
    try:
        hosts = zapi.host.get(
            output=['hostid', 'host', 'status'],
            selectGroups=['groupid', 'name'],
            filter={'status': 0}  # 0 = enabled, 1 = disabled
        )
    except Exception as e:
        print(f"Failed to fetch hosts from Zabbix API: {e}")
        return []

    try:
        print(f"Zabbix API returned {len(hosts)} hosts")
    except Exception:
        print("Received unexpected hosts response from API; cannot enumerate results")
    
    enriched_hosts = []
    for host in hosts:
        host_id = host['hostid']
        hostname = host['host']

        items = zapi.item.get(
                output=['itemid', 'name', 'key_', 'lastclock', 'lastvalue', 'state', 'value_type'],
                hostids=host_id,
                filter={'key_': keys}
            )
            
        items_with_history = []
        print(f"Host {hostname} (ID: {host_id}) has {len(items)} fetching items ")

        for item in items:
            itemid = item.get('itemid')
            value_type = int(item.get('value_type', 0))
                
            history = get_item_history(zapi, itemid, value_type, limit=HISTORY_LIMIT)
                
            items_with_history.append({
                    'itemid': itemid,
                    'key_': item.get('key_'),
                    'name': item.get('name'),
                    'value_type': value_type,
                    'state': item.get('state'),
                    'lastvalue': item.get('lastvalue'),
                    'lastclock': item.get('lastclock'),
                    'allhistory': history  # List of {itemid, clock, value, ns}
                })
            
            
            enriched_host = {
                'hostid': host_id,
                'host': hostname,
                'status': host.get('status'),
                'groups': host.get('groups', []),
                'items': items_with_history
            }
            enriched_hosts.append(enriched_host)

    filter_host = filter_golive_hosts(enriched_hosts)
    
    
    return filter_host


def filter_empty_history_hosts(non_golive_hosts):
    
    host_with_no_history = []
    for host in non_golive_hosts:
        items = host.get('items', [])
        has_history = True
        for item in items:
            history = item.get('allhistory', [])
            if (len(history) < HISTORY_LIMIT) or not history:
                has_history = False
                break
        if has_history:
            host_with_no_history.append(host)
    return host_with_no_history
    


def main():
    zapi = connect()
    print("Connected to Zabbix API (zapi created)")

    try:
        filter_host = get_all_hosts(zapi)
        print(f"\nFetched {len(filter_host)} hosts with items and history:\n")
        non_golive_hosts = filter_golive_hosts(filter_host)
        print(json.dumps(non_golive_hosts, indent=2))
        
       

    except ZabbixAPIException as e:
        print(f"Error connecting to Zabbix API: {e}")
        return




if __name__ == "__main__":
    main()


