#!/bin/bash
# Instala un servidor de CoD UO 1.51 en Debian 13 (o 12) de 64 bits. Correr como root o con sudo:
#   sudo bash instalar.sh
# Se puede repetir: no rompe lo que ya esta hecho. Lo que NO hace: copiar el juego y el mod (ver docs/GUIA.md §21).
#
# Variables (opcionales):
#   DIR=/srv/coduo        carpeta del servidor
#   MOD=MiMod             carpeta del mod (fs_game)
#   PUERTO=28960          puerto UDP del juego
#   SERVICIO=coduo        nombre del servicio de systemd
#   RED_CASA=192.168.1.0/24   tu red interna: solo desde ahi se entra por SSH
#   FIREWALL=1            0 = no tocar el firewall
#   ADMIN=tu_usuario      usuario que administra (queda en el grupo del servidor para editar archivos)
set -euo pipefail

DIR="${DIR:-/srv/coduo}"
MOD="${MOD:-MiMod}"
PUERTO="${PUERTO:-28960}"
SERVICIO="${SERVICIO:-coduo}"
RED_CASA="${RED_CASA:-192.168.1.0/24}"
FIREWALL="${FIREWALL:-1}"
ADMIN="${ADMIN:-${SUDO_USER:-}}"
USUARIO="$SERVICIO"
AQUI="$(cd "$(dirname "$0")" && pwd)"

[ "$(id -u)" = 0 ] || { echo "Correlo con sudo: sudo bash $0"; exit 1; }
echo "== Servidor de CoD UO: $DIR (mod $MOD, puerto UDP $PUERTO, servicio $SERVICIO)"

echo "1) paquetes: librerias de 32 bits y herramientas"
dpkg --add-architecture i386
apt-get update -q
DEBIAN_FRONTEND=noninteractive apt-get install -y -q \
  curl bzip2 file nftables unattended-upgrades \
  libc6:i386 libgcc-s1:i386 libstdc++6:i386 zlib1g:i386 >/dev/null

echo "2) usuario propio, sin consola ni permisos de administrador"
id "$USUARIO" >/dev/null 2>&1 || useradd --system --home-dir "$DIR" --shell /usr/sbin/nologin "$USUARIO"
mkdir -p "$DIR/$MOD" "$DIR/main" "$DIR/uo" "$DIR/lib"
[ -n "$ADMIN" ] && id "$ADMIN" >/dev/null 2>&1 && usermod -aG "$USUARIO" "$ADMIN"

echo "3) libstdc++.so.5 (el servidor es de 2005 y la necesita; Debian ya no la trae)"
if [ ! -e "$DIR/lib/libstdc++.so.5" ]; then
  curl -fsSL https://icculus.org/updates/cod/gcc3-libs.tar.bz2 -o /tmp/gcc3-libs.tar.bz2
  tar xjf /tmp/gcc3-libs.tar.bz2 -C "$DIR/lib"
fi

echo "4) script de arranque"
sed -e "s#@DIR@#$DIR#g" -e "s#@MOD@#$MOD#g" -e "s#@PUERTO@#$PUERTO#g" "$AQUI/arrancar.sh" > "$DIR/arrancar.sh"
chmod 755 "$DIR/arrancar.sh"
chown -R "$USUARIO:$USUARIO" "$DIR"
chmod -R g+rwX "$DIR"
find "$DIR" -type d -exec chmod g+s {} +

echo "5) servicio de systemd ($SERVICIO): arranca solo y se reinicia si se cae"
sed -e "s#@DIR@#$DIR#g" -e "s#@USUARIO@#$USUARIO#g" "$AQUI/coduo.service" > "/etc/systemd/system/$SERVICIO.service"
systemctl daemon-reload
systemctl enable "$SERVICIO" >/dev/null 2>&1

echo "6) ajustes de red del sistema"
cp "$AQUI/90-servidor.conf" /etc/sysctl.d/90-servidor.conf
sysctl --system >/dev/null

echo "7) actualizaciones de seguridad automaticas"
printf 'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";\n' > /etc/apt/apt.conf.d/20auto-upgrades

if [ "$FIREWALL" = 1 ]; then
  echo "8) firewall: juego abierto, SSH solo desde $RED_CASA"
  sed -e "s#@PUERTO@#$PUERTO#g" -e "s#@RED_CASA@#$RED_CASA#g" "$AQUI/nftables.conf" > /tmp/nftables.nuevo
  nft -c -f /tmp/nftables.nuevo
  # red de seguridad: si te deja afuera de SSH, en 3 minutos se borra el firewall
  ( sleep 180; [ -e /tmp/firewall.ok ] || nft flush ruleset ) >/dev/null 2>&1 &
  nft -f /tmp/nftables.nuevo
  cp /tmp/nftables.nuevo /etc/nftables.conf
  systemctl enable nftables >/dev/null 2>&1
  echo "   Abri OTRA conexion SSH ahora. Si entra, corre:  sudo touch /tmp/firewall.ok"
  echo "   (si no lo haces, en 3 minutos se quita el firewall solo, hasta el proximo reinicio)"
fi

echo
FALTA=""
[ -x "$DIR/coduo_lnxded" ] || FALTA="$FALTA\n  - $DIR/coduo_lnxded  (del paquete coduo-lnxded-1.51b-large.tar.bz2)"
[ -e "$DIR/$MOD/game.mp.uo.i386.so" ] || FALTA="$FALTA\n  - $DIR/$MOD/game.mp.uo.i386.so  (del mismo paquete: uo/game.mp.uo.i386.so)"
ls "$DIR"/main/pak*.pk3 >/dev/null 2>&1 || FALTA="$FALTA\n  - $DIR/main/*.pk3 y $DIR/uo/*.pk3  (del juego)"
[ -e "$DIR/$MOD/server.cfg" ] || FALTA="$FALTA\n  - $DIR/$MOD/server.cfg  (ver ejemplos/server.cfg)"
if [ -n "$FALTA" ]; then
  echo -e "Listo el sistema. Falta copiar:$FALTA"
  echo "Despues:  sudo systemctl start $SERVICIO"
else
  systemctl restart "$SERVICIO"
  sleep 3
  systemctl --no-pager --lines=0 status "$SERVICIO" | head -3
  echo "Consola: $DIR/$MOD/console_mp_server.log   Registro de partidas: $DIR/$MOD/games_mp.log"
fi
