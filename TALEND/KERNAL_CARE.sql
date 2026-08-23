select [ason], [dc], [kernal_care_resource_id], [host_name], [ip], [account], [e2customer], [product_family], [product_name], [patchset], [instance_name], [kcare_version], [distro], [distro_version], [release], [euname], [checkin], [updated], [registered], [env], [purpose], [os_family], [os_name], [os_major_version], [is_eol], [uptime] from [dbo].[t_exp_patch_kernal_care_details]

data_stream_dataset => "kernal-care-patch"
      data_stream_namespace => "kernal-care-patch-details" 