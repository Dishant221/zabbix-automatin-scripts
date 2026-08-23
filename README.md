 Here's the list of committed files containing company data, grouped so you can decide what
  to remove. The big ones and the most sensitive ones are marked.
     
  Most sensitive — delete these first:

  File: SNOW_SCRIPT/csv_files/user_accounts_sample.csv (321 KB)
  Why: employee user account data
  ────────────────────────────────────────
  File: SNOW_SCRIPT/csv_files/ (whole folder, incl. archive/)
  Why: license, computer, oracle instance exports
  ────────────────────────────────────────
  File: SNOW_SCRIPT/computers.json (35 MB)
  Why: full company computer inventory
  ────────────────────────────────────────
  File: SSM_PATCH_REPORT/CHG_PROD_desktop_central_details_allsystems_2026-06-02_*.json (4
  MB)
  Why: prod system details
  ────────────────────────────────────────
  File: SSM_PATCH_REPORT/PATCH-INFO/ (whole folder)
  Why: AWS instance IDs + patch compliance state (useful to attackers)
  ────────────────────────────────────────
  File: SSM_PATCH_REPORT/ALL-RESERVATION-FROM-US-WEST-2-CL-DEV.JSON
  Why: AWS EC2 reservation dump
  ────────────────────────────────────────
  File: BITBUCKET/.../Zabbix-Log-Feed-script/NotificationConfig*.json (4 copies)
  Why: internal DB server IP, employee emails

  Zabbix host/infrastructure exports:

  - hostgroup_delete_script/hgDetails.json (6 MB)
  - disable_host_Data_collection_not_happeing/version3.json, metrics.json, hosts.json,
    itemsDetails.json, new.json — plus the same 5 files again under
    Version4-no-items-keys-in-host/
  - disable_host_Data_collection_not_happeing/output.txt (both copies)

  VM / CloudInsight reports:

  - Host_HG_modification_from_CI_Excel/VM_details_report-not_monitoredbyZB-10-Dec-25.xlsx
  - UAT_hostGroup_modification_..._FIRST_RUN/DATA/INPUT/*.xlsx
  - UAT_hostGroup_modification_..._SECOND_RUN/DATA/INPUT/*.xlsx, VMs Not Monitored By
    Zabbix.json, output_uat_to_json.txt
  - JSON_to_UAT_Hostgroup/Data/SFTP_DATA/VMs Not Monitored By Zabbix.json,
    Zabbix_ASG_Hosts.json

  Script outputs with real hostnames:

  - Go-Live_validation_script/output1.txt, output2.txt
  - AUTO-go-live-validation-script/jenkin_output.txt, formated_output.txt
  - CLOUD_INSIGHT/files_deletion_script/output1.txt
  - add_host*/hosts.csv, add_host_to_hostgroup/host_list.csv (small, not in the table above
    but same category)
  - Notebooks with saved outputs: SNOW_SCRIPT/ALL_REQUEST.ipynb,
    SSM_PATCH_REPORT/get_patch_details.ipynb — these contain Snow/AWS API response data
    embedded in cell outputs, not just code

  One critical detail after you delete: the data is already in the pushed commit, so a
  normal "delete + new commit" leaves it all in git history on GitHub. Since there's only
  one commit, the clean way is to amend and force-push:

  git add -A
  git commit --amend --no-edit
  git push --force origin main

  That rewrites the single commit so the deleted files never existed in history. Tell me
  when you've deleted them (or just say the word and I'll delete the whole list and run
  those commands for you).

✻ Crunched for 57s

────────────────────────────────────────────────────────────────────────────────────────────
❯ 
────────────────────────────────────────────────────────────────────────────────────────────
  ⏵⏵ accept edits on (shift+tab to cycle) · ← 1 agent
