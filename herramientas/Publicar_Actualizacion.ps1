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

# 4) Borrar del release lo que ya no esta en la carpeta maestra
$validos = @($files | ForEach-Object { $_.asset }) + 'manifest.json'
foreach ($name in @($assets.Keys)) {
    if ($validos -notcontains $name) { Write-Host "  BORRANDO del release: $name"; Remove-Asset $name }
}

# 5) Subir el manifest (siempre al final, asi el launcher nunca ve una lista a medias)
$tmp = Join-Path $env:TEMP 'manifest.json'
[IO.File]::WriteAllText($tmp, ($manifest | ConvertTo-Json -Depth 5), (New-Object Text.UTF8Encoding($false)))
Upload $tmp 'manifest.json'
Copy-Item $tmp $ultimo -Force

Write-Host ""
Write-Host "LISTO. Version $($manifest.version) publicada. Archivos subidos: $subidos de $($files.Count)." -ForegroundColor Green
