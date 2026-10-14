@echo off
rem Publica en GitHub lo que haya en la carpeta "maestro". Los jugadores lo reciben al abrir el launcher.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Publicar_Actualizacion.ps1" %*
pause
