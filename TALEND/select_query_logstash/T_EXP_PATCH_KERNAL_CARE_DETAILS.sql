SELECT [ASON]
      ,[DC]
      ,[kernal_care_resource_id]
      ,[host_name]
      ,[IP]
      ,[Account]
      ,[E2CUSTOMER]
      ,[Hub_ID]
      ,[Product_Family]
      ,[Product_Name]
      ,[patchset]
      ,[INSTANCE_NAME]
      ,[kcare_version]
      ,[distro]
      ,[distro_version]
      ,[release]
      ,[euname]
      ,[checkin]
      ,[updated]
      ,[registered]
      ,[ENV]
      ,[PURPOSE]
      ,[OS_FAMILY]
      ,[OS_NAME]
      ,[OS_MAJOR_VERSION]
      ,[IS_EOL]
      ,[uptime]
  FROM [dbo].[T_EXP_PATCH_KERNAL_CARE_DETAILS]



select [ason], [dc], [kernal_care_resource_id], [host_name], [ip], [account], [e2customer], [hub_id], [product_family], [product_name], [patchset], [instance_name], [kcare_version], [distro], [distro_version], [release], [euname], [checkin], [updated], [registered], [env], [purpose], [os_family], [os_name], [os_major_version], [is_eol], [uptime] from [dbo].[t_exp_patch_kernal_care_details]


timestamp 
ASON
checkin
updated
[uptime]

yyyy-MM-dd'T'HH:mm:ss
