import requests
import json
import csv
import os

# Snow Atlas API config
api_url = "https://australiasoutheast.snowsoftware.io"
client_id = "5c25b29c-d30a-4d26-11ff-08deb6eebece"
client_secret = "REDACTED"

# Output folder
csv_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'csv_files')
os.makedirs(csv_dir, exist_ok=True)


# --- Step 1: Get Token ---
def get_token():
    url = f"{api_url}/idp/api/connect/token"
    payload = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    resp = requests.post(url, data=payload, headers=headers)
    resp.raise_for_status()
    return resp.json()['access_token']


# --- Helper: GET with auth ---
def api_get(token, endpoint, page_size=100, page_number=1):
    url = f"{api_url}{endpoint}"
    headers = {'Authorization': f'Bearer {token}'}
    params = {'page_size': page_size, 'page_number': page_number}
    resp = requests.get(url, headers=headers, params=params)
    resp.raise_for_status()
    return resp.json()


# --- Step 2: Get Computers ---
def get_computers(token, page_size=100):
    data = api_get(token, "/api/sam/estate/v1/computers", page_size)
    items = data.get('items', [])
    print(f"Computers fetched: {len(items)} \n")
    return items


# --- Step 3: Get Applications installed on a Computer ---
def get_computer_applications(token, computer_id, page_size=100):
    endpoint = f"/api/sam/estate/v1/computers/{computer_id}/applications"
    data = api_get(token, endpoint, page_size)
    return data.get('items', [])


# --- Step 4: Get Licenses ---
def get_licenses(token, page_size=500):
    data = api_get(token, "/api/sam/v1/licenses", page_size)
    items = data.get('items', [])
    print(f"Licenses fetched: {len(items)}\n")
    return items


# --- Step 5: Get Agreements ---
def get_agreements(token, page_size=200):
    data = api_get(token, "/api/sam/v2/agreements", page_size)
    items = data.get('items', [])
    print(f"Agreements fetched: {len(items)}\n")
    return items


# --- Main: Build the relationship ---
def main():
    token = get_token()
    print("Token acquired.\n")

    # Get computers (sample of 10 to keep it simple)
    computers = get_computers(token, page_size=10)

    # Get all licenses and build lookup by application_id
    licenses = get_licenses(token)
    # license -> application mapping (field may be 'applicationId' or 'application_id')
    license_by_app = {}
    for lic in licenses:
        app_id = lic.get('applicationId') or lic.get('application_id') or ''
        if app_id:
            license_by_app.setdefault(app_id, []).append(lic)

    # Get all agreements and build lookup by id
    agreements = get_agreements(token)
    agreement_by_id = {}
    for agr in agreements:
        agr_id = agr.get('id', '')
        if agr_id:
            agreement_by_id[agr_id] = agr

    # Build relationship rows: Computer -> Application -> License -> Agreement
    rows = []

    for comp in computers:
        comp_id = comp.get('id', '')
        comp_name = comp.get('hostName') or comp.get('hostname') or comp.get('name', '')
        print(f"\nGetting apps for computer: {comp_name} ({comp_id})")

        apps = get_computer_applications(token, comp_id)
        print(f"  Applications found: {len(apps)}")

        for app in apps:
            app_id = app.get('applicationId') or app.get('id', '')
            app_name = app.get('applicationName') or app.get('name', '')

            # Find licenses for this application
            matching_licenses = license_by_app.get(app_id, [])

            if matching_licenses:
                for lic in matching_licenses:
                    lic_id = lic.get('id', '')
                    lic_name = lic.get('name') or lic.get('licenseName', '')
                    # Find agreement for this license
                    agr_id = lic.get('agreementId') or lic.get('agreement_id', '')
                    agr = agreement_by_id.get(agr_id, {})
                    agr_name = agr.get('name', '')

                    rows.append({
                        'computer_id': comp_id,
                        'computer_name': comp_name,
                        'application_id': app_id,
                        'application_name': app_name,
                        'license_id': lic_id,
                        'license_name': lic_name,
                        'agreement_id': agr_id,
                        'agreement_name': agr_name
                    })
            else:
                # No license found for this app
                rows.append({
                    'computer_id': comp_id,
                    'computer_name': comp_name,
                    'application_id': app_id,
                    'application_name': app_name,
                    'license_id': '',
                    'license_name': '',
                    'agreement_id': '',
                    'agreement_name': ''
                })

    # Save to CSV
    csv_path = os.path.join(csv_dir, 'computer_app_license_agreement.csv')
    if rows:
        fields = list(rows[0].keys())
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nSaved {len(rows)} rows to {csv_path}")
    else:
        print("\nNo relationship data found.")

    # Print sample
    print("\n--- Sample Output (first 5 rows) ---")
    for row in rows[:5]:
        print(f"  {row['computer_name']} | {row['application_name']} | {row['license_name']} | {row['agreement_name']}")


if __name__ == "__main__":
    main()
