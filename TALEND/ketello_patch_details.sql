USE [CloudInsights_Prod]
GO
/****** Object:  StoredProcedure [dbo].[P_EXP_PATCH_KATELLO_DETAILS]    Script Date: 7/10/2026 5:25:10 AM ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
 

ALTER PROCEDURE [dbo].[P_EXP_PATCH_KATELLO_DETAILS]
AS
BEGIN

/******************************************************************************************
  Stored Procedure Name : [dbo].[P_EXP_KATELLO_PATCH_COVERAGE]
  Author                : Aryan
  Created Date          : 2026-05-21
  Description           : Extracts and exports Tenable asset details (mapped with VM, OS,
                          SFDC, and infrastructure data) into export table for reporting
                          and observability.

  Features:
  

  Modification History:
  ------------------------------------------------------------------------------------------
  Date         | Modified By | Description
  ------------------------------------------------------------------------------------------
  2026-05-21   | DISHANT       | Initial version
******************************************************************************************/


 --Step 1: Drop existing AWS SSM export table if it exists

IF OBJECT_ID('dbo.T_EXP_PATCH_KATELLO_DETAILS', 'U') IS NOT NULL
DROP TABLE dbo.T_EXP_PATCH_KATELLO_DETAILS;

select	
	CONVERT(VARCHAR(30), cast(cast(GETUTCDATE() as date) as datetime), 126)  AS [ASON],
	[a11].[KATELLO_RES_ID]  [KATELLO_RES_ID],
	[a11].[RESOURCE_NAME]  [RESOURCE_NAME],
	[a11].[DC_ID]  [DC_ID],
	[a110].[DC_NAME]  [DC],
	[a11].[IPV4]  [IP],
	[a11].[ENV_ID]  [ENV_ID],
	[a17].[ENV_NAME]  [ENV],
	[a11].[purpose_id]  [purpose_id],
	[a18].[PURPOSE_NAME]  [PURPOSE],
	[a11].[ACCOUNT_ID]  [ACCOUNT_ID],
	[a19].[Name]  [Account],
	[a11].[E2Customer_ID]  [E2Customer_ID],
	[a16].[Name]  [E2CUSTOMER],
	[a15].[Hub_Identifier__c]  [Hub_ID],
	[a15].[Portfolio]  [Product_Family],
	[a15].[Product]  [Product_Name],
	[a11].[operatingsystem_name]  [operatingsystem_name],
	[a11].[OS_VERSION_ID]  [OS_VERSION_ID],
	[a12].[os_name]  [os_name],
	[a12].[OS_FAMILY_ID]  [OS_FAMILY_ID],
	[a14].[OS_FAMILY_NAME]  [OS_FAMILY],
	[a12].[OS_MAJOR_VERSION]  [OS_MAJOR_VERSION],
	[a12].[IS_EOL]  [IS_EOL],
	[a11].[hostgroup_name]  [hostgroup],
	[a11].[boot_time]  [boot_time],
	[a11].[build_status_label]  [build_status_label],
	[a11].[errata_status_label]  [errata_status_label],
	[a11].[execution_status_label]  [execution_status_label],
	[a11].[global_status_label]  [global_status_label],
	[a11].[hypervisor]  [hypervisor],
	[a11].[KATELLO_INSTANCE_ID]  [KATELLO_INSTANCE_ID],
	[a13].[INSTANCE_NAME]  [INSTANCE_NAME],
	[a13].[URL]  [URL],
	[a11].[bmc_available]  [bmc_available],
	[a11].[kernel_version]  [kernel_version],
	--[a11].[last_checkin]  [last_checkin],
	--[a11].[last_compile]  [last_compile],
	--[a11].[registered_at]  [registered_at],
	--[a11].[updated_at]  [updated_at],
    CONVERT(VARCHAR(30), CAST(CAST([a11].[last_checkin] AS DATE) AS DATETIME), 126) AS [last_checkin],
    CONVERT(VARCHAR(30), CAST(CAST([a11].[last_compile] AS DATE) AS DATETIME), 126) AS [last_compile],
    CONVERT(VARCHAR(30), CAST(CAST([a11].[registered_at] AS DATE) AS DATETIME), 126) AS [registered_at],
    CONVERT(VARCHAR(30), CAST(CAST([a11].[updated_at] AS DATE) AS DATETIME), 126) AS [updated_at],
	[a11].[UPDATED_FLAG]  [UPDATED_FLAG],
	[a11].[security]  [security],
	[a11].[bugfix]  [bugfix],
	[a11].[enhancement]  [enhancement],
	[a11].[total]  [total]
	into T_EXP_PATCH_KATELLO_DETAILS
from	[T_DIM_PATCH_KATELLO]	[a11]
	join	[T_DIM_OS_VERSIONS]	[a12]
	  on 	([a11].[OS_VERSION_ID] = [a12].[OS_VERSION_ID])
	join	[T_DIM_PATCH_KATELLO_INSTANCE]	[a13]
	  on 	([a11].[KATELLO_INSTANCE_ID] = [a13].[KATELLO_INSTANCE_ID])
	join	[T_DIM_OS_FAMILY]	[a14]
	  on 	([a12].[OS_FAMILY_ID] = [a14].[OS_FAMILY_ID])
	join	[T_DIM_SF_E2Customers]	[a15]
	  on 	([a11].[E2Customer_ID] = [a15].[E2Customer_ID])
	join	[T_LU_SF_E2CUSTOMERS]	[a16]
	  on 	([a11].[E2Customer_ID] = [a16].[E2Customer_ID])
	join	[T_DIM_ENVIRONMENT]	[a17]
	  on 	([a11].[ENV_ID] = [a17].[ENV_ID])
	join	[T_DIM_PURPOSE]	[a18]
	  on 	([a11].[purpose_id] = [a18].[purpose_id])
	join	[T_LU_SF_ACCOUNTS]	[a19]
	  on 	([a11].[ACCOUNT_ID] = [a19].[ACCOUNT_ID] and 
	[a15].[ACCOUNT_ID] = [a19].[ACCOUNT_ID])
	join	[T_LU_DATACENTER]	[a110]
	  on 	([a11].[DC_ID] = [a110].[DC_ID])
where	[a11].[UPDATED_FLAG] in (1)

end