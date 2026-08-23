USE [CloudInsights_Prod]
GO
/****** Object:  StoredProcedure [dbo].[P_EXP_PATCH_AWS_SSM_DETAILS]    Script Date: 7/10/2026 4:03:29 AM ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
 

ALTER PROCEDURE [dbo].[P_EXP_PATCH_AWS_SSM_DETAILS]
AS
BEGIN

/******************************************************************************************
  Stored Procedure Name : [dbo].[[[P_EXP_AWS_SSM_PATCH_COVERAGE]]]
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

IF OBJECT_ID('dbo.T_EXP_PATCH_AWS_SMM_DETAILS', 'U') IS NOT NULL
DROP TABLE dbo.T_EXP_PATCH_AWS_SMM_DETAILS;
 --Step 2: Export deduplicated Rapid7 vulnerability details using latest asset per VM from staging

 select	
	CONVERT(VARCHAR(30), cast(cast(GETUTCDATE() as date) as datetime), 126)  AS [ASON],
	[a11].[ComputerName]  [ComputerName],
	[a11].[instanceid]  [instanceid],
	[a11].[AgentVersion]  [AgentVersion],
	[a11].[Profile]  [Profile],
	[a11].[AssociationStatus]  [AssociationStatus],
	[a11].[PlatformName]  [PlatformName],
	[a11].[PlatformType]  [PlatformType],
	[a11].[IPAddress]  as IP,
	CONVERT(VARCHAR(30), CAST(CAST(a11.LAST_ASSOCIATION_EXECUTION_DATE AS DATE) AS DATETIME), 126) AS  [LAST_ASSOCIATION_EXECUTION_DATE],
	CONVERT(VARCHAR(30), CAST(CAST(a11.LAST_PING_DATE_TIME AS DATE) AS DATETIME), 126) AS   [LAST_PING_DATE_TIME],
	CONVERT(VARCHAR(30), CAST(CAST(a11.LAST_SUCCESSFUL_ASSOCIATION_EXECUTION_DATE AS DATE) AS DATETIME), 126) AS   [LAST_SUCCESSFUL_ASSOCIATION_EXECUTION_DATE],
	[a11].[PingStatus]  [PingStatus],
	[a11].[PlatformVersion]  [PlatformVersion],
	[a11].[UPDATED_FLAG]  [UPDATED_FLAG],
	[a11].[DC_ID]  [DC_ID],
	[a13].[DC_NAME]  [DC],
	[a11].[ENV_ID]  [ENV_ID],
	[a15].[ENV_NAME]  [ENV],
	[a11].[purpose_id]  [purpose_id],
	[a16].[PURPOSE_NAME]  [PURPOSE],
	[a11].[ACCOUNT_ID]  [ACCOUNT_ID],
	[a17].[Name]  [ACCOUNT],
	[a12].[Portfolio]  [Product_Family],
	[a12].[Product]  [Product_Name],
	[a12].[Is_HVP]  [Is_HVP],
	[a11].[E2Customer_ID]  [E2Customer_ID],
	[a14].[Name]  [E2CUSTOMER],
	[a11].[CriticalNonCompliantCount]  [CRITICAL_NON_COMPLIANT_COUNT],
	[a11].[FailedCount]  [FAILED_COUNT],
	[a11].[InstalledCount]  [INSTALLED_COUNT],
	[a11].[InstalledOtherCount]  [INSTALLED_OTHER_COUNT],
	[a11].[InstalledPendingRebootCount]  [INSTALLED_PENDING_REBOOT_COUNT],
	[a11].[InstalledRejectedCount]  [INSTALLED_REJECTED_COUNT],
	[a11].[MissingCount]  [MISSING_COUNT],
	[a11].[NotApplicableCount]  [NOT_APPLICABLE_COUNT],
	[a11].[OtherNonCompliantCount]  [OTHER_NON_COMPLIANT_COUNT],
	[a11].[SecurityNonCompliantCount]  [SECURITY_NON_COMPLIANT_COUNT]

	into T_EXP_PATCH_AWS_SMM_DETAILS
from	[T_DIM_PATCH_AWS_SSM]	[a11]
	join	[T_DIM_SF_E2Customers]	[a12]
	  on 	([a11].[E2Customer_ID] = [a12].[E2Customer_ID])
	join	[T_LU_DATACENTER]	[a13]
	  on 	([a11].[DC_ID] = [a13].[DC_ID])
	join	[T_LU_SF_E2CUSTOMERS]	[a14]
	  on 	([a11].[E2Customer_ID] = [a14].[E2Customer_ID])
	join	[T_DIM_ENVIRONMENT]	[a15]
	  on 	([a11].[ENV_ID] = [a15].[ENV_ID])
	join	[T_DIM_PURPOSE]	[a16]
	  on 	([a11].[purpose_id] = [a16].[purpose_id])
	join	[T_LU_SF_ACCOUNTS]	[a17]
	  on 	([a11].[ACCOUNT_ID] = [a17].[ACCOUNT_ID] and 
	[a12].[ACCOUNT_ID] = [a17].[ACCOUNT_ID])
where	[a11].[UPDATED_FLAG] in (1)
 

	end