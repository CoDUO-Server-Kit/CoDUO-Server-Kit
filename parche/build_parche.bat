@echo off
rem Arma Output\Parche_Launcher_CoDUOKit.exe con el launcher actual adentro (launcher\CoDUOKitLauncher.exe).
cd /d "%~dp0"
set CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe
rem Windows de 32 bits: no tiene Framework64
if not exist "%CSC%" set CSC=%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe
if not exist "%CSC%" (echo No encuentro el compilador de .NET 4 ^(csc.exe^). Instala .NET Framework 4.8. & exit /b 1)
if not exist ..\Output mkdir ..\Output
if not exist ..\launcher\CoDUOKitLauncher.exe (echo Primero compila el launcher: launcher\build.bat & exit /b 1)
set ICON=
if exist "..\..\Call of Duty Deluxe Edition\united_offensive.ico" if not exist ..\Output mkdir ..\Output
if not exist ..\launcher\CoDUOKitLauncher.exe (echo Primero compila el launcher: launcher\build.bat & exit /b 1)
set ICON=/win32icon:"..\..\Call of Duty Deluxe Edition\united_offensive.ico"
"%CSC%" /nologo /target:winexe /optimize+ /out:..\Output\Parche_Launcher_CoDUOKit.exe %ICON% ^
  /resource:..\launcher\CoDUOKitLauncher.exe,launcher.bin ^
  /r:System.dll /r:System.Drawing.dll /r:System.Windows.Forms.dll Parche.cs
if errorlevel 1 (echo ERROR al compilar & exit /b 1)
echo OK: Output\Parche_Launcher_CoDUOKit.exe
