#___________________________________________NOTE_______________________________________________________

# Note for csv formet
"""
1> CSV file should be in this format
2> Host should have respective hostgroup in same record in csv
3> Format : hostgroup,scpm,client,assetid,host
UAT/SCPM/DELL-AGDS,SCPM,Dell-aGDS,HUB00000737,dev3571
UAT/SCPM/DELL-AGDS,SCPM,Dell-aGDS,HUB00000737,dev3572
UAT/SCPM/DELL-AGDS,SCPM,Dell-aGDS,HUB00000737,dev3573


# Note for predefine tag
# This script does not update tag, it just adds tags
1> ControlledAccess, CustomerCategory, Hub tags values can be updated if you want.
2> To change the values of predefine tag you need to update below in PREDEFINE VALUES section


"""
#____________________________________How to run this script________________________________
"""
1> check csv is in correct format
2> csv should be same folder as this script
3> check PREDEFINE VALUES and TAGS below (line number: 33,34,35) 
4> REQUIRED_TAGS_CHECK tag (line number: 72) should be empty values
5> command to run : python script_name.py

"""

#____________________________________PREDEFINE VALUES_______________________________________________
ControlledAccess_tag='{INVENTORY.SOFTWARE.APP.D}'
CustomerCategory_tag='{INVENTORY.SOFTWARE.APP.C}'
Hub_tag ='{INVENTORY.TYPE.FULL}'



CSV_FILE_PATH = "hosts.csv" 
DEV_ZABBIX_TOKEN = 'REDACTED'
DEV_ZABBIX_URL = 'http://192.168.65.130/zabbix/api_jsonrpc.php'


#________________________________________________________________________________________________________

import csv
import requests
import json
import sys
import logging

logging.basicConfig(filename='logFile_check_host_group_assettag.log',
                    filemode='a',
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

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
        print(f"[INFO] Host group '{hostgroup}' already exists.")
        logging.info("[INFO] Host group '{hostgroup}' already exists.")
        return gid
    result = zabbix_api("hostgroup.create", {"name": hostgroup})
    print(f"[CREATE] Host group '{hostgroup}' created.")
    logging.info(f"[CREATE] Host group '{hostgroup}' created.")

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
        

        # Step 3: Send update
        zabbix_api("host.update", {
            "hostid": host_id,
            "groups": [{"groupid": gid} for gid in combined_group_ids]
        })

        print(f"[UPDATE] Host Name {hostname} assigned to host groups (merged safely): {hostgroup}")
        logging.info(f"[UPDATE] Host Name {hostname} assigned to host groups (merged safely): {hostgroup}")

    except Exception as e:
        print(f"[ERROR] Exception in update_host_groups for {hostname}: {e}")
        logging.info(f"[ERROR] Exception in update_host_groups for {hostname}: {e}")



def update_asset_tag(host_id, asset_tag,hostname):
    zabbix_api("host.update", {
        "hostid": host_id,
        "inventory_mode": 0,  # enable manual inventory
        "inventory": {
            "asset_tag": asset_tag
        }
    })
    print(f"[UPDATE] Host Name {hostname} asset tag set to: {asset_tag}")
    logging.info(f"[UPDATE] Host Name {hostname} asset tag set to: {asset_tag}")

def with_parameter(hostgroup,tag,asset_tag,hostname,domainInput):
    domain_lower_hostname = hostname + domainInput
    domain_upper_hostname = hostname.upper() + domainInput
    if get_host_id(domain_lower_hostname):
        # for case prod1122.stage.e2open.com
        host_id = get_host_id(domain_lower_hostname)
        group_id = create_hostgroup(domain_lower_hostname,hostgroup)
        update_host_groups(host_id, [group_id], hostgroup, domain_lower_hostname)
        update_asset_tag(host_id, asset_tag, domain_lower_hostname)
        check_tags(domain_lower_hostname, host_id)
    elif get_host_id(domain_upper_hostname):
        #for case  PROD1122.stage.e2open.com
        host_id = get_host_id(domain_upper_hostname)
        group_id = create_hostgroup(domain_upper_hostname,hostgroup)
        update_host_groups(host_id, [group_id], hostgroup, domain_upper_hostname)
        update_asset_tag(host_id, asset_tag, domain_upper_hostname)
        check_tags(domain_upper_hostname, host_id)
    else:
        print("________________________________________________________________________")
        logging.info("________________________________________________________________________")
        print(f"[NOT FOUND] Host '{hostname}' does not exist in Zabbix. Skipping...\n")
        logging.info(f"[NOT FOUND] Host '{hostname}' does not exist in Zabbix. Skipping...\n")
        print("________________________________________________________________________")
        logging.info("________________________________________________________________________")

def without_parameter(hostgroup,tag,asset_tag,hostname):
    if get_host_id(hostname):
        # for case prod1122
        host_id = get_host_id(hostname)
        group_id = create_hostgroup(hostname,hostgroup)
        update_host_groups(host_id, [group_id], hostgroup, hostname)
        update_asset_tag(host_id, asset_tag, hostname)
        check_tags(hostname, host_id)
    elif get_host_id(hostname.upper()):
        #for case PROD1122
        upper_hostname = hostname.upper()
        host_id = get_host_id(upper_hostname)
        group_id = create_hostgroup(upper_hostname,hostgroup)
        update_host_groups(host_id, [group_id], hostgroup, upper_hostname)
        update_asset_tag(host_id, asset_tag, upper_hostname)
        check_tags(upper_hostname, host_id)
    else:
        print("________________________________________________________________________")
        logging.info("________________________________________________________________________")
        print(f"[NOT FOUND] Host '{hostname}' does not exist in Zabbix. Skipping...\n")
        logging.info(f"[NOT FOUND] Host '{hostname}' does not exist in Zabbix. Skipping...\n")
        print("________________________________________________________________________")
        logging.info("________________________________________________________________________")

def process_host_row(hostgroup, tag, _, asset_tag, hostname):
    
    domainInput = sys.argv[1]
    #cases prod1122, PROD1122, prod1122.stage.e2open.com, PROD1122.stage.e2open.com

    if domainInput:
        with_parameter(hostgroup,tag,asset_tag,hostname,domainInput)
    else:
        without_parameter(hostgroup,tag,asset_tag,hostname)





    #_________________________________________________________________________
    ''' 
    domainInput = sys.argv[1]
    upper_hostname = hostname.upper()
    #if not hostname.endswith(hostname_format):
    hostname += domainInput
    host_id = get_host_id(hostname)

    if not host_id:
        upper_hostname += domainInput
        host_id = get_host_id(upper_hostname)
        if host_id:
            hostname = upper_hostname
            print(hostname)
            group_id = create_hostgroup(hostname,hostgroup)
            update_host_groups(host_id, [group_id], hostgroup, hostname)
            update_asset_tag(host_id, asset_tag, hostname)
            check_tags(hostname, host_id)
        else:
            print("________________________________________________________________________")
            logging.info("________________________________________________________________________")
            print(f"[NOT FOUND] Host '{hostname}' does not exist in Zabbix. Skipping...\n")
            logging.info(f"[NOT FOUND] Host '{hostname}' does not exist in Zabbix. Skipping...\n")
            print("________________________________________________________________________")
            logging.info("________________________________________________________________________")
        return
    group_id = create_hostgroup(hostname,hostgroup)
    update_host_groups(host_id, [group_id], hostgroup, hostname)
    update_asset_tag(host_id, asset_tag, hostname)
    check_tags(hostname, host_id)
'''

def check_tags(hostname, hostid):
    result = zabbix_api("host.get", {
        "output": ["hostid"],
        "selectTags": "extend",
        "filter": {"host": [hostname]}
    })

    if not result:
        print(f"[ERROR] Could not retrieve tags for host '{hostname}'.")
        logging.info(f"[ERROR] Could not retrieve tags for host '{hostname}'.")
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
        logging.info(f"[OK] Host '{hostname}' already has all required tags.")
        print("_____________________________________________________________")
        logging.info("_____________________________________________________________")
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
        logging.info(f"[UPDATE] Tags updated successfully for host ID {hostname}")
        print("_______________________________________________________________")
        logging.info("_______________________________________________________________")
    except Exception as e:
        print(f"[ERROR] Failed to update tags for host ID {hostname}: {e}")
        logging.info(f"[ERROR] Failed to update tags for host ID {hostname}: {e}")
        print("_______________________________________________________________")
        logging.info("______________________________________________________________")

 
 

#_____________________________________MAIN___________________________________________________     



def main():
    csv_path = CSV_FILE_PATH  # 🔁 Update this to the actual file path
    try:
        with open(csv_path, newline='') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                if len(row) != 5:
                    print(f"[SKIP] Malformed row: {row}")
                    logging.info(f"[SKIP] Malformed row: {row}")
                    continue

                process_host_row(*row)

    except Exception as e:
        print(f"[ERROR] An error occurred while reading the CSV: {e}")
        logging.info(f"[ERROR] An error occurred while reading the CSV: {e}")


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