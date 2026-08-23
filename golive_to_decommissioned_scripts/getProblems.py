import requests

# ---- CONFIG ----
ZABBIX_URL = "https://monitor.dev.e2open.com/zabbix/api_jsonrpc.php"
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

def acknowledge_and_close(event_id, message):
    msg_sent = call_zabbix_api("event.acknowledge", {
        "eventids": [event_id],
        "message": message,
        "action": 0  # Just add message
    })
    return msg_sent





def main():
    hostname = input("Enter hostname: ").strip()
    try:
        host_id = get_host_id(hostname)
        if not host_id:
            print(f"❌ Host '{hostname}' not found.")
            return

        problems = get_problems(host_id)
        if not problems:
            print(f"✅ No active problems found for host '{hostname}'.")
            return

        print(f"\n🔍 Found {len(problems)} active problem(s) for host '{hostname}':\n")

        # Build trigger info
        trigger_id_map = {p["objectid"]: p for p in problems}
        trigger_ids = list(trigger_id_map.keys())
        triggers = get_triggers(trigger_ids)
        trigger_info_map = {t["triggerid"]: t for t in triggers}

        # Display problem details
        for i, problem in enumerate(problems, 1):
            event_id = problem["eventid"]
            name = problem.get("name", "Unnamed problem")
            ack = problem.get("acknowledged", "0")
            trigger_id = problem.get("objectid")
            trigger = trigger_info_map.get(trigger_id, {})
            can_close = trigger.get("manual_close", "0")
            trigger_desc = trigger.get("description", "No trigger description")

            print(f"--- Problem {i} ---")
            print(f"🆔 Event ID      : {event_id}")
            print(f"📛 Problem Name  : {name}")
            print(f"🧠 Trigger Desc  : {trigger_desc}")
            print(f"✅ Acknowledged  : {'Yes' if ack == '1' else 'No'}")
            print(f"🔒 Can be closed : {'Yes' if can_close == '1' else '❌ No (manual close disabled)'}\n")

        # Interactive loop
        while True:
            print("\n🔧 Options:")
            print("1. Enter Event ID to acknowledge and close")
            print("2. Exit")

            choice = input("Select an option (1/2): ").strip()
            if choice == "2":
                print("👋 Exiting.")
                break
            elif choice == "1":
                event_id = input("Enter Event ID: ").strip()
                message = input("Enter closing message: ").strip()

                # Check if event_id is valid
                matched_problem = next((p for p in problems if p["eventid"] == event_id), None)
                if not matched_problem:
                    print(f"❌ Event ID {event_id} not found among active problems.")
                    continue

                trigger_id = matched_problem["objectid"]
                trigger = trigger_info_map.get(trigger_id, {})
                can_close = trigger.get("manual_close", "0")

                if can_close != "1":
                     print("❌ Problem cannot be closed because the trigger option \"Allow manual close\" is not enabled.")
                     continue


                try:
                    result= acknowledge_and_close(event_id, message)
                    print(f"msg sent :{result}")
                    print(f"✅ Problem {event_id} acknowledged and closed with message.")
                except Exception as e:
                    print(f"❌ Failed to close problem: {e}")
            else:
                print("⚠️ Invalid option. Please choose 1 or 2.")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
