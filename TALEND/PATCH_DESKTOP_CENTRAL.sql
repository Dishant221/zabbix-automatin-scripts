USE [CloudInsights_Prod]
GO
/****** Object:  StoredProcedure [dbo].[P_EXP_PATCH_DESKTOP_CENTRAL_DETAILS]    Script Date: 7/10/2026 5:39:14 AM ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
 

ALTER PROCEDURE [dbo].[P_EXP_PATCH_DESKTOP_CENTRAL_DETAILS]
AS
BEGIN

/******************************************************************************************
  Stored Procedure Name : [dbo].[P_EXP_DESKTOP_CENTRAL_PATCH_COVERAGE]
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

IF OBJECT_ID('dbo.T_EXP_PATCH_DESKTOP_CENTRAL_DETAILS', 'U') IS NOT NULL
DROP TABLE dbo.T_EXP_PATCH_DESKTOP_CENTRAL_DETAILS;

 select	
	CONVERT(VARCHAR(30), cast(cast(GETUTCDATE() as date) as datetime), 126)  AS [ASON],
	[a11].[DC_RES_ID]  [DC_RES_ID],
	[a11].[RESOURCE_NAME]  [RESOURCE_NAME],
	[a11].[IPV4]  [IP],
	[a11].[scan_status]  [scan_status],
	[a112].[status_name]  [status_name],
	[a11].[status_label]  [status_label],
	--[a11].[last_successful_scan]  [last_successful_scan],
	CONVERT(VARCHAR(19), [a11].[last_successful_scan], 126) AS [last_successful_scan],
	[a11].[UPDATED_FLAG]  [UPDATED_FLAG],
	[a11].[DC_ID]  [DC_ID],
	[a17].[DC_NAME]  [DC],
	[a11].[ENV_ID]  [ENV_ID],
	[a19].[ENV_NAME]  [ENV],
	[a11].[purpose_id]  [purpose_id],
	[a110].[PURPOSE_NAME]  [PURPOSE],
	[a13].[OS_MAJOR_VERSION]  [OS_MAJOR_VERSION],
	[a13].[OS_FAMILY_ID]  [OS_FAMILY_ID],
	[a14].[OS_FAMILY_NAME]  [OS_FAMILY],
	[a13].[IS_EOL]  [IS_EOL],
	[a11].[ACCOUNT_ID]  [ACCOUNT_ID],
	[a113].[Name]  [Account],
	[a11].[E2Customer_ID]  [E2Customer_ID],
	[a18].[Name]  [E2CUSTOMER],
	[a15].[Portfolio]  [Product_Family],
	[a15].[Product]  [Product_Name],
	[a11].[resource_health_status]  [resource_health_status],
	[a111].[health_status_name]  [health_status_name],
	[a11].[computer_live_status]  [computer_live_status],
	[a16].[live_status_name]  [live_status_name],
	--[a11].[last_patched_time]  [last_patched_time],
    CONVERT(VARCHAR(19), [a11].[last_patched_time], 126) AS [last_patched_time]
	[a11].[remarks]  [remarks],
	[a11].[scan_remarks]  [scan_remarks],
	[a11].[domain]  [domain],
	[a11].[DC_INSTANCE_ID]  [DC_INSTANCE_ID],
	[a12].[INSTANCE_NAME]  [INSTANCE_NAME],
	[a11].[os_name]  [os_name],
	[a11].[os_platform_name]  [os_platform_name],
	[a12].[URL]  [URL],
	[a11].[missing_ms_patches]  [missing_ms_patches],
	[a11].[missing_tp_patches]  [missing_tp_patches],
	[a11].[total_ms_patches]  [total_ms_patches],
	[a11].[total_tp_patches]  [total_tp_patches],
	[a11].[installed_tp_patches]  [installed_tp_patches],
	[a11].[installed_ms_patches]  [installed_ms_patches],
	([a11].[missing_ms_patches] + [a11].[missing_tp_patches])  [TOTAL_MISSING_PATCHES]
	into T_EXP_PATCH_DESKTOP_CENTRAL_DETAILS
from	[T_DIM_PATCH_DESKTOP_CENTRAL]	[a11]
	join	[T_DIM_PATCH_DESKTOP_CENTRAL_INSTANCE]	[a12]
	  on 	([a11].[DC_INSTANCE_ID] = [a12].[DC_INSTANCE_ID])
	join	[T_DIM_OS_VERSIONS]	[a13]
	  on 	([a11].[OS_VERSION_ID] = [a13].[OS_VERSION_ID])
	join	[T_DIM_OS_FAMILY]	[a14]
	  on 	([a13].[OS_FAMILY_ID] = [a14].[OS_FAMILY_ID])
	join	[T_DIM_SF_E2Customers]	[a15]
	  on 	([a11].[E2Customer_ID] = [a15].[E2Customer_ID])
	join	[T_DIM_PATCH_DESKTOP_CENTRAL_COMPUTER_LIVE_STATUS]	[a16]
	  on 	([a11].[computer_live_status] = [a16].[computer_live_status])
	join	[T_LU_DATACENTER]	[a17]
	  on 	([a11].[DC_ID] = [a17].[DC_ID])
	join	[T_LU_SF_E2CUSTOMERS]	[a18]
	  on 	([a11].[E2Customer_ID] = [a18].[E2Customer_ID])
	join	[T_DIM_ENVIRONMENT]	[a19]
	  on 	([a11].[ENV_ID] = [a19].[ENV_ID])
	join	[T_DIM_PURPOSE]	[a110]
	  on 	([a11].[purpose_id] = [a110].[purpose_id])
	join	[T_DIM_PATCH_DESKTOP_CENTRAL_RESOURCE_HEALTH_STATUS]	[a111]
	  on 	([a11].[resource_health_status] = [a111].[resource_health_status])
	join	[T_DIM_PATCH_DESKTOP_CENTRAL_SCAN_STATUS]	[a112]
	  on 	([a11].[scan_status] = [a112].[scan_status])
	join	[T_LU_SF_ACCOUNTS]	[a113]
	  on 	([a11].[ACCOUNT_ID] = [a113].[ACCOUNT_ID] and 
	[a15].[ACCOUNT_ID] = [a113].[ACCOUNT_ID])
where	[a11].[UPDATED_FLAG] in (1)

end