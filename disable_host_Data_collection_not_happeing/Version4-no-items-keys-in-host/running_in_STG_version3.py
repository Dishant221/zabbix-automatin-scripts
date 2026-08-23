from datetime import datetime
from pyzabbix import ZabbixAPI, ZabbixAPIException
import logging
import os
import json
import time
import pymysql
import pymysql.cursors
from typing import List, Dict, Any

#QUERY = '''
#select  distinct h.name , h.hostid
#from hosts_groups hg inner join hstgrp g on g.groupid=hg.groupid
#     inner join hosts h on hg.hostid=h.hostid
#       where h.status=0 and
#       UPPER(g.name)  like 'GO-LIVE/%' and
#       g.name Not like 'GO-LIVE/INFRA/TKC/%' and
#       g.name Not like 'GO-LIVE/INTTRA/INTTRA-Internal%' and
#       h.name not like '%_asg%';
#'''

QUERY = '''
select  distinct h.name , h.hostid
from hosts_groups hg inner join hstgrp g on g.groupid=hg.groupid
     inner join hosts h on hg.hostid=h.hostid
       where h.status=0 and
       UPPER(g.name)  like 'DO-LIKE%';
'''



# Configure logging
logging.basicConfig(
    filename='host_disable_log.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

keys = ['system.uptime','agent.ping','system.localtime']
HISTORY_LIMIT = 10

ZABBIX_URL = "https://monitor.staging.e2open.com/zabbix"
ZABBIX_API_TOKEN = "REDACTED"


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


def get_all_hosts_details_from_json(zapi, hosts_json, keys, HISTORY_LIMIT):
    """
    Given a list of host dicts (from JSON), fetch items and history for each host.
        list of host dicts:
            {
                'hostid', 'host' (hostname), 'status',
                'groups': [{'name': ...}, ...],
                'items': [ { item fields..., 'allhistory': [...] }, ... ]
            }
    """
    complete_host_details = []

    if not isinstance(hosts_json, list):
        print("Input hosts_json must be a list of host dicts")
        return complete_host_details

    for host in hosts_json:
        try:
            host_id = host.get('hostid') or host.get('hostid')
            # some JSON used "name", original used "host"
            hostname = host.get('name') or host.get('host')
            status = host.get('status')

            # Convert groups_list (strings) into group dicts (no groupid available)
            groups = []
            for g in host.get('groups_list', []) or []:
                groups.append({'name': g})

            # Fetch items for this host using Zabbix API
            try:
                items = zapi.item.get(
                    output=['itemid', 'name', 'key_', 'lastclock', 'lastvalue', 'state', 'value_type'],
                    hostids=str(host_id),
                    filter={'key_': keys}
                )
            except Exception as e_item:
                print(f"Failed to fetch items for host {hostname} ({host_id}): {e_item}")
                items = []

            items_with_history = []
            # iterate items and attach history
            for item in items:
                itemid = item.get('itemid')
                # ensure value_type is int for history API
                try:
                    value_type = int(item.get('value_type', 0))
                except Exception:
                    value_type = 0

                # call external history function (assumed implemented elsewhere)
                try:
                    history = get_item_history(zapi, itemid, value_type, limit=HISTORY_LIMIT)
                except Exception as e_hist:
                    print(f"Failed to fetch history for item {itemid} on host {hostname}: {e_hist}")
                    history = []

                items_with_history.append({
                    'itemid': itemid,
                    'key_': item.get('key_'),
                    'name': item.get('name'),
                    'value_type': value_type,
                    'state': item.get('state'),
                    'lastvalue': item.get('lastvalue'),
                    'lastclock': item.get('lastclock'),
                    'allhistory': history
                })

            single_host_details = {
                'hostid': host_id,
                'host': hostname,
                'status': status,
                'groups': groups,
                'items': items_with_history
            }
            complete_host_details.append(single_host_details)
            print(f"Processed host {hostname} (ID: {host_id}) with {len(items_with_history)} items.")
            logger.info(f"Processed host {hostname} (ID: {host_id}) with {len(items_with_history)} items.")

        except Exception as e:
            # Defensive: ensure one broken host doesn't stop whole process
            print(f"Error processing host entry {host!r}: {e}")
            continue

    return complete_host_details




def filter_empty_history_hosts(non_golive_hosts):

    hosts_missing_history = []
    for host in non_golive_hosts:
        items = host.get('items', [])
        missing_items = []

        for item in items:
            history = item.get('allhistory') or []
            # If the history list has fewer than the required samples, record it
            if len(history) < HISTORY_LIMIT:
                missing_items.append({
                    'key_': item.get('key_'),
                    'name': item.get('name'),
                    'history_count': len(history)
                })

        if missing_items:
            hosts_missing_history.append({
                'hostid': host.get('hostid'),
                'host': host.get('host'),
                'missing_items': missing_items
            })
    print("___________Hosts with missing history:_____________")
    #print(json.dumps(hosts_missing_history, indent=2))


    return hosts_missing_history



def add_hostgroup_to_hosts(normalized, zapi):
    from datetime import datetime
    today_data = datetime.now().strftime('%m/%d/%Y')

    group_name = 'HOSTS_TO_BE_DELETED/HOST_DELETE_' + today_data

    try:
        existing = zapi.hostgroup.get(filter={'name': group_name})
    except Exception as e:
        existing = None
        print(f"Error checking existing hostgroup: {e}")
        logger.error(f"Error checking existing hostgroup: {e}")

    if existing:
        groupid = existing[0].get('groupid')
        print(f"Reusing existing hostgroup {group_name} (id={groupid})")
        logger.info(f"Reusing existing hostgroup {group_name} (id={groupid})")
    else:
        try:
            res = zapi.hostgroup.create(name=group_name)
            # pyzabbix returns {'groupids': ['<id>']}
            groupid = res.get('groupids')[0]
            print(f"Created hostgroup {group_name} (id={groupid})")
            logger.info(f"Created hostgroup {group_name} (id={groupid})")
        except Exception as e:
            print(f"Failed to create hostgroup {group_name}: {e}")
            logger.error(f"Failed to create hostgroup {group_name}: {e}")
            return None

    # Build hosts payload for massadd
    hosts_payload = []
    for h in normalized:
        if isinstance(h, dict): # to check if h is dict or just normal  for hostid
            hid = h.get('hostid') or h.get('host')
        else:
            hid = h
        if hid is None:
            continue
        hosts_payload.append({'hostid': str(hid)})

    if not hosts_payload:
        print("No valid hosts provided to add to hostgroup.")
        return groupid

    try:
        zapi.hostgroup.massadd(groups=[{'groupid': groupid}], hosts=hosts_payload)
        msg = f"Added {len(hosts_payload)} hosts to group {group_name} (id={groupid}). Hostids: {[h['hostid'] for h in hosts_payload]}"
        print(msg)
        logger.info(msg)
    except Exception as e:
        print(f"Failed to add hosts to group {group_name}: {e}")
        logger.error(f"Failed to add hosts to group {group_name}: {e}")
        return groupid

    return groupid



def disable_hosts(hosts_with_missing_history, zapi):

    if not hosts_with_missing_history:
        print("No hosts provided to disable.")
        return

    try:
        add_hostgroup_to_hosts(hosts_with_missing_history, zapi)
        print("Adding hosts to HOSTS_TO_BE_DELETED hostgroup before disabling...")
    except Exception as e:
        print(f"Failed to add hosts to hostgroup before disabling: {e}")
        logger.error(f"Failed to add hosts to hostgroup before disabling: {e}")


    for host in hosts_with_missing_history:
        hostid = host.get('hostid')
        hostname = host.get('host')
        try:
            zapi.host.update(hostid=hostid, status=1)  # 1 = disabled
            msg = f"Disabled host {hostname} (ID: {hostid}) due to missing history."
            logger.info(msg)
            print(msg)
            logger.info(msg)
        except Exception as e:
            print(f"Failed to disable host {hostname} (ID: {hostid}): {e}")
            logger.error(f"Failed to disable host {hostname} (ID: {hostid}): {e}")
    #print(json.dumps(hosts_with_missing_history, indent=2))



def connect(): #1

    zapi = ZabbixAPI(ZABBIX_URL)
    zapi.session.headers.update({"Authorization": f"Bearer {ZABBIX_API_TOKEN}"})
    zapi.auth = ZABBIX_API_TOKEN
    return zapi



def make_connection_with_database():
    """
    Create and return a pymysql connection configured to use unix socket.
    Update credentials or use env vars/secret manager in real usage.
    """
    print("Creating database connection............")
    logger.info(f"__________________________{datetime.now()}______________________________")
    return pymysql.connect(
        host="stg5054.sjcus.prod.e2open.com",
        port=8010,
        user="zabbix",
        password="REDACTED",
        database="zabbix",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        connect_timeout=10
    )





def rows_to_json(rows):
    """
    Convert a list of row-dicts (as returned by DictCursor.fetchall())
    into a JSON string. Ensures groups_list is a list (possibly empty).
    """

    out = []

    for row in rows:
        # Copy row so original is not modified
        r = dict(row)

        group_list = r.get("groups_list")

        if group_list and isinstance(group_list, str):
            parts = group_list.split(",")
            cleaned = []

            for p in parts:
                stripped = p.strip()
                if stripped:
                    cleaned.append(stripped)

            r["groups_list"] = cleaned

        else:
            r["groups_list"] = []

        out.append(r)

    return json.dumps(out, indent=4)


def get_enabled_hostids(connection: pymysql.connections.Connection) -> str:
    """
    Execute the query and return JSON string (rows -> JSON).
    """
    cursor = None
    try:
        # Use DictCursor so fetchall() returns list of dicts
        cursor = connection.cursor()
        cursor.execute(QUERY)
        rows = cursor.fetchall()  # list of dicts
        #print(rows)
        return rows_to_json(rows)
    finally:
        if cursor:
            cursor.close()



def main():

    conn = None
    try:
        conn =  make_connection_with_database()
        json_output = get_enabled_hostids(conn)
        # json_output is a JSON string; parse it to a Python list
        try:
            hosts_list = json.loads(json_output)
            print("___________________________Fetched Hosts List______________________________")
            #print(json.dumps(hosts_list, indent=2))
        except Exception as e:
            print(f"Failed to parse hosts JSON: {e}")
            hosts_list = []

        zapi = connect()
        print("Connected to Zabbix API (zapi created) at ")
        logger.info(f"Connected to Zabbix API (zapi created) at {datetime.now()}")
        try:
            #filter_host = get_all_hosts(zapi)
            print(f"\nFetching {len(hosts_list)} hosts with items and history:\n")
            host_complete_details = get_all_hosts_details_from_json(zapi, hosts_list, keys, HISTORY_LIMIT)
            hosts_with_missing_history = filter_empty_history_hosts(host_complete_details)
            #print(json.dumps(non_golive_hosts, indent=2))
            disable_hosts(hosts_with_missing_history, zapi)



        except ZabbixAPIException as e:
            print(f"Error connecting to Zabbix API: {e}")
            return


    except Exception as e:
        print("Database Connection Error:", str(e))

    finally:
        if conn:
            conn.close()







if __name__ == "__main__":
    main()

