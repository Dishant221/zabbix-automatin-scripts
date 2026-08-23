

from datetime import datetime, timedelta
import json
import os
import logging
from pyzabbix import ZabbixAPI, ZabbixAPIException
from CredentialUtils import ZBCredentials
import sys
"""
This script is return by : Dishant Totade
Email : dishant.totade@wisetechglobal.com
"""


#ZABBIX_URL = "https://monitor.e2open.com/zabbix"
#ZABBIX_API_TOKEN = "REDACTED"

BaseDirectory=os.path.dirname(os.path.realpath(__file__))
logfilePATH=os.path.join(BaseDirectory,"DATA","LOG_OUTPUT","count_problem.log")


logging.basicConfig(filename=logfilePATH,
                    filemode='a',
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
# also log to console so errors/prints are visible when running interactively
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
logging.getLogger().addHandler(console_handler)


def connect(ZABBIX_URL, ZABBIX_API_TOKEN): #1
    
    zapi = ZabbixAPI(ZABBIX_URL)
    #zapi.session.headers.update({"Authorization": f"Bearer {ZABBIX_API_TOKEN}"})
    #zapi.auth = ZABBIX_API_TOKEN
    #zapi = ZabbixAPI(ZABBIX_URL)
    zapi.login(api_token=ZABBIX_API_TOKEN)
    return zapi



def get_host_problems(zapi, host_id):
    """
    Fetching problems for a specific host, including
    1. All currently active problems
    2. All problems from last 7 days (resolved + active)

    
    """
    #print(f"Fetching problems for host ID: {host_id}")

    # Calculate timestamp for 7 days ago
    time_from = int((datetime.now() - timedelta(days=7)).timestamp())

    # Get last 7 days problems
    # (Active and Resolved)
    # -----------------------------
    last_7_days_problems = zapi.problem.get(
        hostids=host_id,
        time_from=time_from,
        severities=[4, 5],
        #recent=True,
        output="extend",
        sortfield="eventid",
        sortorder="DESC"
    )

   
    # Get currently active problems
    # (r_eventid = 0 means not resolved)
    active_problems = zapi.problem.get(
        hostids=host_id,
        severities=[4, 5],
        recent=True,
        output="extend",
        filter={"r_eventid": "0"},
        sortfield="eventid",
        sortorder="DESC"
    )

    return {
        "active_problems": active_problems,
        "last_7_days_problems": last_7_days_problems
    }



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
    print(f"Found host group '{hostgroup_name}' with ID: {group_id}")
    
    print(f"Using host group ID: {group_id}")
    # Step 2: Get hosts in that group
    hosts = zapi.host.get(
        groupids=group_id,
        output=["hostid", "host"]
    )

    return hosts


def main():

    # Validate CLI args early so we show helpful usage instead of an IndexError
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
    


    try:
        zapi = connect(ZABBIX_URL, ZABBIX_API_TOKEN)
        logging.info("Connected to Zabbix API successfully.")

        # Example: Get problems for a specific host (replace with actual host ID)
        #host_id = "24515"  # 
        hostgroup_filePath = os.path.join(BaseDirectory,"DATA","INPUT","INPUT_hostgroup.txt")
        hostgroup_name = "UAT/CI-PROD-PRODUCTION/HUB/Channel/Channel Data Management/HUB00000546/CDM-Internal"
        with open(hostgroup_filePath, "r") as f:
            hostgroup_name = f.read().strip()
        hosts = get_hosts_from_group(zapi, hostgroup_name)
        '''  
        for host in hosts:
            host_id = host["hostid"]
            problems = get_host_problems(zapi, host_id)
            active_count = len(problems["active_problems"])
            last_7_days_count = len(problems["last_7_days_problems"])
            print(f"Host ID: {host_id} - Active Problems with high and disater: {active_count}, Last 7 Days Problems: {last_7_days_count}")
            logging.info(f"Host ID: {host_id} - Active Problems: {active_count}, Last 7 Days Problems: {last_7_days_count}")
        '''  
                # Table header
        print("\n" + "+" + "-"*15 + "+" + "-"*35 + "+" + "-"*25 + "+" + "-"*15 + "+")
        print("| {0:<13} | {1:<33} | {2:<23} | {3:<13} |".format(
            "Host ID", "Hostname", "Active (High+Disaster)", "Last 7 Days"
        ))
        print("+" + "-"*15 + "+" + "-"*35 + "+" + "-"*25 + "+" + "-"*15 + "+")

        for host in hosts:
            host_id = host["hostid"]
            hostname = host["host"]

            problems = get_host_problems(zapi, host_id)
            active_count = len(problems["active_problems"])
            last_7_days_count = len(problems["last_7_days_problems"])

            print("| {0:<13} | {1:<33} | {2:<23} | {3:<13} |".format(
                host_id,
                hostname[:33],   # prevent overflow
                active_count,
                last_7_days_count
            ))

        print("+" + "-"*15 + "+" + "-"*35 + "+" + "-"*25 + "+" + "-"*15 + "+")


    except ZabbixAPIException as e:
        logging.error(f"Zabbix API error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")



if __name__ == "__main__":
    main()