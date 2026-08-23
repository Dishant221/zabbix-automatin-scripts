import requests
import json

api_url = "https://australiasoutheast.snowsoftware.io"
client_id = "5c25b29c-d30a-4d26-11ff-08deb6eebece"
client_secret = "REDACTED"

def get_accesstoken():
    token_url = f"{api_url}/idp/api/connect/token"
    payload = {'grant_type': 'client_credentials', 'client_id': client_id, 'client_secret': client_secret}
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    resp = requests.post(token_url, data=payload, headers=headers)
    resp.raise_for_status()
    return resp.json()['access_token']


def pagination(endpoint, token):
    token = get_accesstoken()
    
    url = f"{api_url}{endpoint}"
    headers = {'Authorization': f'Bearer {token}'}
    params = {'page_size': 50, 'page_number': 1}
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    data = response.json()

    pagination_info = data.get('pagination', {})
    total_items = pagination_info.get('total_items', 0)
    print(f"Total Records: {total_items}")



main():




if __name__ == "__main__":
    main()