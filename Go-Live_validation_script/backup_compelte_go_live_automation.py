from CredentialUtils import ZBCredentials
import os
import sys
import json
import pyzabbix
import logging
from datetime import datetime, timedelta
from pyzabbix import ZabbixAPI, ZabbixAPIException
import time
from tabulate import tabulate



tags_added = False
last_7_days_problems_close = False
data_validation = False

new_tag_with_no_values = [
    {"tag": "SFID", "value": ""},
    {"tag": "JID", "value": ""},
    {"tag": "USER", "value": ""},
    {"tag": "SuppressedBy", "value": ""}
]
special_tags = {
    "ControlledAccess": "{INVENTORY.SOFTWARE.APP.D}",
    "CustomerCategory": "{INVENTORY.SOFTWARE.APP.C}",
    "Hub": "{INVENTORY.TYPE.FULL}",
    "SOLUTION": "{INVENTORY.SOFTWARE}"
}

keys = ['system.uptime','agent.ping']

system_uptime_standard_last_hour_value = 60  # values in a hour for 1 minute interval
agent_ping_standard_last_hour_value = 20   # values in a hour for 3 minute interval
HISTORY_LIMIT = 60 



BaseDirectory = os.path.dirname(os.path.abspath(__file__))
logfilePATH = os.path.join(BaseDirectory,"DATA","LOG_OUTPUT","GO-LIVE_VALIDATION_LOGS.log")


logging.basicConfig(filename=logfilePATH,
                    filemode='a',
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
# also log to console so errors/prints are visible when running interactively


def connect(ZABBIX_URL, ZABBIX_API_TOKEN): #1
    
    zapi = ZabbixAPI(ZABBIX_URL)
    #zapi.session.headers.update({"Authorization": f"Bearer {ZABBIX_API_TOKEN}"})
    #zapi.auth = ZABBIX_API_TOKEN
    #zapi = ZabbixAPI(ZABBIX_URL)
    zapi.login(api_token=ZABBIX_API_TOKEN)
    print(f"Connected to Zabbix API Version: {zapi.api_version()}")
    logging.info(f"Connected to Zabbix API Version: {zapi.api_version()}")
    return zapi


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
                    else:
                        pass

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
            #print(f"Processed host {hostname} (ID: {host_id}) with {len(items_with_history)} items collecting Data.")
            #logging.info(f"Processed host {hostname} (ID: {host_id}) with {len(items_with_history)}  items.")

        except Exception as e:
            print(f"Error processing host entry {host!r}: {e}")
            logging.error(f"Error processing host entry {host!r}: {e}")
            continue

    return complete_host_details



def get_host_from_hostgroup(zapi, hostgroup_name):
    """
    Fetch host IDs for a given host group name.
    """
    try:
        hostgroup = zapi.hostgroup.get(filter={"name": hostgroup_name})
        if not hostgroup:
            logging.warning(f"No host group found with name: {hostgroup_name}")
            return []
        hostgroup_id = hostgroup[0]['groupid']
        hosts = zapi.host.get(groupids=hostgroup_id, output=["hostid", "name","status"], selectGroups="extend")
        return hosts
    except ZabbixAPIException as e:
        logging.error(f"Error fetching hosts from host group '{hostgroup_name}': {e}")
        return []



# version2
def filter_empty_history_hosts(non_golive_hosts):
    """
    Analyze hosts and separate into two lists:
      - hosts_collecting_data: hosts that have sufficient history for the monitored keys
      - hosts_not_collecting: hosts missing all required key history or with insufficient data

    Returns a tuple: (hosts_collecting_data, hosts_not_collecting)
    """
    hosts_not_collecting = []
    hosts_collecting_data = []

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
        # Track which keys we actually evaluated (in case some items are missing)
        evaluated_keys = set()

        for item in items:
            history = item.get('allhistory') or []
            key = item.get('key_')

            if key == 'system.uptime':
                expected = system_uptime_standard_last_hour_value
            elif key == 'agent.ping':
                expected = agent_ping_standard_last_hour_value
            else:
                # ignore any keys we don't evaluate
                continue

            evaluated_keys.add(key)

            # Condition: no data or too little data
            if len(history) == 0 or len(history) < expected * 0.9:
                failed_items.append({
                    'key_': key,
                    'history_count': len(history),
                    'expected': expected
                })

        # Determine classification: if ALL required keys are bad (3 keys) -> not collecting
        # Otherwise treat as collecting data
        if len(failed_items) > 0:
            hosts_not_collecting.append({
                'hostid': host.get('hostid'),
                'host': host.get('host'),
                'status': host.get('status'),
                'failed_items': failed_items
            })
        else:
            hosts_collecting_data.append({
                'hostid': host.get('hostid'),
                'host': host.get('host'),
                'status': host.get('status'),
                'failed_items': failed_items,
                'evaluated_keys': list(evaluated_keys)
            })

    return hosts_collecting_data, hosts_not_collecting




    
    
def add_tag_to_host(zapi, hostid, new_tag_with_no_values):
    #Fetch host info
    host = zapi.host.get(
        hostids=hostid,
        output=["hostid", "name"],
        selectTags="extend"
    )

    if not host:
        msg = f"⚠️ No host found for hostid {hostid}"
        print(msg)
        logging.info(msg)
        return {"success": False, "message": msg}

    hostname = host[0].get("host", f"unknown_{hostid}")
    current_tags = host[0].get("tags", [])

    # Clean tags (remove "automatic")
    cleaned_existing_tags = []
    previous_tag = []
    for tag in current_tags:
        new_tag = {}
        for k, v in tag.items():
            if k != "automatic":
                new_tag[k] = v
        cleaned_existing_tags.append(new_tag)
        previous_tag.append(new_tag)

    #Merge special_tags and new tags wiht no value
    merged_tags = {}
    merged_tags.update(special_tags)  # special tags first
    for t in new_tag_with_no_values:
        merged_tags[t["tag"]] = t.get("value", "")

    new_tags_added = 0
    tags_updated = 0

    #Apply merged tags
    for tag_key, new_value in merged_tags.items():
        # Find if tag already exists
        existing_tag = None
        for t in cleaned_existing_tags:
            if t.get("tag") == tag_key:
                existing_tag = t
                break

        if existing_tag:
            current_value = existing_tag.get("value", "")
            # Update only if new_value is not empty and different
            if new_value and current_value != new_value:
                existing_tag["value"] = new_value
                tags_updated += 1
        else:
            # Add new tag if it doesn't exist
            cleaned_existing_tags.append({"tag": tag_key, "value": new_value})
            new_tags_added += 1

    #Skip if no changes
    if new_tags_added == 0 and tags_updated == 0:
        msg = f"⏭️ No tag changes needed, skipping.."
        print(msg)
        logging.info(msg)
        return {"success": True, "message": msg}

    #Update host in Zabbix
    try:
        zapi.host.update(hostid=hostid, tags=cleaned_existing_tags)
        
        msg = f"✅ {hostid}: Added {new_tags_added} new tag(s)"
        print(msg)
        logging.info(msg)
        logging.info(f"PREVIOUS Tags of {hostname} : {json.dumps(previous_tag)}")
        #logging.info("_____________________________________________________________")
        return {"success": True, "message": msg}
    except Exception as e:
        msg = f"❌ Failed to update host {hostid}: {e}"
        print(msg)
        logging.error(msg)
        return {"success": False, "message": msg}

def host_collecting_data_message(hosts_collecting_data):
    table_data = []
    print("********************************************************************************")
    print(f"\nTotal hosts collecting data: {len(hosts_collecting_data)}\n")

    for host in hosts_collecting_data:
        hostid = host.get('hostid')
        hostname = host.get('host')
        failed_items = host.get('failed_items', [])
        status = host.get('status', 'N/A')

        if status == "1" or status == "N/A":
            status = "Disabled/Unknown"
        else:  status = "Enabled"

        if not failed_items:
            data_collection = "YES"
            failed_keys = "-"
        else:
            data_collection = "NO"
            failed_keys = ", ".join([item['key_'] for item in failed_items])

        table_data.append([
            hostid,
            hostname,
            data_collection,
            failed_keys,
            status
        ])

    print(tabulate(
        table_data,
        headers=["HostID", "Hostname", "Data Collection", "Failed Keys", "Status"],
        tablefmt="grid"
    ))


def host_not_collecting_data_message(hosts_with_missing_history):

    table_data = []
    print("************************************************************************")
    print(f"\nTotal hosts NOT collecting data: {len(hosts_with_missing_history)}\n")

    for host in hosts_with_missing_history:
        hostid = host.get('hostid')
        hostname = host.get('host')
        failed_items = host.get('failed_items', [])
        status = host.get('status', 'N/A')

        # Combine item keys into one field
        failed_keys = []
        history_details = []

        if status == "1" or status == "N/A":
            status = "Disabled/Unknown"
        else:  status = "Enabled"

        for item in failed_items:
            key = item.get('key_', 'N/A')
            history_count = item.get('history_count', 0)
            expected = item.get('expected', 'N/A')

            failed_keys.append(key)
            history_details.append(f"{key} ({history_count}/{expected})\n")

        combined_keys = ", ".join(failed_keys)
        combined_history_info = ", ".join(history_details)

        table_data.append([
            hostid,
            hostname,
            combined_keys,
            combined_history_info,
            status
        ])

    #print("\nHosts NOT Collecting Data:\n")

    print(tabulate(
        table_data,
        headers=[
            "HostID",
            "Hostname",
            "Failed Item Keys",
            "History (Actual/Expected)",
            "Data Collection",
                "Status"
        ],
        tablefmt="grid"
    ))
    print("\n\n")



def get_hosts_from_group(zapi, hostgroup_name):
    """
    Get all hosts (hostid and host name) from a given host group.

    :param zapi: Authenticated ZabbixAPI instance
    :param hostgroup_name: Name of the host group
    :return: List of dictionaries with hostid and host
    """
    # Step 1: Get host group ID
    groups = zapi.hostgroup.get(
        filter={"name": [hostgroup_name]},
        output=["groupid", "name"]
    )
    

    if not groups:
        raise ValueError(f"Host group '{hostgroup_name}' not found.")
        

    group_id = groups[0]["groupid"]
    #print(f"Found host group '{hostgroup_name}' with ID: {group_id}")
    print(f"High and Disaster problems in last 7 days and currently active problems")
    #print(f"Using host group ID: {group_id}")
    # Step 2: Get hosts in that group
    hosts = zapi.host.get(
        groupids=group_id,
        output=["hostid", "host","status"]
    )

    return hosts

    
def get_host_problems(zapi, host_id):
    """
    Fetching problems for a specific host, including
    1. All currently active problems
    2. All problems from last 7 days (resolved + active)

    
    """
    #print(f"Fetching problems for host ID: {host_id}")

    # Calculate timestamp for 7 days ago
    time_from = int((datetime.now() - timedelta(days=7)).timestamp())

    try:
        last_7_days_resolveed_problems = zapi.event.get(
            hostids=host_id,
            time_from=time_from,
            value=0, #value =0  problem that were resolved in last 7 days or recovery event
            object=0, #object 0 is trigger
            severities=[4, 5],
            output="extend"
        )
    except Exception as e:
        print(f"Error fetching last 7 days resolved problems for host {host_id}: {e}")
        last_7_days_resolveed_problems = []

    # Get all problems from last 7 days (both active and resolved)
    # Using time_from to filter by time, severities for high/disaster only
    # This will return all problems matching the criteria regardless of current state
    # -----------------------------
    try:
        last_7_days_active_problems = zapi.event.get(
            hostids=host_id,
            time_from=time_from,
            value=1, #value =1  problem that were trigger in last 7 days
            object=0, #object 0 is trigger
            severities=[4, 5],
            output="extend",
            sortfield="eventid",
            sortorder="DESC"
        )

    except Exception as e:
        print(f"Error fetching last 7 days active  problems  for host {host_id}: {e}")
        last_7_days_active_problems = []
    
    # Get currently active problems (r_eventid = 0 means not yet resolved)
    try:
        active_problems = zapi.problem.get(
            hostids=host_id,
            severities=[4, 5],
            recent=True,
            output="extend",
            filter={"r_eventid": "0"},
            sortfield="eventid",
            sortorder="DESC"
        )
    except Exception as e:
        print(f"Error fetching active problems for host {host_id}: {e}")
        active_problems = []

    return {
        "active_problems": active_problems,
        "last_7_days_active_problems": last_7_days_active_problems,
        "last_7_days_resolveed_problems": last_7_days_resolveed_problems
    }


def main():
    # Validate CLI args early so we show helpful usage instead of an IndexError
    if len(sys.argv) < 3:
        print("Usage: python count_problem.py <ENVIRONMENT> <HOSTGROUP_NAME>  # PROD | STG | DEV")
        logging.error("No environment argument provided; exiting.")
        sys.exit(1)

    SCRITP_START_DATE_TIME = datetime.now()

    logging.info(f"_________________SCRIPTING_STARTING_{SCRITP_START_DATE_TIME}________________")

    environment  = sys.argv[1].upper()
    hostgroup_name = sys.argv[2] if len(sys.argv) > 2 else None

    
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
    try:
        zapi = connect(ZABBIX_URL, ZABBIX_API_TOKEN)
    except Exception as e:
        logging.error(f"Error connecting to Zabbix API: {e}")
        sys.exit(1)


    

    uat_hostgroup_name = hostgroup_name.strip()
    print("********************************************************************************")
    #print(f"Fetching hosts for host group: {uat_hostgroup_name}")
    uat_hosts = get_host_from_hostgroup(zapi, uat_hostgroup_name)
    if uat_hosts:
        print(f"Found {len(uat_hosts)} hosts in host group '{uat_hostgroup_name}'")
        print("********************************************************************************")
    for host in uat_hosts:
        print(f" Processing Host ID: {host['hostid']}, Host Name: {host['name']}")
        add_tag_to_host(zapi,host['hostid'], new_tag_with_no_values)
        print("\n")
    host_complete_details = get_all_hosts_details_from_json(zapi, uat_hosts, keys)
    hosts_collecting_data, hosts_with_missing_history = filter_empty_history_hosts(host_complete_details)


    host_collecting_data_message(hosts_collecting_data)
    host_not_collecting_data_message(hosts_with_missing_history)

    hosts = get_hosts_from_group(zapi, hostgroup_name)
    total_active_problems = 0
    total_last_7_days_active_problems = 0
    total_last_7_days_resolved_problems = 0
    #{4:<20} |
    print("\n" + "+" + "-"*15 + "+" + "-"*35 + "+" + "-"*18 + "+" + "-"*30 + "+")
    print("| {0:<13} | {1:<33} | {2:<16} | {3:<28} |".format(
    "Host ID",
    "Hostname",
    "Active Now",
    "Last 7 Days Active + Resolved"
    ))
    print("+" + "-"*15 + "+" + "-"*35 + "+" + "-"*18 + "+" + "-"*30 + "+")

    for host in hosts:
        host_id = host["hostid"]
        hostname = host["host"]
        host_status = host.get("status", "N/A")
        if host_status == "1" or host_status == "N/A":
            #print(f"Skipping host {hostname} (status: {host_status})")
            continue
        problems = get_host_problems(zapi, host_id)
        active_count = len(problems["active_problems"])
        last_7_days_active_problem_count = len(problems["last_7_days_active_problems"])
        last_7_days_resolved_problem_count = len(problems["last_7_days_resolveed_problems"])
        
        total_active_problems += active_count
        total_last_7_days_active_problems += last_7_days_active_problem_count
        total_last_7_days_resolved_problems += last_7_days_resolved_problem_count
        #| {4:<20} |

        print("| {0:<13} | {1:<33} | {2:<16} | {3:<18} |".format(
            host_id,
            hostname[:33],
            active_count,
            last_7_days_active_problem_count
            #,last_7_days_resolved_problem_count
        ))

        print("+" + "-"*15 + "+" + "-"*35 + "+" + "-"*18 + "+" + "-"*20 + "+" )
    print(f"\nTotal Active Problems (High + Disaster): {total_active_problems}")
    #print(f"Total Last 7 Days Active Problems (High + Disaster): {total_last_7_days_active_problems}")
    #print(f"Total Last 7 Days Resolved Problems (High + Disaster): {total_last_7_days_resolved_problems}")
    print(f"Total Last 7 Days Problems (Active + Resolved): {total_last_7_days_active_problems + total_last_7_days_resolved_problems}\n\n")

    #closing the all active problems
    for host in hosts:
        host_id = host["hostid"]
        hostname = host["host"]
        host_status = host.get("status", "N/A")
        if host_status == "1" or host_status == "N/A":
            #print(f"Skipping host {hostname} (status: {host_status})")
            continue
        problems = get_host_problems(zapi, host_id)
        active_problems = problems["active_problems"]

        
        for problem in active_problems:
            event_id = problem.get("eventid")
            try:
                zapi.event.acknowledge(eventids=[event_id],
                                    action = 5, #5 means close the problem and add msg
                                    message="closing the problem  by go-live validation script.")
                print(f"closed problem with Event ID: {event_id} for Host: {hostname}")
                logging.info(f"Closed problem with Event ID: {event_id} for Host: {hostname}")
            except Exception as e:
                print(f"Error closing problem with Event ID: {event_id} for Host: {hostname}: {e}")
                logging.error(f"Error closing problem with Event ID: {event_id} for Host: {hostname}: {e}")
        
        
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error(f"Error running main function: {e}")
        sys.exit(1)