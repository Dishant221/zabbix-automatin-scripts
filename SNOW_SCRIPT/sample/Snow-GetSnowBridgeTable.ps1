#==============================================================================
# Snow Atlas API - Export Bridge Table (Datacenter / Hostname / VM Name)
#
# Produces a CSV with:
#   DatacenterName  - the DCC (datacenter cluster) name
#   HostName        - the physical host name
#   VmName          - the virtual machine name
#   DC_Host_Key     - "DatacenterName|HostName"  -> join key for your DC/Hostname Power BI query
#   Host_VM_Key     - "HostName|VmName"          -> join key to match 1-Snow-All-Computers
#
# Authentication:
#   OAuth2 client_credentials (Bearer token), matching the other Snow Atlas scripts.
#   Token is refreshed proactively (5 min before expiry) and reactively (on 401).
#
# Prerequisites:
#   Application Registration in Snow Atlas with permissions:
#     sam.dcc.r       - read datacenters/clusters
#     sam.computer.r  - read computers/VMs
#
# Usage:
#   .\Get-SnowBridgeTable.ps1
#   You will be prompted for Region, Client ID, and Client Secret.
#   Or hard-code them in the CONFIG section below.
#==============================================================================

#==============================================================================
# CONFIG - fill in or leave blank to be prompted at runtime
#==============================================================================
$Region       = "australiasoutheast"    # e.g. "au1", "eu1", "us1"
$ClientId     = "b066c338-79ff-4cc3-2a87-08dd91a4d6a6"    # From Snow Atlas > Settings > Application Registrations
$ClientSecret = "REDACTED"    # From Snow Atlas > Settings > Application Registrations

$OutFile      = ".\Snow_Bridge_Table_$(Get-Date -Format 'yyyyMMdd_HHmmss').csv"
$PageSize     = 100   # Items per page (100 is typically the maximum)
$TimeoutSec   = 120   # Per-request timeout in seconds
$MaxRetries   = 3     # Retry attempts for transient failures

# How many minutes before token expiry to proactively refresh
$TokenRefreshBufferMinutes = 5

#==============================================================================
# DIAGNOSTICS MODE
# On first run, set $true to inspect raw VM field names from your instance.
# Once confirmed, set $false and update the FIELD MAPPING section below.
#==============================================================================
$DiagnosticsMode = $true

#==============================================================================
# FIELD MAPPING - update after running diagnostics
# These defaults match the most common Snow Atlas field names.
# Common alternatives: vmName, computerName, name, virtualMachineName
#==============================================================================
$VmEndpointSuffix = "/vms"        # Appended to /api/sam/estate/v1/dcc/{id}
$FieldHostName    = "hostName"    # Field name for the host/physical server name
$FieldVmName      = "name"        # Field name for the virtual machine name

#==============================================================================
# PROMPT if not configured above
#==============================================================================
if (-not $Region) {
    $Region = Read-Host "Enter your Snow Atlas region (e.g. au1, eu1, us1)"
}
if (-not $ClientId) {
    $ClientId = Read-Host "Enter your Client ID"
}
if (-not $ClientSecret) {
    $SecureSecret = Read-Host "Enter your Client Secret" -AsSecureString
    $ClientSecret = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
                        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureSecret))
}

$BaseUrl  = "https://$Region.snowsoftware.io"
$TokenUrl = "$BaseUrl/idp/api/connect/token"

#==============================================================================
# TOKEN MANAGEMENT
#==============================================================================
$script:Token          = $null
$script:TokenExpiresAt = [datetime]::MinValue

function Get-SnowToken {
    Write-Host "Authenticating with Snow Atlas..." -ForegroundColor Cyan
    try {
        $Body = @{
            grant_type    = "client_credentials"
            client_id     = $ClientId
            client_secret = $ClientSecret
        }
        $Response = Invoke-RestMethod -Uri $TokenUrl -Method POST -Body $Body `
                        -ContentType "application/x-www-form-urlencoded" `
                        -TimeoutSec 30 -ErrorAction Stop

        $script:Token          = $Response.access_token
        $script:TokenExpiresAt = (Get-Date).AddSeconds($Response.expires_in)
        Write-Host "  Token acquired. Expires at $($script:TokenExpiresAt.ToString('HH:mm:ss'))." -ForegroundColor Green
    } catch {
        Write-Error "Authentication failed: $_"
        exit 1
    }
}

function Invoke-EnsureValidToken {
    $MinutesRemaining = ($script:TokenExpiresAt - (Get-Date)).TotalMinutes
    if ($MinutesRemaining -le $TokenRefreshBufferMinutes) {
        Write-Host "  Token expiring in $([math]::Round($MinutesRemaining,1)) min — refreshing..." -ForegroundColor Yellow
        Get-SnowToken
    }
}

function Get-AuthHeaders {
    Invoke-EnsureValidToken
    return @{
        "Authorization" = "Bearer $script:Token"
        "Content-Type"  = "application/json"
        "Accept"        = "application/json"
    }
}

#==============================================================================
# API CALL WRAPPER - retry with backoff, reactive 401 token refresh
#==============================================================================
function Invoke-SnowApi {
    param(
        [string]$Uri,
        [string]$Label = "request"
    )

    $Attempt = 0
    while ($Attempt -lt $MaxRetries) {
        $Attempt++
        $Headers = Get-AuthHeaders
        try {
            return Invoke-RestMethod -Uri $Uri -Method GET -Headers $Headers `
                       -TimeoutSec $TimeoutSec -ErrorAction Stop
        } catch {
            $ErrMsg = "$_"

            # Reactive token refresh on 401
            if ($ErrMsg -match '401' -or $ErrMsg -match 'token is invalid or expired') {
                Write-Warning "  $Label — 401 received, refreshing token and retrying..."
                Get-SnowToken
                if ($Attempt -lt $MaxRetries) { continue }
            }

            if ($Attempt -lt $MaxRetries) {
                $Wait = $Attempt * 10
                Write-Warning "  $Label — attempt $Attempt failed: $_. Retrying in ${Wait}s..."
                Start-Sleep -Seconds $Wait
            } else {
                Write-Warning "  $Label — all $MaxRetries attempts failed. Skipping. Error: $_"
                return $null
            }
        }
    }
}

#==============================================================================
# PAGER - fetches all pages from a paginated Snow Atlas endpoint
#==============================================================================
function Get-AllPages {
    param(
        [string]$EndpointPath,
        [string]$Label
    )

    $AllItems   = [System.Collections.Generic.List[object]]::new()
    $PageNum    = 1
    $TotalPages = 1

    do {
        $Uri      = "$BaseUrl$EndpointPath`?page_number=$PageNum&page_size=$PageSize"
        $Response = Invoke-SnowApi -Uri $Uri -Label "$Label (page $PageNum)"

        if ($null -eq $Response) { break }

        if ($Response.items -and $Response.items.Count -gt 0) {
            foreach ($Item in $Response.items) { $AllItems.Add($Item) }
        }

        if ($Response.pagination.total_pages) {
            $TotalPages = $Response.pagination.total_pages
        }

        if ($PageNum -eq 1 -and $Response.pagination.total_items) {
            Write-Host "    $Label — $($Response.pagination.total_items) total items, $TotalPages pages" -ForegroundColor Gray
        }

        $PageNum++

    } while ($PageNum -le $TotalPages)

    return $AllItems
}

#==============================================================================
# INITIAL AUTH
#==============================================================================
Get-SnowToken

#==============================================================================
# DIAGNOSTICS MODE - inspect raw VM field names before committing
#==============================================================================
if ($DiagnosticsMode) {
    Write-Host ""
    Write-Host "====== DIAGNOSTICS MODE ======" -ForegroundColor Magenta
    Write-Host "Fetching first datacenter to discover VM endpoint and field names..." -ForegroundColor Magenta
    Write-Host ""

    $FirstDccResponse = Invoke-SnowApi -Uri "$BaseUrl/api/sam/estate/v1/dcc?page_number=1&page_size=1" -Label "DCC list"

    if ($null -eq $FirstDccResponse -or $FirstDccResponse.items.Count -eq 0) {
        Write-Error "No datacenters returned. Verify your region, Client ID, Client Secret, and sam.dcc.r permission."
        exit 1
    }

    $SampleDcc = $FirstDccResponse.items[0]
    Write-Host "  First datacenter: '$($SampleDcc.name)'" -ForegroundColor Cyan
    Write-Host "  DCC id:           $($SampleDcc.id)" -ForegroundColor Cyan
    Write-Host ""

    # Try common VM sub-endpoint variants
    $Candidates = @("/vms", "/virtualmachines", "/computers")
    $FoundEndpoint = $null

    foreach ($Suffix in $Candidates) {
        $TestUri = "$BaseUrl/api/sam/estate/v1/dcc/$($SampleDcc.id)$Suffix`?page_number=1&page_size=3"
        Write-Host "  Testing: /api/sam/estate/v1/dcc/{id}$Suffix" -ForegroundColor Gray
        try {
            $TestResp = Invoke-RestMethod -Uri $TestUri -Method GET -Headers (Get-AuthHeaders) `
                            -TimeoutSec 30 -ErrorAction Stop
            if ($null -ne $TestResp.items) {
                Write-Host "  ✓ Valid endpoint: /api/sam/estate/v1/dcc/{id}$Suffix" -ForegroundColor Green
                $FoundEndpoint = $Suffix
                Write-Host ""

                if ($TestResp.items.Count -gt 0) {
                    Write-Host "  Sample VM record — all field names and values:" -ForegroundColor Yellow
                    Write-Host "  -----------------------------------------------" -ForegroundColor Yellow
                    $TestResp.items[0].PSObject.Properties | ForEach-Object {
                        Write-Host ("  {0,-40} = {1}" -f $_.Name, $_.Value) -ForegroundColor DarkYellow
                    }
                } else {
                    Write-Host "  (No VMs in this datacenter — endpoint is valid but empty)" -ForegroundColor Yellow
                    Write-Host "  Try pointing diagnostics at a datacenter you know has VMs." -ForegroundColor Yellow
                }
                break
            }
        } catch {
            $Code = $_.Exception.Response.StatusCode.value__
            Write-Host "  ✗ HTTP $Code" -ForegroundColor DarkGray
        }
    }

    Write-Host ""
    if ($FoundEndpoint) {
        Write-Host "====== ACTION REQUIRED ======" -ForegroundColor Yellow
        Write-Host "  1. Review the field names printed above." -ForegroundColor Yellow
        Write-Host "  2. Update the FIELD MAPPING section in this script:" -ForegroundColor Yellow
        Write-Host "       `$VmEndpointSuffix = `"$FoundEndpoint`"" -ForegroundColor Cyan
        Write-Host "       `$FieldHostName    = `"<field with the host/physical server name>`"" -ForegroundColor Cyan
        Write-Host "       `$FieldVmName      = `"<field with the VM name>`"" -ForegroundColor Cyan
        Write-Host "  3. Set `$DiagnosticsMode = `$false" -ForegroundColor Yellow
        Write-Host "  4. Re-run the script." -ForegroundColor Yellow
    } else {
        Write-Host "  Could not find a valid VM sub-endpoint." -ForegroundColor Red
        Write-Host "  Check Snow Atlas API docs for your version, or contact Flexera support." -ForegroundColor Red
    }
    Write-Host "====== END DIAGNOSTICS ======" -ForegroundColor Magenta
    exit 0
}

#==============================================================================
# MAIN RUN - fetch all datacenters, then all VMs per datacenter
#==============================================================================
Write-Host ""
Write-Host "Fetching all datacenters..." -ForegroundColor Cyan
$AllDatacenters = Get-AllPages -EndpointPath "/api/sam/estate/v1/dcc" -Label "Datacenters"
Write-Host "  $($AllDatacenters.Count) datacenters found." -ForegroundColor Green
Write-Host ""

$BridgeRows   = [System.Collections.Generic.List[object]]::new()
$DcCount      = 0
$SkippedCount = 0

foreach ($Dc in $AllDatacenters) {
    $DcCount++
    $DcName       = $Dc.name
    $DcId         = $Dc.id
    $EndpointPath = "/api/sam/estate/v1/dcc/$DcId$VmEndpointSuffix"

    Write-Host "[$DcCount/$($AllDatacenters.Count)] $DcName" -ForegroundColor Cyan

    $Vms = Get-AllPages -EndpointPath $EndpointPath -Label "VMs"

    if ($Vms.Count -eq 0) {
        Write-Host "    (no VMs)" -ForegroundColor DarkGray
        continue
    }

    foreach ($Vm in $Vms) {
        $HostName = $Vm.$FieldHostName
        $VmName   = $Vm.$FieldVmName

        if ([string]::IsNullOrWhiteSpace($HostName) -or [string]::IsNullOrWhiteSpace($VmName)) {
            $SkippedCount++
            continue
        }

        $BridgeRows.Add([PSCustomObject]@{
            DatacenterName = $DcName
            HostName       = $HostName
            VmName         = $VmName
            DC_Host_Key    = "$DcName|$HostName"    # Join to your DC/Hostname Power BI query
            Host_VM_Key    = "$HostName|$VmName"    # Join to 1-Snow-All-Computers
        })
    }

    Write-Host "    $($Vms.Count) VMs processed. Running total: $($BridgeRows.Count) rows." -ForegroundColor Gray
}

#==============================================================================
# EXPORT
#==============================================================================
Write-Host ""
Write-Host "------------------------------------------------------------" -ForegroundColor DarkGray
Write-Host "Total bridge rows : $($BridgeRows.Count)" -ForegroundColor Green
Write-Host "Skipped (null key): $SkippedCount" -ForegroundColor $(if ($SkippedCount -gt 0) { "Yellow" } else { "Green" })

if ($BridgeRows.Count -gt 0) {
    $BridgeRows | Export-Csv -Path $OutFile -NoTypeInformation -Encoding UTF8
    Write-Host "Exported to       : $OutFile" -ForegroundColor Green
} else {
    Write-Warning "No rows to export. Check field mapping or API permissions."
}

Write-Host "Done." -ForegroundColor Green
