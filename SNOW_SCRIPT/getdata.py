import requests
import json

api_url = "https://australiasoutheast.snowsoftware.io"
token_url = f"{api_url}/idp/api/connect/token"

data_region = "australiasoutheast"

client_id = "5c25b29c-d30a-4d26-11ff-08deb6eebece"
client_secret = "REDACTED"

payload = {'grant_type': 'client_credentials', 'client_id': client_id, 'client_secret': client_secret}
headers = {'Content-Type': 'application/x-www-form-urlencoded'}
data = requests.post(token_url, data=payload, headers=headers)
jsondata = data.content
content = json.loads(jsondata)
token = content['access_token']
print(token)

def get_accesstoken(api_url, client_id, client_secret):
    token_url = f"{api_url}/idp/api/connect/token"
    payload = {'grant_type': 'client_credentials', 'client_id': client_id, 'client_secret': client_secret}
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    data = requests.post(token_url, data=payload, headers=headers)
    jsondata = data.content
    content = json.loads(jsondata)
    token = content['access_token']
    return token


def _paginated_get(api_url, token, endpoint, page_size=100):
    """Generic paginated GET for Snow Atlas SAM APIs."""
    url = f"{api_url}{endpoint}"
    headers = {'Authorization': f'Bearer {token}'}
    all_items = []
    page = 1

    while True:
        params = {'page_size': page_size, 'page_number': page}
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        items = data.get('items', [])
        if not items:
            break

        all_items.extend(items)

        pagination = data.get('pagination', {})
        total_pages = pagination.get('total_pages', 1)
        print(f"  Page {page}/{total_pages} - {len(items)} items (total: {len(all_items)})")

        if page >= total_pages:
            break
        page += 1

    return all_items


def get_agreements(api_url, token, page_size=100):
    """Fetch all SAM Agreements."""
    return _paginated_get(api_url, token, '/api/sam/estate/v1/agreements', page_size)


def get_applications(api_url, token, page_size=100):
    """Fetch all SAM Applications from the software registry."""
    return _paginated_get(api_url, token, '/api/sam/software-registry/v1/applications', page_size)


def get_computers(api_url, token, page_size=100):
    """Fetch all SAM Computers."""
    return _paginated_get(api_url, token, '/api/sam/estate/v1/computers', page_size)


def get_custom_fields(api_url, token, page_size=100):
    """Fetch all SAM Custom field values."""
    return _paginated_get(api_url, token, '/api/custom-fields/v1/custom-fields-values', page_size)


def get_custom_metrics(api_url, token, page_size=100):
    """Fetch all SAM Custom metrics."""
    return _paginated_get(api_url, token, '/api/sam/estate/v1/custom-metrics', page_size)


def get_custom_objects(api_url, token, page_size=100):
    """Fetch all SAM Custom objects."""
    return _paginated_get(api_url, token, '/api/sam/estate/v1/custom-objects', page_size)


def get_datacenters_clusters(api_url, token, page_size=100):
    """Fetch all SAM Datacenters/Clusters."""
    return _paginated_get(api_url, token, '/api/sam/estate/v1/datacenters', page_size)


def get_files(api_url, token, page_size=100):
    """Fetch all SAM Files."""
    return _paginated_get(api_url, token, '/api/sam/estate/v1/files', page_size)


def get_licenses(api_url, token, page_size=100):
    """Fetch all SAM Licenses."""
    return _paginated_get(api_url, token, '/api/sam/estate/v1/licenses', page_size)


def get_links(api_url, token, page_size=100):
    """Fetch all SAM Links."""
    return _paginated_get(api_url, token, '/api/sam/estate/v1/links', page_size)


def get_mobile_devices(api_url, token, page_size=100):
    """Fetch all SAM Mobile devices."""
    return _paginated_get(api_url, token, '/api/sam/estate/v1/mobile-devices', page_size)


def get_oracle(api_url, token, page_size=100):
    """Fetch all SAM Oracle data."""
    return _paginated_get(api_url, token, '/api/sam/estate/v1/oracle', page_size)


def get_user_accounts(api_url, token, page_size=100):
    """Fetch all SAM User accounts."""
    return _paginated_get(api_url, token, '/api/sam/estate/v1/user-accounts', page_size)


def check_endpoint(api_url, token, name, endpoint):
    """Check if endpoint is reachable and return page/item counts."""
    url = f"{api_url}{endpoint}"
    headers = {'Authorization': f'Bearer {token}'}
    params = {'page_size': 100, 'page_number': 1}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()
        pagination = data.get('pagination', {})
        total_pages = pagination.get('total_pages', 1)
        total_items = pagination.get('total_items', len(data.get('items', [])))
        print(f"  [200 OK] Pages: {total_pages} | Estimated items: {total_pages * 100} | Actual total: {total_items}")
    else:
        print(f"  [{response.status_code}] Not available")


def main():
    token = get_accesstoken(api_url, client_id, client_secret)

    endpoints = [
        ("SAM Agreements", '/api/sam/estate/v1/agreements'),
        ("SAM Applications", '/api/sam/software-registry/v1/applications'),
        ("SAM Computers", '/api/sam/estate/v1/computers'),
        ("SAM Custom Fields", '/api/custom-fields/v1/custom-fields-values'),
        ("SAM Custom Metrics", '/api/sam/estate/v1/custom-metrics'),
        ("SAM Custom Objects", '/api/sam/estate/v1/custom-objects'),
        ("SAM Datacenters/Clusters", '/api/sam/estate/v1/datacenters'),
        ("SAM Files", '/api/sam/estate/v1/files'),
        ("SAM Licenses", '/api/sam/estate/v1/licenses'),
        ("SAM Links", '/api/sam/estate/v1/links'),
        ("SAM Mobile Devices", '/api/sam/estate/v1/mobile-devices'),
        ("SAM Oracle", '/api/sam/estate/v1/oracle'),
        ("SAM User Accounts", '/api/sam/estate/v1/user-accounts'),
    ]

    for name, endpoint in endpoints:
        print(f"\n--- {name} ---")
        check_endpoint(api_url, token, name, endpoint)


if __name__ == "__main__":
    main()




    E	n	d	P	O	I	N	T	:	 	h	t	t	p	s	:	/	/	a	u	s	t	r	a	l	i	a	s	o	u	t	h	e	a	s	t	.	s	n	o	w	s	o	f	t	w	a	r	e	.	i	o	/	a	p	i	/	c	u	s	t	o	m	-	m	e	t	r	i	c	s	/	v	1	/	c	u	s	t	o	m	-	m	e	t	r	i	c	s
