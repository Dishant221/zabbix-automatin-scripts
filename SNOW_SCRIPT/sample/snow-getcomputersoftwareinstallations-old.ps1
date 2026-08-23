#==============================================================================
# Snow Atlas API - Export Computer Software Installs/Usage to CSV
#
# Tries the bulk endpoint first (fast):
#   GET /api/sam/estate/v1/computers-applications
#
# If that returns empty, falls back to per-computer calls (slower but reliable):
#   GET /api/sam/estate/v1/computers/{id}/applications
#
# Includes automatic token refresh, retry logic, and configurable timeout.
#
# Output: One row per computer-application combination (fact table).
# In Power BI, join:
#   - computerId    → Computers.id
#   - applicationId → ApplicationRegistry.applicationId
#
# Prerequisites:
#   1. Application Registration with permissions:
#        - sam.computer.r
#        - sam.application.r  (may be needed for the bulk endpoint)
#   2. Client ID, Client Secret, and Data Region
#==============================================================================

#--- Configuration (UPDATE THESE VALUES) ---
$ClientId     = 'b066c338-79ff-4cc3-2a87-08dd91a4d6a6'
$ClientSecret = 'REDACTED'
$Region       = 'australiasoutheast'
$CSVPath      = 'e:\reports\API\SnowAtlas_ComputerSoftwareInstalls.csv'
$PageSize     = 100
$TimeoutSec   = 300
$MaxRetries   = 3
$TokenRefreshBufferMinutes = 5

#==============================================================================
# TOKEN MANAGEMENT
#==============================================================================
$script:Token          = $null
$script:TokenExpiresAt = [datetime]::MinValue

function Get-SnowToken {
    Write-Host "Requesting access token..." -ForegroundColor Cyan
    $TokenUri = "https://$Region.snowsoftware.io/idp/api/connect/token"
    $TokenBody = @{
        grant_type    = 'client_credentials'
        client_id     = $ClientId
        client_secret = $ClientSecret
    }
    try {
        $TokenResponse = Invoke-WebRequest -Uri $TokenUri -ContentType 'application/x-www-form-urlencoded' -Method Post -Body $TokenBody -TimeoutSec 60 -ErrorAction Stop
        if ($TokenResponse.StatusCode -eq 200) {
            $TokenData = $TokenResponse.Content | ConvertFrom-Json
            $script:Token = $TokenData.access_token
            $ExpiresInSeconds = if ($TokenData.expires_in) { $TokenData.expires_in } else { 3300 }
            $script:TokenExpiresAt = (Get-Date).AddSeconds($ExpiresInSeconds)
            Write-Host "Token acquired (expires in $([math]::Round($ExpiresInSeconds / 60, 1)) min)." -ForegroundColor Green
        } else {
            Write-Error "Unexpected status code: $($TokenResponse.StatusCode)"; exit 1
        }
    } catch {
        Write-Error "Authentication failed: $_"; exit 1
    }
}

function Ensure-ValidToken {
    $MinutesRemaining = ($script:TokenExpiresAt - (Get-Date)).TotalMinutes
    if ($MinutesRemaining -le $TokenRefreshBufferMinutes) {
        Write-Host "Token expiring soon ($([math]::Round($MinutesRemaining, 1)) min left). Refreshing..." -ForegroundColor Yellow
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
                Write-Warning "  $Label - token expired. Refreshing..."
                Get-SnowToken
                if ($attempt -lt $MaxRetries) { continue }
            }
            if ($attempt -lt $MaxRetries) {
                $wait = $attempt * 10
                Write-Warning "  $Label - attempt $attempt failed: $err. Retrying in ${wait}s..."
                Start-Sleep -Seconds $wait
            } else { throw $err }
        }
    }
}

#--- Initial authentication ---
Get-SnowToken

#==============================================================================
# FUNCTION: Generic paginated GET
#==============================================================================
function Get-SnowPaginated {
    param([string]$BaseUri, [string]$Label)
    $Page = 1
    $All = [System.Collections.Generic.List[object]]::new()

    do {
        $Sep = if ($BaseUri -match '\?') { '&' } else { '?' }
        $Uri = "${BaseUri}${Sep}page_size=$PageSize&page_number=$Page"

        try {
            $Response = Invoke-SnowApi -Uri $Uri -Label "$Label p$Page"
        } catch {
            Write-Warning "Failed to fetch $Label page $Page : $_"; break
        }

        $Items = $Response.items
        $Count = if ($Items) { $Items.Count } else { 0 }
        foreach ($item in $Items) { $All.Add($item) }

        $TotalPages = $Response.pagination.total_pages
        $TotalItems = $Response.pagination.total_items
        if ($Page -eq 1) {
            Write-Host "  Total $Label : $TotalItems ($TotalPages pages)" -ForegroundColor Gray
        }
        if ($Page % 25 -eq 0 -or $Page -eq $TotalPages) {
            Write-Host "  Page $Page/$TotalPages ($($All.Count) items)..." -ForegroundColor Gray
        }
        $Page++
    } while ($Count -ge $PageSize)

    return $All
}

#==============================================================================
# STEP 1: Try the bulk endpoint
#==============================================================================
Write-Host "Attempting bulk computer-applications endpoint..." -ForegroundColor Cyan
$BulkUri = "https://$Region.snowsoftware.io/api/sam/estate/v1/computers-applications"
$CompApps = Get-SnowPaginated -BaseUri $BulkUri -Label "computer-application records"

#==============================================================================
# STEP 2: If bulk returned empty, fall back to per-computer iteration
#==============================================================================
if ($CompApps.Count -eq 0) {
    Write-Warning "Bulk endpoint returned no results. Falling back to per-computer queries..."
    Write-Host "  (Tip: ensure your app registration has both sam.computer.r AND sam.application.r)" -ForegroundColor Yellow

    Write-Host "Fetching computer list..." -ForegroundColor Cyan
    $ComputersUri = "https://$Region.snowsoftware.io/api/sam/estate/v1/computers"
    $Computers = Get-SnowPaginated -BaseUri $ComputersUri -Label "computers"

    if ($Computers.Count -eq 0) {
        Write-Warning "No computers found either. Check credentials and permissions."; exit 0
    }

    $CompApps = [System.Collections.Generic.List[object]]::new()
    $i = 0

    foreach ($comp in $Computers) {
        $i++
        $CompId = $comp.id
        Write-Progress -Activity "Fetching applications per computer" -Status "$i / $($Computers.Count)" -PercentComplete (($i / $Computers.Count) * 100)

        $PerCompUri = "https://$Region.snowsoftware.io/api/sam/estate/v1/computers/$CompId/applications"
        $Page = 1

        do {
            $Uri = "${PerCompUri}?page_size=$PageSize&page_number=$Page"
            try {
                $Response = Invoke-SnowApi -Uri $Uri -Label "computer $CompId p$Page"
            } catch {
                Write-Warning "  Failed for computer $CompId page $Page : $_"; break
            }

            $Items = $Response.items
            $Count = if ($Items) { $Items.Count } else { 0 }

            foreach ($item in $Items) {
                if (-not $item.computerId) {
                    $item | Add-Member -NotePropertyName 'computerId' -NotePropertyValue $CompId -Force
                }
                $CompApps.Add($item)
            }
            $Page++
        } while ($Count -ge $PageSize)
    }
    Write-Progress -Activity "Fetching applications per computer" -Completed
    Write-Host "Retrieved $($CompApps.Count) records via per-computer fallback." -ForegroundColor Green
}

if ($CompApps.Count -eq 0) {
    Write-Warning "No computer-application records found via either method."; exit 0
}

#==============================================================================
# STEP 3: Build output
#==============================================================================
Write-Host "Building export ($($CompApps.Count) records)..." -ForegroundColor Cyan

$Results = [System.Collections.Generic.List[PSCustomObject]]::new()

foreach ($ca in $CompApps) {
    $obj = [PSCustomObject]@{
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
    }
    $Results.Add($obj)
}

#--- Export ---
$Results | Export-Csv -Path $CSVPath -NoTypeInformation -Force
Write-Host "`nExported $($Results.Count) install records to: $CSVPath" -ForegroundColor Green
Write-Host "Done!" -ForegroundColor Green