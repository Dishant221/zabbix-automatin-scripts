USE [CloudInsights_Prod]
GO
/****** Object:  StoredProcedure [dbo].[P_EXP_PATCH_KERNAL_CARE_DETAILS]    Script Date: 7/10/2026 5:04:45 AM ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO

 

ALTER PROCEDURE [dbo].[P_EXP_PATCH_KERNAL_CARE_DETAILS]
AS
BEGIN

/******************************************************************************************
  Stored Procedure Name : [dbo].[P_EXP_IS_TENABLE_VULNERABILITY_JAVA]
  Author                : Aryan
  Created Date          : 2026-05-21
  Description           : Extracts and exports Tenable asset details (mapped with VM, OS,
                          SFDC, and infrastructure data) into export table for reporting
                          and observability.

  Features:
  - Groups Tenable, VM, OS, and SFDC attributes
  - Applies fallback logic for unknown values
  - Formats timestamps for reporting
  - Handles multi-IP scenarios

  Modification History:
  ------------------------------------------------------------------------------------------
  Date         | Modified By | Description
  ------------------------------------------------------------------------------------------
  2026-05-21   | Aryan       | Initial version
******************************************************************************************/


 --Step 1: Drop existing vulnerability export table if it exists

IF OBJECT_ID('dbo.T_EXP_PATCH_KERNAL_CARE_DETAILS', 'U') IS NOT NULL
DROP TABLE dbo.T_EXP_PATCH_KERNAL_CARE_DETAILS;
 --Step 2: Export deduplicated Rapid7 vulnerability details using latest asset per VM from staging

 select	
	CONVERT(VARCHAR(30), cast(cast(GETUTCDATE() as date) as datetime), 126)  AS [ASON],
	[a11].[DC_ID]  [DC_ID],
	[a110].[DC_NAME]  [DC],
	[a11].[KCARE_RES_ID]  [KCARE_RES_ID],
	[a11].[RESOURCE_NAME]  [RESOURCE_NAME],
	[a11].[IPV4]  [IP],
	[a11].[ACCOUNT_ID]  [ACCOUNT_ID],
	[a19].[Name]  [Account],
	[a11].[E2Customer_ID]  [E2Customer_ID],
	[a15].[Name]  E2CUSTOMER,
	[a14].[Hub_Identifier__c]  [Hub_ID],
	[a14].[Portfolio]  [Product_Family],
	[a14].[Product]  [Product_Name],
	[a11].[patchset]  [patchset],
	[a11].[KCARE_INSTANCE_ID]  [KCARE_INSTANCE_ID],
	[a17].[INSTANCE_NAME]  [INSTANCE_NAME],
	[a11].[kcare_version]  [kcare_version],
	[a11].[distro]  [distro],
	[a11].[distro_version]  [distro_version],
	[a11].[release]  [release],
	[a11].[euname]  [euname],
	[a11].[checkin]  [checkin],
	[a11].[updated]  [updated],
	[a11].[UPDATED_FLAG]  [UPDATED_FLAG],
	[a11].[registered]  [registered],
	[a11].[ENV_ID]  [ENV_ID],
	[a16].[ENV_NAME]  [ENV],
	[a11].[purpose_id]  [purpose_id],
	[a18].[PURPOSE_NAME]  [PURPOSE],
	[a12].[OS_FAMILY_ID]  [OS_FAMILY_ID],
	[a13].[OS_FAMILY_NAME]  [OS_FAMILY],
	[a11].[OS_VERSION_ID]  [OS_VERSION_ID],
	[a12].[os_name]  [OS_NAME],
	[a12].[OS_MAJOR_VERSION]  [OS_MAJOR_VERSION],
	[a12].[IS_EOL]  [IS_EOL],
	[a11].[uptime]  [uptime]
	into T_EXP_PATCH_KERNAL_CARE_DETAILS
from	[T_DIM_PATCH_KERNEL_CARE]	[a11]
	join	[T_DIM_OS_VERSIONS]	[a12]
	  on 	([a11].[OS_VERSION_ID] = [a12].[OS_VERSION_ID])
	join	[T_DIM_OS_FAMILY]	[a13]
	  on 	([a12].[OS_FAMILY_ID] = [a13].[OS_FAMILY_ID])
	join	[T_DIM_SF_E2Customers]	[a14]
	  on 	([a11].[E2Customer_ID] = [a14].[E2Customer_ID])
	join	[T_LU_SF_E2CUSTOMERS]	[a15]
	  on 	([a11].[E2Customer_ID] = [a15].[E2Customer_ID])
	join	[T_DIM_ENVIRONMENT]	[a16]
	  on 	([a11].[ENV_ID] = [a16].[ENV_ID])
	join	[T_DIM_PATCH_KERNEL_CARE_INSTANCE]	[a17]
	  on 	([a11].[KCARE_INSTANCE_ID] = [a17].[KCARE_INSTANCE_ID])
	join	[T_DIM_PURPOSE]	[a18]
	  on 	([a11].[purpose_id] = [a18].[purpose_id])
	join	[T_LU_SF_ACCOUNTS]	[a19]
	  on 	([a11].[ACCOUNT_ID] = [a19].[ACCOUNT_ID] and 
	[a14].[ACCOUNT_ID] = [a19].[ACCOUNT_ID])
	join	[T_LU_DATACENTER]	[a110]
	  on 	([a11].[DC_ID] = [a110].[DC_ID])
where	[a11].[UPDATED_FLAG] in (1)



 end