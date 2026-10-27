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
    os.makedirs(os.path.dirname(out), exist_ok=True)
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
    awe = awe.replace(old, old + "\tmaps\\mp\\gametypes\\_awe_bots::kit_precache();\t// CoDUOKit: armas de caminar de los bots" + anl +
                      "\tprecacheMenu(\"practica_mapas\");\t// CoDUOKit: cambiar mapa/modo sin votacion (practica)" + anl)
    extra["maps/mp/gametypes/_awe.gsc"] = awe.encode("latin-1")
    extra.update(practica_mapas())

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


def practica_mapas():
    """Practica (22-10-2026): cambiar de mapa y de modo SIN votacion (en la practica los bots cuentan como jugadores
    y la votacion nunca llegaba a la mitad). Solo dentro del pk3 de practica:
    - _awe_mapvote.gsc del fixes: "Cambiar Mapa" abre el menu practica_mapas en vez de pedir la votacion
    - callvote.menu del fixes: "Cambiar Modo de Juego" tambien abre ese menu (antes era la votacion del juego)
    - practica_mapas.menu: pestanas por modo y todos los mapas de ese modo (de CoDmaps.arena, como la votacion)
    - _kit_practica_lista.gsc: que mapa y modo es cada boton
    """
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import Armar_Votacion as av
    extra = {}
    fx = zipfile.ZipFile(OUT)
    # 1) Cambiar Mapa -> menu de la practica
    mv = fx.read("maps/mp/gametypes/_awe_mapvote.gsc").decode("latin-1")
    viejo = ('\t\tif(menu == "callvote" && response == "votarmapa")\r\n\t\t\tlevel thread PedirVotacion(self, "mapa");\r\n'
             '\t\telse if(menu == "callvote" && response == "votarmodo")\r\n\t\t\tlevel thread PedirVotacion(self, "modo");\r\n')
    if mv.count(viejo) != 1:
        raise SystemExit("no encuentro el pedido de votacion en _awe_mapvote.gsc")
    mv = mv.replace(viejo, '\t\tif(menu == "callvote" && (response == "votarmapa" || response == "votarmodo" || response == "practicamodo"))\r\n'
                    '\t\t\tself thread maps\\mp\\gametypes\\_kit_practica::Abrir();\t// practica: sin votacion\r\n'
                    '\t\telse if(menu == "practica_mapas")\r\n'
                    '\t\t\tself thread maps\\mp\\gametypes\\_kit_practica::Elegir(response);\r\n')
    viejo = '\tlevel thread EnPartidaJugadores();\r\n'
    if mv.count(viejo) != 1:
        raise SystemExit("no encuentro EnPartidaJugadores en _awe_mapvote.gsc")
    mv = mv.replace(viejo, viejo + '\tif(getcvar("kit_practica_prueba") != "")\r\n'
                    '\t\tlevel thread maps\\mp\\gametypes\\_kit_practica::Prueba();\r\n')
    extra["maps/mp/gametypes/_awe_mapvote.gsc"] = mv.encode("latin-1")
    # 2) Cambiar Modo de Juego -> el mismo menu
    for ruta in ("ui_mp/scriptmenus/callvote.menu", "ui_mp/scriptmenus/spanish/callvote.menu"):
        m = fx.read(ruta).decode("latin-1")
        b = re.search(r'(name\s+"button_changegametype".*?action\s*\{)(.*?)(\})', m, re.S)
        if not b or ("show gametype" not in b.group(2) and "votarmodo" not in b.group(2)):
            raise SystemExit("no encuentro el boton Cambiar Modo en " + ruta)
        m = m[:b.start(2)] + ('\r\n\t\t\t\tplay "mouse_click";\r\n\t\t\t\t// CoDUOKit practica: elegir modo y mapa sin votacion\r\n'
                              '\t\t\t\tscriptMenuResponse "practicamodo";\r\n\t\t\t\tclose callvote;\r\n\t\t\t') + m[b.end(2):]
        extra[ruta] = m.encode("latin-1")
    # 3) lista de mapas por modo (mismos filtros que la votacion: .bsp presente y no roto)
    z = zipfile.ZipFile(os.path.join(av.MAESTRO, av.ARENA_PK3))
    arena = next(n for n in z.namelist() if n.lower().endswith(".arena"))
    hay = av.bsp_existentes()
    modos = [("tdm", "Equipos"), ("dm", "Todos c/ todos"), ("ctf", "Bandera"), ("bas", "Bases"), ("sd", "Buscar y destr."),
             ("hq", "Cuartel"), ("bel", "Tras lineas"), ("dom", "Dominacion"), ("re", "Recuperacion")]
    por_modo, vistos = {}, set()
    for mapa, nombre, ms in av.leer_arena(z.read(arena).decode("latin-1")):
        ml = mapa.lower()
        if ml in vistos or ml in av.ROTOS or ml not in hay:
            continue
        vistos.add(ml)
        for g in ms:
            por_modo.setdefault(g.lower(), []).append((mapa, nombre))
    modos = [(g, t) for g, t in modos if por_modo.get(g)]
    ent = []   # (modo, mapa, nombre)
    for g, _ in modos:
        for mapa, nombre in sorted(por_modo[g], key=lambda x: re.sub(r"\^.", "", x[1]).lower()):
            ent.append((g, mapa, nombre))
    gsc = ["// Lo genera publicar\\Armar_Pk3.py practica (lista del menu practica_mapas). No editar a mano.", ""]
    for fn, k in (("Mapas", 1), ("Modos", 0), ("Nombres", 2)):
        gsc += [fn + "()", "{", "\tr = [];"] + ['\tr[%d] = "%s";' % (i, av.gsc_str(e[k])) for i, e in enumerate(ent)] + ["\treturn r;", "}", ""]
    extra["maps/mp/gametypes/_kit_practica_lista.gsc"] = "\r\n".join(gsc).encode("latin-1")
    # 4) el menu: pestanas arriba y 64 lugares para mapas (4 columnas). Los nombres los manda el script por cvars
    # (ui_pm_1..64) segun el modo elegido: un boton por mapa y modo eran 228 items / 100 KB y el juego no abria el
    # menu (los menus aguantan ~96 items; el mas grande del juego pesa 59 KB)
    cols, alto, ancho, x0, y0, LUGARES = 4, 22, 150, 20, 92, 64
    for g, _ in modos:
        if len(por_modo[g]) > LUGARES:
            raise SystemExit("el modo %s tiene %d mapas: el menu de la practica muestra %d" % (g, len(por_modo[g]), LUGARES))
    it = []
    def item(cuerpo):
        it.append("\t\titemDef\n\t\t{\n" + "".join("\t\t\t" + l + "\n" for l in cuerpo) + "\t\t}\n")
    item(['name "fondo"', "visible 1", "rect 0 0 640 480", "style WINDOW_STYLE_FILLED", "backcolor 0 0 0 0.88", "decoration"])
    item(['name "titulo"', "visible 1", "rect 0 14 640 26", 'text "^3PRACTICA: CAMBIAR MAPA Y MODO"', "textfont UI_FONT_NORMAL",
          "textscale .34", "textalign ITEM_ALIGN_CENTER", "textalignx 320", "textaligny 22", "forecolor 1 1 1 1", "decoration"])
    item(['name "ayuda"', "visible 1", "rect 0 40 640 18", 'text "Elegi el modo arriba y despues el mapa: cambia al instante, sin votacion. ESC para volver."',
          "textfont UI_FONT_NORMAL", "textscale .2", "textalign ITEM_ALIGN_CENTER", "textalignx 320", "textaligny 14", "forecolor .75 .75 .75 1", "decoration"])
    tw = 600 // len(modos)
    for k, (g, t) in enumerate(modos):
        x = 20 + k * tw
        item(['name "tabsel_%s"' % g, "visible 1", "rect %d 62 %d 22" % (x, tw - 4), "style WINDOW_STYLE_FILLED", "backcolor .35 .38 .9 .8",
              'cvartest "ui_practica_modo"', 'showCvar { "%s" }' % g, "decoration"])
        item(['name "tab_%s"' % g, "visible 1", "rect %d 62 %d 22" % (x, tw - 4), "style WINDOW_STYLE_FILLED", "backcolor 1 1 1 .08",
              "type ITEM_TYPE_BUTTON", 'text "%s"' % t, "textfont UI_FONT_NORMAL", "textscale .21", "textalign ITEM_ALIGN_CENTER",
              "textalignx %d" % ((tw - 4) // 2), "textaligny 16", "forecolor 1 1 1 1",
              'action { play "mouse_click"; setcvar ui_practica_modo "%s"; scriptMenuResponse "m_%s"; }' % (g, g),
              'onFocus { play "mouse_over"; }'])
    for j in range(LUGARES):
        x, y = x0 + (j % cols) * ancho, y0 + (j // cols) * alto
        # texto con la cvar (como los de votarmapa) que ademas se puede tocar
        item(['name "lugar%d"' % (j + 1), "visible 1", "rect %d %d %d %d" % (x, y, ancho - 4, alto - 4), 'cvar "ui_pm_%d"' % (j + 1),
              "textfont UI_FONT_NORMAL", "textscale .22", "textstyle ITEM_TEXTSTYLE_SHADOWED", "textalignx 4", "textaligny 14",
              "forecolor 1 1 1 1", 'cvartest "ui_pm_%d"' % (j + 1), 'hideCvar { "" }',
              'action { play "mouse_click"; scriptMenuResponse "s%d"; close practica_mapas; }' % (j + 1), 'onFocus { play "mouse_over"; }'])
    if y + alto > 470:
        raise SystemExit("los lugares del menu de la practica no entran en la pantalla")
    if len(it) > 95:
        raise SystemExit("el menu de la practica tiene %d items (maximo ~96)" % len(it))
    menu = ('#include "ui_mp/menudef.h"\n\n// Practica: cambiar mapa y modo sin votacion (lo genera publicar\\Armar_Pk3.py practica)\n{\n\tmenuDef\n\t{\n'
            '\t\tname\t\t\t"practica_mapas"\n\t\tfullscreen\t\t0\n\t\trect\t\t\t0 0 640 480\n\t\tfocuscolor\t\t1 .8 .2 1\n'
            '\t\tdisablecolor\t\t0 0 0 0\n\t\tstyle\t\t\tWINDOW_STYLE_EMPTY\n\t\tonEsc\n\t\t{\n\t\t\tclose practica_mapas;\n\t\t}\n\n'
            + "".join(it) + "\t}\n}\n").replace("\n", "\r\n").encode("latin-1")
    for sub in ("", "spanish/"):
        extra["ui_mp/scriptmenus/" + sub + "practica_mapas.menu"] = menu
    print("practica: %d mapas en %d modos" % (len(ent), len(modos)))
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

# --- Votacion de mapas en espanol (19-10-2026; la votacion la genera Armar_Votacion.py en fixes_src) ---
rep('level.mapvotetext["MapVote"]\t= &"Press ^2FIRE^7 to vote                           Votes";',
    'level.mapvotetext["MapVote"]\t= &"Vota con ^2F1^7 a ^2F5^7                              Votos";')
rep('level.mapvotetext["TimeLeft"] = &"Time Left: ";', 'level.mapvotetext["TimeLeft"] = &"Quedan: ";')
rep('level.mapvotetext["MapVoteHeader"] = &"Next Map Vote";', 'level.mapvotetext["MapVoteHeader"] = &"Proximo mapa";')
# votacion de mapa en partida ("Solicitar votacion > Cambiar Mapa"): menu votarmapa + escucha en cada ronda
rep("doPrecaching()" + nl + "{" + nl,
    "doPrecaching()" + nl + "{" + nl + "\tprecacheMenu(\"votarmapa\");\t// CoDUOKit: votacion de mapa en partida (Armar_Votacion.py)" + nl)
rep("\t// Start threads" + nl + "\tthread startThreads();" + nl + "}" + nl,
    "\t// Start threads" + nl + "\tthread startThreads();" + nl + nl +
    "\t// CoDUOKit: votacion de mapa en partida (callvote > Cambiar Mapa)" + nl +
    "\tmaps\\mp\\gametypes\\_awe_mapvote::EnPartidaInit();" + nl + "}" + nl)

armar(OUT, SRC, {"maps/mp/gametypes/_awe.gsc": src.encode("latin-1")})
