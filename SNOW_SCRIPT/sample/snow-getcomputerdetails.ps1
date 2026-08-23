#==============================================================================
# Snow Atlas API - Export All Computer Fields
# 
# Designed to run unattended via Windows Task Scheduler.
#
# Task Scheduler setup:
#   Program:   powershell.exe
#   Arguments: -NoProfile -ExecutionPolicy Bypass -File "E:\Scripts\Atlas\SnowAtlas_Computers.ps1"
#   Start in:  E:\Scripts\Atlas
#
# Prerequisites:
#   1. Application Registration with sam.computer.r permission
#   2. Client ID, Client Secret, and Data Region
#
# Related CSVs (join in Power BI):
#   - Organizations: join on organizationId
#   - Custom Fields: join on id = assetId
#   - Software Installs: join on id = computerId
#
# Data Regions: westeurope, australiasoutheast, eastus2, uksouth
#==============================================================================

#--- Configuration (UPDATE THESE VALUES) ---
$ClientId     = 'b066c338-79ff-4cc3-2a87-08dd91a4d6a6'
$ClientSecret = 'REDACTED'
$Region       = 'australiasoutheast'
$FetchDetails = $true
$PageSize     = 100
$TimeoutSec   = 300
$MaxRetries   = 3
$TokenRefreshBufferMinutes = 5

# Output paths — use $PSScriptRoot so paths resolve correctly in Task Scheduler
$OutputDir = 'E:\Reports\API'
if (-not (Test-Path $OutputDir)) { New-Item -Path $OutputDir -ItemType Directory -Force | Out-Null }

$CSVPath = Join-Path $OutputDir 'SnowAtlas_AllComputers.csv'
$LogPath = Join-Path $OutputDir "SnowAtlas_Computers_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"

#--- Force TLS 1.2 (required by Snow Atlas, not always default in older PS) ---
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

#==============================================================================
# LOGGING — writes to both console and log file
#==============================================================================
function Write-Log {
    param(
        [string]$Message,
        [ValidateSet('INFO','WARN','ERROR')]
        [string]$Level = 'INFO'
    )
    $Timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $Entry = "[$Timestamp] [$Level] $Message"
    Add-Content -Path $LogPath -Value $Entry -ErrorAction SilentlyContinue

    switch ($Level) {
        'WARN'  { Write-Warning $Message }
        'ERROR' { Write-Error $Message }
        default { Write-Output $Message }
    }
}

#==============================================================================
# TOKEN MANAGEMENT
#==============================================================================
$script:Token          = $null
$script:TokenExpiresAt = [datetime]::MinValue

function Get-SnowToken {
    Write-Log "Requesting access token..."
    $TokenUri = "https://$Region.snowsoftware.io/idp/api/connect/token"
    $TokenBody = @{
        grant_type    = 'client_credentials'
        client_id     = $ClientId
        client_secret = $ClientSecret
    }
    try {
        $TokenResponse = Invoke-WebRequest -Uri $TokenUri -ContentType 'application/x-www-form-urlencoded' -Method Post -Body $TokenBody -TimeoutSec 60 -UseBasicParsing -ErrorAction Stop
        if ($TokenResponse.StatusCode -eq 200) {
            $TokenData = $TokenResponse.Content | ConvertFrom-Json
            $script:Token = $TokenData.access_token
            $ExpiresInSeconds = if ($TokenData.expires_in) { $TokenData.expires_in } else { 3300 }
            $script:TokenExpiresAt = (Get-Date).AddSeconds($ExpiresInSeconds)
            Write-Log "Token acquired (expires in $([math]::Round($ExpiresInSeconds / 60, 1)) min)."
        } else {
            Write-Log "Unexpected status code: $($TokenResponse.StatusCode)" -Level ERROR
            exit 1
        }
    } catch {
        Write-Log "Authentication failed: $_" -Level ERROR
        exit 1
    }
}

function Ensure-ValidToken {
    $MinutesRemaining = ($script:TokenExpiresAt - (Get-Date)).TotalMinutes
    if ($MinutesRemaining -le $TokenRefreshBufferMinutes) {
        Write-Log "Token expiring soon ($([math]::Round($MinutesRemaining, 1)) min left). Refreshing..." -Level WARN
        Get-SnowToken
    }
}

function Get-AuthHeaders {
    Ensure-ValidToken
    return @{ Authorization = "Bearer $script:Token"; 'Content-Type' = 'application/json' }
}

#==============================================================================
# API CALL WITH RETRY + TOKEN REFRESH
#==============================================================================
function Invoke-SnowApi {
    param([string]$Uri, [string]$Label = "request")
    $attempt = 0
    while ($attempt -lt $MaxRetries) {
        $attempt++
        $hdrs = Get-AuthHeaders
        try {
            return (Invoke-RestMethod -Uri $Uri -Method GET -Headers $hdrs -TimeoutSec $TimeoutSec -ErrorAction Stop)
        } catch {
            $err = $_; $errMsg = "$err"
            if ($errMsg -match 'token is invalid or expired' -or $errMsg -match '401') {
                Write-Log "$Label - token expired. Refreshing..." -Level WARN
                Get-SnowToken
                if ($attempt -lt $MaxRetries) { continue }
            }
            if ($attempt -lt $MaxRetries) {
                $wait = $attempt * 10
                Write-Log "$Label - attempt $attempt failed: $err. Retrying in ${wait}s..." -Level WARN
                Start-Sleep -Seconds $wait
            } else { throw $err }
        }
    }
}

#==============================================================================
# MAIN
#==============================================================================
Write-Log "=== Snow Atlas Computers Export Started ==="
Write-Log "Output CSV: $CSVPath"
Write-Log "Log file:   $LogPath"

Get-SnowToken

#--- Get all computers (paginated) ---
$Page = 1
$Computers = [System.Collections.Generic.List[object]]::new()
Write-Log "Fetching computers (page_size=$PageSize)..."

do {
    $Uri = "https://$Region.snowsoftware.io/api/sam/estate/v1/computers?page_size=$PageSize&page_number=$Page"
    try {
        $Response = Invoke-SnowApi -Uri $Uri -Label "computers p$Page"
    } catch {
        Write-Log "Failed to fetch page $Page : $_" -Level ERROR; break
    }

    $Items = $Response.items
    $Count = if ($Items) { $Items.Count } else { 0 }
    foreach ($c in $Items) { $Computers.Add($c) }

    $TotalPages = $Response.pagination.total_pages
    $TotalItems = $Response.pagination.total_items
    Write-Log "  Page $Page/$TotalPages ($($Computers.Count)/$TotalItems computers)"
    $Page++
} while ($Count -ge $PageSize)

Write-Log "Retrieved $($Computers.Count) computers."

if ($Computers.Count -eq 0) {
    Write-Log "No computers found." -Level WARN; exit 0
}

#--- Build results ---
$Results = [System.Collections.Generic.List[PSCustomObject]]::new()

if ($FetchDetails) {
    Write-Log "Fetching detailed records for each computer..."
    $i = 0

    foreach ($comp in $Computers) {
        $i++
        if ($i % 100 -eq 0) { Write-Log "  Progress: $i / $($Computers.Count)" }

        $Detail = $null
        $DetailUri = "https://$Region.snowsoftware.io/api/sam/estate/v1/computers/$($comp.id)"
        try {
            $Detail = Invoke-SnowApi -Uri $DetailUri -Label "detail $($comp.id)"
        } catch {
            Write-Log "Could not fetch detail for $($comp.id): $_" -Level WARN
        }

        $src = if ($null -ne $Detail) { $Detail } else { $comp }

        $obj = [PSCustomObject]@{
            id                              = $src.id
            hostName                        = $src.hostName
            domain                          = $src.domain
            status                          = $src.status
            organizationId                  = $src.organizationId
            manufacturer                    = $src.manufacturer
            manufacturerWebsite             = $src.manufacturerWebsite
            model                           = $src.model
            isPortable                      = $src.isPortable
            is64bit                         = $src.is64bit
            isServer                        = $src.isServer
            isVDI                           = $src.isVDI
            isVirtual                       = $src.isVirtual
            processorCount                  = $src.processorCount
            coreCount                       = $src.coreCount
            vendor                          = $src.vendor
            biosSerialNumber                = $src.biosSerialNumber
            biosVersion                     = $src.biosVersion
            biosDate                        = $src.biosDate
            operatingSystem                 = $src.operatingSystem
            operatingSystemId               = $src.operatingSystemId
            operatingSystemServicePack      = $src.operatingSystemServicePack
            operatingSystemSerialNumber     = $src.operatingSystemSerialNumber
            ipAddress                       = $src.ipAddress
            lastScanDate                    = $src.lastScanDate
            infoTransferDate                = $src.infoTransferDate
            clientInstallDate               = $src.clientInstallDate
            clientVersion                   = $src.clientVersion
            clientSiteName                  = $src.clientSiteName
            clientConfigurationName         = $src.clientConfigurationName
            scannerVersion                  = $src.scannerVersion
            quarantineDate                  = $src.quarantineDate
            isQuarantineManagementDisabled  = $src.isQuarantineManagementDisabled
            hostComputerId                  = $src.hostComputerId
            siblingComputerId               = $src.siblingComputerId
            mostFrequentUser                = $src.mostFrequentUser
            mostRecentUser                  = $src.mostRecentUser
            isUpdated                       = $src.isUpdated
            notes                           = $src.notes
            purchaseDate                    = $src.purchaseDate
            purchasePrice                   = $src.purchasePrice
            purchaseCurrency                = $src.purchaseCurrency
            warrantyDate                    = $src.warrantyDate
            leaseEndDate                    = $src.leaseEndDate
        }
        $Results.Add($obj)
    }
} else {
    Write-Log "Using list-level fields only."

    foreach ($comp in $Computers) {
        $obj = [PSCustomObject]@{
            id               = $comp.id
            hostName         = $comp.hostName
            domain           = $comp.domain
            status           = $comp.status
            organizationId   = $comp.organizationId
            manufacturer     = $comp.manufacturer
            model            = $comp.model
            isPortable       = $comp.isPortable
            isServer         = $comp.isServer
            isVDI            = $comp.isVDI
            isVirtual        = $comp.isVirtual
            ipAddress        = $comp.ipAddress
            lastScanDate     = $comp.lastScanDate
            operatingSystem  = $comp.operatingSystem
            hostComputerId   = $comp.hostComputerId
            mostFrequentUser = $comp.mostFrequentUser
            mostRecentUser   = $comp.mostRecentUser
            vendor           = $comp.vendor
            processorCount   = $comp.processorCount
            coreCount        = $comp.coreCount
        }
        $Results.Add($obj)
    }
}

#--- Export ---
$Results | Export-Csv -Path $CSVPath -NoTypeInformation -Force
Write-Log "Exported $($Results.Count) computers to: $CSVPath"
Write-Log "=== Snow Atlas Computers Export Completed ==="
exit 0