from asyncio import sleep
import json
from json.tool import main
from pyzabbix import ZabbixAPI, ZabbixAPIException
import logging
from datetime import datetime
import sys
import os
from CredentialUtils import ZBCredentials
from Utils import *

BaseDirectory=os.path.dirname(os.path.realpath(__file__))
log_path=os.path.join(BaseDirectory,"Logs","UAThostgroup_create_fromJSON.log")





logging.basicConfig(
    filename=log_path,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
    
logger = logging.getLogger(__name__)


CloudInsights_monitored_VMs = []

def process_VM_details_reportNot_monitoredbyZB(json_ci_path):

    with open(json_ci_path, "r") as f:
        json_data = json.load(f)
    
    CloudInsights_monitored_VMs = []

    for vm in json_data["data"]:
        ci_host_name = vm.get("ZB_HOST_NAME")
        ci_portfolio = vm.get("Portfolio")
        ci_product = vm.get("Product_Name")
        ci_E2customer_Hub = vm.get("E2Customer")
        ci_hub_identifier = vm.get("HUB_ID")
        ci_ZB_status = vm.get("ZB_STATUS")
        ci_zb_host_id = vm.get("ZB_HOST_ID")
        ci_os_major_version = vm.get("OS_MAJOR_VERSION", "")


        CI_json_input = {
            "host_name": ci_host_name,
            "portfolio": ci_portfolio,
            "product": ci_product,
            "e2customer_hub": ci_E2customer_Hub,
            "hub_identifier": ci_hub_identifier,
            "ci_hostid":  ci_zb_host_id,
            "ci_host_status" : ci_ZB_status,
            "OS_MAJOR_VERSION": ci_os_major_version
        }

        CloudInsights_monitored_VMs.append(CI_json_input)

    return CloudInsights_monitored_VMs


def delete_empty_uat_hostgroups(zapi, old_hostgroup_name):
    try:
        hostgroup = zapi.hostgroup.get(filter={"name": old_hostgroup_name})
        if not hostgroup:
            logging.warning(f"No host uat group found with name to delete: {old_hostgroup_name}")
            return
        hostgroup_id = hostgroup[0]['groupid']
        hosts = zapi.host.get(groupids=hostgroup_id, output=["hostid"])
        if not hosts:
            zapi.hostgroup.delete(hostgroup_id)
            print(f"Deleted empty uat host group: {old_hostgroup_name}")
            logging.info(f"Deleted empty host group: {old_hostgroup_name}")
        else:
            print(f"Host group '{old_hostgroup_name}' is not empty, skipping deletion.")
            logging.info(f"Host group '{old_hostgroup_name}' is not empty, skipping deletion.")
    except ZabbixAPIException as e:
        logging.error(f"Error checking/deleting host group '{old_hostgroup_name}': {e}")


#uat hostgroup fething
def get_child_hostgroups(zapi, parent_group_name):
    all_groups = zapi.hostgroup.get(output=["name"])
 
    child_groups = []
    for group in all_groups:
        group_name = group["name"]
        is_child = group_name.startswith(parent_group_name + "/")
        is_known = "<UNKNOWN>" not in group_name and "UAT/CI-PROD-PRODUCTION/HUB/DISABLE" not in group_name
       
 
        if is_child and is_known:
            child_groups.append(group_name)
 
    return child_groups




    
    
def change_hostgroup_of_host(zapi, filtered_vm_from_json):

    for ci_vms in filtered_vm_from_json:
        #UAT/CI-PROD-PRODUCTION/HUB/<Portfolio>/<Product>/<Hub Identifier>/<E2customer/Hub>
        updated_hostgroup_name = 'UAT/CI-PROD-PRODUCTION/HUB' + '/' + ci_vms['portfolio'] + '/' + ci_vms['product'] + '/' + ci_vms['hub_identifier'] + '/' + ci_vms['e2customer_hub']
        asset_tag_ci = ci_vms['hub_identifier']
        hostid = ci_vms['ci_hostid']
        try:
            group = zapi.hostgroup.get(filter={"name": updated_hostgroup_name})
            if not group:
                print("-"*40)
                print("Host Group '{}' not found. Creating new host group.".format(updated_hostgroup_name))
                logging.info("Host Group '%s' not found. Creating new host group.", updated_hostgroup_name)
                new_group = zapi.hostgroup.create(name=updated_hostgroup_name)
                groupid = new_group['groupids'][0]
                print("Created Host Group '{}' with ID: {}".format(updated_hostgroup_name, groupid))
                logging.info("Created Host Group '%s' with ID: %s", updated_hostgroup_name, groupid)
            else:
                groupid = group[0].get('groupid')
                print("-"*40)
                logging.info("-"*40)
                print("Found Host Group '{}' with ID: {}".format(updated_hostgroup_name, groupid))
                logging.info("Found Host Group '%s' with ID: %s", updated_hostgroup_name, groupid)

            #get existing hostgroup from host, add uat hg and send the payload

            try :
                host = zapi.host.get(
                    hostids=hostid,
                    output=["hostid", "host", "flags"],
                    selectGroups=["groupid","name"]
                    )

                if not host:
                    print(f"Host with ID {hostid} ({ci_vms['host_name']}) not found in Zabbix. Skipping.")
                    logging.warning(f"Host with ID {hostid} ({ci_vms['host_name']}) not found in Zabbix. Skipping.")
                    continue

                # flags=4 means the host was created by a discovery rule; groups cannot be updated
                if host[0].get("flags") == "4":
                    print(f"Host {hostid} ({ci_vms['host_name']}) is a discovered host. Skipping group update.")
                    logging.warning(f"Host {hostid} ({ci_vms['host_name']}) is a discovered host. Skipping group update.")
                    continue

                existing_groups = [{"groupid": g["groupid"]} for g in host[0].get("groups", [])]
                existing_groups_name = [g["name"] for g in host[0].get("groups", [])]

                go_live_group = next((g for g in existing_groups_name if g.startswith("GO-LIVE/")), None)
                if go_live_group:
                    msg = f" Skipping {ci_vms['host_name']}: already in GO-LIVE group '{go_live_group}'"
                    print(msg)
                    logging.info(msg)
                    continue

                if not any(g["groupid"] == groupid for g in existing_groups):
                    existing_groups.append({"groupid": groupid})

                zapi.host.update(
                        hostid=hostid,
                        groups=existing_groups
                    )
                print(f"HOST {hostid} attached to HG : {updated_hostgroup_name}")
                logging.info(f"existing hostgroup of the host : {hostid}  : {existing_groups}")
                logging.info(f"HOST {hostid} attached to HG : {updated_hostgroup_name}")
            except ZabbixAPIException as e:
                print(f"Error while loading host {hostid} to hostgroup {updated_hostgroup_name}: {e}")
                logging.error(f"Error while loading host {hostid} to hostgroup {updated_hostgroup_name}: {e}") 

            try :
               add_assets_tag(zapi,hostid,asset_tag_ci) #call add_assets_tag function to add asset tag
            except ZabbixAPIException as e:
                print(f"Error while loading asset tag for host {hostid} and assettag {asset_tag_ci}: {e}")
        except ZabbixAPIException as e:
            print("Error updating host '{}': {}".format(ci_vms['host_name'], e))
            logging.error("Error updating host '%s': %s", ci_vms['host_name'], e)



        
               

def add_assets_tag(zapi, hostid, asset_tag_ci):
    try:
        # Get the host with inventory details including current asset_tag
        host = zapi.host.get(
            hostids=[hostid],
            output=["hostid", "name"],
            selectInventory=["asset_tag"]
        )
        
        if not host:
            print("Host with ID '{}' not found.".format(hostid))
            logging.warning("Host with ID '%s' not found.", hostid)
            return
        
        host_name = host[0].get('name', 'Unknown')
        
        # Handle inventory as either dict or list
        inventory = host[0].get('inventory', {})
        if isinstance(inventory, list):
            current_asset_tag = inventory[0].get('asset_tag', '') if inventory and isinstance(inventory[0], dict) else ''
        elif isinstance(inventory, dict):
            current_asset_tag = inventory.get('asset_tag', '')
        else:
            current_asset_tag = ''
        
        # If asset_tag is the same as asset_tag_ci, skip
        if current_asset_tag == asset_tag_ci:
            print("Asset tag for host '{}' is already set to '{}'".format(host_name, asset_tag_ci))
            logging.info("Asset tag for host '%s' is already set to '%s'", host_name, asset_tag_ci)
            return
        
        # If asset_tag is different, log it and update
        if current_asset_tag:
            print("Asset tag for host '{}' is changing from '{}' to '{}'".format(host_name, current_asset_tag, asset_tag_ci))
            logging.info("Asset tag for host '%s' is changing from '%s' to '%s'", host_name, current_asset_tag, asset_tag_ci)
        else:
            print("Setting asset tag for host '{}' to '{}'".format(host_name, asset_tag_ci))
            logging.info("Setting asset tag for host '%s' to '%s'", host_name, asset_tag_ci)
        
        # Update the host with the new asset_tag within inventory object
        # Do NOT change inventory_mode to preserve current state (manual/automatic)
        zapi.host.update(
            hostid=hostid,
            inventory={
                'asset_tag': asset_tag_ci
            }
        )
        
        print("Successfully updated asset tag for host '{}' to '{}'".format(host_name, asset_tag_ci))
        logging.info("Successfully updated asset tag for host '%s' to '%s'", host_name, asset_tag_ci)
        
    except ZabbixAPIException as e:
        print("Error updating asset tag for hostid '{}': {}".format(hostid, e))
        logging.error("Error updating asset tag for hostid '%s': %s", hostid, e)



def connect(ZABBIX_URL,ZABBIX_API_TOKEN): #1
    
    zapi = ZabbixAPI(ZABBIX_URL)
    #zapi.session.headers.update({"Authorization": f"Bearer {ZABBIX_API_TOKEN}"})
    #zapi.auth = ZABBIX_API_TOKEN
    #zapi = ZabbixAPI(ZABBIX_URL)
    zapi.login(api_token=ZABBIX_API_TOKEN)
    return zapi

def add_disableHost_to_hostgroup(zapi, hostid, host_name):
    ci_uat_disable_hostgroup_name = 'UAT/CI-PROD-PRODUCTION/HUB/DISABLE'

    try:
        group = zapi.hostgroup.get(filter={"name": ci_uat_disable_hostgroup_name})

        if not group:
            print("-"*40)
            print("Host Group '{}' not found. Creating new host group.".format(ci_uat_disable_hostgroup_name))
            logging.info("Host Group '%s' not found. Creating new host group.", ci_uat_disable_hostgroup_name)
            new_group = zapi.hostgroup.create(name=ci_uat_disable_hostgroup_name)
            uat_disable_hostgroup_id = new_group['groupids'][0]
            print("Created Host Group '{}' with ID: {}".format(ci_uat_disable_hostgroup_name, uat_disable_hostgroup_id))
            logging.info("Created Host Group '%s' with ID: %s", ci_uat_disable_hostgroup_name, uat_disable_hostgroup_id)
        else:
            uat_disable_hostgroup_id = group[0].get('groupid')
            print("-"*40)
            logging.info("-"*40)
            print("Found Host Group '{}' with ID: {}".format(ci_uat_disable_hostgroup_name, uat_disable_hostgroup_id))
            logging.info("Found Host Group '%s' with ID: %s", ci_uat_disable_hostgroup_name, uat_disable_hostgroup_id)
    except ZabbixAPIException as e:
        print("Error while creating/fetching host group '{}': {}".format(ci_uat_disable_hostgroup_name, e))
        logging.error("Error while creating/fetching host group '%s': %s", ci_uat_disable_hostgroup_name, e)
    try :
        host = zapi.host.get(
                hostids=hostid,
                output=["hostid", "host", "flags"],
                selectGroups=["groupid"]
                )

        if not host:
            print(f"Host with ID {hostid} ({host_name}) not found in Zabbix. Skipping.")
            logging.warning(f"Host with ID {hostid} ({host_name}) not found in Zabbix. Skipping.")
            return

        # flags=4 means the host was created by a discovery rule; groups cannot be updated
        if host[0].get("flags") == "4":
            print(f"Host {hostid} ({host_name}) is a discovered host. Skipping group update.")
            logging.warning(f"Host {hostid} ({host_name}) is a discovered host. Skipping group update.")
            return

        existing_groups = [{"groupid": g["groupid"]} for g in host[0].get("groups", [])]

        if any(g["groupid"] == str(uat_disable_hostgroup_id) for g in existing_groups):
            print(f"Host {hostid} ({host_name}) already in DISABLE hostgroup. Skipping.")
            logging.info(f"Host {hostid} ({host_name}) already in DISABLE hostgroup. Skipping.")
            return

        existing_groups.append({"groupid": uat_disable_hostgroup_id})

        zapi.host.update(
                        hostid=hostid,
                        groups=existing_groups
                    )
        print(f"Found DISABLED HOST {hostid} : ({host_name}) attached to HG : {uat_disable_hostgroup_id} UAT/CI-PROD-PRODUCTION/HUB/DISABLE")
        logging.info(f"existing hostgroup of the host : {hostid} : ({host_name})  : {existing_groups}")
        logging.info(f"Found DISABLED HOST {hostid} : ({host_name}) attached to HG : {uat_disable_hostgroup_id} UAT/CI-PROD-PRODUCTION/HUB/DISABLE")
    except ZabbixAPIException as e:
        print(f"Error while loading host {hostid} : ({host_name}) to hostgroup {uat_disable_hostgroup_id} UAT/CI-PROD-PRODUCTION/HUB/DISABLE: {e}")
        logging.error(f"Error while loading host {hostid} : ({host_name}) to hostgroup {uat_disable_hostgroup_id} UAT/CI-PROD-PRODUCTION/HUB/DISABLE: {e}") 




"""
def filter_vm_from_json(vm_list):

    return [
        vm for vm in vm_list
        if vm.get("ci_host_status") != -1
        and vm.get("ci_hostid") != -1
        and "asg" not in vm.get("host_name", "").lower()
    ]
"""

def filter_vm_from_json(vm_list,zapi):
    result = []

    for vm in vm_list:
        #if "<UNKNOWN>" in vm.get("OS_MAJOR_VERSION", ""):
        #    continue
        
        if vm.get("ci_host_status") == -1:
            continue
        if vm.get("ci_hostid") == -1:
            continue
        if "asg" in vm.get("host_name", "").lower():
            continue
        if vm.get("ci_host_status") == 1: #if host is in disabled state in zabbix, add that host to disable hostgroup in zabbix and skip the host from processing for UAT hostgroup
            try:
                add_disableHost_to_hostgroup(zapi, vm.get("ci_hostid"), vm.get("host_name"))
            except ZabbixAPIException as e:
                print(f"Error while adding disabled host {vm.get('ci_hostid')} to disable hostgroup: {e}")
                logging.error(f"Error while adding disabled host {vm.get('ci_hostid')} to disable hostgroup: {e}")
            continue
        
        result.append(vm)
        
    return result




if __name__ == "__main__":
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

    encrypted_file_path = os.path.join(BaseDirectory,"DATA","IN",ENV_FILE_MAP[environment])


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

    
    current_date = datetime.today().strftime("%Y-%m-%d %H:%M:%S")
    print("--------------------Script started at {}---".format(current_date))
    logging.info("--------------------Script started at {}---".format(current_date))

    #__________________Json Integration from sftp_____________________
    config = None

    #elif envType.upper() == "Production".upper(): 
    with open(BaseDirectory + "/Data/IN/" + "SFTP_CONFIG_PROD.json") as f:
        config = json.load(f) 

    configManager = ConfigurationManager(config)

    sftpConfig = configManager.SFTPConfig


    try:
    
        _sftpClient =  SFTPClient(sftpConfig)

        for f in _sftpClient.List("/CI_SFTP/ci-sftp/inbound/Zabbix/Custom Json"):
            logging.info(f"Processing file: {f}")
            _sftpClient.Download("/CI_SFTP/ci-sftp/inbound/Zabbix/Custom Json/" + f, BaseDirectory + "/Data/SFTP_DATA/" + f)
    
    except Exception as e:
        logging.error(e)
        raise(e)

    json_ci_path = os.path.join(BaseDirectory,"Data","SFTP_DATA","VMs Not Monitored By Zabbix.json")
    #_________________________________________________________________



    zapi = connect(ZABBIX_URL,ZABBIX_API_TOKEN) 
    CloudInsights_monitored_VM_list = process_VM_details_reportNot_monitoredbyZB(json_ci_path)
    filtered_vm_from_json = filter_vm_from_json(CloudInsights_monitored_VM_list,zapi)
    #print(json.dumps(filtered_vm_from_json, indent= 2))


   


    try:
        #zapi = connect(ZABBIX_URL,ZABBIX_API_TOKEN) #2
        print("Connected to Zabbix API Version:", zapi.apiinfo.version())
        logging.info("Connected to Zabbix API Version: %s", zapi.apiinfo.version())
        change_hostgroup_of_host(zapi, filtered_vm_from_json)
    

    except ZabbixAPIException as e:
        print("Zabbix API Exception: %s" % e)

    try:
        sleep(5) #wait for 5 seconds before fetching the hostgroups to delete empty uat hostgroups
        child_group=get_child_hostgroups(zapi, "UAT/CI-PROD-PRODUCTION/HUB")
        for uat_old_HG in child_group:
            delete_empty_uat_hostgroups(zapi, uat_old_HG)
    except ZabbixAPIException as e:
        print("Zabbix API Exception while fetching child hostgroups: %s" % e)

