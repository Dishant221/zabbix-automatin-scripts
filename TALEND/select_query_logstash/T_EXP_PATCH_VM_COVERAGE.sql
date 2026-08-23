SELECT [ASON]
      ,[DC]
      ,[Cluster]
      ,[host_name]
      ,[VM]
      ,[PowerState]
      ,[VM_CREATED_DATE]
      ,[ENV]
      ,[PURPOSE]
      ,[VCENTER_SERVER]
      ,[VCENTER]
      ,[E2CUSTOMER]
      ,[ACCOUNT]
      ,[Hub_ID]
      ,[OS_FAMILY]
      ,[OS_MAJOR_VERSION]
      ,[IS_DB]
      ,[LATEST_SCAN_DATE]
      ,[AV_INSTALLED]
      ,[ISACTIVE]
      ,[DC_PROVIDER]
      ,[Product_Family]
      ,[Product_Name]
      ,[sfdc_product_family]
      ,[sfdc_product_name]
      ,[HUB_TYPE]
      ,[sfdc_hub_type]
      ,[DEPARTMENT]
      ,[PS_Practice]
      ,[COVERED_FOR_PATCHING]
      ,[IP]
      ,[LAST_SUCCESSFUL_SCAN_DATE]
      ,[LAST_PATCH_UPDATE_DATE]
      ,[IS_KATELLO_COVERED]
      ,[IS_DESKTOP_CENTRAL_COVERED]
      ,[PATCH_PROVENANCE]
      ,[CI_APPLIANCE]
      ,[BOOT_KERNEL]
      ,[EFFECTIVE_KERNEL]
      ,[IS_KCARE_COVERED]
      ,[IS_EOL]
      ,[NumCpu]
      ,[MemoryGB]
      ,[ProvisionedSpaceGB]
      ,[MISSING_PATCHES]
  FROM [dbo].[T_EXP_PATCH_VM_COVERAGE]



select [ason], [dc], [cluster], [host_name], [vm], [powerstate], [vm_created_date], [env], [purpose], [vcenter_server], [vcenter], [e2customer], [account], [hub_id], [os_family], [os_major_version], [is_db], [latest_scan_date], [av_installed], [isactive], [dc_provider], [product_family], [product_name], [sfdc_product_family], [sfdc_product_name], [hub_type], [sfdc_hub_type], [department], [ps_practice], [covered_for_patching], [ip], [last_successful_scan_date], [last_patch_update_date], [is_katello_covered], [is_desktop_central_covered], [patch_provenance], [ci_appliance], [boot_kernel], [effective_kernel], [is_kcare_covered], [is_eol], [numcpu], [memorygb], [provisionedspacegb], [missing_patches] from [dbo].[t_exp_patch_vm_coverage]


timestamp 
ASON
vm_created_date
latest_scan_date

[last_successful_scan_date], 
[last_patch_update_date],
yyyy-MM-dd'T'HH:mm:ss


numeric 
,[numcpu]
,[memorygb]
missing_patches  --  aryan


float doublt 
[ProvisionedSpaceGB]
#--arayn
CONVERT(VARCHAR(30), CAST(CAST(a11.LATEST_SCAN_DATE AS DATE) AS DATETIME), 126) AS LATEST_SCAN_DATE,