#!/bin/bash
# Arranca el servidor de CoD UO 1.51 (lo usa el servicio de systemd; instalar.sh completa las rutas).
# DEDICATED=2 internet (aparece en la lista publica)   DEDICATED=1 solo red local
# MAPA = primer mapa al arrancar (con sv_mapRotation vacio, map_rotate no tiene que elegir y el servidor no arranca)
cd @DIR@
export LD_LIBRARY_PATH=@DIR@/lib
exec ./coduo_lnxded +set dedicated ${DEDICATED:-2} +set net_port @PUERTO@ \
  +set fs_basepath @DIR@ +set fs_homepath @DIR@ +set fs_game @MOD@ \
  +set sv_pure 1 +set ttycon 0 +set logfile 2 +exec server.cfg +map ${MAPA:-mp_uo_harbor}
