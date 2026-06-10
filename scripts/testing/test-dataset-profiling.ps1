param(
    [Alias("f")]
    [string]$File,

    [Alias("d")]
    [string]$Data = "age,salary,department`n25,50000,Engineering`n30,60000,Engineering`n35,75000,Marketing`n28,55000,Marketing`n40,90000,Engineering`n32,65000,HR`n45,95000,Engineering`n29,52000,HR",

    [Alias("i")]
    [ValidateSet("csv", "json", "auto")]
    [string]$InputType = "auto",

    [Alias("w")]
    [int]$WaitTime = 5
)

# If a file path was provided, read its contents and use that as the data
if ($File) {
    if (-not (Test-Path -Path $File)) {
        Write-Error "File not found: $File"
        exit 1
    }
    $Data = Get-Content -Path $File -Raw
}

# Create a new job
$body = @{
    job_type        = "dataset_profiling"
    input_data      = @{
        data       = $Data
        input_type = $InputType
    }
    priority        = 5
    timeout_seconds = 300
} | ConvertTo-Json -Depth 10

$response = Invoke-RestMethod `
    -Method POST `
    -Uri "http://localhost:5000/api/v1/jobs" `
    -ContentType "application/json" `
    -Body $body

$jobId = $response.data.id

Write-Host "Job ID: $jobId"
Write-Host "InputType: $InputType"
if ($File) {
    Write-Host "File: $File"
} else {
    Write-Host "Data: $Data"
}
Write-Host "Waiting $WaitTime seconds..."

Start-Sleep -Seconds $WaitTime

Invoke-RestMethod `
    -Method GET `
    -Uri "http://localhost:5000/api/v1/jobs/$jobId" |
    ConvertTo-Json -Depth 10
