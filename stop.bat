@echo off
chcp 65001 >nul
cd /d "%~dp0"
title JobParser — stop
echo Останавливаю Docker-сервисы JobParser...
docker compose down
echo Готово.
pause
