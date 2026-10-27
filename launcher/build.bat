@echo off
rem Compila CoDUOKitLauncher.exe con el compilador de .NET Framework 4.8 que trae Windows.
cd /d "%~dp0"
set CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe
rem Windows de 32 bits: no tiene Framework64
if not exist "%CSC%" set CSC=%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe
if not exist "%CSC%" (echo No encuentro el compilador de .NET 4 ^(csc.exe^). Instala .NET Framework 4.8. & exit /b 1)
set ICON=
rem icono opcional: poner icono.ico al lado de este script
if exist "%~dp0icono.ico" set ICON=/win32icon:"%~dp0icono.ico"
"%CSC%" /nologo /nowarn:649 /target:winexe /optimize+ /out:CoDUOKitLauncher.exe %ICON% ^
  /r:System.dll /r:System.Drawing.dll /r:System.Windows.Forms.dll /r:System.Web.Extensions.dll ^
  /r:System.Core.dll /r:Microsoft.CSharp.dll /r:System.IO.Compression.dll /r:System.IO.Compression.FileSystem.dll ^
  CoDUOKitLauncher.cs Teclas.cs Practica.cs Top.cs Ui.cs Editor.cs
if errorlevel 1 (echo ERROR al compilar & exit /b 1)
echo OK: CoDUOKitLauncher.exe
