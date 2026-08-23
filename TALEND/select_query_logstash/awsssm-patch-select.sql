SELECT [ASON]
      ,[host_name]
      ,[instanceid]
      ,[AgentVersion]
      ,[Profile]
      ,[AssociationStatus]
      ,[PlatformName]
      ,[PlatformType]
      ,[IP]
      ,[LAST_ASSOCIATION_EXECUTION_DATE]
      ,[LAST_PING_DATE_TIME]
      ,[LAST_SUCCESSFUL_ASSOCIATION_EXECUTION_DATE]
      ,[PingStatus]
      ,[Platform_Version]
      ,[DC]
      ,[ENV_ID]
      ,[ENV]
      ,[PURPOSE]
      ,[ACCOUNT]
      ,[Product_Family]
      ,[Product_Name]
      ,[Is_HVP]
      ,[E2CUSTOMER]
      ,[CRITICAL_NON_COMPLIANT_COUNT]
      ,[FAILED_COUNT]
      ,[INSTALLED_COUNT]
      ,[INSTALLED_OTHER_COUNT]
      ,[INSTALLED_PENDING_REBOOT_COUNT]
      ,[INSTALLED_REJECTED_COUNT]
      ,[MISSING_COUNT]
      ,[NOT_APPLICABLE_COUNT]
      ,[OTHER_NON_COMPLIANT_COUNT]
      ,[SECURITY_NON_COMPLIANT_COUNT]
  FROM [dbo].[T_EXP_PATCH_AWS_SMM_DETAILS]



  [LAST_ASSOCIATION_EXECUTION_DATE]
      ,[LAST_PING_DATE_TIME]
      ,[LAST_SUCCESSFUL_ASSOCIATION_EXECUTION_DATE]

________________________________________________
select [ason], [host_name], [instanceid], [agentversion], [profile], [associationstatus], [platformname], [platformtype], [ip], 
[last_association_execution_date], 
[last_ping_date_time], 
[last_successful_association_execution_date], 

[pingstatus], 
[platform_version], 
[dc], 
[env_id], 
[env],
 [purpose],
  [account],
   [product_family], 
   [product_name], 
   [is_hvp],
    [e2customer], 
    [critical_non_compliant_count], 
    [failed_count], 
    [installed_count],
     [installed_other_count],
      [installed_pending_reboot_count],
       [installed_rejected_count],
        [missing_count], 
        [not_applicable_count], 
        [other_non_compliant_count], 
        [security_non_compliant_count] from [dbo].[t_exp_patch_aws_smm_details]


timestamp
[ason],
[last_association_execution_date], 
[last_ping_date_time], 
[last_successful_association_execution_date], 

integer/numeric

[installed_other_count]
   [installed_pending_reboot_count],
       [installed_rejected_count],
        [missing_count], 
        [not_applicable_count], 
        [other_non_compliant_count], 
        [security_non_compliant_count]
        [critical_non_compliant_count], 
    [failed_count], 
    [installed_count]


float/numric


