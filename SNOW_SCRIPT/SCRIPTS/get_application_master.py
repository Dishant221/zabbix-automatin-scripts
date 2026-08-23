import requests
import json
import os
import logging
from datetime import date
from Utils.SFTPClient import SFTPClient
from Utils.ConfigurationManager import ConfigurationManager

BASE_DIR = os.path.dirname(os.path.realpath(__file__))
logging.basicConfig(filename=os.path.join(BASE_DIR,"logs", 'get_computer_application_relation.log'), level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def get_accesstoken(SNOW_API_URL,CLIENT_ID,CLIENT_SECRET):
    token_url = f"{SNOW_API_URL}/idp/api/connect/token"
    payload = {'grant_type': 'client_credentials', 'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET}
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    resp = requests.post(token_url, data=payload, headers=headers)
    resp.raise_for_status()
    resp.json()['access_token']
    return resp.json()['access_token']


def get_applications(api_url, token, page_size=1000):
    
    today = date.today().strftime("%Y-%m-%d")
    endpoint = "/api/sam/software-registry/v1/applications"
    page_number = 1
    item_index = 0
    while True:
        url = f"{api_url}{endpoint}"
        headers = {'Authorization': f'Bearer {token}'}
        params = {'page_size': page_size, 'page_number': page_number}
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        items = data.get('items', [])
        if not items:
            print("No more items to fetch.")
            logging.info("No more items to fetch.")
            break
        
        filename = f"Applications_master_{today}_{item_index}.json"
        filepath = os.path.join(BASE_DIR,"DATA","OUT", filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
        print(f"Page {page_number} fetched - {len(items)} items saved in {filename}")
        logging.info(f"Page {page_number} fetched - {len(items)} items saved in {filename}")
        if len(items) < page_size:
            break
        page_number += 1
        item_index += 1
    print(f"\nDone. Total {item_index} JSON files saved to DATA/OUT")
    logging.info(f"\nDone. Total {item_index} JSON files saved to DATA/OUT")


def main():
    with open(os.path.join(BASE_DIR, "Data/IN/SNOW_CONFIG.json")) as f:
        SNOW_CRED = json.load(f)
    SNOW_API_URL = SNOW_CRED["SNOW_CRED"]["api_url"]
    CLIENT_ID = SNOW_CRED["SNOW_CRED"]["client_id"]
    CLIENT_SECRET = SNOW_CRED["SNOW_CRED"]["client_secret"]


    token = get_accesstoken(SNOW_API_URL,CLIENT_ID,CLIENT_SECRET)
    #token = "bLIeEY1J2K7lZ5XwvLTuW3eRYwZv7VLgM1RhNKmyuIrUvIJiQuk19VYdSMyddunmpLLp4zLa0UPwstGZvcu3Bg"
    print(f"TOKEN : {token}\n")
    get_applications(SNOW_API_URL, token)
    



if __name__ == "__main__":
    main()




