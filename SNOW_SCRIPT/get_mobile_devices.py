import requests
import json
import csv
import os



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
    if 'access_token' not in content:
        print(f"Token request failed (HTTP {data.status_code}): {content}")
        raise SystemExit("Failed to get access token. Check client_id/client_secret.")
    token = content['access_token']
    return token


def get_mobile_devices(api_url, token, sample_size=500):
    endpoint = "/api/sam/estate/v1/mobiledevices"
    url = f"{api_url}{endpoint}"
    headers = {'Authorization': f'Bearer {token}'}

    # Fetch first page to get total count and sample records
    params = {'page_size': sample_size, 'page_number': 1}
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    data = response.json()

    total_items = data.get('pagination', {}).get('total_items', 0)
    sample_records = data.get('items', [])

    print(f"Total mobile devices: {total_items}")
    if sample_records:
        print(f"Sample record: {sample_records[0]}")

    return total_items, sample_records, url

def main():
    #token = get_accesstoken(api_url, client_id, client_secret)
    token = "NG3mYh2RvWIuOhmPmrafbJkvmrmbrd2y7Yj5cHO2985XXnF04LjQgPzWfdI-JPNXOrBjeh6BTRe1c2SgUYz1AQ"
    total_items, sample_records, url = get_mobile_devices(api_url, token)

    # Save results to CSV
    csv_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'csv_files')
    os.makedirs(csv_dir, exist_ok=True)
    csv_path = os.path.join(csv_dir, 'mobile_devices.csv')

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
