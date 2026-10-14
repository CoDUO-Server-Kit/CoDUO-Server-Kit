# Genera maestro\MiMod\practica.cfg a partir de la config REAL del server (server.cfg + awe.cfg),
# quitando lo que es solo del servidor (claves, red, masters, rotacion). Ejecutar cada vez que cambie la config del server.
$ErrorActionPreference = 'Stop'
$root   = Split-Path -Parent $PSScriptRoot
$srv    = Join-Path $root 'servidor\MiMod'   # copia local de la carpeta del mod del servidor (server.cfg, awe.cfg)
$out    = Join-Path $root 'maestro\MiMod\practica.cfg'

$fuera = 'rconpassword|rcon_password|sv_master|^\s*sets\s|sv_hostname|g_password|sv_privatepassword|sv_privateclients|sv_pure|sv_allow|sv_www|' +
         'sv_dl_|sv_punkbuster|sv_maxclients|sv_maxping|sv_minping|sv_maxrate|sv_minrate|g_inactivity|sv_timeout|sv_gamespy|sv_reconnect|' +
         'sv_floodprotect|exec\s+"?awe\.cfg|sv_mapRotation|g_gametype|g_log|com_hunkmegs|pb_sv|^\s*WAIT'

$lines = @(
    '// PRACTICA LOCAL - generado automaticamente desde la config del server (no editar a mano)'
    "// Generado: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
    'set sv_hostname "^3Practica local ^7- Mi Comunidad"'
    'set g_password ""'
    'set sv_privateclients "0"'
    'set g_inactivity "0"'
    'set scr_teambalance "0"'
    'set sv_mapRotation ""'
    ''
    '// ===== server.cfg (juego) ====='
)
$lines += Get-Content (Join-Path $srv 'server.cfg') | Where-Object { $_ -notmatch $fuera }
$lines += '', '// ===== awe.cfg ====='
$lines += Get-Content (Join-Path $srv 'awe.cfg') | Where-Object { $_ -notmatch $fuera }
$lines += '', '// Practica: no rotar el mapa aunque no haya nadie', 'set awe_rotate_if_empty "0"'

[IO.File]::WriteAllLines($out, $lines, (New-Object Text.UTF8Encoding($false)))
Write-Host "OK: $out ($($lines.Count) lineas)"
