# pip install pyzabbix

from pyzabbix import ZabbixAPI, ZabbixAPIException
import logging
from datetime import datetime
import os

ZABBIX_URL = "https://monitor.dev.e2open.com/zabbix"  
ZABBIX_API_TOKEN = "REDACTED"

# Configure logging
log_file = os.path.join(os.path.dirname(__file__), 'version2_HG_deletion.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

EXCLUDE_PREFIXES = ("GO-LIVE", "Templates", "TEMPLATES")


def connect():
    logging.info("Connecting to Zabbix API...")
    zapi = ZabbixAPI(ZABBIX_URL)
    zapi.login(api_token=ZABBIX_API_TOKEN)
    return zapi


def get_deletable_hostgroups(zapi):
    groups = zapi.hostgroup.get(
        output=["groupid", "name"],
        selectHosts=["hostid", "name"]
    )

    deletable = []
    for g in groups:
        name = g.get("name", "")
        hosts = g.get("hosts")
        if not hosts and not name.startswith(EXCLUDE_PREFIXES):
            deletable.append({"groupid": g["groupid"], "name": name})
    return deletable


def ask_selection(items):
    if not items:
        print("No hostgroups found for deletion.")
        return []

    print("Hostgroups eligible for deletion:")
    for i, g in enumerate(items, 1):
        print(f"{i}. groupid: {g['groupid']}, name: {g['name']}")

    raw = input("Enter numbers (comma separated) to delete: ").strip()
    if not raw:
        return []

    nums = set()
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            nums.add(int(part))
    chosen = [g for i, g in enumerate(items, 1) if i in nums]

    if not chosen:
        print("No valid selection provided. No hostgroups will be deleted.")
        return []

    print("\nYou selected:")
    for i, g in enumerate(items, 1):
        if i in nums:
            print(f"{i}. groupid: {g['groupid']}, name: {g['name']}")

    confirm = input("\nAre you sure you want to delete ALL the above hostgroups? (yes/no): ").strip().lower()
    if confirm not in ("yes", "y"):
        print("Deletion cancelled.")
        return []

    return chosen


def delete_hostgroups(zapi, groups):
    for g in groups:
        try:
            logging.info(f"Attempting to delete hostgroup: groupid={g['groupid']}, name={g['name']}")
            zapi.hostgroup.delete(g["groupid"])
            logging.info(f"Successfully deleted hostgroup: groupid={g['groupid']}, name={g['name']}")
            print(f"Deleted hostgroup: groupid={g['groupid']}, name={g['name']}")
        except ZabbixAPIException as e:
            print(f"Failed to delete groupid={g['groupid']} ({g['name']}): {e}")


def main():
    logging.info("Script started")
    try:
        zapi = connect()
        deletable = get_deletable_hostgroups(zapi)
        chosen = ask_selection(deletable)
        if chosen:
            delete_hostgroups(zapi, chosen)
    except ZabbixAPIException as e:
        print(f"Zabbix API error: {e}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
