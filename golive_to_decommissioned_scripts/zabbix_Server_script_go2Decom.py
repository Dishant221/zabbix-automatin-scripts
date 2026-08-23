
# ---- CONFIG ----
ZABBIX_URL = "https://monitor.staging.e2open.com/zabbix/api_jsonrpc.php"
ZABBIX_API_TOKEN = "REDACTED"

logfilePATH = '/usr/lib/zabbix/externalscripts/e2beat_utils/zabbix_Server_script_go2Decom.log'

import requests
from datetime import datetime
import sys
import logging



logging.basicConfig(filename=logfilePATH,
                    filemode='a',
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

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
    result = response.json()
    if 'error' in result:
        raise Exception(f"Zabbix API Error: {result['error']}")
    return result['result']

def get_host_id(hostname):
    result = call_zabbix_api("host.get", {
        "filter": {"host": [hostname]},
        "output": ["hostid"]
    })
    return result[0]["hostid"] if result else None

def get_problems(host_id):
    return call_zabbix_api("problem.get", {
        "output": ["eventid", "name", "acknowledged", "objectid"],
        "hostids": [host_id],
        "source": 0,
        "object": 0
    })

def get_triggers(trigger_ids):
    return call_zabbix_api("trigger.get", {
        "triggerids": trigger_ids,
        "output": ["triggerid", "description", "manual_close"]
    })

def add_message_and_close(event_id, message):
    return call_zabbix_api("event.acknowledge", {
        "eventids": [event_id],
        "message": message,
        "action": 5  # 1 (close) + 4 (add message), no ack
    })

def get_host_by_name(hostname):
    # Step 1: Get hostid
    host_result = call_zabbix_api("host.get", {
        "filter": {"host": [hostname]},
        "output": ["hostid"]
    })

    if not host_result:
        print(f"❌ Host '{hostname}' not found.")
        return None

    hostid = host_result[0]["hostid"]

    # Step 2: Get group info separately
    groups = call_zabbix_api("hostgroup.get", {
        "hostids": hostid,
        "output": ["groupid", "name"]
    })

    host = {
        "hostid": hostid,
        "groups": groups
    }

    #print(f"\n🔍 DEBUG: Merged host and group info:\n{host}\n")
    return host

def get_group_by_name(group_name):
    result = call_zabbix_api("hostgroup.get", {
        "filter": {"name": [group_name]},
        "output": ["groupid", "name"]
    })
    return result[0] if result else None

def create_group(group_name):
    result = call_zabbix_api("hostgroup.create", {
        "name": group_name
    })
    return {"groupid": result["groupids"][0], "name": group_name}

def update_host_groups(hostid, groupids):
    return call_zabbix_api("host.update", {
        "hostid": hostid,
        "groups": [{"groupid": gid} for gid in groupids]
    })

def update_host_description(hostid, new_entry):
    # Step 1: Get current description
    result = call_zabbix_api("host.get", {
        "hostids": [hostid],
        "output": ["description"]
    })

    current_desc = result[0].get("description", "").strip() if result else ""

    # Step 2: Append new entry as a new line
    if current_desc:
        updated_desc = f"{current_desc}\n{new_entry}"
    else:
        updated_desc = new_entry

    # Step 3: Update host with new description
    call_zabbix_api("host.update", {
        "hostid": hostid,
        "description": updated_desc
    })

    print("✅ Host description updated.")
    logging.info(f"✅ Host description updated to:\n{updated_desc}")



def disable_host(host_id):
    call_zabbix_api("host.update", {
        "hostid": host_id,
        "status": 1  # 1 = disabled
    })
def process_host_groups(hostname):
    host = get_host_by_name(hostname)
    if not host:
        print(f"❌ Host '{hostname}' not found.")
        logging.info(f"❌ Host '{hostname}' not found.")
        return

    hostid = host['hostid']
    original_groups = host.get('groups', [])

    if not original_groups:
        print(f"❌ Host '{hostname}' has no groups assigned.")
        logging.error(f"❌ Host '{hostname}' has no groups assigned.")
        return

    updated_groupids = []
    has_golive = False
    has_decommissioned = any(g['name'].startswith("DECOMMISSIONED") for g in original_groups)

    for group in original_groups:
        group_name = group['name']
        if group_name.startswith("GO-LIVE/"):
            has_golive = True
            hubname = group_name.split("GO-LIVE/")[1]
            new_group_name = f"DECOMMISSIONED/{hubname}"

            new_group = get_group_by_name(new_group_name)
            if not new_group:
                new_group = create_group(new_group_name)
                print(f"✅ Created new group: {new_group_name}")
                logging.info(f"✅ Created new group: {new_group_name}")

            updated_groupids.append(new_group['groupid'])
        else:
            # Keep existing non-GO-LIVE groups
            updated_groupids.append(group['groupid'])

    if has_golive:
        # Case 1: GO-LIVE exists → switch to DECOMMISSIONED/<hub>
        update_host_groups(hostid, updated_groupids)
        print(f"✅ GO-LIVE group(s) replaced with DECOMMISSIONED for host '{hostname}'.")
        logging.info(f"✅ GO-LIVE group(s) replaced with DECOMMISSIONED for host '{hostname}'.")

    elif not has_decommissioned:
        # Case 2: No GO-LIVE and no DECOMMISSIONED → add generic DECOMMISSIONED
        generic_group = get_group_by_name("DECOMMISSIONED")
        if not generic_group:
            generic_group = create_group("DECOMMISSIONED")
            print("✅ Created group: DECOMMISSIONED")
            logging.info("✅ Created group: DECOMMISSIONED")

        updated_groupids = [g['groupid'] for g in original_groups]
        updated_groupids.append(generic_group['groupid'])

        update_host_groups(hostid, updated_groupids)
        print(f"✅ Added generic DECOMMISSIONED group to host '{hostname}'.")
        logging.info(f"✅ Added generic DECOMMISSIONED group to host '{hostname}'.")

    else:
        # Case 3: No GO-LIVE but DECOMMISSIONED exists → do nothing
        print("ℹ️ DECOMMISSIONED group already present. No changes made.")
        logging.info(f"ℹ️ Host '{hostname}' already has DECOMMISSIONED group. No changes made.")


def main():
    #hostname = input("Enter Hostname: ").strip()
    #ticket = input("Enter Ticket Number: ").strip()
    #executor = input("Enter Your Name: ").strip()
    hostname = sys.argv[1]
    ticket = sys.argv[2]
    executor = sys.argv[3]
    message = "DECOMMISSIONED request"
    today = datetime.now().strftime("%d%b%Y")

    try:
        host_id = get_host_id(hostname)
        if not host_id:
            print(f"❌ Host '{hostname}' not found.")
            logging.info(f"❌ Host '{hostname}' not found.")
            return

        # Step 1: List and process problems
        problems = get_problems(host_id)
        if not problems:
            print("✅ No active problems found.")
            logging.info("✅ No active problems found.")
        else:
            print(f"\n🔍 {len(problems)} active problem(s) found for host '{hostname}':\n")
            logging.info(f"\n🔍 {len(problems)} active problem(s) found for host '{hostname}':\n")
            trigger_ids = [p["objectid"] for p in problems]
            triggers = get_triggers(trigger_ids)
            trigger_info_map = {t["triggerid"]: t for t in triggers}

            for i, problem in enumerate(problems, 1):
                event_id = problem["eventid"]
                name = problem.get("name", "Unnamed problem")
                trigger = trigger_info_map.get(problem["objectid"], {})
                desc = trigger.get("description", "No trigger description")
                can_close = trigger.get("manual_close", "0")

                print(f"--- Problem {i} ---")
                logging.info(f"--- Problem {i} ---")
                print(f"🆔 Event ID     : {event_id}")
                logging.info(f"🆔 Event ID     : {event_id}")
                print(f"📛 Problem Name : {name}")
                logging.info(f"📛 Problem Name : {name}")
                print(f"🧠 Description  : {desc}")
                logging.info(f"🧠 Description  : {desc}")
                print(f"🔒 Can Close    : {'Yes' if can_close == '1' else '❌ No'}")
                logging.info(f"🔒 Can Close    : {'Yes' if can_close == '1' else '❌ No'}")

                if can_close == "1":
                    add_message_and_close(event_id, message)
                    print(f"✅ Message added & problem closed.")
                    logging.info(f"✅ Message added & problem closed.")

                else:
                    print("⚠️ Cannot close: Trigger is not set for manual close.")
                    logging.info("⚠️ Cannot close: Trigger is not set for manual close.")

        # Step 2: Group update
        process_host_groups(hostname)

        # Step 3: Description update
        full_desc = f"Disabled_{ticket}_{executor}_{today}"
        update_host_description(host_id, full_desc)

        print("✅ Host description updated.")
        logging.info("✅ Host description updated.")

        # Step 4: Disable host
        disable_host(host_id)
        print("✅ Host disabled.")
        logging.info("✅ Host disabled.")

    except Exception as e:
        print(f"❌ Error: {e}")
        logging.info(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
