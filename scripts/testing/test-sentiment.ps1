param(
    [Alias("t")]
    [string]$Text = "The new product is absolutely fantastic!",

    [Alias("w")]
    [int]$WaitTime = 3
)

# Create a new job
$body = @{
    job_type        = "sentiment_analysis"
    input_data      = @{
        text = $Text
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
Write-Host "Text: $Text"
Write-Host "Waiting $WaitTime seconds..."

Start-Sleep -Seconds $WaitTime

Invoke-RestMethod `
    -Method GET `
    -Uri "http://localhost:5000/api/v1/jobs/$jobId" |
    ConvertTo-Json -Depth 10