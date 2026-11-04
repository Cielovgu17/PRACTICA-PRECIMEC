@echo off
rem Actualiza el link de Vercel con la ultima version que publicaste en el modo edicion.
cd /d "%~dp0"
echo Preparando la carpeta publicar...
python exportar.py || goto :error
cd /d "%~dp0publicar"
call vercel link --yes --project practica-precimec || goto :error
del /q .env.local .gitignore 2>nul
call vercel deploy --prod --yes || goto :error
echo.
echo Listo: https://practica-precimec.vercel.app
pause
exit /b 0
:error
echo.
echo Algo fallo. Copia el mensaje de arriba y compartelo.
pause
exit /b 1
