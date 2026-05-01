@echo off
echo Launching Independent Chrome Window...
:: 建立一個暫存資料夾
if not exist "C:\temp_pchome" mkdir "C:\temp_pchome"

powershell -Command "Start-Process 'C:\Program Files\Google\Chrome\Application\chrome.exe' -ArgumentList '--remote-debugging-port=9223', '--user-data-dir=C:\temp_pchome', '--no-first-run', 'https://24h.pchome.com.tw'"

echo.
echo ====================================================
echo Independent Chrome is opening (Port 9223).
echo 1. LOG IN to PChome in this NEW window.
echo 2. Keep this window open.
echo 3. Run: python pchome_sniper.py [URL] -c
echo ====================================================
pause
