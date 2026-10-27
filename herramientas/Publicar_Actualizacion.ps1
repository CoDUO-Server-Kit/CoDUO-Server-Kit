# Publica el contenido de ..\maestro en el release privado de GitHub que usa el launcher.
# Sube solo los archivos que cambiaron y al final el manifest.json.
# Requiere ..\privado\github.json con: { "owner": "...", "repo": "...", "tag": "mod", "write_token": "...", "read_token": "..." }
param([switch]$Forzar)

$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$root     = Split-Path -Parent $PSScriptRoot
$maestro  = Join-Path $root 'maestro'
$privado  = Join-Path $root 'privado'
$cfg      = Get-Content (Join-Path $privado 'github.json') -Raw | ConvertFrom-Json
$ultimo   = Join-Path $privado 'ultimo_manifest.json'
$api      = "https://api.github.com/repos/$($cfg.owner)/$($cfg.repo)"
$headers  = @{ Authorization = "Bearer $($cfg.write_token)"; Accept = 'application/vnd.github+json'; 'User-Agent' = 'CoDUOKitPublicar' }

function AssetName($rel) { $rel -replace '/', '__' }

# 1) Armar el manifest desde la carpeta maestra
Write-Host "Calculando huellas de los archivos de $maestro ..."
$files = @()
$managed = @()
Get-ChildItem $maestro -Recurse -File | Sort-Object FullName | ForEach-Object {
    $rel = $_.FullName.Substring($maestro.Length + 1).Replace('\', '/')
    $top = $rel.Split('/')[0]
    # Solo la carpeta del mod se "vigila" (pk3 sobrantes -> cuarentena). main\ y uo\ tienen archivos del juego
    # que no estan en GitHub: si se vigilaran, el launcher los moveria a cuarentena y romperia el juego.
    if ($rel -match '\.pk3$' -and $top -eq 'MiMod' -and $managed -notcontains $top) { $managed += $top }
    $files += [ordered]@{
        path   = $rel
        sha256 = (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower()
        size   = $_.Length
        asset  = AssetName $rel
        # uoconfig_mp.cfg es la config personal del jugador (teclas, video): solo se instala si falta.
        # El resto (pk3, practica.cfg) se mantiene siempre igual a lo publicado.
        mode   = $(if ($rel -match '(^|/)uoconfig_mp\.cfg$') { 'ifmissing' } else { 'sync' })
    }
}
$manifest = [ordered]@{ version = (Get-Date -Format 'yyyy-MM-dd HH:mm'); managedDirs = $managed; files = $files }

# 2) Buscar (o crear) el release
try {
    $rel = Invoke-RestMethod "$api/releases/tags/$($cfg.tag)" -Headers $headers
} catch {
    if ($_.Exception.Response.StatusCode.value__ -ne 404) { throw }
    Write-Host "Creando el release '$($cfg.tag)'..."
    $body = @{ tag_name = $cfg.tag; name = 'Mod MiMod'; body = 'Archivos del mod. Los publica Publicar_Actualizacion.bat'; prerelease = $false } | ConvertTo-Json
    $rel = Invoke-RestMethod "$api/releases" -Method Post -Headers $headers -Body $body -ContentType 'application/json'
}
$assets = @{}
foreach ($a in $rel.assets) { $assets[$a.name] = $a }

$prev = @{}
if ((Test-Path $ultimo) -and -not $Forzar) {
    foreach ($f in (Get-Content $ultimo -Raw | ConvertFrom-Json).files) { $prev[$f.path] = $f.sha256 }
}

function Remove-Asset($name) {
    if ($assets.ContainsKey($name)) {
        Invoke-RestMethod "$api/releases/assets/$($assets[$name].id)" -Method Delete -Headers $headers | Out-Null
        $assets.Remove($name)
    }
}
function Refresh-Assets {
    $script:assets = @{}
    foreach ($a in (Invoke-RestMethod "$api/releases/$($rel.id)/assets?per_page=100" -Headers $headers)) { $script:assets[$a.name] = $a }
}
function Upload($path, $name) {
    $url = "https://uploads.github.com/repos/$($cfg.owner)/$($cfg.repo)/releases/$($rel.id)/assets?name=$([uri]::EscapeDataString($name))"
    for ($intento = 1; $intento -le 3; $intento++) {
        try {
            Remove-Asset $name
            $r = Invoke-RestMethod $url -Method Post -Headers $headers -InFile $path -ContentType 'application/octet-stream' -TimeoutSec 0
            $assets[$r.name] = $r
            if ($r.name -ne $name) { throw "GitHub renombro el asset '$name' a '$($r.name)'. Cambia el nombre del archivo." }
            return
        } catch {
            if ($intento -eq 3) { throw }
            Write-Host "    se corto la subida ($($_.Exception.Message)); reintento $($intento + 1) de 3..."
            Start-Sleep 5
            Refresh-Assets      # borra la subida a medias en el proximo Remove-Asset
        }
    }
}

# 3) Subir lo que cambio
$subidos = 0
foreach ($f in $files) {
    $local = Join-Path $maestro ($f.path -replace '/', '\')
    $ok = $assets.ContainsKey($f.asset) -and $assets[$f.asset].size -eq $f.size -and $prev[$f.path] -eq $f.sha256
    if ($ok) { Write-Host "  igual   $($f.path)"; continue }
    Write-Host ("  SUBIENDO {0} ({1:N1} MB)..." -f $f.path, ($f.size / 1MB))
    Upload $local $f.asset
    $subidos++
}

# 3b) EDITOR DE MAPAS (opcional): va aparte, en un zip con su propia lista firmada (manifest_editor.json). Solo lo baja
# el launcher de quien instalo el editor; los demas (y los launchers viejos) ni lo ven. Se arma con Armar_Editor.ps1.
$zipEd = Join-Path $root 'editor_paquete\EditorMapas.zip'
$ultimoEd = Join-Path $privado 'ultimo_manifest_editor.json'
$manEd = $null
if (Test-Path $zipEd) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $z = [IO.Compression.ZipFile]::OpenRead($zipEd)
    $desc = 0; foreach ($e in $z.Entries) { $desc += $e.Length }; $cant = $z.Entries.Count; $z.Dispose()
    $manEd = [ordered]@{
        version  = (Get-Date -Format 'yyyy-MM-dd HH:mm')
        asset    = 'EditorMapas.zip'
        sha256   = (Get-FileHash $zipEd -Algorithm SHA256).Hash.ToLower()
        size     = (Get-Item $zipEd).Length
        unpacked = $desc
        files    = $cant
    }
    $prevEd = $null
    if ((Test-Path $ultimoEd) -and -not $Forzar) { $prevEd = (Get-Content $ultimoEd -Raw | ConvertFrom-Json).sha256 }
    if ($assets.ContainsKey('EditorMapas.zip') -and $assets['EditorMapas.zip'].size -eq $manEd.size -and $prevEd -eq $manEd.sha256) {
        Write-Host "  igual   EditorMapas.zip (editor de mapas)"
        $manEd.version = (Get-Content $ultimoEd -Raw | ConvertFrom-Json).version
    } else {
        Write-Host ("  SUBIENDO EditorMapas.zip (editor de mapas, {0:N1} MB)..." -f ($manEd.size / 1MB))
        Upload $zipEd 'EditorMapas.zip'
        $subidos++
    }
}

# 4) Borrar del release lo que ya no esta en la carpeta maestra
$validos = @($files | ForEach-Object { $_.asset }) + 'manifest.json' + 'manifest.sig'
if ($manEd) { $validos += 'EditorMapas.zip', 'manifest_editor.json', 'manifest_editor.sig' }
foreach ($name in @($assets.Keys)) {
    if ($validos -notcontains $name) { Write-Host "  BORRANDO del release: $name"; Remove-Asset $name }
}

# 5) Subir el manifest (siempre al final, asi el launcher nunca ve una lista a medias)
$tmp = Join-Path $env:TEMP 'manifest.json'
[IO.File]::WriteAllText($tmp, ($manifest | ConvertTo-Json -Depth 5), (New-Object Text.UTF8Encoding($false)))
# Firma (si generaste las claves con Generar_Claves.ps1): el launcher con "publicKey" solo acepta listas firmadas
$clave = Join-Path $privado 'firma_privada.dat'
if (Test-Path $clave) {
    Add-Type -AssemblyName System.Security
    $rsa = New-Object Security.Cryptography.RSACryptoServiceProvider
    $rsa.PersistKeyInCsp = $false
    $rsa.FromXmlString([Text.Encoding]::UTF8.GetString([Security.Cryptography.ProtectedData]::Unprotect([IO.File]::ReadAllBytes($clave), $null, 'CurrentUser')))
    $sig = Join-Path $env:TEMP 'manifest.sig'
    [IO.File]::WriteAllText($sig, [Convert]::ToBase64String($rsa.SignData([IO.File]::ReadAllBytes($tmp), 'SHA256')))
    Upload $sig 'manifest.sig'
    Write-Host "  manifest firmado"
} else {
    Write-Host "  AVISO: sin firma (no existe $clave). Recomendado: herramientas\Generar_Claves.ps1" -ForegroundColor Yellow
}
Upload $tmp 'manifest.json'
Copy-Item $tmp $ultimo -Force

# lista del editor (firmada con la misma clave)
if ($manEd) {
    $tmpEd = Join-Path $env:TEMP 'manifest_editor.json'
    [IO.File]::WriteAllText($tmpEd, ($manEd | ConvertTo-Json -Depth 3), (New-Object Text.UTF8Encoding($false)))
    if (Test-Path $clave) {
        $sigEd = Join-Path $env:TEMP 'manifest_editor.sig'
        [IO.File]::WriteAllText($sigEd, [Convert]::ToBase64String($rsa.SignData([IO.File]::ReadAllBytes($tmpEd), 'SHA256')))
        Upload $sigEd 'manifest_editor.sig'
    }
    Upload $tmpEd 'manifest_editor.json'
    Copy-Item $tmpEd $ultimoEd -Force
    Write-Host "  editor de mapas: version $($manEd.version)"
}

Write-Host ""
Write-Host "LISTO. Version $($manifest.version) publicada. Archivos subidos: $subidos de $($files.Count)." -ForegroundColor Green
