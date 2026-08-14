$ErrorActionPreference = 'Stop'
$Host.UI.RawUI.WindowTitle = 'Diehl VIN Platform Initializer'

$InstallRoot = Join-Path $env:LOCALAPPDATA 'DiehlVINWorker'
$RawBase = 'https://raw.githubusercontent.com/Wickey23/Diehl-vin-platform/main/worker'
$Files = @(
  'server.py',
  'server_ext.py',
  'requirements.txt',
  'worker.env.example',
  'SETUP_AND_RUN.bat',
  'START_PUBLIC_TUNNEL.bat',
  'dtna_login_and_sync.py'
)

Write-Host ''
Write-Host 'DIEHL VIN PLATFORM INITIALIZER' -ForegroundColor Cyan
Write-Host '================================'
Write-Host "Install folder: $InstallRoot"
Write-Host ''

New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null

function Have-Command($name) {
  return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

if (-not (Have-Command 'py') -and -not (Have-Command 'python')) {
  if (-not (Have-Command 'winget')) {
    throw 'Python is not installed and Windows Package Manager (winget) is unavailable. Install Python 3.12+ and run the initializer again.'
  }
  Write-Host 'Installing Python...' -ForegroundColor Yellow
  winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements
  $env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
}

if (-not (Have-Command 'cloudflared')) {
  if (Have-Command 'winget') {
    Write-Host 'Installing Cloudflare Tunnel...' -ForegroundColor Yellow
    winget install --id Cloudflare.cloudflared -e --silent --accept-package-agreements --accept-source-agreements
    $env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
  } else {
    Write-Host 'winget is unavailable. Cloudflare Tunnel will need to be installed manually.' -ForegroundColor Yellow
  }
}

Write-Host 'Downloading worker files...' -ForegroundColor Yellow
foreach ($file in $Files) {
  $uri = "$RawBase/$file"
  $dest = Join-Path $InstallRoot $file
  Invoke-WebRequest -UseBasicParsing $uri -OutFile $dest
  Write-Host "  OK  $file"
}

$EnvFile = Join-Path $InstallRoot 'worker.env'
if (-not (Test-Path $EnvFile)) {
  $KeyBytes = New-Object byte[] 32
  [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($KeyBytes)
  $AccessKey = ([Convert]::ToBase64String($KeyBytes)).Replace('+','').Replace('/','').Replace('=','')
  $Workbook = Join-Path $env:USERPROFILE "OneDrive - Diehl's Truck World\Documents\VIN In-Service Checker\VIN_Master_Data.xlsx"
  @"
PORT=8765
WORKER_ACCESS_KEY=$AccessKey
MASTER_WORKBOOK=$Workbook
ALLOWED_ORIGINS=https://diehl-vin-platform.vercel.app,http://localhost:3000
DTNA_SYNC_COMMAND=python dtna_login_and_sync.py
VIN_LOOKUP_COMMAND=
OUTLOOK_SYNC_COMMAND=
"@ | Set-Content -Path $EnvFile -Encoding UTF8
} else {
  $AccessKeyLine = Get-Content $EnvFile | Where-Object { $_ -like 'WORKER_ACCESS_KEY=*' } | Select-Object -First 1
  $AccessKey = if ($AccessKeyLine) { $AccessKeyLine.Substring('WORKER_ACCESS_KEY='.Length) } else { '' }
}

Write-Host 'Creating Python virtual environment and installing packages...' -ForegroundColor Yellow
Push-Location $InstallRoot
try {
  if (-not (Test-Path '.venv')) {
    if (Have-Command 'py') { & py -m venv .venv } else { & python -m venv .venv }
  }
  & .\.venv\Scripts\python.exe -m pip install --upgrade pip
  & .\.venv\Scripts\pip.exe install -r requirements.txt
  try { & .\.venv\Scripts\python.exe -m playwright install msedge } catch { & .\.venv\Scripts\python.exe -m playwright install chromium }
} finally {
  Pop-Location
}

$Desktop = [Environment]::GetFolderPath('Desktop')
$StartWorker = Join-Path $Desktop 'Start Diehl VIN Worker.bat'
$StartTunnel = Join-Path $Desktop 'Start Diehl VIN Tunnel.bat'
"@echo off`r`ncd /d `"$InstallRoot`"`r`ncall SETUP_AND_RUN.bat" | Set-Content $StartWorker -Encoding ASCII
"@echo off`r`ncd /d `"$InstallRoot`"`r`ncall START_PUBLIC_TUNNEL.bat" | Set-Content $StartTunnel -Encoding ASCII

$Info = Join-Path $InstallRoot 'connection-info.txt'
@"
DIEHL VIN PLATFORM WORKER
=========================
Install folder: $InstallRoot
Local URL: http://127.0.0.1:8765
Access key: $AccessKey

NEXT:
1. Keep the worker window open.
2. Start the tunnel using the second desktop shortcut.
3. Copy the HTTPS trycloudflare.com URL from that window.
4. Paste that URL and the access key into the website Initializer screen.

DTNA:
Use the DTNA tab in the website. The first run opens a persistent local browser profile and may require login/MFA.
"@ | Set-Content $Info -Encoding UTF8

Write-Host ''
Write-Host 'Installation complete.' -ForegroundColor Green
Write-Host 'Starting the worker now...'
Start-Process -FilePath 'cmd.exe' -ArgumentList '/k', "cd /d `"$InstallRoot`" && SETUP_AND_RUN.bat"
Start-Sleep -Seconds 2
Write-Host 'Starting the secure tunnel now...'
Start-Process -FilePath 'cmd.exe' -ArgumentList '/k', "cd /d `"$InstallRoot`" && START_PUBLIC_TUNNEL.bat"
Start-Process notepad.exe $Info
Write-Host ''
Write-Host 'Use the tunnel URL plus the access key in connection-info.txt on the website Initializer page.' -ForegroundColor Cyan
