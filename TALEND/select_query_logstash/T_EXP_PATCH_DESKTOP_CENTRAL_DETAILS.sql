SELECT [ASON]
      ,[DC_RES_ID]
      ,[host_name]
      ,[IP]
      ,[scan_status]
      ,[status_name]
      ,[status_label]
      ,[last_successful_scan]
      ,[DC]
      ,[ENV]
      ,[PURPOSE]
      ,[OS_MAJOR_VERSION]
      ,[OS_FAMILY]
      ,[IS_EOL]
      ,[Account]
      ,[E2CUSTOMER]
      ,[Product_Family]
      ,[Product_Name]
      ,[resource_health_status]
      ,[health_status_name]
      ,[computer_live_status]
      ,[live_status_name]
      ,[last_patched_time]
      ,[remarks]
      ,[scan_remarks]
      ,[domain]
      ,[INSTANCE_NAME]
      ,[os_name]
      ,[os_platform_name]
      ,[URL]
      ,[missing_ms_patches]
      ,[missing_tp_patches]
      ,[total_ms_patches]
      ,[total_tp_patches]
      ,[installed_tp_patches]
      ,[installed_ms_patches]
      ,[TOTAL_MISSING_PATCHES]
  FROM [dbo].[T_EXP_PATCH_DESKTOP_CENTRAL_DETAILS]



select [ason],
 [dc_res_id],--not in elastic
  [host_name], 
  [ip], 
  [scan_status], --not in elastic
  [status_name], --not in elastic
  [status_label], --not in elastic
  [last_successful_scan], 
  [dc], 
  [env], 
  [purpose], 
  [os_major_version], 
  [os_family], 
  [is_eol], 
  [account], 
  [e2customer], 
  [product_family], 
  [product_name], 
  [resource_health_status], --not in elastic
  [health_status_name],  --not in elastic
  [computer_live_status],  --not in elastic
  [live_status_name], --not in elastic
   [last_patched_time],
    [remarks], 
    [scan_remarks],
     [domain],-- not in elastic
     [instance_name],
      [os_name], 
      [os_platform_name], --not in elastic
      [url], --not in elastic
      [missing_ms_patches], 
      [missing_tp_patches], 
      [total_ms_patches], 
      [total_tp_patches], 
      [installed_tp_patches], 
      [installed_ms_patches], 
      [total_missing_patches] from [dbo].[t_exp_patch_desktop_central_details]


timestamp
[ason],
[last_patched_time],
[last_successful_scan], 

interger/
[missing_ms_patches], 
      [missing_tp_patches], 
      [total_ms_patches], 
      [total_tp_patches], 
      [installed_tp_patches], 
      [installed_ms_patches], 
      [total_missing_patches]


      yyyy-MM-dd'T'HH:mm:ss