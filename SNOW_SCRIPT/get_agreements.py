import requests
import json
import os
import csv

api_url = "https://australiasoutheast.snowsoftware.io"
token_url = f"{api_url}/idp/api/connect/token"

data_region = "australiasoutheast"

client_id = "5c25b29c-d30a-4d26-11ff-08deb6eebece"
client_secret = "REDACTED"



def get_accesstoken(api_url, client_id, client_secret):
    token_url = f"{api_url}/idp/api/connect/token"
    payload = {'grant_type': 'client_credentials', 'client_id': client_id, 'client_secret': client_secret}
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    data = requests.post(token_url, data=payload, headers=headers)
    jsondata = data.content
    content = json.loads(jsondata)
    token = content['access_token']
    return token


def get_agreements(api_url, token, sample_size=50):
    endpoint = "/api/sam/v2/agreements"
    url = f"{api_url}{endpoint}"
    headers = {'Authorization': f'Bearer {token}'}
    params = {'page_size': sample_size, 'page_number': 1}
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    data = response.json()

    pagination = data.get('pagination', {})
    total_pages = pagination.get('total_pages', 0)
    total_items = total_pages * sample_size
    items = data.get('items', [])
    sample_records = items[:sample_size]

    print(f"Total Records (estimated): {total_items}")
    print(f"Sample records fetched: {len(sample_records)}")
    print(f"Endpoint URL: {url}")

    return total_items, sample_records, url


def main():
    #token = get_accesstoken(api_url, client_id, client_secret)
    token = "1lBJA6DyQEjhzGLIrO8gxgL_edhc65QFSNplljduw7JAJ_f6yiHY1epRGqztV6MLp-tIS2gX3kr84Aq2kZUemQ"
    total_items, sample_records, url = get_agreements(api_url, token)

    # Save results to CSV
    csv_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'csv_files')
    os.makedirs(csv_dir, exist_ok=True)
    csv_path = os.path.join(csv_dir, 'agreements.csv')

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # First row: total record count
        writer.writerow([f"Total Records: {total_items}"])
        writer.writerows([f"EndPOINT: {url}"])

        if sample_records:
            # Header row with field names
            field_names = list(sample_records[0].keys())
            writer.writerow(field_names)
            # Data rows
            for record in sample_records:
                writer.writerow([record.get(field, '') for field in field_names])

if __name__ == "__main__":
    main()


