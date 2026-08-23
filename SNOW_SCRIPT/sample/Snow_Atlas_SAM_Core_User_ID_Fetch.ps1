# =============================================================================
# CONFIGURATION
# =============================================================================
$ClientId     = 'b066c338-79ff-4cc3-2a87-08dd91a4d6a6'
$ClientSecret = 'REDACTED'
$Region       = 'australiasoutheast'

$PageSize      = 100
$TimeoutSec    = 120
$PageDelay     = 0.5
$MaxRetries    = 3
$RetryDelaySec = 5

# Token expiry buffer — refresh this many seconds before actual expiry
$TokenExpiryBufferSec = 60

# =============================================================================
# TOKEN MANAGEMENT
# =============================================================================
$Script:Token          = $null
$Script:TokenExpiresAt = [datetime]::MinValue

function Get-SnowToken {
    $TokenUri  = "https://$Region.snowsoftware.io/idp/api/connect/token"
    $TokenBody = @{
        grant_type    = 'client_credentials'
        client_id     = $ClientId
        client_secret = $ClientSecret
    }

    try {
        $Response = Invoke-WebRequest -Uri $TokenUri -Method Post `
            -ContentType 'application/x-www-form-urlencoded' `
            -Body $TokenBody -TimeoutSec $TimeoutSec -ErrorAction Stop

        $Parsed = $Response.Content | ConvertFrom-Json
        $Script:Token          = $Parsed.access_token
        # expires_in is in seconds; default to 3600 if not returned
        $ExpiresIn             = if ($Parsed.expires_in) { [int]$Parsed.expires_in } else { 3600 }
        $Script:TokenExpiresAt = (Get-Date).AddSeconds($ExpiresIn - $TokenExpiryBufferSec)

        Write-Host "    Token acquired. Expires at $($Script:TokenExpiresAt.ToString('HH:mm:ss'))" -ForegroundColor Green
    }
    catch {
        Write-Error "FATAL: Failed to acquire OAuth token.`n$_"
        exit 1
    }
}

function Get-ValidAuthHeader {
    if ((Get-Date) -ge $Script:TokenExpiresAt) {
        Write-Host "    Token expired or expiring soon — refreshing..." -ForegroundColor Yellow
        Get-SnowToken
    }
    return @{ Authorization = "Bearer $Script:Token" }
}

# =============================================================================
# STEP 1 — Initial token acquisition
# =============================================================================
Write-Host "`n[1/2] Acquiring access token..." -ForegroundColor Cyan
Get-SnowToken

# =============================================================================
# STEP 2 — Fetch User Accounts (paginated)
# =============================================================================
Write-Host "`n[2/2] Fetching user accounts..." -ForegroundColor Cyan

$UserUri  = "https://$Region.snowsoftware.io/api/sam/estate/v1/user-accounts"
$AllUsers = [System.Collections.Generic.List[PSObject]]::new()
$Page     = 1

do {
    $Uri     = "${UserUri}?page_size=${PageSize}&page_number=${Page}"
    $Attempt = 0

    while ($Attempt -lt $MaxRetries) {
        $Attempt++
        try {
            $AuthHeader  = Get-ValidAuthHeader
            $RawResponse = Invoke-WebRequest -Uri $Uri -Method Get -Headers $AuthHeader `
                -TimeoutSec $TimeoutSec -ErrorAction Stop
            $Response = $RawResponse.Content | ConvertFrom-Json
            break
        }
        catch {
            $StatusCode = $_.Exception.Response.StatusCode.value__

            # 401 = force token refresh immediately, don't burn a retry
            if ($StatusCode -eq 401) {
                Write-Warning "    HTTP 401 on page $Page — forcing token refresh..."
                $Script:TokenExpiresAt = [datetime]::MinValue
                continue
            }

            Write-Warning "    Page $Page attempt $Attempt/$MaxRetries failed (HTTP $StatusCode): $($_.Exception.Message)"
            if ($Attempt -lt $MaxRetries) {
                $Delay = if ($StatusCode -in 429, 503) { $RetryDelaySec * 3 } else { $RetryDelaySec }
                Write-Warning "    Retrying in $Delay seconds..."
                Start-Sleep -Seconds $Delay
            }
            else { throw }
        }
    }

    if ($Response.items -and $Response.items.Count -gt 0) {
        foreach ($Item in $Response.items) { $AllUsers.Add($Item) }
        Write-Host "    Page $Page — $($Response.items.Count) users retrieved (running total: $($AllUsers.Count))"
    }

    $TotalPages = if ($Response.pagination -and $Response.pagination.total_pages) {
        [int]$Response.pagination.total_pages
    } else { 1 }

    Write-Host "    (Page $Page of $TotalPages)"
    $Page++

    if ($Page -le $TotalPages) { Start-Sleep -Milliseconds ($PageDelay * 1000) }

} while ($Page -le $TotalPages)

# =============================================================================
# OUTPUT
# =============================================================================
$UserAccounts  = $AllUsers | Select-Object id, userName, email, status, fullName
$OutputCsvPath = "C:\temp\useraccount-export.csv"
$UserAccounts | Export-Csv -Path $OutputCsvPath -NoTypeInformation -Encoding UTF8

Write-Host "`n    Total users fetched: $($UserAccounts.Count)" -ForegroundColor Green
Write-Host "    CSV saved to: $OutputCsvPath" -ForegroundColor Green