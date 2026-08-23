USE [CloudInsights_Prod]
GO
/****** Object:  StoredProcedure [dbo].[P_EXP_IS_TENABLE_VULNERABILITY]    Script Date: 6/10/2026 7:07:50 AM ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
 

ALTER PROCEDURE [dbo].[P_EXP_IS_TENABLE_VULNERABILITY]
AS
BEGIN

/******************************************************************************************
  Stored Procedure Name : [dbo].[P_EXP_IS_TENABLE_VULNERABILITY]
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

IF OBJECT_ID('dbo.T_EXP_IS_TENABLE_VULNERABILITY_DETAILS', 'U') IS NOT NULL
DROP TABLE dbo.T_EXP_IS_TENABLE_VULNERABILITY_DETAILS;
 --Step 2: Export deduplicated Rapid7 vulnerability details using latest asset per VM from staging

SELECT
    CONVERT(VARCHAR(30), cast(cast(GETUTCDATE() as date) as datetime), 126)                           AS [ASON],
    CONVERT(VARCHAR(30), CAST(a11.scan_started_at AS DATETIME), 126) AS [LATEST_SCAN_DATE],
    CONVERT(VARCHAR(30), CAST(isnull(a11.vuln_published_date ,a11.vuln_first_found)AS DATETIME), 126) AS [VUL_PUBLISHED_DATE],
    CONVERT(VARCHAR(30), CAST(a11.vuln_first_found AS DATETIME), 126) AS [VUL_DETECTION_DATE],
    CONVERT(VARCHAR(30), CAST(a15.VM_CREATED_DATE AS DATETIME), 126) AS [VM_CREATED_DATE],
    a11.VM_ID AS [VM_ID],
    a15.VM_NAME AS [VM_NAME],
    a114.DC_NAME AS [DC_NAME],
    a114.DC_PROVIDER AS [DC_PROVIDER],
    CASE 
        WHEN a12.IPv4 IS NOT NULL 
             AND a12.IPv4 LIKE '%;%' 
        THEN LEFT(a12.IPv4, CHARINDEX(';', a12.IPv4) - 1)
        ELSE a12.IPv4 
    END AS [IP],
    a133.OS_FAMILY_NAME AS OS_FAMILY,
    a13.OS_NAME AS [OS_NAME],
    a13.OS_MAJOR_VERSION AS [OS_MAJOR_VERSION],
    a13.IS_EOL AS IS_EOL,
    CONVERT(VARCHAR(30), CAST(a13.EOL_ON AS DATETIME), 126) AS [EOL_ON],
    CONVERT(VARCHAR(30), CAST(a13.RELEASED_ON AS DATETIME), 126) AS RELEASED_ON,
    a16.Name AS [Account],
    a14.Name AS [E2Customer],
    a14.Hub_Type__c AS [Hub_Type],
    ISNULL(NULLIF(LTRIM(RTRIM(a14.Product)), ''), '<UNKNOWN>') AS [Product_Name],
    ISNULL(NULLIF(a14.Portfolio, ''), '<UNKNOWN>') AS [Product_Family],
    ISNULL(NULLIF(a14.Is_HVP, ''), '<UNKNOWN>') AS Is_HVP,
    ISNULL(NULLIF(a14.Status, ''), '<UNKNOWN>') AS [Status],
    ISNULL(NULLIF(a14.CSM, ''), '<UNKNOWN>') AS [CSM],
    ISNULL(NULLIF(a14.CSE, ''), '<UNKNOWN>') AS [CSE],
    ISNULL(NULLIF(a15.ci_solution, ''), '<UNKNOWN>') AS ci_solution,

    ISNULL(NULLIF(a14.Product_Version, ''), '<UNKNOWN>') AS [Product_Version],
    ISNULL(NULLIF(a14.Product_Release_Year, ''), 2015) AS [Product_Release_Year],
    ISNULL(NULLIF(a14.Latest_BR_Version__c, ''), '<UNKNOWN>') AS [Hub_Version],
    ISNULL(NULLIF(a14.Hub_Identifier__c, ''), '<UNKNOWN>') AS hub_id,
    ISNULL(NULLIF(a16.PS_Practice__c, ''), '<UNKNOWN>') AS PS_Practice,
    ISNULL(a11.vuln_id, '<UNKNOWN>') AS related_cve_ids,
    ISNULL(a11.vuln_description, '<UNKNOWN>') AS [VULNERABILITY],
    ISNULL(a11.vuln_output, '<UNKNOWN>') AS [PROOF],
    a112.env_name AS [ENVIRONMENT],
    a113.PURPOSE_NAME AS [PURPOSE],
    ISNULL(a11.vuln_severity, '<UNKNOWN>') AS [SEVERITY],
    ISNULL(a11.plugin_solution, '<UNKNOWN>') AS [SOLUTION],
    a11.ageBin,
    a11.DAYS_AGE,
    a11.AGEBIN_ORDINAL,
    a11.host_name AS [ASSET_NAME],
    a11.TENABLE_ID AS [ASSET_ID],
    a11.plugin_vpr_score AS [vpr_score],
    ISNULL(NULLIF(a15.CI_USAGE, ''), '<UNKNOWN>') AS CI_USAGE,
    CASE 
        WHEN a15.is_db = 1 THEN 'Yes'
        ELSE 'No'
    END AS IsDB,
    -- Newly added columns from a11
    ISNULL(NULLIF(LTRIM(RTRIM(a11.host_id)), ''), '<UNKNOWN>') AS host_id,
    ISNULL(NULLIF(LTRIM(RTRIM(a11.event_id)), ''), '<UNKNOWN>') AS event_id,
    ISNULL(NULLIF(LTRIM(RTRIM(a11.report_confidence)), ''), '<UNKNOWN>') AS report_confidence,
    ISNULL(NULLIF(LTRIM(RTRIM(a11.remediation_level)), ''), '<UNKNOWN>') AS remediation_level,
    ISNULL(NULLIF(LTRIM(RTRIM(a11.exploitability)), ''), '<UNKNOWN>') AS exploitability,
    ISNULL(NULLIF(LTRIM(RTRIM(a11.plugin_risk_factor)), ''), '<UNKNOWN>') AS plugin_risk_factor,
    ISNULL(NULLIF(LTRIM(RTRIM(a11.plugin_type)), ''), '<UNKNOWN>') AS plugin_type,
    CONVERT(VARCHAR(30), CAST(a11.plugin_vpr_updated AS DATETIME), 126) AS plugin_vpr_updated,
    ISNULL(NULLIF(LTRIM(RTRIM(a11.cve_id)), ''), '<UNKNOWN>') AS cve_id,
    ISNULL(CONVERT(VARCHAR(30), CAST(a11.plugin_publication_date AS DATETIME), 126), '<UNKNOWN>') AS plugin_publication_date,
    ISNULL(NULLIF(LTRIM(RTRIM(a11.vuln_state)), ''), '<UNKNOWN>') AS vuln_state,
    ISNULL(NULLIF(LTRIM(RTRIM(a11.vuln_source)), ''), '<UNKNOWN>') AS vuln_source,
    ISNULL(NULLIF(LTRIM(RTRIM(a11.vuln_classification)), ''), '<UNKNOWN>') AS vuln_classification,
    ISNULL(NULLIF(LTRIM(RTRIM(a11.vuln_title)), ''), '<UNKNOWN>') AS vuln_title,
    ISNULL(NULLIF(LTRIM(RTRIM(a11.vuln_category)), ''), '<UNKNOWN>') AS vuln_category

INTO T_EXP_IS_TENABLE_VULNERABILITY_DETAILS

FROM T_DIM_IS_TENABLE_VULNERABILITY a11
JOIN T_DIM_IS_TENABLE_ASSETS a12
    ON a11.TENABLE_ID = a12.TENABLE_ID
JOIN T_DIM_OS_VERSIONS a13
    ON a11.OS_VERSION_ID = a13.OS_VERSION_ID
JOIN T_DIM_OS_FAMILY a133
    ON a133.OS_FAMILY_ID = a13.OS_FAMILY_ID
JOIN T_DIM_SF_E2Customers a14
    ON a11.E2Customer_ID = a14.E2Customer_ID
JOIN T_DIM_VCENTER_VM a15
    ON a11.VM_ID = a15.VM_ID
JOIN T_DIM_SF_ACCOUNTS a16
    ON a14.ACCOUNT_ID = a16.ACCOUNT_ID
JOIN t_dim_environment a112
    ON a11.env_id = a112.env_id  
JOIN t_dim_PURPOSE a113
    ON a11.PURPOSE_id = a113.PURPOSE_id  
JOIN T_DIM_DATACENTER a114
    ON a11.DC_ID = a114.DC_ID  
WHERE 
    a11.VM_ID > 0  
    AND a15.PowerState = 'PoweredOn'
    AND a133.OS_FAMILY_NAME != 'UNMANAGED - Appliance' and a11.plugin_risk_factor!='info'
	and a11.vuln_state!='FIXED' ;

--Step 3: Drop existing vulnerability export table if it exists

	IF OBJECT_ID('dbo.T_EXP_IS_TENABLE_VULNERABILITY_AGGREGATE', 'U') IS NOT NULL
	DROP TABLE dbo.T_EXP_IS_TENABLE_VULNERABILITY_AGGREGATE;
	 --Step 4: Export Aggregated vulnerability 
 
	SELECT
		[ASON],
		[VM_ID],
		[VM_NAME],
		[DC_NAME],
		[DC_PROVIDER],
		[IP],
		[OS_FAMILY],
		[OS_NAME],
		[OS_MAJOR_VERSION],
		[IS_EOL],
		[Account],
		[E2Customer],
		[Hub_Type],
		[Product_Name],
		[Product_Family],
		[Is_HVP],
		[CSM],
		[CSE],
		[ci_solution],
		[Product_Version],
		[Product_Release_Year],
		[Hub_Version],
		[hub_id],
		[PS_Practice],
		[ENVIRONMENT],
		[PURPOSE],
		[SEVERITY],
		[ageBin],
		[ASSET_NAME],
		[ASSET_ID],
		[IsDB],
		[plugin_risk_factor],
		[plugin_type],
		[vuln_state],
		ROUND(SUM(ISNULL([vpr_score], 0)), 1) AS [vpr_score],
		COUNT(*) AS vuls
	INTO T_EXP_IS_TENABLE_VULNERABILITY_AGGREGATE
	FROM 
		[dbo].[T_EXP_IS_TENABLE_VULNERABILITY_DETAILS]
	GROUP BY 
		[ASON],
		[VM_ID],
		[VM_NAME],
		[DC_NAME],
		[DC_PROVIDER],
		[IP],
		[OS_FAMILY],
		[OS_NAME],
		[OS_MAJOR_VERSION],
		[IS_EOL],
		[Account],
		[E2Customer],
		[Hub_Type],
		[Product_Name],
		[Product_Family],
		[Is_HVP],
		[CSM],
		[CSE],
		[ci_solution],
		[Product_Version],
		[Product_Release_Year],
		[Hub_Version],
		[hub_id],
		[PS_Practice],
		[ENVIRONMENT],
		[PURPOSE],
		[SEVERITY],
		[ageBin],
		[ASSET_NAME],
		[ASSET_ID],
		[IsDB],
		[plugin_risk_factor],
		[plugin_type],
		[vuln_state]




   ------------------------------------------------------------------
    -- Step 5: Delete today's snapshot from history table
    -- Ensures only one snapshot per day is retained
    ------------------------------------------------------------------
    DELETE FROM dbo.[T_EXP_IS_TENABLE_VULNERABILITY_AGGREGATE_HISTORY]
    WHERE CAST(ASON AS DATE) = CAST(GETUTCDATE() AS DATE);

    ------------------------------------------------------------------
    -- Step 6: Insert fresh aggregate snapshot into history table
    -- Preserves daily counts for reporting and trend analysis
    ------------------------------------------------------------------
INSERT INTO [dbo].[T_EXP_IS_TENABLE_VULNERABILITY_AGGREGATE_HISTORY]
           ([ASON]
		  ,[VM_ID]
		  ,[VM_NAME]
		  ,[DC_NAME]
		  ,[DC_PROVIDER]
		  ,[IP]
		  ,[OS_FAMILY]
		  ,[OS_NAME]
		  ,[OS_MAJOR_VERSION]
		  ,[IS_EOL]
		  ,[Account]
		  ,[E2Customer]
		  ,[Hub_Type]
		  ,[Product_Name]
		  ,[Product_Family]
		  ,[Is_HVP]
		  ,[CSM]
		  ,[CSE]
		  ,[ci_solution]
		  ,[Product_Version]
		  ,[Product_Release_Year]
		  ,[Hub_Version]
		  ,[hub_id]
		  ,[PS_Practice]
		  ,[ENVIRONMENT]
		  ,[PURPOSE]
		  ,[SEVERITY]
		  ,[ageBin]
		  ,[ASSET_NAME]
		  ,[ASSET_ID]
		  ,[IsDB]
		  ,[plugin_risk_factor]
		  ,[plugin_type]
		  ,[vuln_state]
		  ,[vpr_score]
		  ,[vuls])


SELECT [ASON]
      ,[VM_ID]
      ,[VM_NAME]
      ,[DC_NAME]
      ,[DC_PROVIDER]
      ,[IP]
      ,[OS_FAMILY]
      ,[OS_NAME]
      ,[OS_MAJOR_VERSION]
      ,[IS_EOL]
      ,[Account]
      ,[E2Customer]
      ,[Hub_Type]
      ,[Product_Name]
      ,[Product_Family]
      ,[Is_HVP]
      ,[CSM]
      ,[CSE]
      ,[ci_solution]
      ,[Product_Version]
      ,[Product_Release_Year]
      ,[Hub_Version]
      ,[hub_id]
      ,[PS_Practice]
      ,[ENVIRONMENT]
      ,[PURPOSE]
      ,[SEVERITY]
      ,[ageBin]
      ,[ASSET_NAME]
      ,[ASSET_ID]
      ,[IsDB]
      ,[plugin_risk_factor]
      ,[plugin_type]
      ,[vuln_state]
      ,[vpr_score]
      ,[vuls]
  FROM [dbo].[T_EXP_IS_TENABLE_VULNERABILITY_AGGREGATE]





END