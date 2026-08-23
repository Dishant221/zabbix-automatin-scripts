SELECT [ASON]
      ,[KATELLO_RES_ID]
      ,[host_name]
      ,[DC]
      ,[IP]
      ,[ENV]
      ,[PURPOSE]
      ,[Account]
      ,[E2CUSTOMER]
      ,[Hub_ID]
      ,[Product_Family]
      ,[Product_Name]
      ,[operatingsystem_name]
      ,[os_name]
      ,[OS_FAMILY]
      ,[OS_MAJOR_VERSION]
      ,[IS_EOL]
      ,[hostgroup]
      ,[boot_time]
      ,[build_status_label]
      ,[errata_status_label]
      ,[execution_status_label]
      ,[global_status_label]
      ,[hypervisor]
      ,[KATELLO_INSTANCE_ID]
      ,[INSTANCE_NAME]
      ,[URL]
      ,[bmc_available]
      ,[kernel_version]
      ,[last_checkin]
      ,[last_compile]
      ,[registered_at]
      ,[updated_at]
      ,[security]
      ,[bugfix]
      ,[enhancement]
      ,[total]
  FROM [dbo].[T_EXP_PATCH_KATELLO_DETAILS]




select [ason],
 [katello_res_id], 
 [host_name], 
 [dc], 
 [ip], 
 [env], 
 [purpose], 
 [account], 
 [e2customer], 
 [hub_id], 
 [product_family],
  [product_name],
   [operatingsystem_name],
    [os_name], 
    [os_family],
     [os_major_version],
      [is_eol], 
      [hostgroup], 
      [boot_time],
       [build_status_label], 
       [errata_status_label],
        [execution_status_label],
         [global_status_label],
          [hypervisor], 
          [katello_instance_id],
           [instance_name], 
           [url], 
           [bmc_available],
            [kernel_version], 
            [last_checkin], 
            [last_compile], 
            [registered_at],
             [updated_at], 
             [security], 
             [bugfix], 
             [enhancement],
              [total] from [dbo].[t_exp_patch_katello_details]


timestamp
ason
[boot_time],
[last_checkin], 
[last_compile], 
[registered_at],
[updated_at]


interger

[security], 
             [bugfix], 
             [enhancement],
              [total]

yyyy-MM-dd'T'HH:mm:ss

