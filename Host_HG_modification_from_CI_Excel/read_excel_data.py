import json
import pylightxl as xl


"""

db = xl.readxl(fn='VM_details_report-not_monitoredbyZB-10-Dec-25.xlsx', ws='VM details report - not monitor')


'''
['DC', 'vCenter/Account', 'Cluster/Region', 'Host/AVZ', 'Name', 'Power State', 'DB Server ?', 'Environment', 'Purpose',
 'Account', 'E2customer/Hub', 'Hub Identifier', 'Hub Type', 'Hub IsActive?', 'Hub Status', 'Hub State', 'CI Solution', 
 'Department', 'Requested by', 'HW Request', 'Provisioned by', 'Created On', 'CSM', 'ESE', 'OS Family', 'OS', 'OS Major Version',
   'Released On', 'EOL ON', 'IS EOL?', 'EOL Age', 'EOL Age Range', 'VMware Tools Version', 'VMware Tools Status', 'DNS Name', 'Vm Fqdn',
     'R7 Monitored?', 'ZB Monitored?', 'Usage', 'IS R7 LastScan Date', 'AV Installed?', 'Cylance Monitored?', 'CB Monitored?', 'CS Monitored?',
       'OS Provenance', 'Record CollectionTS', 'Shutdown Date', 'Shutdown Days', 'Metrics', '#vCores', 'Memory-GB', 'Storage-GB', 'Storage-Used-GB', 
       'Resource Point', 'VM-STATS-Memory-Used-%', 'VM-STATS-CPU-Used-%', 'VM-STATS-Memory-Consumed-GB', 'VM-STATS-Memory-Overhead-GB', 'VM R7 Risk Score', 
       'VM Used Space (TB)', 'VM provisioned Space (TB)', 'IS R7 Critical', 'IS R7 Exploits', 'IS R7 Malwarekits', 'IS R7 Moderate', 'IS R7 Severe', 'Shutdown Days']
'''

#columns_list = db.ws(ws='VM details report - not monitor').row(1)

CloudInsights_monitored_VMs = []


for row in db.ws(ws='VM details report - not monitor').rows:
    ci_host_name = row[4]
    ci_ENV = row[7]
    ci_Env_purpose = row[8]
    ci_E2customer_Hub = row[10]
    ci_hub_type= row[12]
    ci_hub_identifier = row[11]

    CI_json_input = {
        "host_name": ci_host_name,
        "environment": ci_ENV,
        "env_purpose": ci_Env_purpose,
        "e2customer_hub": ci_E2customer_Hub,
        "hub_type": ci_hub_type,
        "hub_identifier": ci_hub_identifier
    }
    CloudInsights_monitored_VMs.append(CI_json_input)


print(json.dumps(CloudInsights_monitored_VMs, indent=4))
print(len(CloudInsights_monitored_VMs))

""" 

import json
import pylightxl as xl

# Read Excel
db = xl.readxl(fn='VM_details_report-not_monitoredbyZB-10-Dec-25.xlsx',
               ws='VM details report - not monitor')

ws = db.ws(ws='VM details report - not monitor')

# Get header row (first row)
headers = ws.row(1)
rows = ws.rows

# Get header first
headers = next(rows)
header_index = {header: index for index, header in enumerate(headers)}

CloudInsights_monitored_VMs = []

for row in rows:   # continues from second row automatically

    ci_host_name = row[header_index['Name']]
    ci_ENV = row[header_index['Environment']]
    ci_Env_purpose = row[header_index['Purpose']]
    ci_E2customer_Hub = row[header_index['E2customer/Hub']]
    ci_hub_type = row[header_index['Hub Type']]
    ci_hub_identifier = row[header_index['Hub Identifier']]

    CloudInsights_monitored_VMs.append({
        "host_name": ci_host_name,
        "environment": ci_ENV,
        "env_purpose": ci_Env_purpose,
        "e2customer_hub": ci_E2customer_Hub,
        "hub_type": ci_hub_type,
        "hub_identifier": ci_hub_identifier
    })


print(json.dumps(CloudInsights_monitored_VMs, indent=4))
print(len(CloudInsights_monitored_VMs))