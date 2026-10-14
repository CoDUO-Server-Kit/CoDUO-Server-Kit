@echo off
rem Arma Output\Parche_Launcher_CoDUOKit.exe con el launcher actual adentro (launcher\CoDUOKitLauncher.exe).
cd /d "%~dp0"
set CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe
set ICON=
if exist "..\..\Call of Duty Deluxe Edition\united_offensive.ico" set ICON=/win32icon:"..\..\Call of Duty Deluxe Edition\united_offensive.ico"
"%CSC%" /nologo /target:winexe /optimize+ /out:..\Output\Parche_Launcher_CoDUOKit.exe %ICON% ^
  /resource:..\launcher\CoDUOKitLauncher.exe,launcher.bin ^
  /r:System.dll /r:System.Drawing.dll /r:System.Windows.Forms.dll Parche.cs
if errorlevel 1 (echo ERROR al compilar & exit /b 1)
echo OK: Output\Parche_Launcher_CoDUOKit.exe
