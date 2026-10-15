# Genera el par de claves para FIRMAR las actualizaciones del launcher (una sola vez).
#  - La clave PRIVADA queda en ..\privado\firma_privada.dat, cifrada con tu usuario de Windows (DPAPI):
#    copiada a otra PC o a otro usuario no sirve. Publicar_Actualizacion.ps1 la usa para firmar manifest.json.
#  - La clave PUBLICA se muestra al final: copiala en "publicKey" del config.json del launcher.
# Con -Exportar <archivo> guarda ademas una copia SIN cifrar de la privada (para un pendrive de respaldo;
# guardala fuera de la PC). Con -Importar <archivo> restaura esa copia en esta PC.
param([string]$Exportar, [string]$Importar)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Security
$privado = Join-Path (Split-Path -Parent $PSScriptRoot) 'privado'
$dat     = Join-Path $privado 'firma_privada.dat'
New-Item -ItemType Directory -Force $privado | Out-Null

function Guardar($xml) {
    $b = [Security.Cryptography.ProtectedData]::Protect([Text.Encoding]::UTF8.GetBytes($xml), $null, 'CurrentUser')
    [IO.File]::WriteAllBytes($dat, $b)
}

if ($Importar) {
    Guardar (Get-Content $Importar -Raw)
    Write-Host "Clave privada importada en $dat" -ForegroundColor Green
} elseif (Test-Path $dat) {
    Write-Host "Ya existe $dat. Si generas otra, los launchers repartidos dejan de aceptar actualizaciones." -ForegroundColor Yellow
    Write-Host "Para regenerarla de todos modos, borrala a mano y volve a correr este script."
} else {
    $rsa = New-Object Security.Cryptography.RSACryptoServiceProvider 3072
    $rsa.PersistKeyInCsp = $false
    Guardar $rsa.ToXmlString($true)
    Write-Host "Clave privada creada y cifrada en $dat" -ForegroundColor Green
}

$xml = [Text.Encoding]::UTF8.GetString([Security.Cryptography.ProtectedData]::Unprotect([IO.File]::ReadAllBytes($dat), $null, 'CurrentUser'))
$rsa = New-Object Security.Cryptography.RSACryptoServiceProvider
$rsa.PersistKeyInCsp = $false
$rsa.FromXmlString($xml)
if ($Exportar) {
    [IO.File]::WriteAllText($Exportar, $xml)
    Write-Host "Copia SIN cifrar en $Exportar : guardala fuera de la PC y no la compartas." -ForegroundColor Yellow
}
Write-Host ""
Write-Host "Clave PUBLICA (va en config.json del launcher, campo publicKey):"
Write-Host $rsa.ToXmlString($false)
