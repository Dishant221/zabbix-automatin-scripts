from CredentialUtils import ZBCredentials
import os
import sys
import json
import pyzabbix
import logging
from datetime import datetime, timedelta
from pyzabbix import ZabbixAPI, ZabbixAPIException
import time
from tabulate import tabulate

def connect(ZABBIX_URL, ZABBIX_API_TOKEN): #1
    
    zapi = ZabbixAPI(ZABBIX_URL)
    #zapi.session.headers.update({"Authorization": f"Bearer {ZABBIX_API_TOKEN}"})
    #zapi.auth = ZABBIX_API_TOKEN
    #zapi = ZabbixAPI(ZABBIX_URL)
    zapi.login(api_token=ZABBIX_API_TOKEN)
    print(f"Connected to Zabbix API Version: {zapi.api_version()}")
    logging.info(f"Connected to Zabbix API Version: {zapi.api_version()}")
    return zapi

def get_child_hostgroups(zapi, parent_group_name):
    groups = zapi.hostgroup.get(output=["name"])

    return [
        g["name"]
        for g in groups
        if g["name"].startswith(parent_group_name + "/")
        and "<UNKNOWN>" not in g["name"]
    ]

def main():
    # Validate CLI args early so we show helpful usage instead of an IndexError
    if len(sys.argv) < 2:
        print("Usage: python count_problem.py <ENVIRONMENT> <HOSTGROUP_NAME>  # PROD | STG | DEV")
        logging.error("No environment argument provided; exiting.")
        sys.exit(1)

    SCRITP_START_DATE_TIME = datetime.now()

    logging.info(f"_________________SCRIPTING_STARTING_{SCRITP_START_DATE_TIME}________________")

    environment  = sys.argv[1].upper()
    #hostgroup_name = sys.argv[2] if len(sys.argv) > 2 else None

    
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
        child_group=get_child_hostgroups(zapi, "UAT/CI-PROD-PRODUCTION/HUB")
        print(json.dumps(child_group, indent=2))
        print(len(child_group))
    except Exception as e:
        logging.error(f"Error connecting to Zabbix API: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error(f"Error running main function: {e}")
        sys.exit(1)