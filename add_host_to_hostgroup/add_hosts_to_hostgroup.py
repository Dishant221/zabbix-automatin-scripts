
import csv
import requests
import json
import logging

CSV_FILE_PATH = "host_list.csv"
ZABBIX_TOKEN = 'REDACTED'
ZABBIX_URL = 'http://192.168.174.128/zabbix/api_jsonrpc.php'

logging.basicConfig(filename='logFile_add_hostgroup.log',
                    filemode='a',
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

ZABBIX_API_URL = ZABBIX_URL
ACCESS_TOKEN = ZABBIX_TOKEN

HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json-rpc"
}


def zabbix_api(method, params):
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1,
    }
    response = requests.post(ZABBIX_API_URL, headers=HEADERS, json=payload)
    result = response.json()
    if "error" in result:
        raise Exception(f"Zabbix API error: {result['error']}")
    return result["result"]


def get_or_create_group_id(group_name):
    result = zabbix_api("hostgroup.get", {
        "output": ["groupid"],
        "filter": {"name": [group_name]}
    })

    if result:
        return result[0]["groupid"]

    # Create host group if not found
    new_group = zabbix_api("hostgroup.create", {"name": group_name})
    logging.info(f"Created new host group: {group_name}")
    return new_group["groupids"][0]


def update_host_groups(host_id, new_group_ids, hostgroup, hostname):
    try:
        # Step 1: Get all host groups with their hosts
        group_result = zabbix_api("hostgroup.get", {
            "output": ["groupid", "name"],
            "selectHosts": ["hostid"]
        })

        existing_group_ids = set()
        for group in group_result:
            for host in group.get("hosts", []):
                if host.get("hostid") == host_id:
                    existing_group_ids.add(group["groupid"])

        # Step 2: Add only new groups (preserving existing)
        combined_group_ids = existing_group_ids.union(new_group_ids)

        # Step 3: Send update
        zabbix_api("host.update", {
            "hostid": host_id,
            "groups": [{"groupid": gid} for gid in combined_group_ids]
        })

        print(f"[UPDATE] Host Name {hostname} assigned to host groups (merged safely): {hostgroup}")
        logging.info(f"[UPDATE] Host Name {hostname} assigned to host groups (merged safely): {hostgroup}")

    except Exception as e:
        print(f"[ERROR] Exception in update_host_groups for {hostname}: {e}")
        logging.error(f"[ERROR] Exception in update_host_groups for {hostname}: {e}")


def add_host_to_hostgroup_by_hostid(hostid, new_group_id, new_group_name):
    try:
        # Fetch host info including name and current groups
        host_info = zabbix_api("host.get", {
            "output": ["hostid", "name"],
            "selectGroups": ["groupid"],
            "hostids": [hostid]
        })

        if not host_info:
            logging.warning(f"Host ID '{hostid}' not found.")
            return "failed"

        hostname = host_info[0].get("name", "Unknown")
        existing_group_ids = {group["groupid"] for group in host_info[0].get("groups", [])}

        if new_group_id in existing_group_ids:
            logging.info(f"Host ID '{hostid}' already in group '{new_group_name}'. Skipping.")
            return "skipped"

        # Use centralized function to update group safely
        update_host_groups(
            host_id=hostid,
            new_group_ids={new_group_id},
            hostgroup=new_group_name,
            hostname=hostname
        )

        return "success"

    except Exception as e:
        logging.error(f"[ERROR] Host ID '{hostid}' failed: {e}")
        return "failed"




def main():
    hostgroup = input("Enter Hostgroup Name: ").strip()

    try:
        new_group_id = get_or_create_group_id(hostgroup)
    except Exception as e:
        print(f"[ERROR] {e}")
        logging.error(f"[ERROR] {e}")
        return

    success, skipped, failed = 0, 0, 0

    try:
        with open(CSV_FILE_PATH, newline='') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                if len(row) == 0:
                    continue
                hostid = row[0].strip()
                try:
                    result = add_host_to_hostgroup_by_hostid(hostid, new_group_id, hostgroup)
                    if result == "success":
                        success += 1
                    elif result == "skipped":
                        skipped += 1
                    else:
                        failed += 1
                except Exception as e:
                    failed += 1
                    logging.error(f"[ERROR] Host ID '{hostid}' failed: {e}")

        print(f"\nSummary:")
        print(f"  ✅ {success} host(s) updated")
        print(f"  ⚠️  {skipped} host(s) already had the group")
        print(f"  ❌ {failed} host(s) failed to update")

    except Exception as e:
        print(f"[ERROR] Failed to process CSV: {e}")
        logging.error(f"[ERROR] Failed to process CSV: {e}")


if __name__ == "__main__":
    main()
