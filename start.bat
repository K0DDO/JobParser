@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

title JobParser
set "WEB_PORT=7357"
set "ROOT=%~dp0"
set "FRONTEND=%ROOT%frontend"

echo ========================================
echo   JobParser — запуск
echo ========================================
echo.

if not exist "%ROOT%.env" (
  if exist "%ROOT%.env.example" (
    echo [!] Нет .env — копирую из .env.example
    copy /Y "%ROOT%.env.example" "%ROOT%.env" >nul
  ) else (
    echo [X] Нет файла .env и .env.example
    pause
    exit /b 1
  )
)

where docker >nul 2>&1
if errorlevel 1 (
  echo [X] Docker не найден. Установи Docker Desktop и повтори.
  pause
  exit /b 1
)

where flutter >nul 2>&1
if errorlevel 1 (
  echo [X] Flutter не найден в PATH.
  pause
  exit /b 1
)

echo [1/4] Останавливаю предыдущий Flutter / порт %WEB_PORT%...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$port=%WEB_PORT%;" ^
  "Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue };" ^
  "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {" ^
  "  if (-not $_.CommandLine) { return $false };" ^
  "  $c = $_.CommandLine;" ^
  "  ($c -match 'parser_bot' -and $c -match 'flutter') -or" ^
  "  ($c -match 'web-port=%WEB_PORT%') -or" ^
  "  ($_.Name -eq 'chrome.exe' -and $c -match 'flutter_tools')" ^
  "} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
timeout /t 1 /nobreak >nul

echo [2/4] Поднимаю Docker (postgres, redis, backend)...
docker compose up -d
if errorlevel 1 (
  echo [X] docker compose up не удался
  pause
  exit /b 1
)

echo [3/4] Жду backend на http://localhost:8000 ...
set /a _tries=0
:wait_health
set /a _tries+=1
curl.exe -sf http://localhost:8000/api/v1/health >nul 2>&1
if not errorlevel 1 goto health_ok
if %_tries% GEQ 60 (
  echo [X] Backend не ответил за ~2 минуты. Логи:
  docker compose logs backend --tail 40
  pause
  exit /b 1
)
timeout /t 2 /nobreak >nul
goto wait_health

:health_ok
echo       Backend OK

echo [4/4] Запускаю Flutter в Chrome...
pushd "%FRONTEND%"
call flutter pub get
if errorlevel 1 (
  popd
  echo [X] flutter pub get не удался
  pause
  exit /b 1
)

flutter devices 2>nul | findstr /I /C:"chrome" >nul
if errorlevel 1 (
  popd
  echo [X] Chrome не найден для Flutter.
  flutter devices
  pause
  exit /b 1
)

echo.
echo ----------------------------------------
echo Backend:  http://localhost:8000
echo API docs: http://localhost:8000/docs
echo Frontend: http://localhost:%WEB_PORT%/
echo.
echo Один терминал. q — выход из Flutter.
echo Docker остановить: stop.bat
echo ----------------------------------------
echo.

call flutter run -d chrome --web-hostname=localhost --web-port=%WEB_PORT%

popd
echo.
echo Flutter остановлен. Docker всё ещё работает — stop.bat чтобы выключить.
pause
endlocal
