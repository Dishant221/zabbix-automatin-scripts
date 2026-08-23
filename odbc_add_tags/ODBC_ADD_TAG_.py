"""
Script Written By : Dishant Totade 
Email : dishant.totade@e2open.com

"""
#____________________________________________________________________________________________

logfilePATH='odbc_add_tags.log'
number_of_threads = 5


zabbixURL = None
zabbixTOKEN = None  

new_tag_with_no_values = [
    {"tag": "SFID", "value": ""},
    {"tag": "JID", "value": ""},
    {"tag": "USER", "value": ""},
    {"tag": "SuppressedBy", "value": ""}
]
special_tags = {
    "ControlledAccess": "{INVENTORY.SOFTWARE.APP.D}",
    "CustomerCategory": "{INVENTORY.SOFTWARE.APP.C}",
    "Hub": "{INVENTORY.TYPE.FULL}",
    "SOLUTION": "{INVENTORY.SOFTWARE}"
}



#_______________________________________________________________________________________________

import requests
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from datetime import datetime
import pymysql
import os
import sys


BaseDirectory=os.path.dirname(os.path.realpath(__file__))
logfilePATH=os.path.join(BaseDirectory,"DATA","LOG_OUTPUT","odbc_add_tags.log")


logging.basicConfig(filename=logfilePATH,
                    filemode='a',
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    level=logging.INFO)



def call_zabbix_api(method, params):
    HEADERS = {
    "Content-Type": "application/json-rpc",
    "Authorization": f"Bearer {zabbixTOKEN}"
    }
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1
    }
    response = requests.post(zabbixURL, headers=HEADERS, json=payload)
    data = response.json()
    if "error" in data:
        raise Exception(f"❌ Zabbix API Error: {data['error']}")
    return data["result"]

def get_all_Enabled_host():
    return call_zabbix_api("host.get", {
        "output": ["hostid", "host", "status"],
        "status": 0, # status = 0 enabled host
        "selectTags": "extend"
    })

def add_tag_to_host(hostid, new_tag_with_no_values):
    #Fetch host info
    host = call_zabbix_api(
        "host.get",
        {
            "output": ["hostid", "host"],
            "selectTags": "extend",
            "hostids": [str(hostid)]
        },
    )

    if not host:
        msg = f"⚠️ No host found for hostid {hostid}"
        print(msg)
        logging.info(msg)
        return {"success": False, "message": msg}

    hostname = host[0].get("host", f"unknown_{hostid}")
    current_tags = host[0].get("tags", [])

    # Clean tags (remove "automatic")
    cleaned_existing_tags = []
    previous_tag = []
    for tag in current_tags:
        new_tag = {}
        for k, v in tag.items():
            if k != "automatic":
                new_tag[k] = v
        cleaned_existing_tags.append(new_tag)
        previous_tag.append(new_tag)

    #Merge special_tags and new tags wiht no value
    merged_tags = {}
    merged_tags.update(special_tags)  # special tags first
    for t in new_tag_with_no_values:
        merged_tags[t["tag"]] = t.get("value", "")

    new_tags_added = 0
    tags_updated = 0

    #Apply merged tags
    for tag_key, new_value in merged_tags.items():
        # Find if tag already exists
        existing_tag = None
        for t in cleaned_existing_tags:
            if t.get("tag") == tag_key:
                existing_tag = t
                break

        if existing_tag:
            current_value = existing_tag.get("value", "")
            # Update only if new_value is not empty and different
            if new_value and current_value != new_value:
                existing_tag["value"] = new_value
                tags_updated += 1
        else:
            # Add new tag if it doesn't exist
            cleaned_existing_tags.append({"tag": tag_key, "value": new_value})
            new_tags_added += 1

    #Skip if no changes
    if new_tags_added == 0 and tags_updated == 0:
        msg = f"⏭️ No tag changes needed for {hostname}, skipping.."
        print(msg)
        logging.info(msg)
        return {"success": True, "message": msg}

    #Update host in Zabbix
    try:
        call_zabbix_api("host.update", {"hostid": hostid, "tags": cleaned_existing_tags})
        msg = f"✅ {hostname}: Added {new_tags_added} new tag(s), Updated {tags_updated} tag(s)"
        print(msg)
        logging.info(msg)
        logging.info(f"PREVIOUS Tags of {hostname} : {json.dumps(previous_tag)}")
        logging.info("_____________________________________________________________")
        return {"success": True, "message": msg}
    except Exception as e:
        msg = f"❌ Failed to update host {hostname}: {e}"
        print(msg)
        logging.error(msg)
        return {"success": False, "message": msg}




def createThread_to_add_tags_to_hosts(all_hosts, new_tag_with_no_values):
    MAX_THREADS = number_of_threads

    # Create a thread pool
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        # Loop through each host
        process_list = []
        for hostid in all_hosts:
            # Schedule the process_host function to run in a thread
            process = executor.submit(add_tag_to_host, hostid, new_tag_with_no_values)
            process_list.append(process)

        # Wait for all threads to complete
        for process in process_list:
            try:
                process.result()  # Raise exception if any occurred inside thread
            except Exception as e:
                print(f"❌ Error occurred in thread: {e}")
                logging.info(f" Error occurred in thread: {e}")



def get_enabled_hostids(cursor):
    """
    Fetches all enabled host IDs,Name, status, tags, values  from the Zabbix hosts, host_tag, hstgrp, hosts_groups table 
    and returns them as a Python list of integers.
    """
    query = '''SELECT 
    h.hostid,
    h.name,
    h.status,
    ht.tag,
    ht.value
    FROM hosts_groups hg
    INNER JOIN hstgrp g 
    ON g.groupid = hg.groupid
    INNER JOIN hosts h 
    ON hg.hostid = h.hostid
    LEFT JOIN host_tag ht 
    ON ht.hostid = h.hostid
    WHERE 
    UPPER(g.name) LIKE 'GO-LIVE%'
    AND h.status = 0
    ORDER BY h.name ASC;
    '''
    cursor.execute(query)
    
    # cursor.fetchall() will return a list of tuples like [(10084,), (10333,), ...]
    rows = cursor.fetchall()
    hostid_list = list(set(row[0] for row in rows))
    
    return hostid_list


if __name__ == "__main__":

    SCRITP_START_DATE_TIME = datetime.now()

    logging.info(f"_________________SCRIPTING_STARTING_{SCRITP_START_DATE_TIME}________________")

    environment  = sys.argv[1].upper()
    
    config = None
    BaseDirectory=os.path.dirname(os.path.realpath(__file__))

    if environment=='PROD':
        with open(BaseDirectory+"/DATA/CONFIG/ODBC_add_tag_PROD.json") as f:
            config= json.load(f)   
    #elif environment=="STG":
        #with open(BaseDirectory+"/DATA/CONFIG/ODBC_add_tag_STAGE.json") as f:
            #config= json.load(f)   
    elif environment=='DEV':
        with open(BaseDirectory+"/DATA/CONFIG/ODBC_add_tag_DEV.json") as f:
            config= json.load(f) 

    ZABBIX_URL = config["ENV_CRED"]["ZABBIX_URL"]
    ZABBIX_TOKEN = config["ENV_CRED"]["ZABBIX_TOKEN"]
    zabbixURL = ZABBIX_URL
    zabbixTOKEN = ZABBIX_TOKEN

    HOST = config["ENV_CRED"]["DB_CONNECTION"]["host"]
    USER = config["ENV_CRED"]["DB_CONNECTION"]["user"]
    PASSWORD = config["ENV_CRED"]["DB_CONNECTION"]["password"]
    DATABASE = config["ENV_CRED"]["DB_CONNECTION"]["database"]
    PORT = config["ENV_CRED"]["DB_CONNECTION"]["port"]
    UNIX_SOCKET = config["ENV_CRED"]["DB_CONNECTION"]["unix_socket"]

    try:
        
        connection = pymysql.connect(
        host=HOST,                  # can also be omitted if using socket
        user=USER,
        password=PASSWORD,
        database=DATABASE,
        port=PORT,
        unix_socket=UNIX_SOCKET
        )
        
        cursor = connection.cursor()
        host_ids = get_enabled_hostids(cursor)


    except Exception as e:
        print("Database Connection " + str(e))
        logging.info(str(e))


    try:
        
        createThread_to_add_tags_to_hosts(host_ids, new_tag_with_no_values)
    except Exception as e:
        print("Thread Errroe : " + str(e))
        logging.info(str(e))

