from datetime import datetime
from pyzabbix import ZabbixAPI, ZabbixAPIException
import logging
import os
import json
import time
import pymysql
import pymysql.cursors
from typing import List, Dict, Any
from datetime import timedelta 
from CredentialUtils import ZBCredentials
import sys


QUERY = '''
SELECT 
 h.name,
    h.hostid
FROM hosts h
WHERE h.status =0
and h.flags=0
  AND NOT EXISTS (
        SELECT 1
        FROM hosts_groups hg
        JOIN hstgrp g ON g.groupid = hg.groupid
        WHERE hg.hostid = h.hostid
          AND g.name like 'GO-LIVE%'
  )
ORDER BY h.name limit 10;
'''
baseDirectory=os.path.dirname(os.path.realpath(__file__))
logFilePath=os.path.join(baseDirectory,"DATA","LOG_OUTPUT","host_disable_log.log")

# Configure logging
logging.basicConfig(
    filename=logFilePath,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

keys = ['system.uptime','agent.ping','system.localtime']
keys_limit_interval_values = {'system.uptime':'1m','agent.ping':'3m','system.localtime':'5m'}

system_uptime_standard_last_hour_value = 60  # values in a hour for 1 minute interval
agent_ping_standard_last_hour_value = 20   # values in a hour for 3 minute interval
system_localtime_standard_last_hour_value = 6  # values in a hour for 10 minute interval in prod 
HISTORY_LIMIT = 60  # Default history limit for other items





def get_item_history(zapi, item_id, value_type, no_of_item_values_last_one_hour):
    """Fetch recent history records for a single item."""
    try:
        now = int(time.time())
        # use a 1-hour window for history
        one_hour_ago = now - 3600  # 3600 seconds = 1 hour
        history = zapi.history.get(
            output='extend',
            itemids=item_id,
            time_from=one_hour_ago,
            time_till=now,
            history=value_type,
            sortfield='clock',
            sortorder='DESC',
            limit=no_of_item_values_last_one_hour
        )
        return history
    except Exception as e:
        print(f"Failed to fetch history for item {item_id}: {e}")
        return []
    

def get_all_hosts_details_from_json(zapi, hosts_json, keys):
    """
    Given a list of host dicts (from JSON), fetch items and history for each host.
        list of host dicts:
            {
                'hostid', 'host' (hostname), 'status',
                'groups': [{'name': ...}, ...],
                'items': [ { item fields..., 
                'allhistory': [...] }, ... ]
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
                item_key = item.get('key_')
                # ensure value_type is int for history API
                try:
                    value_type = int(item.get('value_type', 0))
                except Exception:
                    value_type = 0

                # call external history function 
                try:
                    if item_key == 'system.uptime':
                        history = get_item_history(zapi, itemid, value_type, system_uptime_standard_last_hour_value)
                    elif item_key == 'agent.ping':
                        history = get_item_history(zapi, itemid, value_type, agent_ping_standard_last_hour_value)
                    elif item_key == 'system.localtime':
                        history = get_item_history(zapi, itemid, value_type, system_localtime_standard_last_hour_value)
                    else:
                        history = get_item_history(zapi, itemid, value_type, HISTORY_LIMIT)

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
            logger.info(f"Processed host {hostname} (ID: {host_id}) with {len(items_with_history)}  items.")

        except Exception as e:
            print(f"Error processing host entry {host!r}: {e}")
            logger.error(f"Error processing host entry {host!r}: {e}")
            continue

    return complete_host_details




# version2
def filter_empty_history_hosts(non_golive_hosts):
    hosts_not_collecting = []

    for host in non_golive_hosts:
        items = host.get('items', [])
        # If a host has no items at all, mark it as not collecting
        if not items:
            hosts_not_collecting.append({
                'hostid': host.get('hostid'),
                'host': host.get('host'),
                'failed_items': [{'reason': 'no_items'}]
            })
            continue
        failed_items = []

        for item in items:
            history = item.get('allhistory') or []
            key = item.get('key_')

            if key == 'system.uptime':
                expected = system_uptime_standard_last_hour_value
            elif key == 'agent.ping':
                expected = agent_ping_standard_last_hour_value
            elif key == 'system.localtime':
                expected = system_localtime_standard_last_hour_value
            else:
                continue

            # Condition: no data or too little data
            if len(history) == 0 or len(history) < expected * 0.8:
                failed_items.append({
                    'key_': key,
                    'history_count': len(history),
                    'expected': expected
                })

        # If ALL keys are bad → host is not collecting
        if len(failed_items) == 3:
            hosts_not_collecting.append({
                'hostid': host.get('hostid'),
                'host': host.get('host'),
                'failed_items': failed_items
            })

    return hosts_not_collecting



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
        logger.info("Adding hosts to HOSTS_TO_BE_DELETED hostgroup before disabling...")
    except Exception as e:
        print(f"Failed to add hosts to hostgroup before disabling: {e}")
        logger.error(f"Failed to add hosts to hostgroup before disabling: {e}")

  
    for host in hosts_with_missing_history:
        hostid = host.get('hostid')
        hostname = host.get('host')
        try:
             
            #zapi.host.update(hostid=hostid, status=1)  # 1 = disabled
            msg = f"host can be Disabled  {hostname} (ID: {hostid}) due to missing history."
            logger.info(msg)
            print(msg)
            
        except Exception as e:
            print(f"Failed to disable host {hostname} (ID: {hostid}): {e}")
            logger.error(f"Failed to disable host {hostname} (ID: {hostid}): {e}")    
    #print(json.dumps(hosts_with_missing_history, indent=2))
    


def connect(ZABBIX_URL, ZABBIX_API_TOKEN): #1
    
    zapi = ZabbixAPI(ZABBIX_URL)
    zapi.login(api_token=ZABBIX_API_TOKEN)
    return zapi

 
def make_connection_with_database(HOST, USER, PASSWORD, DATABASE, PORT, UNIX_SOCKET):
    """
    Create and return a pymysql connection configured to use unix socket.
    Update credentials or use env vars/secret manager in real usage.
    """
    print("Creating database connection............")
    logger.info(f"__________________________{datetime.now()}______________________________")
    return pymysql.connect(
        host=HOST,
        port=PORT,
        user=USER,
        password=PASSWORD,
        database=DATABASE,
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
    if len(sys.argv) < 2:
        print("Usage: python count_problem.py <ENVIRONMENT>  # PROD | STG | DEV")
        logging.error("No environment argument provided; exiting.")
        sys.exit(1)

    SCRITP_START_DATE_TIME = datetime.now()

    logging.info(f"_________________SCRIPTING_STARTING_{SCRITP_START_DATE_TIME}________________")

    environment  = sys.argv[1].upper()
    
    config = None
    BaseDirectory=os.path.dirname(os.path.realpath(__file__))
    ENV_FILE_MAP = {
    "PROD": "Credentails_for_PROD.json.enc",
    "STG": "Credentails_for_STAGE.json.enc",
    "DEV": "Credentails_for_DEV.json.enc",
    }

    if environment not in ENV_FILE_MAP:
        logging.error(f"Invalid environment specified: {environment}. Please choose from PROD, STG, or DEV.")
        raise ValueError(f"Invalid environment specified: {environment}. Please choose from PROD, STG, or DEV.")        
        sys.exit(1)

    encrypted_file_path = os.path.join(BaseDirectory,"DATA","CONFIG",ENV_FILE_MAP[environment])


    if environment=='PROD':
        creds = ZBCredentials(enc_file_path=encrypted_file_path)
        config = creds.load()  
    elif environment=="STG":
        creds = ZBCredentials(enc_file_path=encrypted_file_path)
        config = creds.load()   
    elif environment=='DEV':
        creds = ZBCredentials(enc_file_path=encrypted_file_path)
        config = creds.load() 

    global ZABBIX_URL, ZABBIX_API_TOKEN

    ZABBIX_URL = config["ENV_CRED"]["ZABBIX_URL"]
    ZABBIX_API_TOKEN = config["ENV_CRED"]["ZABBIX_TOKEN"]

    HOST = config["ENV_CRED"]["DB_CONNECTION"]["host"]
    USER = config["ENV_CRED"]["DB_CONNECTION"]["user"]
    PASSWORD = config["ENV_CRED"]["DB_CONNECTION"]["password"]
    DATABASE = config["ENV_CRED"]["DB_CONNECTION"]["database"]
    PORT = config["ENV_CRED"]["DB_CONNECTION"]["port"]
    UNIX_SOCKET = config["ENV_CRED"]["DB_CONNECTION"]["unix_socket"]

    conn = None
    try:
        conn =  make_connection_with_database(HOST, USER, PASSWORD, DATABASE, PORT, UNIX_SOCKET)
        json_output = get_enabled_hostids(conn)
        # json_output is a JSON string; parse it to a Python list
        try:
            hosts_list = json.loads(json_output)
            print("___________________________Fetched Hosts List______________________________")
            #print(json.dumps(hosts_list, indent=2))
        except Exception as e:
            print(f"Failed to parse hosts JSON: {e}")
            hosts_list = []

        zapi = connect(ZABBIX_URL, ZABBIX_API_TOKEN)
        print("Connected to Zabbix API (zapi created) at ")
        logger.info(f"Connected to Zabbix API (zapi created) at {datetime.now()}")
        try:
            #filter_host = get_all_hosts(zapi)
            print(f"\nFetching {len(hosts_list)} hosts with items and history:\n")
            logger.info(f"Fetching {len(hosts_list)} hosts with items and history:")
            host_complete_details = get_all_hosts_details_from_json(zapi, hosts_list, keys)
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



