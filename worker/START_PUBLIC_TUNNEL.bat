@echo off
cd /d %~dp0
where cloudflared >nul 2>nul
if errorlevel 1 (
  echo Installing Cloudflare Tunnel...
  winget install --id Cloudflare.cloudflared --accept-package-agreements --accept-source-agreements
)
echo.
echo Keep this window open. Copy the HTTPS trycloudflare.com URL into the website Worker Connection box.
cloudflared tunnel --url http://127.0.0.1:8765
pause
