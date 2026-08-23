#___________________________________________________________________________________________________
# Guide to Run This Script
"""
1> replace below url and token as per your enviorment on which this script will execute.
2> command to execute : python Maintenances_script.py
3> enter number of days before, on which you want to delete that maintanance.
4> find report of deleted maintanance in present folder.
"""

#for any issue running this script contact the Owner 
"""
Owner: Dishant Totade
Email: dishant.totade@e2open.com
"""
#____________________________________________________________________________________________________


token ='REDACTED'
url = 'http://192.168.174.128/zabbix//api_jsonrpc.php'

import requests
import json
from datetime import datetime, timedelta, timezone
import logging
import os
import csv



logging.basicConfig(filename='Maintenances_script.log',
                    filemode='a',
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    level=logging.INFO)


HEADERS = {
    "Content-Type": "application/json-rpc",
    "Authorization": f"Bearer {token}"
}




def call_zabbix_api(method, params):
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1
    }
    response = requests.post(url, headers=HEADERS, json=payload)
    result = response.json()
    if 'error' in result:
        error_message = f"Zabbix API Error: {result['error']}"
        logging.error(error_message)
        raise Exception(error_message)
    return result['result']

def parse_timeperiod(timeperiod):
    type_map = {
        '0': 'One time only',
        '2': 'Daily',
        '3': 'Weekly',
        '4': 'Monthly'
    }

    t_type = str(timeperiod.get('timeperiod_type', '0'))
    period_sec = int(timeperiod.get('period', 3600))
    duration_min = period_sec // 60
    start_date = int(timeperiod.get('start_date', 0))
    start_dt = datetime.fromtimestamp(start_date).strftime('%Y-%m-%d %H:%M:%S')

    description = f"{type_map.get(t_type, 'Unknown')} - Every {timeperiod.get('every', '1')} unit(s), Duration: {duration_min} minutes, Starts at: {start_dt}"
    return description




def generate_report(maintenances_deleting_list, maintenances_list, inputDays):
    # Create human-readable timestamp for the filename
    current_time_str = datetime.now().strftime("%Y-%m-%d_")
    csv_file = f"maintenances_delete_report_last_{inputDays}days_from_{current_time_str}.csv"

    fieldnames = [
        'Maintenance Name', 'Maintenance ID', 'Hosts', 'Hostgroups', 'Maintenance Type', 'Tags',
        'Description', 'Active Since', 'Active Till',
        'Maintenance Window Duration (hrs)', 'Time period'
    ]

    with open(csv_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        del_maint_count = 0
        for maintenance in maintenances_list:
            if del_maint_count >= len(maintenances_deleting_list):
                break

            if maintenances_deleting_list[del_maint_count] == maintenance.get('maintenanceid'):
                del_maint_count += 1

                # Maintenance Type
                maintenance_type = maintenance.get('maintenance_type', '0')
                maintenance_type_str = 'With data collection' if maintenance_type == '0' else 'Without data collection'

                # Active Since
                try:
                    active_since = int(maintenance.get('active_since', 0))
                    active_since_str = datetime.fromtimestamp(active_since).strftime('%Y-%m-%d %H:%M:%S')
                except:
                    active_since_str = 'Invalid timestamp'

                # Active Till
                try:
                    active_till = int(maintenance.get('active_till', 0))
                    active_till_str = datetime.fromtimestamp(active_till).strftime('%Y-%m-%d %H:%M:%S')
                except:
                    active_till_str = 'Invalid timestamp'

                # Duration
                if active_since > 0 and active_till > 0:
                    duration_seconds = active_till - active_since
                    days = duration_seconds // 86400
                    hours = (duration_seconds % 86400) // 3600
                    minutes = (duration_seconds % 3600) // 60

                    duration_parts = []
                    if days > 0:
                        duration_parts.append(f"{days} day{'s' if days != 1 else ''}")
                    if hours > 0:
                        duration_parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
                    if minutes > 0:
                        duration_parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")

                    duration_hrs = ', '.join(duration_parts) if duration_parts else 'Less than a minute'
                else:
                    duration_hrs = 'Invalid'

                # Hostgroups
                hostgroups = maintenance.get('hostgroups', [])
                hostgroup_names = ', '.join(group.get('name', '') for group in hostgroups) if hostgroups else 'none'

                # Hosts
                hosts = maintenance.get('hosts', [])
                host_names = ', '.join(host.get('host', '') for host in hosts) if hosts else 'none'

                # Tags
                tags = maintenance.get('tags', [])
                tag_names = ', '.join(tag.get('tag', '') for tag in tags) if tags else 'none'

                
                # Time period
                timeperiods = maintenance.get('timeperiods', [])
                time_period_str = parse_timeperiod(timeperiods[0]) if timeperiods else 'Not defined'

                # Write row
                writer.writerow({
                    'Maintenance Name': maintenance.get('name', ''),
                    'Maintenance ID': maintenance.get('maintenanceid', ''),
                    'Hosts': host_names,
                    'Hostgroups': hostgroup_names,
                    'Maintenance Type': maintenance_type_str,
                    'Tags': tag_names,
                    'Description': maintenance.get('description', '').replace('\r\n', ' ').strip(),
                    'Active Since': active_since_str,
                    'Active Till': active_till_str,
                    'Maintenance Window Duration (hrs)': duration_hrs,
                    'Time period': time_period_str
                    
                })

    print(f"✅ Report saved as: {csv_file}")



def get_all_maintenances(inputDays):

    all_maintenances = call_zabbix_api("maintenance.get", 

       {
        "output": "extend",
        "selectHosts": "extend",
        "selectHostGroups": "extend",
        "selectTimeperiods": "extend",
        "selectTags": "extend"
    })
    Processing_date_for_maintenances(all_maintenances,inputDays)

    #print(json.dumps(all_maintenances, indent=2, ensure_ascii=False))

def Processing_date_for_maintenances(maintenances_list, inputDays):
    maintenances_before_date = []

    # Get current UTC time as timestamp
    utc_timestamp_today = int(datetime.now(timezone.utc).timestamp())

    # Convert days to seconds
    delta_seconds = int(timedelta(days=inputDays).total_seconds())

    # Calculate the cutoff timestamp
    going_back_timestamp = utc_timestamp_today - delta_seconds

    for maintenance in maintenances_list:
        try:
            # active_till is already in UTC (from Zabbix)
            active_till_ts = int(maintenance.get('active_till'))
            maintenance_name = maintenance.get('name')
            maintenance_id = maintenance.get('maintenanceid')

            # Compare timestamps (int vs int)
            if active_till_ts < going_back_timestamp:
                active_till_str = datetime.fromtimestamp(active_till_ts, tz=timezone.utc).strftime('%Y-%m-%d %H:%M')
                print(f"🔴 DELETE Maintenance: '{maintenance_name}' (ID: {maintenance_id}) — active till {active_till_str}")
                logging.info(f"DELETE: '{maintenance_name}' (ID: {maintenance_id}) — active till {active_till_str}")
                maintenances_before_date.append(maintenance_id)

        except (TypeError, ValueError):
            print(f"⚠️ Skipping invalid maintenance entry: {maintenance}")
            logging.info(f"Skipping invalid maintenance entry: {maintenance}")

    print(f"❌❌🔔 Total maintenances deleted: {len(maintenances_before_date)} 🔔❌❌")
    return delete_maintenance(maintenances_before_date, maintenances_list,inputDays)




def delete_maintenance(maintenances_deleting_list,maintenances_list,inputDays):

    if not maintenances_deleting_list:
        print(" 🟢 No old maintenances to delete.")
        logging.info(" No old maintenances to delete.")
        return
    generate_report(maintenances_deleting_list,maintenances_list,inputDays)

    
    
    return call_zabbix_api('maintenance.delete',maintenances_deleting_list)




def main():
    inputDays = int(input('Enter Days : '))

    try:
        get_all_maintenances(inputDays)

    except Exception as e:
        print(str(e))



if __name__ == "__main__":
    main()
