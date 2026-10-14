"""Arma los pk3 propios de CoDUOKit en maestro/MiMod:

  python Armar_Pk3.py fixes      -> zzzzzz_kit_fixes.pk3   (VA AL SERVIDOR y a los jugadores)
        _awe.gsc del MiMod_v1.pk3 con los parches de abajo + todo Instalador/fixes_src
  python Armar_Pk3.py practica   -> zzzzzz_kit_practica.pk3 (SOLO launcher; el server no lo tiene)
        todo Instalador/practica_src (bots por equipo y dificultad para la practica local)
  python Armar_Pk3.py armas      -> z_zzz_kit_armas.pk3      (VA AL SERVIDOR y a los jugadores)
        todo Instalador/armas_src (weapons/mp/...: AUG correcta, francotiradores, cambios de dano del Excel)

Si cambias el de fixes: probar en local, subirlo al servidor + Restart, y publicar (Publicar_Actualizacion.bat).
El de practica solo hay que publicarlo. Con sv_pure el server ignora el pk3 de practica de los jugadores.
"""
import os, re, sys, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(ROOT, "maestro", "MiMod", "MiMod_v1.pk3")
OUT = os.path.join(ROOT, "maestro", "MiMod", "zzzzzz_kit_fixes.pk3")
SRC = os.path.join(ROOT, "fixes_src")
OUT_P = os.path.join(ROOT, "maestro", "MiMod", "zzzzzz_kit_practica.pk3")
SRC_P = os.path.join(ROOT, "practica_src")
# Armas: el nombre "z_zzz_..." queda PRIMERO en la prioridad del juego (compara en mayusculas y "_" > letras),
# asi ningun pack de mapas (ej. Zzz_mapa_ejemplo, que convierte el springfield en lanzacohetes) pisa nuestras armas.
OUT_A = os.path.join(ROOT, "maestro", "MiMod", "z_zzz_kit_armas.pk3")
SRC_A = os.path.join(ROOT, "armas_src")
# juego base (de ahi sale el playeranim.script original de UO y las armas que el mod no cambia)
JUEGO = r"C:\Juegos\Call of Duty UO"
que = sys.argv[1] if len(sys.argv) > 1 else ""
if que not in ("fixes", "practica", "armas"):
    raise SystemExit(__doc__)


def armar(out, carpeta, extra=None):
    tmp = out + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for nombre, datos in (extra or {}).items():
            z.writestr(nombre, datos)
        for dirpath, _, files in os.walk(carpeta):
            for f in sorted(files):
                full = os.path.join(dirpath, f)
                z.write(full, os.path.relpath(full, carpeta).replace("\\", "/"))
    os.replace(tmp, out)
    print("OK", out)
    for n in zipfile.ZipFile(out).namelist():
        print("  ", n)


def practica_extra():
    """Archivos generados para los bots de la practica (13-10-2026, ideas de MeatBot):
    - _awe.gsc: el del pk3 de fixes + registra las armas de caminar en el primer instante del mapa
    - weapons/mp/bwalk_*: copia de cada arma de los bots sin municion; con ella el bot "camina"
    - mp/playeranim.script: el original de UO + la pose de correr para las armas bwalk_*
    """
    import glob
    extra = {}
    # 1) _awe.gsc del fixes (ya parcheado) + precache de las armas de caminar
    awe = zipfile.ZipFile(OUT).read("maps/mp/gametypes/_awe.gsc").decode("latin-1")
    anl = "\r\n" if "\r\n" in awe else "\n"
    old = "\tdoPrecaching();" + anl
    if awe.count(old) != 1:
        raise SystemExit("no encuentro doPrecaching() en _awe.gsc")
    awe = awe.replace(old, old + "\tmaps\\mp\\gametypes\\_awe_bots::kit_precache();\t// CoDUOKit: armas de caminar de los bots" + anl)
    extra["maps/mp/gametypes/_awe.gsc"] = awe.encode("latin-1")

    # 2) armas de caminar: la version que usa el juego (mayor prioridad) de cada arma de los bots
    bots = re.findall(r'w\[\d+\] = "(\w+)";', open(os.path.join(SRC_P, "maps", "mp", "gametypes", "_awe_bots.gsc"), encoding="latin-1").read())
    orden = sorted(glob.glob(os.path.join(ROOT, "maestro", "MiMod", "*.pk3")), key=lambda f: os.path.basename(f).upper(), reverse=True)
    orden = [f for f in orden if os.path.basename(f) != os.path.basename(OUT_P)]
    orden += sorted(glob.glob(os.path.join(JUEGO, "uo", "pakuo*.pk3")), key=lambda f: os.path.basename(f).upper(), reverse=True)
    cambios = {"ammoName": "bwalk", "clipName": "bwalk", "clipSize": "0", "maxAmmo": "999", "startAmmo": "999",
               "dropAmmoMin": "0", "dropAmmoMax": "0", "moveSpeedScale": "0", "noPartialReload": "1",
               "weaponClass": "flamethrower", "raiseTime": "0.1", "dropTime": "0.1"}
    for w in bots:
        datos = None
        for f in orden:
            z = zipfile.ZipFile(f)
            if "weapons/mp/" + w in z.namelist():
                datos = z.read("weapons/mp/" + w).decode("latin-1")
                break
        if datos is None:
            raise SystemExit("no encuentro el arma " + w)
        p = datos.strip().split("\\")
        for i in range(1, len(p) - 1, 2):
            if p[i] in cambios:
                p[i + 1] = cambios[p[i]]
        extra["weapons/mp/bwalk_" + w] = "\\".join(p).encode("latin-1")

    # 3) playeranim.script: original de UO + "weapons walkingbot" (correr) al principio de los estados quietos
    pa = zipfile.ZipFile(os.path.join(JUEGO, "uo", "pakuo01.pk3")).read("mp/playeranim.script").decode("latin-1")
    pnl = "\r\n" if "\r\n" in pa else "\n"
    m = re.search(r"set movetype backstep[^\r\n]*" + pnl, pa)
    pa = pa[:m.end()] + pnl + "set weapons walkingbot = " + " AND ".join("bwalk_" + w for w in bots) + pnl + pa[m.end():]
    for estado, anim in (("idle", "pb_combatrun_forward_loop"), ("idlecr", "pb_crouch_run_forward"),
                         ("turnright", "pb_combatrun_right_loop"), ("turnleft", "pb_combatrun_left_loop")):
        cab = "\t" + estado + pnl + "\t{" + pnl
        if pa.count(cab) != 1:
            raise SystemExit("playeranim: esperaba 1 estado " + estado + " y hay " + str(pa.count(cab)))
        bloque = "\t\tweapons walkingbot\t// CoDUOKit: bots caminando" + pnl + "\t\t{" + pnl + "\t\t\tboth " + anim + pnl + "\t\t}" + pnl
        pa = pa.replace(cab, cab + bloque)
    extra["mp/playeranim.script"] = pa.encode("latin-1")
    return extra


if que == "practica":
    armar(OUT_P, SRC_P, practica_extra())
    raise SystemExit(0)
if que == "armas":
    armar(OUT_A, SRC_A)
    raise SystemExit(0)

src = zipfile.ZipFile(MOD).read("maps/mp/gametypes/_awe.gsc").decode("latin-1")
nl = "\r\n" if "\r\n" in src else "\n"


def rep(old, new, count=1):
    global src
    n = src.count(old)
    if n != count:
        raise SystemExit(f"esperaba {count} coincidencia(s) y hay {n}: {old[:70]!r}")
    src = src.replace(old, new)


# --- Estrella del camper que quedaba para siempre (12-10-2026) ---
# markme: sin endon; los bucles ya terminan con isAlive(self). Con endon el hilo se cortaba al morir
# y nunca borraba la estrella ni el objetivo de la brujula.
rep("markme(icon, obj, time)" + nl + "{" + nl + "\tself endon(\"awe_spawned\");" + nl + "\tself endon(\"awe_died\");" + nl,
    "markme(icon, obj, time)" + nl + "{" + nl +
    "\t// CoDUOKit fix: sin endon awe_spawned/awe_died. Los bucles ya terminan con isAlive(self);" + nl +
    "\t// con endon el hilo se cortaba al morir y la estrella/objetivo quedaban para siempre." + nl)
rep("\tif(isdefined(self.awe_objnum))" + nl + "\t{" + nl + "\t\tobjective_delete(objnum);" + nl +
    "\t\tself.awe_objnum = undefined;" + nl + "\t}" + nl + nl + "\tself restoreHeadicon(game[\"headicon_star\"]);" + nl,
    "\tobjective_delete(objnum);" + nl + nl +
    "\tif(!isPlayer(self))\t// se desconecto mientras estaba marcado" + nl + "\t\treturn;" + nl + nl +
    "\tself.awe_objnum = undefined;" + nl +
    "\tself restoreHeadicon(game[\"headicon_star\"]);" + nl)
# camper(): la limpieza de muerte ya destruye el reloj -> no destruirlo dos veces
rep("\tself markme(\"crosshair\", \"camper\", level.awe_anticampmarktime);" + nl + nl +
    "\t// Destroy timer" + nl + "\tself.awe_camptimer destroy();" + nl,
    "\tself markme(\"crosshair\", \"camper\", level.awe_anticampmarktime);" + nl + nl +
    "\tif(!isPlayer(self))\t// CoDUOKit fix: se desconecto mientras estaba marcado" + nl + "\t\treturn;" + nl + nl +
    "\t// Destroy timer (CoDUOKit fix: si murio, la limpieza de muerte ya lo destruyo)" + nl +
    "\tif(isdefined(self.awe_camptimer))" + nl + "\t\tself.awe_camptimer destroy();" + nl)
# --- Vida de los jugadores configurable (12-10-2026) ---
# El modo de juego pone maxhealth=100 y despues llama a _awe::spawnPlayer(); aca lo pisamos con la cvar.
rep("\tif(level.awe_disable) return;" + nl + nl + "\tself notify(\"awe_spawned\");" + nl,
    "\tif(level.awe_disable) return;" + nl + nl + "\tself notify(\"awe_spawned\");" + nl + nl +
    "\t// CoDUOKit: vida de los jugadores (server.cfg: set kit_player_health \"150\"). 0 o vacio = 100 normal" + nl +
    "\tkit_hp = getcvarint(\"kit_player_health\");" + nl +
    "\tif(kit_hp > 0)" + nl + "\t{" + nl + "\t\tself.maxhealth = kit_hp;" + nl + "\t\tself.health = kit_hp;" + nl + "\t}" + nl)

# mensajes en espanol
rep('iprintlnbold("You ^7will be marked for camping for " + level.awe_anticampmarktime + " seconds.");',
    'iprintlnbold("^7Vas a quedar ^1marcado por camper^7 durante " + level.awe_anticampmarktime + " segundos.");', 2)
rep('iprintln(self.name + " ^7will be marked for camping for " + level.awe_anticampmarktime + " seconds.");',
    'iprintln(self.name + " ^7queda ^1marcado por camper^7 durante " + level.awe_anticampmarktime + " segundos.");', 2)

armar(OUT, SRC, {"maps/mp/gametypes/_awe.gsc": src.encode("latin-1")})
