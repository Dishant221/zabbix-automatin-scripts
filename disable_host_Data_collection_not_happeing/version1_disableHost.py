from pyzabbix import ZabbixAPI, ZabbixAPIException
import logging
import os
import json
import time




given_keys = []
no_of_data_points = 5

# Collected hosts missing sufficient history will be stored here
DISABLE_HOST_LIST = []

keys = ['system.uptime','agent.ping','system.localtime']



ZABBIX_URL = "https://monitor.dev.e2open.com/zabbix"
ZABBIX_API_TOKEN = "REDACTED"

def connect():
    
    zapi = ZabbixAPI(ZABBIX_URL)
    zapi.session.headers.update({"Authorization": f"Bearer {ZABBIX_API_TOKEN}"})
    zapi.auth = ZABBIX_API_TOKEN
    return zapi


def get_all_hosts(zapi):
    
    # Return hostid, host (hostname) and the groups each host belongs to.
    # selectGroups returns an array of group objects for each host.
    # Filter only enabled hosts (status=0) at the API level
    hosts = zapi.host.get(
        output=['hostid', 'host', 'status'],
        selectGroups=['groupid', 'name'],
        filter={'status': 0}  # 0 = enabled, 1 = disabled
    )
    return hosts



def filter_non_golive_hosts(hosts):
    filtered_hosts = []
    for host in hosts:
        groups = host.get('groups', [])
        if all(not group['name'].upper().startswith('GO-LIVE') for group in groups):
            filtered_hosts.append(host)
    return filtered_hosts


def get_item_values_of_host(zapi, filtered_hosts):
    """Process a list of hosts, collect each host's items + history, and return list of results.

    For each host the function will:
    - fetch configured items
    - fetch recent history per item
    - build a host result dict and append it to `results`
    - call `filter_host_to_Disbled(host_result, zapi)` to mark candidates
    """

    results = []

    for host in filtered_hosts:
        host_id = host['hostid']
        hostname = host['host']
        # trace: show which host is being processed
        print(f"Processing host: {hostname} (id={host_id})")

        checks = zapi.item.get(
            output=['itemid', 'name', 'key_', 'lastclock', 'lastvalue', 'state', 'value_type'],
            hostids=host_id,
            filter={'key_': keys}
        )

        host_result = {
            'hostname': hostname,
            'hostid': host_id,
            'checks': checks,
            'allhistory': []
        }

        # For each check (item) fetch recent history and attach it under host_result['allhistory']
        for item in checks:
            try:
                itemid = item.get('itemid')
                if item.get('value_type') is not None:
                    value_type = int(item.get('value_type', 0))
                else:
                    value_type = 0
            except Exception:
                itemid = item.get('itemid')
                value_type = 0

            # fetch history for this item (limit configurable by changing get_history_of_item)
            history = []
            if itemid:
                history = get_history_of_item(zapi, itemid, value_type)

            host_result['allhistory'].append({
                'itemid': itemid,
                'key_': item.get('key_'),
                'name': item.get('name'),
                'value_type': value_type,
                'lastvalue': item.get('lastvalue'),
                'lastclock': item.get('lastclock'),
                'history': history
            })

        results.append(host_result)
        
        try:
            filter_host_to_Disbled(host_result, zapi)
        except Exception as e:
            print(f"filter_host_to_Disbled failed for host {hostname} (id={host_id}): {e}")

    #print(json.dumps(results, indent=4))
    return results


def get_history_of_item(zapi, item_id, value_type, limit=no_of_data_points):
    now = int(time.time())
    one_hour_ago = now - 3600
    history = zapi.history.get(
        output='extend',
        itemids=item_id,
        time_from=one_hour_ago,
        time_till=now,
        history=value_type,
        sortfield='clock',
        sortorder='DESC',
        limit=limit
    )
    
    return history


def filter_host_to_Disbled(host_result, zapi):
    """Check each item's history records and mark host if any item has insufficient data.
    
    host_result: dict with keys 'hostname', 'hostid', 'checks', 'allhistory'
                 where 'allhistory' is a list of items, each with nested 'history' records
    zapi: ZabbixAPI instance (unused here, kept for future expansion)
    """
    
    missing_items = []
    
    # Iterate each item in allhistory (agent.ping, system.uptime, system.localtime)
    for item in host_result.get('allhistory', []):
        # Get the nested history records for this item
        records = item.get('history') or []
        
        # Check if this item has fewer than required data points
        if len(records) < no_of_data_points or not records:
            missing_items.append(item.get('key_') or item.get('name'))
            # Optional: print detailed info
            print(f"  Item {item.get('key_')} has {len(records)} records (need {no_of_data_points})")
    
    # If any item is missing data, add this host to disable list
    if missing_items:
        DISABLE_HOST_LIST.append({
            'hostid': host_result.get('hostid'),
            'hostname': host_result.get('hostname'),
            'missing_items': missing_items
        })
    return to_disable_hosts(DISABLE_HOST_LIST, zapi)




def add_host_group_for_disable(hosts_list, zapi):
    """Create (or reuse) a host group named '<YYYY-MM-DD>-hostDisablelist' and add hosts to it.

    hosts_list: list of host dicts (with 'hostid') or list of hostid strings
    zapi: connected pyzabbix.ZabbixAPI instance
    Returns the hostgroup id on success.
    """
    from datetime import datetime

    group_name = datetime.now().strftime('%Y-%m-%d') + '-hostDisablelist'

    # Check if group already exists
    try:
        existing = zapi.hostgroup.get(filter={'name': group_name})
    except Exception:
        existing = None

    if existing:
        groupid = existing[0].get('groupid')
        print(f"Reusing existing hostgroup {group_name} (id={groupid})")
    else:
        # Create new group
        try:
            res = zapi.hostgroup.create(name=group_name)
            # pyzabbix returns {'groupids': ['<id>']}
            groupid = res.get('groupids')
            print(f"Created hostgroup {group_name} (id={groupid})")
        except Exception as e:
            print(f"Failed to create hostgroup {group_name}: {e}")
            return None

    # Build hosts payload
    hosts_payload = []
    for h in hosts_list:
        if isinstance(h, dict):
            hid = h.get('hostid') or h.get('host')
        else:
            hid = h
        if hid is None:
            continue
        hosts_payload.append({'hostid': str(hid)})

    if not hosts_payload:
        print("No valid hosts provided to add to hostgroup.")
        return groupid

    # Mass-add hosts to the group
    try:
        zapi.hostgroup.massadd(groups=[{'groupid': groupid}], hosts=hosts_payload)
        print(f"Added {len(hosts_payload)} hosts to group {group_name} (id={groupid})")
    except Exception as e:
        print(f"Failed to add hosts to group {group_name}: {e}")
        return groupid

    return groupid


def to_disable_hosts(DISABLE_HOST_LIST, zapi):
    print(json.dumps(DISABLE_HOST_LIST, indent=4))

def main():
    zapi = connect()
    print("Connected to Zabbix API (zapi created)")

    try:
        filtered_hosts = get_all_hosts(zapi)
        filtered_hosts = filter_non_golive_hosts(filtered_hosts)
        get_item_values_of_host(zapi, filtered_hosts)



        """
        for host in filtered_hosts:
            host_id = host['hostid']
            hostname = host['host']
            get_item_values_of_host(zapi, host_id,hostname)
            #print(f"Host ID: {host_id}, Host Name: {host['host']}")
            #print("Metrics:")
            #print(json.dumps(items, indent=4))
            #print("-" * 40)

        #print(json.dumps(filtered_hosts, indent=4))
        """
    except ZabbixAPIException as e:
        print(f"Error connecting to Zabbix API: {e}")
        return


if __name__ == "__main__":
    main()