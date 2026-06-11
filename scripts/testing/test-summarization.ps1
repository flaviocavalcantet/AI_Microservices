param(
    [Alias("f")]
    [string]$File,

    [Alias("t")]
    [string]$Text = "Artificial intelligence is transforming industries by automating complex tasks and enabling new capabilities that were previously impossible. Machine learning models can now process vast amounts of data to identify patterns, make predictions, and generate human-like text. These advancements are being applied across healthcare, finance, education, and many other sectors, driving significant improvements in efficiency and outcomes.",

    [Alias("m")]
    [int]$MaxNewTokens = 150,

    [Alias("n")]
    [int]$MinNewTokens = 30,

    [Alias("w")]
    [int]$WaitTime = 10
)

# If a file path was provided, read its contents and use that as the text
if ($File) {
    if (-not (Test-Path -Path $File)) {
        Write-Error "File not found: $File"
        exit 1
    }
    $Text = Get-Content -Path $File -Raw
}

# Create a new job
$body = @{
    job_type        = "summarization"
    input_data      = @{
        text           = $Text
        max_new_tokens = $MaxNewTokens
        min_new_tokens = $MinNewTokens
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
Write-Host "MaxNewTokens: $MaxNewTokens"
Write-Host "MinNewTokens: $MinNewTokens"
if ($File) {
    Write-Host "File: $File"
} else {
    Write-Host "Text: $Text"
}
Write-Host "Waiting $WaitTime seconds..."

Start-Sleep -Seconds $WaitTime

Invoke-RestMethod `
    -Method GET `
    -Uri "http://localhost:5000/api/v1/jobs/$jobId" |
    ConvertTo-Json -Depth 10
