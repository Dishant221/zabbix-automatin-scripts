import requests
import json
import csv
import os

api_url = "https://australiasoutheast.snowsoftware.io"
token_url = f"{api_url}/idp/api/connect/token"

data_region = "australiasoutheast"

client_id = "5c25b29c-d30a-4d26-11ff-08deb6eebece"
client_secret = "REDACTED"
token = "1lBJA6DyQEjhzGLIrO8gxgL_edhc65QFSNplljduw7JAJ_f6yiHY1epRGqztV6MLp-tIS2gX3kr84Aq2kZUemQ"


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
    #token = "1lBJA6DyQEjhzGLIrO8gxgL_edhc65QFSNplljduw7JAJ_f6yiHY1epRGqztV6MLp-tIS2gX3kr84Aq2kZUemQ"
    return token




def get_user_accounts(api_url, token, sample_size=2000):
    endpoint = "/api/sam/estate/v1/user-accounts"
    url = f"{api_url}{endpoint}"
    print(f"Fetching user accounts from endpoint: {endpoint}")
    headers = {'Authorization': f'Bearer {token}'}

    # Fetch first page to get total count and sample records
    params = {'page_size': sample_size, 'page_number': 1}
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    data = response.json()

    items = data.get('items', [])
    pagination = data.get('pagination', {})
    total_items = pagination.get('total_items', len(items))

    sample_records = items[:sample_size]
    print(f"Total records available: {total_items}")
    print(f"Sample records fetched: {len(sample_records)}")

    # Save to CSV
    csv_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'csv_files')
    os.makedirs(csv_dir, exist_ok=True)
    csv_path = os.path.join(csv_dir, 'user_accounts_sample.csv')

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # First row: total record count
        writer.writerow([f"Total Records: {total_items}"])
        writer.writerows([f"EndPOINT: {url}"])


        if sample_records:
            # Header row with field names
            field_names = list(sample_records[0].keys())
            writer.writerow(field_names)
            #writer.writerows([f"EndPOINT: {url}"])
            # Data rows
            for record in sample_records:
                writer.writerow([record.get(field, '') for field in field_names])

    print(f"CSV saved to: {csv_path}")
    return sample_records, total_items


def main():
    #token = get_accesstoken(api_url, client_id, client_secret)
    token = "ZRt_IcfV4ROCsdyCOTy4Vg0iBB0yttVxgDbrrDOubpwqliUUYekPzAvIgrwAcvTEgdlzK4jPwDecl-kt71bF_A"
    print(token)


    sample_records, total_items = get_user_accounts(api_url, token)
    print(f"\nTotal user accounts in endpoint: {total_items}")
    print(f"Sample records stored in CSV: {len(sample_records)}")

if __name__ == "__main__":    main()