import json
from json.tool import main
from pyzabbix import ZabbixAPI, ZabbixAPIException
import logging
from datetime import datetime
import sys
import os
from CredentialUtils import ZBCredentials

BaseDirectory=os.path.dirname(os.path.realpath(__file__))

json_ci_path = os.path.join(BaseDirectory,"VMs Not Monitored By Zabbix.json")




logging.basicConfig(
    filename='UAThostgroup_create_fromJSON.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
    
logger = logging.getLogger(__name__)




CloudInsights_monitored_VMs = []

def process_VM_details_reportNot_monitoredbyZB():

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


        CI_json_input = {
            "host_name": ci_host_name,
            "portfolio": ci_portfolio,
            "product": ci_product,
            "e2customer_hub": ci_E2customer_Hub,
            "hub_identifier": ci_hub_identifier,
            "ci_hostid":  ci_zb_host_id,
            "ci_host_status" : ci_ZB_status
        }

        CloudInsights_monitored_VMs.append(CI_json_input)

    return CloudInsights_monitored_VMs



    
    
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
                    selectGroups=["groupid"]
                    )

                existing_groups = [{"groupid": g["groupid"]} for g in host[0]["groups"]]

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


def filter_vm_from_json(vm_list):

    return [
        vm for vm in vm_list
        if vm.get("ci_host_status") != -1
        and vm.get("ci_hostid") != -1
        and "asg" not in vm.get("host_name", "").lower()
    ]



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

    
    current_date = datetime.today().strftime("%Y-%m-%d %H:%M:%S")
    print("--------------------Script started at {}---".format(current_date))
    logging.info("--------------------Script started at {}---".format(current_date))


    CloudInsights_monitored_VM_list = process_VM_details_reportNot_monitoredbyZB()
    filtered_vm_from_json = filter_vm_from_json(CloudInsights_monitored_VM_list)
    #print(json.dumps(filtered_vm_from_json, indent= 2))
   


    try:
        zapi = connect(ZABBIX_URL,ZABBIX_API_TOKEN) #2
        print("Connected to Zabbix API Version:", zapi.apiinfo.version())
        logging.info("Connected to Zabbix API Version: %s", zapi.apiinfo.version())
        change_hostgroup_of_host(zapi, filtered_vm_from_json)
    

    except ZabbixAPIException as e:
        print("Zabbix API Exception: %s" % e)

