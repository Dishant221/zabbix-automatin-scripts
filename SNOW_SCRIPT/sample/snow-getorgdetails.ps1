#==============================================================================
# Snow Atlas API - Export Organizations to CSV
#
# Task Scheduler setup:
#   Program:   powershell.exe
#   Arguments: -NoProfile -ExecutionPolicy Bypass -File "E:\Scripts\Atlas\SnowAtlas_Organizations.ps1"
#   Start in:  E:\Scripts\Atlas
#==============================================================================

#--- Configuration (UPDATE THESE VALUES) ---
$ClientId     = 'b066c338-79ff-4cc3-2a87-08dd91a4d6a6'
$ClientSecret = 'REDACTED'
$Region       = 'australiasoutheast'
$TimeoutSec   = 300
$MaxRetries   = 3
$TokenRefreshBufferMinutes = 5

$OutputDir = 'E:\Reports\API'
if (-not (Test-Path $OutputDir)) { New-Item -Path $OutputDir -ItemType Directory -Force | Out-Null }

$CSVPath = Join-Path $OutputDir 'SnowAtlas_Organizations.csv'
$LogPath = Join-Path $OutputDir "SnowAtlas_Organizations_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"

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
    param([string]$Uri, [string]$Label = "request")
    $attempt = 0
    while ($attempt -lt $MaxRetries) {
        $attempt++; $hdrs = Get-AuthHeaders
        try { return (Invoke-RestMethod -Uri $Uri -Method GET -Headers $hdrs -TimeoutSec $TimeoutSec -ErrorAction Stop) }
        catch {
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
Write-Log "=== Snow Atlas Organizations Export Started ==="
Write-Log "Output CSV: $CSVPath"
Get-SnowToken

Write-Log "Fetching organization tree..."
try {
    $Response = Invoke-SnowApi -Uri "https://$Region.snowsoftware.io/api/organizations/v1/tree" -Label "org tree"
} catch { Write-Log "Failed to fetch organizations: $_" -Level ERROR; exit 1 }

$Nodes = $Response.nodes
if ($null -eq $Nodes -or $Nodes.Count -eq 0) { Write-Log "No organizations returned." -Level WARN; exit 0 }

$NodeLookup = @{}
foreach ($n in $Nodes) { if ($n.id) { $NodeLookup[$n.id] = $n.name } }

$Results = foreach ($n in $Nodes) {
    $ParentName = if ($n.parentId -and $NodeLookup.ContainsKey($n.parentId)) { $NodeLookup[$n.parentId] } else { $null }
    [PSCustomObject]@{
        organizationId   = $n.id
        organizationName = $n.name
        parentId         = $n.parentId
        parentName       = $ParentName
        isLegal          = $n.isLegal
        externalId       = $n.externalId
    }
}

$Results | Export-Csv -Path $CSVPath -NoTypeInformation -Force
Write-Log "Exported $($Results.Count) organizations to: $CSVPath"
Write-Log "=== Snow Atlas Organizations Export Completed ==="
exit 0