#==============================================================================
# Snow Atlas API - Export Computer Software Installs/Usage to CSV
#
# Task Scheduler setup:
#   Program:   powershell.exe
#   Arguments: -NoProfile -ExecutionPolicy Bypass -File "E:\Scripts\Atlas\SnowAtlas_Installs.ps1"
#   Start in:  E:\Scripts\Atlas
#
# Tries bulk endpoint first, falls back to per-computer if empty.
# Includes diagnostics, token refresh, retry logic, and logging.
#==============================================================================

#--- Configuration (UPDATE THESE VALUES) ---
$ClientId     = 'b066c338-79ff-4cc3-2a87-08dd91a4d6a6'
$ClientSecret = 'REDACTED'
$Region       = 'australiasoutheast'
$PageSize     = 100
$TimeoutSec   = 300
$MaxRetries   = 3
$TokenRefreshBufferMinutes = 5

$OutputDir = 'E:\Reports\API'
if (-not (Test-Path $OutputDir)) { New-Item -Path $OutputDir -ItemType Directory -Force | Out-Null }

$CSVPath = Join-Path $OutputDir 'SnowAtlas_ComputerSoftwareInstalls.csv'
$LogPath = Join-Path $OutputDir "SnowAtlas_Installs_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

#==============================================================================
# LOGGING
#==============================================================================
function Write-Log {
    param([string]$Message, [ValidateSet('INFO','WARN','ERROR')][string]$Level = 'INFO')
    $Entry = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] [$Level] $Message"
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
$script:Token = $null; $script:TokenExpiresAt = [datetime]::MinValue

function Get-SnowToken {
    Write-Log "Requesting access token..."
    $TokenUri = "https://$Region.snowsoftware.io/idp/api/connect/token"
    $TokenBody = @{ grant_type = 'client_credentials'; client_id = $ClientId; client_secret = $ClientSecret }
    try {
        $resp = Invoke-WebRequest -Uri $TokenUri -ContentType 'application/x-www-form-urlencoded' -Method Post -Body $TokenBody -TimeoutSec 60 -UseBasicParsing -ErrorAction Stop
        if ($resp.StatusCode -eq 200) {
            $data = $resp.Content | ConvertFrom-Json
            $script:Token = $data.access_token
            $exp = if ($data.expires_in) { $data.expires_in } else { 3300 }
            $script:TokenExpiresAt = (Get-Date).AddSeconds($exp)
            Write-Log "Token acquired (expires in $([math]::Round($exp / 60, 1)) min)."
        } else { Write-Log "Unexpected status: $($resp.StatusCode)" -Level ERROR; exit 1 }
    } catch { Write-Log "Authentication failed: $_" -Level ERROR; exit 1 }
}

function Ensure-ValidToken {
    if (($script:TokenExpiresAt - (Get-Date)).TotalMinutes -le $TokenRefreshBufferMinutes) {
        Write-Log "Token expiring soon. Refreshing..." -Level WARN; Get-SnowToken
    }
}

function Get-AuthHeaders {
    Ensure-ValidToken
    return @{ Authorization = "Bearer $script:Token"; 'Content-Type' = 'application/json' }
}

function Invoke-SnowApi {
    param([string]$Uri, [string]$Label = "request", [switch]$Raw)
    $attempt = 0
    while ($attempt -lt $MaxRetries) {
        $attempt++; $hdrs = Get-AuthHeaders
        try {
            if ($Raw) {
                $r = Invoke-WebRequest -Uri $Uri -Method GET -Headers $hdrs -TimeoutSec $TimeoutSec -UseBasicParsing -ErrorAction Stop
                return $r.Content
            } else {
                return (Invoke-RestMethod -Uri $Uri -Method GET -Headers $hdrs -TimeoutSec $TimeoutSec -ErrorAction Stop)
            }
        } catch {
            $err = $_; $errMsg = "$err"
            if ($errMsg -match 'token is invalid or expired' -or $errMsg -match '401') {
                Write-Log "$Label - token expired. Refreshing..." -Level WARN; Get-SnowToken
                if ($attempt -lt $MaxRetries) { continue }
            }
            if ($attempt -lt $MaxRetries) {
                $wait = $attempt * 10; Write-Log "$Label - attempt $attempt failed. Retrying in ${wait}s..." -Level WARN; Start-Sleep -Seconds $wait
            } else { throw $err }
        }
    }
}

#==============================================================================
# MAIN
#==============================================================================
Write-Log "=== Snow Atlas Software Installs Export Started ==="
Write-Log "Output CSV: $CSVPath"
Get-SnowToken

#--- Diagnostics ---
Write-Log "--- DIAGNOSTICS ---"
Write-Log "Testing bulk endpoint (page_size=5)..."

$DiagUri = "https://$Region.snowsoftware.io/api/sam/estate/v1/computers-applications?page_size=5&page_number=1"
try {
    $DiagRaw = Invoke-SnowApi -Uri $DiagUri -Label "diag bulk" -Raw
    $DiagParsed = $DiagRaw | ConvertFrom-Json
    Write-Log "  Top-level properties: $($DiagParsed.PSObject.Properties.Name -join ', ')"
    $DiagItems = if ($DiagParsed.items) { $DiagParsed.items } elseif ($DiagParsed.content) { $DiagParsed.content } else { $null }
    $DiagCount = if ($DiagItems) { $DiagItems.Count } else { 0 }
    Write-Log "  Items returned: $DiagCount"
    if ($DiagCount -gt 0) { Write-Log "  First item properties: $($DiagItems[0].PSObject.Properties.Name -join ', ')" }
    if ($DiagParsed.pagination) { Write-Log "  Pagination: total_items=$($DiagParsed.pagination.total_items), total_pages=$($DiagParsed.pagination.total_pages)" }
} catch { Write-Log "  Bulk diagnostic failed: $_" -Level WARN }

Write-Log "Testing per-computer endpoint on first computer..."
try {
    $TestComp = Invoke-SnowApi -Uri "https://$Region.snowsoftware.io/api/sam/estate/v1/computers?page_size=1&page_number=1" -Label "diag comp"
    $TestId = $TestComp.items[0].id; $TestName = $TestComp.items[0].hostName
    Write-Log "  Test computer: $TestName ($TestId)"
    $DiagPerRaw = Invoke-SnowApi -Uri "https://$Region.snowsoftware.io/api/sam/estate/v1/computers/$TestId/applications?page_size=5&page_number=1" -Label "diag per-comp" -Raw
    $DiagPerParsed = $DiagPerRaw | ConvertFrom-Json
    Write-Log "  Top-level properties: $($DiagPerParsed.PSObject.Properties.Name -join ', ')"
    $DiagPerItems = if ($DiagPerParsed.items) { $DiagPerParsed.items } elseif ($DiagPerParsed.content) { $DiagPerParsed.content } else { $null }
    $DiagPerCount = if ($DiagPerItems) { $DiagPerItems.Count } else { 0 }
    Write-Log "  Items returned: $DiagPerCount"
    if ($DiagPerCount -gt 0) { Write-Log "  First item properties: $($DiagPerItems[0].PSObject.Properties.Name -join ', ')" }
    if ($DiagPerParsed.pagination) { Write-Log "  Pagination: total_items=$($DiagPerParsed.pagination.total_items)" }
} catch { Write-Log "  Per-computer diagnostic failed: $_" -Level WARN }

Write-Log "--- END DIAGNOSTICS ---"

#--- Paginated pull helper ---
function Get-SnowPaginated {
    param([string]$BaseUri, [string]$Label)
    $Pg = 1; $All = [System.Collections.Generic.List[object]]::new()
    do {
        $Sep = if ($BaseUri -match '\?') { '&' } else { '?' }
        $Uri = "${BaseUri}${Sep}page_size=$PageSize&page_number=$Pg"
        try { $Resp = Invoke-SnowApi -Uri $Uri -Label "$Label p$Pg" }
        catch { Write-Log "Failed $Label page $Pg : $_" -Level WARN; break }

        $Itms = if ($Resp.items) { $Resp.items } elseif ($Resp.content) { $Resp.content } else { $null }
        $Cnt = if ($Itms) { $Itms.Count } else { 0 }
        foreach ($it in $Itms) { $All.Add($it) }

        $TP = $Resp.pagination.total_pages; $TI = $Resp.pagination.total_items
        if ($Pg -eq 1) { Write-Log "  Total $Label : $TI ($TP pages)" }
        if ($Pg % 25 -eq 0 -or $Pg -eq $TP) { Write-Log "  Page $Pg/$TP ($($All.Count) items)..." }
        $Pg++
    } while ($Cnt -ge $PageSize)
    return $All
}

#--- Step 1: Bulk endpoint ---
Write-Log "Attempting bulk computer-applications endpoint..."
$CompApps = Get-SnowPaginated -BaseUri "https://$Region.snowsoftware.io/api/sam/estate/v1/computers-applications" -Label "comp-app records"
Write-Log "Bulk returned: $($CompApps.Count) records"

#--- Step 2: Fallback to per-computer ---
if ($CompApps.Count -eq 0) {
    Write-Log "Bulk empty. Falling back to per-computer queries..." -Level WARN
    Write-Log "Tip: ensure app registration has sam.computer.r AND sam.application.r"

    $Computers = Get-SnowPaginated -BaseUri "https://$Region.snowsoftware.io/api/sam/estate/v1/computers" -Label "computers"
    if ($Computers.Count -eq 0) { Write-Log "No computers found." -Level WARN; exit 0 }

    $CompApps = [System.Collections.Generic.List[object]]::new()
    $i = 0; $EmptyCount = 0

    foreach ($comp in $Computers) {
        $i++; $CId = $comp.id
        $PerUri = "https://$Region.snowsoftware.io/api/sam/estate/v1/computers/$CId/applications"
        $Pg = 1
        do {
            $Uri = "${PerUri}?page_size=$PageSize&page_number=$Pg"
            try { $Resp = Invoke-SnowApi -Uri $Uri -Label "comp $CId p$Pg" }
            catch { Write-Log "Failed comp $CId p$Pg : $_" -Level WARN; break }

            $Itms = if ($Resp.items) { $Resp.items } elseif ($Resp.content) { $Resp.content } else { $null }
            $Cnt = if ($Itms) { $Itms.Count } else { 0 }
            if ($Cnt -eq 0 -and $Pg -eq 1) { $EmptyCount++ }

            foreach ($it in $Itms) {
                if (-not $it.computerId) { $it | Add-Member -NotePropertyName 'computerId' -NotePropertyValue $CId -Force }
                $CompApps.Add($it)
            }
            $Pg++
        } while ($Cnt -ge $PageSize)

        if ($i % 50 -eq 0) { Write-Log "  Processed $i/$($Computers.Count), $($CompApps.Count) apps found ($EmptyCount empty)..." }
    }
    Write-Log "Per-computer fallback: $($CompApps.Count) records ($EmptyCount computers with no apps)."
}

#--- Step 3: Export ---
if ($CompApps.Count -eq 0) {
    Write-Log "No computer-application records found." -Level WARN
    Write-Log "Check: 1) sam.computer.r + sam.application.r permissions 2) Scanned apps exist 3) Region=$Region is correct" -Level WARN
    exit 0
}

$SampleProps = $CompApps[0].PSObject.Properties.Name
Write-Log "Available fields: $($SampleProps -join ', ')"

$Results = [System.Collections.Generic.List[PSCustomObject]]::new()
foreach ($ca in $CompApps) {
    $Results.Add([PSCustomObject]@{
        computerId            = $ca.computerId
        applicationId         = $ca.applicationId
        bundleApplicationId   = $ca.bundleApplicationId
        isInstalled           = $ca.isInstalled
        isVirtual             = $ca.isVirtual
        firstDiscovered       = $ca.firstDiscovered
        lastUsed              = $ca.lastUsed
        usedCount             = $ca.usedCount
        averageUsedTime       = $ca.averageUsedTime
        bundleUsagePercentage = $ca.bundleUsagePercentage
        unbundled             = $ca.unbundled
    })
}

$Results | Export-Csv -Path $CSVPath -NoTypeInformation -Force
Write-Log "Exported $($Results.Count) install records to: $CSVPath"
Write-Log "=== Snow Atlas Software Installs Export Completed ==="
exit 0