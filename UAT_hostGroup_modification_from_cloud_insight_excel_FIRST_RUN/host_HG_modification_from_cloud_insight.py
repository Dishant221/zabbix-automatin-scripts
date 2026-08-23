import json
from json.tool import main
import pylightxl as xl
from pyzabbix import ZabbixAPI, ZabbixAPIException
import logging
from datetime import datetime
import sys
import os
from CredentialUtils import ZBCredentials

BaseDirectory=os.path.dirname(os.path.realpath(__file__))

xl_file_path = os.path.join(BaseDirectory,"DATA","INPUT","VM_details_report-not_monitoredbyZB-10-Dec-25.xlsx")  

db = xl.readxl(fn=xl_file_path, ws='VM details report - not monitor')

searching_hostGroup_name = 'UAT/CI-PROD-PRODUCTION/ENABLED'



logging.basicConfig(
    filename='hostgroup_modify_from_cloud_insight.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

#column list and sequence reference
'''
['DC', 'vCenter/Account', 'Cluster/Region', 'Host/AVZ', 'Name', 'Power State', 'DB Server ?', 'Environment', 'Purpose',
 'Account', 'E2customer/Hub', 'Hub Identifier', 'Hub Type', 'Hub IsActive?', 'Hub Status', 'Hub State', 'CI Solution', 
 'Department', 'Requested by', 'HW Request', 'Provisioned by', 'Created On', 'CSM', 'ESE', 'OS Family', 'OS', 'OS Major Version',
   'Released On', 'EOL ON', 'IS EOL?', 'EOL Age', 'EOL Age Range', 'VMware Tools Version', 'VMware Tools Status', 'DNS Name', 'Vm Fqdn',
     'R7 Monitored?', 'ZB Monitored?', 'Usage', 'IS R7 LastScan Date', 'AV Installed?', 'Cylance Monitored?', 'CB Monitored?', 'CS Monitored?',
       'OS Provenance', 'Record CollectionTS', 'Shutdown Date', 'Shutdown Days', 'Metrics', '#vCores', 'Memory-GB', 'Storage-GB', 'Storage-Used-GB', 
       'Resource Point', 'VM-STATS-Memory-Used-%', 'VM-STATS-CPU-Used-%', 'VM-STATS-Memory-Consumed-GB', 'VM-STATS-Memory-Overhead-GB', 'VM R7 Risk Score', 
       'VM Used Space (TB)', 'VM provisioned Space (TB)', 'IS R7 Critical', 'IS R7 Exploits', 'IS R7 Malwarekits', 'IS R7 Moderate', 'IS R7 Severe', 'Shutdown Days']
'''


CloudInsights_monitored_VMs = []

 
def process_excel_VM_details_reportNot_monitoredbyZB():
    for row in db.ws(ws='VM details report - not monitor').rows:
        ci_host_name = row[4]
        ci_ENV = row[7]
        ci_Env_purpose = row[8]
        ci_E2customer_Hub = row[10]
        ci_hub_type= row[12]
        ci_hub_identifier = row[11]
        CI_json_input = {
            "host_name": ci_host_name,
            "environment": ci_ENV,
            "env_purpose": ci_Env_purpose,
            "e2customer_hub": ci_E2customer_Hub,
            "hub_type": ci_hub_type,
            "hub_identifier": ci_hub_identifier
        }
        CloudInsights_monitored_VMs.append(CI_json_input)
    return CloudInsights_monitored_VMs


def get_host_from_zabbix_HG(zapi):
    hostsIN_HG = []

    group = zapi.hostgroup.get(filter={"name": searching_hostGroup_name})
    #print(group)
    if not group:
        print("Host Group '{}' not found.".format(searching_hostGroup_name))
        return
    groupid = group[0].get('groupid')
    print("Group ID:", groupid)


    try:
        hosts = zapi.host.get(
            output=["hostid","name","host","status"],
            groupids=[groupid],
            selectGroups=["groupid","name"]
        )
        #print(json.dumps(hosts, indent=4))
    except ZabbixAPIException as e:
        print("host.get raised ZabbixAPIException:", e)
        logging.error("host.get raised ZabbixAPIException: %s", e)
        return

    for host in hosts:
        hostsIN_HG.append(host)
    print("Total Hosts in Host Group '{}': {}".format(searching_hostGroup_name, len(hostsIN_HG)))
    logging.info("Total Hosts in Host Group '%s': %d", searching_hostGroup_name, len(hostsIN_HG))
    #print(json.dumps(hostsIN_HG, indent=4))
    return hostsIN_HG

def seperate_common_VMs(CloudInsights_monitored_VM_list, Zabbix_monitored_VM_list):
    common_VMs = []
    ci_only_VMs = []
    zb_only_VMs = []

    ci_vm_names = {vm['host_name'].lower() for vm in CloudInsights_monitored_VM_list}
    zb_vm_names = {vm['host'].split('.', maxsplit=1)[0] for vm in Zabbix_monitored_VM_list}

    for vm in CloudInsights_monitored_VM_list:
        if vm['host_name'].lower() in [zb_vm_name.lower() for zb_vm_name in zb_vm_names]:
            common_VMs.append(vm)
        else:
            ci_only_VMs.append(vm)

    for vm in Zabbix_monitored_VM_list:
        print(vm['host'])
        if vm['host'].split('.', maxsplit=1)[0].lower() in ci_vm_names:
            zb_only_VMs.append(vm)

    return common_VMs, ci_only_VMs, zb_only_VMs
    
    
def change_hostgroup_of_host(zapi,ci_common_VMs,zb_only_VMs):

    for ci_vms in ci_common_VMs:
        updated_hostgroup_name = 'UAT/CI-PROD-PRODUCTION/HUB' + '/' + ci_vms['hub_type'] + '/' + ci_vms['hub_identifier'] + '/' + ci_vms['e2customer_hub']
        asset_tag_ci = ci_vms['hub_identifier']
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

        except ZabbixAPIException as e:
            print("Error updating host '{}': {}".format(ci_vms['host_name'], e))
            logging.error("Error updating host '%s': %s", ci_vms['host_name'], e)

        for zb_vm in zb_only_VMs:
            zb_vm_name_only = zb_vm['host'].split('.', maxsplit=1)[0]
            zb_vm_fqdn = zb_vm['host']
            #print("Processing Zabbix VM: ", zb_vm_name_only)
            #adding new host group to the host
            if ci_vms['host_name'].lower() == zb_vm_name_only.lower():
                add_assets_tag(zapi,zb_vm['hostid'],asset_tag_ci) #call add_assets_tag function to add asset tag
                zb_vm_Hostgroups = zb_vm['groups']
                updated_groups = []
                for hg in zb_vm_Hostgroups:
                    if hg['name'].startswith('UAT/CI-PROD-PRODUCTION/ENABLED'):
                        # Replace with new group ID only (no 'name' field)
                        updated_groups.append({'groupid': groupid})
                    else:
                        # Keep other groups with only groupid (remove 'name' field)
                        updated_groups.append({'groupid': hg['groupid']})
                try:
                    zapi.host.update(
                        hostid=zb_vm['hostid'],
                        groups=updated_groups
                    )
                    print("Updated host '{}' to new host group '{}'".format(ci_vms['host_name'], updated_hostgroup_name))
                    print("-"*40)
                    logging.info("Updated host '%s' to new host group '%s'", ci_vms['host_name'], updated_hostgroup_name)
                    logging.info("-"*40)
                except ZabbixAPIException as e:
                    print("Error updating host '{}': {}".format(ci_vms['host_name'], e))
        
 


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
        current_asset_tag = host[0].get('inventory', {}).get('asset_tag', '')
        
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


    CloudInsights_monitored_VM_list = process_excel_VM_details_reportNot_monitoredbyZB()
    #print(json.dumps(CloudInsights_monitored_VM_list, indent=4))
    print("Number of CloudInsights monitored VMs: ", len(CloudInsights_monitored_VM_list))
    logging.info("Number of CloudInsights monitored VMs: %d", len(CloudInsights_monitored_VM_list))


    try:
        zapi = connect(ZABBIX_URL,ZABBIX_API_TOKEN) #2
        print("Connected to Zabbix API Version:", zapi.apiinfo.version())
        logging.info("Connected to Zabbix API Version: %s", zapi.apiinfo.version())
        hostsIN_HG = get_host_from_zabbix_HG(zapi) #3
        #print(json.dumps(hostsIN_HG, indent=4))
        logging.info(json.dumps(hostsIN_HG, indent=4))

        
        ci_common_VMs, ci_only_VMs, zb_only_VMs = seperate_common_VMs(CloudInsights_monitored_VM_list, hostsIN_HG)
        print("Number of CI common VMs : ", len(ci_common_VMs))
        logging.info("Number of CI common VMs : %d", len(ci_common_VMs))
        print("Number of CI only VMs: ", len(ci_only_VMs)) 
        logging.info("Number of CI only VMs: %d", len(ci_only_VMs))
        print("Number of ZB only VMs: ", len(zb_only_VMs)) 
        logging.info("Number of ZB only VMs: %d", len(zb_only_VMs)) 
        print("-"*40)
        logging.info("-"*40)

        change_hostgroup_of_host(zapi,ci_common_VMs,zb_only_VMs)
        
        



        ''' 
        print("-"*40)
        print("Common VMs:")
        print(json.dumps(ci_common_VMs, indent=4))

        print("-"*40)
        print("ZB only VMs:")
        print(json.dumps(zb_only_VMs, indent=4))
        print("-"*40)
        print("zabbxix host)s in host group:")
        print(json.dumps(hostsIN_HG, indent=4))
        '''

    except ZabbixAPIException as e:
        print("Zabbix API Exception: %s" % e)

