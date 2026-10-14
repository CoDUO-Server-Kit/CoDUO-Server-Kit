@echo off
rem Compila CoDUOKitLauncher.exe con el compilador de .NET Framework 4.8 que trae Windows.
cd /d "%~dp0"
set CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe
set ICON=
if exist "..\..\Call of Duty Deluxe Edition\united_offensive.ico" set ICON=/win32icon:"..\..\Call of Duty Deluxe Edition\united_offensive.ico"
"%CSC%" /nologo /nowarn:649 /target:winexe /optimize+ /out:CoDUOKitLauncher.exe %ICON% ^
  /r:System.dll /r:System.Drawing.dll /r:System.Windows.Forms.dll /r:System.Web.Extensions.dll ^
  /r:System.Core.dll /r:System.IO.Compression.dll /r:System.IO.Compression.FileSystem.dll ^
  CoDUOKitLauncher.cs Teclas.cs Practica.cs Top.cs Ui.cs
if errorlevel 1 (echo ERROR al compilar & exit /b 1)
echo OK: CoDUOKitLauncher.exe
