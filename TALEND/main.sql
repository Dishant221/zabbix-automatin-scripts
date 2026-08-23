T_EXP_VM_PATCH_COVERAGE
select [ason],[dc_id],[dc],[cluster_id],[cluster],[host_id],[host],[vm_id],[vm],[powerstate],[vm_created_date],[env_id],[env],[purpose_id],[purpose],[vcenter_id],[vcenter_server],[vcenter],[e2customer_id],[e2customer],[account_id],[account],[hub_id],[os_family_id],[os_family],[os_major_version],[is_db],[latest_scan_date],[av_installed],[isactive],[dc_provider],[product_family],[product_name],[sfdc_product_family],[sfdc_product_name],[hub_type],[sfdc_hub_type],[department_id],[department],[ps_practice],[covered_for_patching],[ip],[last_successful_scan_date],[last_patch_update_date],[is_katello_covered],[is_desktop_central_covered],[patch_provenance],[ci_appliance],[boot_kernel],[effective_kernel],[is_kcare_covered],[is_eol],[numcpu],[memorygb],[provisionedspacegb],[missing_patches] from [dbo].[t_exp_patch_vm_coverage];

___________________________________________________________________

t_exp_patch_aws_smm_details


	[IPAddress] [varchar](100) NULL : IP
    last_association_execution_date
     lastpingdatetime, last_successful_association_execution_date
     environment :env_name
     purpose_name: purpose
     product_name : product
     other_non_compliant_count

statement => "select [ason], [computer_name], [instanceid], [agentversion], [profile], [associationstatus], [platformname], [platformtype], [ip], [last_association_execution_date], [last_ping_date_time], [last_successful_association_execution_date], [pingstatus], [platformversion], [updated_flag], [dc_id], [dc], [env_id], [env], [purpose_id], [purpose], [account_id], [account], [product_family], [product_name], [is_hvp], [e2customer_id], [e2customer], [critical_non_compliant_count], [failed_count], [installed_count], [installed_other_count], [installed_pending_reboot_count], [installed_rejected_count], [missing_count], [not_applicable_count], [other_non_compliant_count], [security_non_compliant_count] from t_exp_patch_aws_smm_details;"


select [ason], 
[computer_name], 
[instance_id], 
[agentversion], 
[profile], 
[associationstatus], 
[platformname], 
[platformtype], 
[ip],
[last_association_execution_date],
[last_ping_date_time],
 [last_successful_association_execution_date],
  [pingstatus],
   [platform_version], platform_version
   [updated_flag],
    [dc_id],
     [dc_name], dc_name
     [env_id],
      [env], 
      [purpose_id],
       [purpose],
        [account_id],
         [account], 
         [product_family],
          [product_name],
           [is_hvp], 
           [e2customer_id], 
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
             [security_non_compliant_count] from [dbo].[t_exp_patch_aws_smm_details]______________________________


T_EXP_PATCH_KERNAL_CARE_DETAILS

select ason, 
dc, 
kcare_res_id,
 host_name,
  ip,
   account, 
   e2customer,
    product_family, 
    product_name, 
    patchset, 
    instance_name,
     kcare_version, 
     distro, 
     distro_version, 
     release, 
     euname, 
     checkin, 
     updated, 
     registered, 
     env,
      purpose, 
      os_family, 
      os_name, 
      os_major_version, 
      is_eol, 
      uptime from dbo.t_exp_patch_kernal_care_details
____________________________________
T_EXP_PATCH_KATELLO_DETAILS

select [ason], [katello_res_id], [resource_name], [dc_id], [dc], [ip], [env_id], [env], [purpose_id], [purpose], [account_id], [account], [e2customer_id], [e2customer], [hub_id], [product_family], [product_name], [operatingsystem_name], [os_version_id], [os_name], [os_family_id], [os_family], [os_major_version], [is_eol], [hostgroup], [boot_time], [build_status_label], [errata_status_label], [execution_status_label], [global_status_label], [hypervisor], [katello_instance_id], [instance_name], [url], [bmc_available], [kernel_version], [last_checkin], [last_compile], [registered_at], [updated_at], [updated_flag], [security], [bugfix], [enhancement], [total] from [dbo].[t_exp_patch_katello_details]
_______________________________________
T_EXP_PATCH_DESKTOP_CENTRAL_DETAILS

select [ason], [dc_res_id], [resource_name], [ip], [scan_status], [status_name], [status_label], [last_successful_scan], [updated_flag], [dc_id], [dc], [env_id], [env], [purpose_id], [purpose], [os_major_version], [os_family_id], [os_family], [is_eol], [account_id], [account], [e2customer_id], [e2customer], [product_family], [product_name], [resource_health_status], [health_status_name], [computer_live_status], [live_status_name], [last_patched_time], [remarks], [scan_remarks], [domain], [dc_instance_id], [instance_name], [os_name], [os_platform_name], [url], [missing_ms_patches], [missing_tp_patches], [total_ms_patches], [total_tp_patches], [installed_tp_patches], [installed_ms_patches], [total_missing_patches] from [dbo].[t_exp_patch_desktop_central_details]