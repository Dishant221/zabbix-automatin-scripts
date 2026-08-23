
#____________________________________PREDEFINE VALUES_______________________________________________
ControlledAccess_tag='{INVENTORY.SOFTWARE.APP.D}'
CustomerCategory_tag='{INVENTORY.SOFTWARE.APP.C}'
Hub_tag ='{INVENTORY.TYPE.FULL}'

# This script should be use only to add the tags not to update tags

CSV_FILE_PATH = "hosts.csv" 
DEV_ZABBIX_TOKEN = 'REDACTED'
DEV_ZABBIX_URL = 'https://monitor.dev.e2open.com/zabbix/api_jsonrpc.php'

hostname_format = '.dev.e2open.com'


#________________________________________________________________________________________________________

import csv
import requests
import json


predefined_values = {
    'ControlledAccess': ControlledAccess_tag,
    'CustomerCategory': CustomerCategory_tag,
    'Hub': Hub_tag
}




ZABBIX_API_URL = DEV_ZABBIX_URL
ACCESS_TOKEN = DEV_ZABBIX_TOKEN



HEADERS = headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json-rpc"  # Optional, depending on API requirements
    }

REQUIRED_TAGS_CHECK = { 
                  
                 "SFID", 
                 "JID", 
                 "USER", 
                 "SOLUTION", 
                 "SuppressedBy"}





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

def get_hostgroup_id(name):
    result = zabbix_api("hostgroup.get", {"filter": {"name": [name]}})
    return result[0]["groupid"] if result else None

def create_hostgroup(hostname,hostgroup):
    gid = get_hostgroup_id(hostgroup)
    if gid:
        print(f"[INFO] Host group '{hostgroup}' already exists in host : {hostname}.")
        return gid
    result = zabbix_api("hostgroup.create", {"name": hostgroup})
    print(f"[CREATE] Host group '{hostgroup}' created.")
    return result["groupids"][0]

def get_host_id(hostname):
    result = zabbix_api("host.get", {"filter": {"host": [hostname]}})
    return result[0]["hostid"] if result else None

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
        print()

        # Step 3: Send update
        zabbix_api("host.update", {
            "hostid": host_id,
            "groups": [{"groupid": gid} for gid in combined_group_ids]
        })

        print(f"[UPDATE] Host Name {hostname} assigned to host groups (merged safely): {hostgroup}")

    except Exception as e:
        print(f"[ERROR] Exception in update_host_groups for {hostname}: {e}")



def update_asset_tag(host_id, asset_tag,hostname):
    zabbix_api("host.update", {
        "hostid": host_id,
        "inventory_mode": 1,  # enable manual inventory
        "inventory": {
            "asset_tag": asset_tag
        }
    })
    print(f"[UPDATE] Host Name {hostname} asset tag set to: {asset_tag}")

def process_host_row(hostgroup, tag, _, asset_tag, hostname):
    

    if not hostname.endswith(hostname_format):
        hostname += hostname_format
        #print(type(hostname))
    host_id = get_host_id(hostname)

    if not host_id:
        print("________________________________________________________________________")
        print(f"[NOT FOUND] Host '{hostname}' does not exist in Zabbix. Skipping...\n")
        print("________________________________________________________________________")
        return

    #Create or get the host group
    group_id = create_hostgroup(hostname,hostgroup)

    #Update host group (without removing existing ones)
    update_host_groups(host_id, [group_id], hostgroup, hostname)

    #Update inventory asset tag
    update_asset_tag(host_id, asset_tag, hostname)

    #Check and assign missing tags
    check_tags(hostname, host_id)

def check_tags(hostname, hostid):
    result = zabbix_api("host.get", {
        "output": ["hostid"],
        "selectTags": "extend",
        "filter": {"host": [hostname]}
    })

    if not result:
        print(f"[ERROR] Could not retrieve tags for host '{hostname}'.")
        return

    existing_tags = result[0].get("tags", [])
    existing_tag_keys = {tag['tag'] for tag in existing_tags}

    # Tags that must exist (but with empty values)
    missing_required = REQUIRED_TAGS_CHECK - existing_tag_keys
    missing_required_tags = [{"tag": tag, "value": ""} for tag in missing_required]

    # Tags that must exist with specific values
    missing_predefined_tags = []
    for tag, value in predefined_values.items():
        if tag not in existing_tag_keys:
            missing_predefined_tags.append({"tag": tag, "value": value})

    if not missing_required_tags and not missing_predefined_tags:
        print(f"[OK] Host '{hostname}' already has all required tags.")
        print("_____________________________________________________________")
        return

    # Merge existing and new tags, avoiding duplicates
    updated_tags = existing_tags + missing_required_tags + missing_predefined_tags

    # Remove duplicates by tag key (keep last occurrence — which will be the new value)
    tag_map = {}
    for tag in updated_tags:
        tag_map[tag['tag']] = tag['value']
    final_tags = [{"tag": k, "value": v} for k, v in tag_map.items()]

    # Now update the host with the full tag list
    assign_tag(hostname,hostid, final_tags)

def assign_tag(hostname,hostid, all_tags):
    try:
        result = zabbix_api("host.update", {
            "hostid": hostid,
            "tags": all_tags
        })
        print(f"[UPDATE] Tags updated successfully for host ID {hostname}")
        print("_______________________________________________________________")
    except Exception as e:
        print(f"[ERROR] Failed to update tags for host ID {hostname}: {e}")
        print("_______________________________________________________________")

 
 

     



def main():
    csv_path = CSV_FILE_PATH  # 🔁 Update this to the actual file path
    try:
        with open(csv_path, newline='') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                if len(row) != 5:
                    print(f"[SKIP] Malformed row: {row}")
                    continue

                process_host_row(*row)

    except Exception as e:
        print(f"[ERROR] An error occurred while reading the CSV: {e}")


if __name__ == "__main__":
    main()




"""

[CREATE] Host group 'UAT/SCPM/DELL-AGDS' created.

[UPDATE] Host Name dev3571.dev.e2open.com assigned to host groups (merged safely): UAT/SCPM/DELL-AGDS
[UPDATE] Host Name dev3571.dev.e2open.com asset tag set to: HUB00000737
[UPDATE] Tags updated successfully for host ID dev3571.dev.e2open.com
_______________________________________________________________
[INFO] Host group 'UAT/SCPM/DELL-AGDS' already exists in host : dev3572.dev.e2open.com.

[UPDATE] Host Name dev3572.dev.e2open.com assigned to host groups (merged safely): UAT/SCPM/DELL-AGDS
[UPDATE] Host Name dev3572.dev.e2open.com asset tag set to: HUB00000737
[UPDATE] Tags updated successfully for host ID dev3572.dev.e2open.com
_______________________________________________________________
[INFO] Host group 'UAT/SCPM/DELL-AGDS' already exists in host : dev3573.dev.e2open.com.

[UPDATE] Host Name dev3573.dev.e2open.com assigned to host groups (merged safely): UAT/SCPM/DELL-AGDS
[UPDATE] Host Name dev3573.dev.e2open.com asset tag set to: HUB00000737
[UPDATE] Tags updated successfully for host ID dev3573.dev.e2open.com
_______________________________________________________________

"""