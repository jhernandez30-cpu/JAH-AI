# PowerShell tests for odysseus endpoints
$base = 'http://127.0.0.1:8787'
Write-Host 'Testing /api/health'
Invoke-WebRequest -UseBasicParsing -Uri "$base/api/health" | Select-Object -ExpandProperty Content | Write-Host

Write-Host "Testing /api/odysseus/status"
Invoke-WebRequest -UseBasicParsing -Uri "$base/api/odysseus/status" | Select-Object -ExpandProperty Content | Write-Host

# Upload a small text file
$temp = [System.IO.Path]::GetTempFileName()
Set-Content -Path $temp -Value "hola mundo desde test"
Write-Host "Uploading file"
Invoke-WebRequest -Uri "$base/api/upload" -Method Post -InFile $temp -ContentType "multipart/form-data" -UseBasicParsing -OutFile tmp_upload_resp.json
Get-Content tmp_upload_resp.json | Write-Host

# Upload a zip (create simple zip)
$zip = "$env:TEMP\test_odysseus.zip"
if(Test-Path $zip){ Remove-Item $zip }
Compress-Archive -Path $temp -DestinationPath $zip
Write-Host "Uploading zip"
Invoke-WebRequest -Uri "$base/api/upload" -Method Post -InFile $zip -ContentType "multipart/form-data" -UseBasicParsing -OutFile tmp_upload_zip.json
Get-Content tmp_upload_zip.json | Write-Host

# List files
Write-Host "Listing /api/odysseus/files"
Invoke-WebRequest -Uri "$base/api/odysseus/files" -UseBasicParsing | Select-Object -ExpandProperty Content | Write-Host

# Try reading a file (attempt to read guest/<name> from earlier response)
$resp = Get-Content tmp_upload_resp.json -Raw | ConvertFrom-Json
if($resp.relative_path){
	Write-Host "Reading uploaded file" 
	Invoke-WebRequest -Uri "$base/api/odysseus/files/read" -Method Post -Body (ConvertTo-Json @{ path = $resp.relative_path }) -ContentType 'application/json' -UseBasicParsing | Select-Object -ExpandProperty Content | Write-Host
}

# Analyze a message (fallback or topic_analyzer)
Write-Host "Analyze sample"
Invoke-WebRequest -Uri "$base/api/odysseus/analyze" -Method Post -Body (ConvertTo-Json @{ message = 'Analiza este proyecto y busca temas: python, ai' }) -ContentType 'application/json' -UseBasicParsing | Select-Object -ExpandProperty Content | Write-Host

Write-Host "Done tests"
