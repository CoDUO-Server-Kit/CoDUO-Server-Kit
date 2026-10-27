"""Genera la votacion de mapas de fin de partida (fixes_src/maps/mp/gametypes/_awe_mapvote.gsc).

Reemplaza la de AWE (_awe_mapvote.gsc de el mod). Al terminar la partida pasa a todos a espectador y muestra
5 mapas AL AZAR que sirven para el MODO ACTUAL (sin repetir el que se acaba de jugar). Cada uno vota con el
boton de disparar (cada toque pasa al siguiente) y se va al mas votado; empate = sorteo entre los empatados.
El modo de juego no cambia: se sigue cambiando con la votacion del juego (callvote) como siempre.

Diferencias con la de AWE:
  - candidatos de la lista de mapas del juego (CoDmaps.arena), no de sv_mapRotation (que esta vacia a proposito)
  - solo mapas del modo actual; nombres con sus colores (longname del arena)
  - nadie vota por defecto (en AWE todos arrancaban votando el mapa 1 y ese ganaba casi siempre)
  - textos en espanol

Se activa en server.cfg:  set awe_map_vote "1"   y   set awe_map_vote_time "20"  (segundos para votar)
Despues: python Armar_Pk3.py fixes  -> subir zzzzzz_kit_fixes.pk3 a los dos servidores, reiniciar y publicar.
"""
import glob, os, re, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAESTRO = os.path.join(ROOT, "maestro", "MiMod")
JUEGO = r"C:\Juegos\Call of Duty UO"
SALIDA = os.path.join(ROOT, "fixes_src", "maps", "mp", "gametypes", "_awe_mapvote.gsc")
ARENA_PK3 = "z_kit_clientv2.pk3"
# mapas que no cargan (se probaron uno por uno): no se ofrecen aunque esten en la lista
ROTOS = {"mp_uo_ardennes1944", "townville_ctf", "carcasson_ctf_final", "lw_dawnville", "mechili", "pow"}


def leer_arena(texto):
    """Bloques { map "x" longname "y" gametype "a b c" } (ignora los comentados con //)."""
    texto = "\n".join(l for l in texto.splitlines() if not l.strip().startswith("//"))
    mapas = []
    for b in re.findall(r"\{([^}]*)\}", texto):
        kv = dict(re.findall(r'(\w+)\s+"([^"]*)"', b))
        if kv.get("map"):
            mapas.append((kv["map"], kv.get("longname", kv["map"]), kv.get("gametype", "").split()))
    return mapas


def bsp_existentes():
    pks = glob.glob(os.path.join(JUEGO, "main", "*.pk3")) + glob.glob(os.path.join(JUEGO, "uo", "*.pk3"))
    pks += [p for p in glob.glob(os.path.join(MAESTRO, "*.pk3")) if "practica" not in p.lower()]
    hay = set()
    for p in pks:
        for n in zipfile.ZipFile(p).namelist():
            m = re.match(r"(?i)maps/mp/([^/]+)\.bsp$", n)
            if m:
                hay.add(m.group(1).lower())
    return hay


def gsc_str(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def main():
    z = zipfile.ZipFile(os.path.join(MAESTRO, ARENA_PK3))
    arena = next(n for n in z.namelist() if n.lower().endswith(".arena"))
    mapas = leer_arena(z.read(arena).decode("latin-1"))
    hay = bsp_existentes()
    vistos, por_modo, nombres, fuera = set(), {}, {}, []
    for mapa, nombre, modos in mapas:
        ml = mapa.lower()
        if ml in vistos:
            continue
        vistos.add(ml)
        if ml in ROTOS or ml not in hay:
            fuera.append(mapa + (" (roto)" if ml in ROTOS else " (no esta el .bsp)"))
            continue
        nombres[mapa] = nombre
        for g in modos:
            por_modo.setdefault(g.lower(), []).append(mapa)

    casos = ""
    for g in sorted(por_modo):
        casos += '\t\tcase "%s":\n' % g
        for i, m in enumerate(por_modo[g]):
            casos += '\t\t\tm[%d] = "%s";\n' % (i, m)
        casos += "\t\t\tbreak;\n"
    # modos de cada mapa (votacion de modo en partida): solo los modos que el mod tiene
    conocidos = ["dm", "tdm", "ctf", "sd", "hq", "dom", "bas", "bel", "re", "carrera"]
    por_mapa = {}
    for g in por_modo:
        if g in conocidos:
            for m in por_modo[g]:
                por_mapa.setdefault(m, []).append(g)
    modos = ""
    for m in sorted(por_mapa):
        modos += '\t\tcase "%s":\n' % m
        for i, g in enumerate(sorted(por_mapa[m], key=conocidos.index)):
            modos += '\t\t\tm[%d] = "%s";\n' % (i, g)
        modos += "\t\t\tbreak;\n"
    nom = "".join('\t\tcase "%s": return "%s";\n' % (m, gsc_str(n)) for m, n in sorted(nombres.items()))
    plano = "".join('\t\tcase "%s": return "%s";\n' % (m, gsc_str(re.sub(r"\^.", "", n))) for m, n in sorted(nombres.items()))

    # menus: callvote (el boton "Cambiar Mapa" pide la votacion) y votarmapa (las 6 opciones)
    base = os.path.join(ROOT, "fixes_src", "ui_mp", "scriptmenus")
    for pk3, ruta in (("pakuo07.pk3", "ui_mp/scriptmenus/callvote.menu"),
                      ("localized_spanish_pakuo01.pk3", "ui_mp/scriptmenus/spanish/callvote.menu")):
        m = zipfile.ZipFile(os.path.join(JUEGO, "uo", pk3)).read(ruta).decode("latin-1")
        viejo = re.search(r'(name\s+"button_changemap".*?action\s*\{)(.*?)(\})', m, re.S)
        if not viejo or "uiScript loadArenas" not in viejo.group(2):
            raise SystemExit("no encuentro el boton Cambiar Mapa en " + ruta)
        nuevo = ("\r\n\t\t\t\tplay \"mouse_click\";\r\n\t\t\t\t// CoDUOKit: votacion de mapa para todos (Armar_Votacion.py)\r\n"
                 "\t\t\t\tscriptMenuResponse \"votarmapa\";\r\n\t\t\t\tclose callvote;\r\n\t\t\t")
        m = m[:viejo.start(2)] + nuevo + m[viejo.end(2):]
        # "Cambiar Tipo de Juego": votacion propia (2 jugadores o mas, 2 votos o mas). Se ve con la misma condicion que
        # "Cambiar Mapa": el servidor tiene apagada la votacion de modo del juego (g_allowvotetypemap/gametype 0)
        b = re.search(r'(name\s+"button_changegametype".*?cvartest\s+")(ui_allowvotetypemap)(".*?action\s*\{)(.*?)(\})', m, re.S)
        if not b or "show gametype" not in b.group(4):
            raise SystemExit("no encuentro el boton Cambiar Tipo de Juego en " + ruta)
        m = (m[:b.start(2)] + "ui_allowvotemap" + m[b.end(2):b.start(4)] +
             "\r\n\t\t\t\tplay \"mouse_click\";\r\n\t\t\t\t// CoDUOKit: votacion de modo (2 jugadores o mas; Armar_Votacion.py)\r\n"
             "\t\t\t\tscriptMenuResponse \"votarmodo\";\r\n\t\t\t\tclose callvote;\r\n\t\t\t" + m[b.end(4):])
        d = os.path.join(ROOT, "fixes_src", *ruta.split("/"))
        os.makedirs(os.path.dirname(d), exist_ok=True)
        open(d, "wb").write(m.encode("latin-1"))
    # HUD: la votacion en partida se ve a la izquierda, en amarillo, sin abrir ningun menu (no frena el juego)
    hud_txt = '// hud menu defs (CoDUOKit: + la votacion de mapa, Armar_Votacion.py)\r\n{\r\n\tloadMenu { "ui_mp/hud.menu" }\r\n\tloadMenu { "ui_mp/hud_votar.menu" }\r\n}\r\n'
    open(os.path.join(ROOT, "fixes_src", "ui_mp", "hud.txt"), "wb").write(hud_txt.encode("latin-1"))
    open(os.path.join(ROOT, "fixes_src", "ui_mp", "hud_votar.menu"), "wb").write(HUD.replace("\n", "\r\n").encode("latin-1"))
    vm = MENU.replace("\n", "\r\n").encode("latin-1")
    for sub in ("", "spanish"):
        d = os.path.join(base, sub, "votarmapa.menu")
        os.makedirs(os.path.dirname(d), exist_ok=True)
        open(d, "wb").write(vm)
    gsc = GSC.replace("@@CASOS@@", casos).replace("@@MODOS@@", modos).replace("@@NOMBRES@@", nom).replace("@@PLANOS@@", plano).replace("\n", "\r\n")
    os.makedirs(os.path.dirname(SALIDA), exist_ok=True)
    open(SALIDA, "wb").write(gsc.encode("latin-1"))
    print("OK", SALIDA)
    for g in sorted(por_modo):
        print("  %-5s %2d mapas" % (g, len(por_modo[g])))
    print("  fuera de la votacion:", ", ".join(fuera) or "ninguno")


MENU = r"""#include "ui_mp/menudef.h"

// Votacion de mapa en partida (lo genera publicar\Armar_Votacion.py). Los textos los manda el servidor (ui_votar_*).
#define ORIGEN 170 110

{
	menuDef
	{
		name			"votarmapa"
		fullscreen		0
		rect			0 0 640 480
		focuscolor		1 1 1 1
		disablecolor		0 0 0 0
		style			WINDOW_STYLE_EMPTY
		onEsc
		{
			close votarmapa;
		}

		itemDef
		{
			name			"fondo"
			visible			1
			rect			0 0 300 236
			origin			ORIGEN
			style			WINDOW_STYLE_FILLED
			backcolor		0 0 0 0.85
			border			1
			bordercolor		1 1 1 .25
			decoration
		}
		itemDef
		{
			name			"titulo"
			visible			1
			rect			0 4 300 24
			origin			ORIGEN
			text			"^3VOTACION DE MAPA"
			textfont		UI_FONT_NORMAL
			textscale		.32
			textalign		ITEM_ALIGN_CENTER
			textalignx		150
			textaligny		20
			forecolor		1 1 1 1
			decoration
		}
		itemDef
		{
			name			"tiempo"
			visible			1
			rect			10 30 280 18
			origin			ORIGEN
			cvar			"ui_votar_titulo"
			textfont		UI_FONT_NORMAL
			textscale		.22
			textaligny		14
			forecolor		1 1 1 1
			decoration
		}
@@OPCIONES@@
		itemDef
		{
			name			"ayuda"
			visible			1
			rect			10 212 280 18
			origin			ORIGEN
			text			"Hace clic en una opcion. ESC para seguir jugando."
			textfont		UI_FONT_NORMAL
			textscale		.2
			textaligny		14
			forecolor		.7 .7 .7 1
			decoration
		}
	}
}
"""
OPCION = r"""		itemDef
		{
			name			"opcion%(n)d"
			visible			1
			rect			10 %(y)d 280 24
			origin			ORIGEN
			style			WINDOW_STYLE_FILLED
			backcolor		1 1 1 .07
			type			ITEM_TYPE_BUTTON
			text			" "
			cvartest		"ui_votar_%(n)d"
			hideCvar		{ "" }
			action
			{
				play "mouse_click";
				scriptMenuResponse "%(n)d";
				close votarmapa;
			}
			onFocus
			{
				play "mouse_over";
			}
		}
		itemDef
		{
			name			"texto%(n)d"
			visible			1
			rect			16 %(y)d 270 24
			origin			ORIGEN
			cvar			"ui_votar_%(n)d"
			textfont		UI_FONT_NORMAL
			textscale		.26
			textstyle		ITEM_TEXTSTYLE_SHADOWED
			textaligny		18
			forecolor		1 1 1 1
			decoration
		}
"""
MENU = MENU.replace("@@OPCIONES@@", "".join(OPCION % {"n": i, "y": 22 + i * 28} for i in range(1, 7)))


HUD = r"""#include "ui_mp/menudef.h"

// Votacion de mapa en partida: textos que manda el servidor (ui_votar_*), vacios fuera de una votacion.
// Lo genera publicar\Armar_Votacion.py. Se vota con F1 a F6 (el launcher las deja como "vstr kit_votoN").
{
	menuDef
	{
		name			"votarmapa_hud"
		fullScreen		MENU_FALSE
		visible			MENU_TRUE
		rect			0 2 330 140
@@LINEAS@@	}
}
"""
LINEA = r"""		itemDef
		{
			name			"votar%(n)s"
			visible			MENU_TRUE
			rect			%(x)d %(y)d 330 16
			cvar			"%(cvar)s"
			%(prueba)s
			textfont		UI_FONT_NORMAL
			textscale		%(escala)s
			textstyle		ITEM_TEXTSTYLE_SHADOWED
			textaligny		13
			forecolor		1 0.85 0.15 1
			decoration
		}
"""
def lineas_hud(x, sufijo, prueba):
    """Las lineas del HUD en la columna x. prueba = hideCvar/showCvar de kit_hd (lo pone el launcher)."""
    ls = [("partida" + sufijo, 0, "ui_kit_partida", ".16"), ("top" + sufijo, 11, "ui_kit_top", ".16"),
          ("titulo" + sufijo, 28, "ui_votar_titulo", ".18")]
    ls += [("v%d%s" % (i, sufijo), 28 + i * 15, "ui_votar_%d" % i, ".2") for i in range(1, 7)]
    return "".join(LINEA % {"n": n, "x": x, "y": y, "cvar": c, "escala": e, "prueba": prueba} for n, y, c, e in ls)


# Con el motor HD en pantalla ancha el HUD se dibuja en un cuadro 4:3 centrado: el launcher pone kit_hd 1 y las
# lineas van 56 unidades mas a la izquierda (fuera del cuadro). Con el motor original (imagen estirada) quedan en 0.
HUD = HUD.replace("@@LINEAS@@", lineas_hud(-56, "_hd", 'cvartest\t\t"kit_hd"\n\t\t\tshowCvar\t\t{ "1" }') +
                  lineas_hud(0, "", 'cvartest\t\t"kit_hd"\n\t\t\thideCvar\t\t{ "1" }'))

GSC = r'''//***********************************************************************************************************
// VOTACION DE MAPAS (lo genera publicar\Armar_Votacion.py: no editar a mano)
// Basada en el MAP VOTE PACKAGE de AWE: originally made by NC-17 (codam, powerserver), reworked by wizard220,
// modified by FrAnCkY55, modified again by Bell. Cambiada para Mi Comunidad: 5 mapas al azar del modo
// actual sacados de la lista de mapas del juego, sin voto por defecto, desempate al azar, textos en espanol.
//***********************************************************************************************************

Initialise()
{
	if(!level.awe_mapvote) return;

	if(isdefined(level.awe_uo))
		level.awe_mapvotehudoffset = 0;
	else
		level.awe_mapvotehudoffset = 30;

	wait .5;
	CleanUp();
	CreateHud();
	thread RunMapVote();
	level waittill("VotingComplete");
	DeleteHud();
}

// Mapas de la lista del juego que admiten el modo (solo los que existen y cargan)
MapasDelModo(gt)
{
	m = [];
	switch(gt)
	{
@@CASOS@@	}
	return m;
}

// Modos que admite cada mapa (para la votacion de modo en partida)
ModosDelMapa(map)
{
	m = [];
	switch(map)
	{
@@MODOS@@	}
	return m;
}

NombreMapa(map)
{
	switch(map)
	{
@@NOMBRES@@	}
	return maps\mp\gametypes\_awe::getMapName(map);
}

// Nombre sin colores (las letras de la votacion en partida van todas en amarillo)
NombrePlano(map)
{
	switch(map)
	{
@@PLANOS@@	}
	return map;
}

// Teclas F1 a F6: el launcher las deja como "vstr kit_votoN" y el servidor decide que hacen.
// En una votacion mandan un voto (comando mr = respuesta de menu: el servidor lo recibe como menuresponse
// "kit_vN"; el menu 0 es el de informacion del servidor, que ignora respuestas desconocidas).
// Fuera de una votacion, F1/F2 son "vote yes"/"vote no" (las votaciones normales del juego).
TeclasVoto(cuantas)
{
	for(n = 1; n <= 6; n++)
	{
		if(n <= cuantas)
			self setClientCvar("kit_voto" + n, "cmd mr " + getcvar("sv_serverid") + " 0 kit_v" + n);
		else
			self setClientCvar("kit_voto" + n, "");
	}
}

TeclasNormales()
{
	self setClientCvar("kit_voto1", "vote yes");
	self setClientCvar("kit_voto2", "vote no");
	for(n = 3; n <= 6; n++)
		self setClientCvar("kit_voto" + n, "");
	self setClientCvar("ui_votar_titulo", "");
	for(n = 1; n <= 6; n++)
		self setClientCvar("ui_votar_" + n, "");
}

TodosTeclasNormales()
{
	ps = getentarray("player", "classname");
	for(i = 0; i < ps.size; i++)
		ps[i] TeclasNormales();
}

NombreModo(gt)
{
	switch(gt)
	{
		case "dm": return "Todos contra todos";
		case "tdm": return "Por equipos";
		case "ctf": return "Capturar la bandera";
		case "sd": return "Buscar y destruir";
		case "hq": return "Cuartel general";
		case "dom": return "Dominacion";
		case "bas": return "Asalto a la base";
		case "bel": return "Detras de las lineas enemigas";
		case "re": return "Recuperacion";
		case "carrera": return "Carrera de jeeps";
	}
	return maps\mp\gametypes\_awe::getGametypeName(gt);
}

CleanUp()
{
	level notify("awe_boot");
	wait .05;
	if(isdefined(level.clock)) level.clock destroy();
	if(isdefined(level.awe_axisicon)) level.awe_axisicon destroy();
	if(isdefined(level.awe_axisnumber)) level.awe_axisnumber destroy();
	if(isdefined(level.awe_deadaxisicon)) level.awe_deadaxisicon destroy();
	if(isdefined(level.awe_deadaxisnumber)) level.awe_deadaxisnumber destroy();
	if(isdefined(level.awe_alliedicon)) level.awe_alliedicon destroy();
	if(isdefined(level.awe_alliednumber)) level.awe_alliednumber destroy();
	if(isdefined(level.awe_deadalliedicon)) level.awe_deadalliedicon destroy();
	if(isdefined(level.awe_deadalliednumber)) level.awe_deadalliednumber destroy();
	if(isdefined(level.awe_warmupmsg)) level.awe_warmupmsg destroy();
}

CreateHud()
{
	level.vote_hud_bgnd = newHudElem();
	level.vote_hud_bgnd.archived = false;
	level.vote_hud_bgnd.alpha = .7;
	level.vote_hud_bgnd.x = 205;
	level.vote_hud_bgnd.y = level.awe_mapvotehudoffset + 17;
	level.vote_hud_bgnd.sort = 9000;
	level.vote_hud_bgnd.color = (0,0,0);
	level.vote_hud_bgnd setShader("white", 260, 140);

	level.vote_header = newHudElem();
	level.vote_header.archived = false;
	level.vote_header.alpha = .3;
	level.vote_header.x = 208;
	level.vote_header.y = level.awe_mapvotehudoffset + 19;
	level.vote_header.sort = 9001;
	level.vote_header setShader("white", 254, 21);

	level.vote_headerText = newHudElem();
	level.vote_headerText.archived = false;
	level.vote_headerText.x = 210;
	level.vote_headerText.y = level.awe_mapvotehudoffset + 21;
	level.vote_headerText.sort = 9998;
	level.vote_headerText.label = level.mapvotetext["MapVoteHeader"];
	level.vote_headerText.fontscale = 1.3;

	level.vote_leftline = newHudElem();
	level.vote_leftline.archived = false;
	level.vote_leftline.alpha = .3;
	level.vote_leftline.x = 207;
	level.vote_leftline.y = level.awe_mapvotehudoffset + 19;
	level.vote_leftline.sort = 9001;
	level.vote_leftline setShader("white", 1, 135);

	level.vote_rightline = newHudElem();
	level.vote_rightline.archived = false;
	level.vote_rightline.alpha = .3;
	level.vote_rightline.x = 462;
	level.vote_rightline.y = level.awe_mapvotehudoffset + 19;
	level.vote_rightline.sort = 9001;
	level.vote_rightline setShader("white", 1, 135);

	level.vote_bottomline = newHudElem();
	level.vote_bottomline.archived = false;
	level.vote_bottomline.alpha = .3;
	level.vote_bottomline.x = 207;
	level.vote_bottomline.y = level.awe_mapvotehudoffset + 154;
	level.vote_bottomline.sort = 9001;
	level.vote_bottomline setShader("white", 256, 1);

	level.vote_hud_timeleft = newHudElem();
	level.vote_hud_timeleft.archived = false;
	level.vote_hud_timeleft.x = 400;
	level.vote_hud_timeleft.y = level.awe_mapvotehudoffset + 26;
	level.vote_hud_timeleft.sort = 9998;
	level.vote_hud_timeleft.fontscale = .8;
	level.vote_hud_timeleft.label = level.mapvotetext["TimeLeft"];
	level.vote_hud_timeleft setValue( level.awe_mapvotetime );

	level.vote_hud_instructions = newHudElem();
	level.vote_hud_instructions.archived = false;
	level.vote_hud_instructions.x = 340;
	level.vote_hud_instructions.y = level.awe_mapvotehudoffset + 56;
	level.vote_hud_instructions.sort = 9998;
	level.vote_hud_instructions.fontscale = 1;
	level.vote_hud_instructions.label = level.mapvotetext["MapVote"];
	level.vote_hud_instructions.alignX = "center";
	level.vote_hud_instructions.alignY = "middle";

	level.vote_map = [];
	for(i = 0; i < 5; i++)
	{
		level.vote_map[i] = newHudElem();
		level.vote_map[i].archived = false;
		level.vote_map[i].x = 434;
		level.vote_map[i].y = level.awe_mapvotehudoffset + 69 + i * 16;
		level.vote_map[i].sort = 9998;
	}
}

RunMapVote()
{
	currentgt = getcvar("g_gametype");
	currentmap = getcvar("mapname");

	// candidatos: mapas del modo actual menos el que se acaba de jugar, mezclados
	todos = MapasDelModo(currentgt);
	pool = [];
	for(i = 0; i < todos.size; i++)
		if(todos[i] != currentmap)
			pool[pool.size] = todos[i];
	for(i = pool.size - 1; i > 0; i--)
	{
		j = randomInt(i + 1);
		t = pool[i]; pool[i] = pool[j]; pool[j] = t;
	}

	// Sin mapas para este modo: se sigue como siempre (se repite el mapa)
	if(pool.size == 0)
	{
		wait 0.05;
		level notify("VotingComplete");
		return;
	}

	for(j = 0; j < 5; j++)
	{
		if(j < pool.size)
		{
			level.mapcandidate[j]["map"] = pool[j];
			level.mapcandidate[j]["mapname"] = NombreMapa(pool[j]);
		}
		else
		{
			// menos de 5 mapas para este modo: el resto es repetir
			level.mapcandidate[j]["map"] = currentmap;
			level.mapcandidate[j]["mapname"] = "Repetir este mapa";
		}
		level.mapcandidate[j]["gametype"] = currentgt;
		level.mapcandidate[j]["votes"] = 0;
	}

	thread DisplayMapChoices();

	level.kit_fin_activa = true;
	players = getentarray("player", "classname");
	for(i = 0; i < players.size; i++)
		players[i] TeclasVoto(5);

	game["menu_team"] = "";

	players = getentarray("player", "classname");
	for(i = 0; i < players.size; i++)
		players[i] thread PlayerVote();

	thread VoteLogic();

	wait 0.1;
	level.mapended = true;
}

DeleteHud()
{
	level.vote_headerText destroy();
	level.vote_hud_timeleft destroy();
	level.vote_hud_instructions destroy();
	for(i = 0; i < 5; i++)
		level.vote_map[i] destroy();
	level.vote_hud_bgnd destroy();
	level.vote_header destroy();
	level.vote_leftline destroy();
	level.vote_rightline destroy();
	level.vote_bottomline destroy();

	players = getentarray("player", "classname");
	for(i = 0; i < players.size; i++)
		if(isdefined(players[i].vote_indicator))
			players[i].vote_indicator destroy();
}

// Los nombres de los 5 mapas, en el centro de la pantalla (se repiten mientras dura la votacion)
DisplayMapChoices()
{
	level endon("VotingDone");
	for(;;)
	{
		iprintln("^7Votacion del proximo mapa - modo: ^3" + NombreModo(level.mapcandidate[0]["gametype"]));
		for(i = 0; i < 5; i++)
			iprintlnbold("^3F" + (i + 1) + "^7 " + level.mapcandidate[i]["mapname"]);
		wait 7.8;
	}
}

// Se vota con F1 a F5 (ver VotoTecla). Hasta que toca una no vota por ninguno.
PlayerVote()
{
	level endon("VotingDone");

	if(self.pers["team"] == "spectator")
		novote = true;

	self maps\mp\gametypes\_awe::spawnSpectator();
	self.sessionstate = "spectator";
	self.spectatorclient = -1;
	resettimeout();

	self setClientCvar("g_scriptMainMenu", "");
	self closeMenu();

	self allowSpectateTeam("allies", false);
	self allowSpectateTeam("axis", false);
	self allowSpectateTeam("freelook", false);
	self allowSpectateTeam("none", true);

	if(isdefined(novote))
		return;

	self.votechoice = undefined;

	colors[0] = (0  ,  0,  1);
	colors[1] = (0  ,0.5,  1);
	colors[2] = (0  ,  1,  1);
	colors[3] = (0  ,  1,0.5);
	colors[4] = (0  ,  1,  0);

	self iprintln("^3Vota con F1 a F5.");

	for(;;)
	{
		wait .01;
		tecla = undefined;
		if(isdefined(self.kit_tecla_voto))
		{
			tecla = self.kit_tecla_voto;
			self.kit_tecla_voto = undefined;
		}
		if(isdefined(tecla))		// solo F1 a F5 (disparar no vota: confundia)
		{
			if(isdefined(tecla))
			{
				if(!isdefined(self.votechoice))
				{
					self.vote_indicator = newClientHudElem( self );
					self.vote_indicator.alignY = "middle";
					self.vote_indicator.x = 208;
					self.vote_indicator.archived = false;
					self.vote_indicator.sort = 9998;
					self.vote_indicator.alpha = .3;
					self.vote_indicator setShader("white", 254, 17);
				}
				self.votechoice = tecla;
			}
			else if(!isdefined(self.votechoice))
			{
				self.votechoice = 0;
				self.vote_indicator = newClientHudElem( self );
				self.vote_indicator.alignY = "middle";
				self.vote_indicator.x = 208;
				self.vote_indicator.archived = false;
				self.vote_indicator.sort = 9998;
				self.vote_indicator.alpha = .3;
				self.vote_indicator setShader("white", 254, 17);
			}
			else
			{
				self.votechoice++;
				if(self.votechoice == 5)
					self.votechoice = 0;
			}

			self iprintln("Votaste por ^2" + (self.votechoice + 1) + ". " + level.mapcandidate[self.votechoice]["mapname"]);
			self.vote_indicator.y = level.awe_mapvotehudoffset + 77 + self.votechoice * 16;
			self.vote_indicator.color = colors[self.votechoice];

			self playLocalSound("hq_score");
		}

		self.sessionstate = "spectator";
		self.spectatorclient = -1;
	}
}

// Cuenta los votos cada 0,1 s y al final elige el mas votado (empate: sorteo entre los empatados)
VoteLogic()
{
	for(;level.awe_mapvotetime >= 0; level.awe_mapvotetime--)
	{
		for(j = 0; j < 10; j++)
		{
			for(i = 0; i < 5; i++) level.mapcandidate[i]["votes"] = 0;
			players = getentarray("player", "classname");
			for(i = 0; i < players.size; i++)
				if(isdefined(players[i].votechoice))
					level.mapcandidate[players[i].votechoice]["votes"]++;

			for(i = 0; i < 5; i++)
				level.vote_map[i] setValue( level.mapcandidate[i]["votes"] );
			wait .1;
		}
		level.vote_hud_timeleft setValue( level.awe_mapvotetime );
	}

	wait 0.2;

	topvotes = 0;
	for(i = 0; i < 5; i++)
		if(level.mapcandidate[i]["votes"] > topvotes)
			topvotes = level.mapcandidate[i]["votes"];
	empatados = [];
	for(i = 0; i < 5; i++)
		if(level.mapcandidate[i]["votes"] == topvotes)
			empatados[empatados.size] = i;
	// sin votos: cualquiera de los 5 (salvo "Repetir", si hay otro)
	if(topvotes == 0)
	{
		reales = [];
		for(i = 0; i < 5; i++)
			if(level.mapcandidate[i]["mapname"] != "Repetir este mapa")
				reales[reales.size] = i;
		if(reales.size)
			empatados = reales;
	}

	SetMapWinner(empatados[randomInt(empatados.size)]);
}

SetMapWinner(winner)
{
	map		= level.mapcandidate[winner]["map"];
	mapname	= level.mapcandidate[winner]["mapname"];
	gametype	= level.mapcandidate[winner]["gametype"];

	setcvar("sv_maprotationcurrent", " gametype " + gametype + " map " + map);

	level.kit_fin_activa = false;
	TodosTeclasNormales();
	wait 0.1;
	level notify( "VotingDone" );
	wait 0.05;

	iprintlnbold(" ");
	iprintlnbold(" ");
	iprintlnbold(" ");
	iprintlnbold("^7Gano");
	iprintlnbold(mapname);
	iprintlnbold("^3" + NombreModo(gametype));

	level.vote_headerText fadeOverTime (1);
	level.vote_hud_timeleft fadeOverTime (1);
	level.vote_hud_instructions fadeOverTime (1);
	for(i = 0; i < 5; i++)
		level.vote_map[i] fadeOverTime (1);
	level.vote_hud_bgnd fadeOverTime (1);
	level.vote_header fadeOverTime (1);
	level.vote_leftline fadeOverTime (1);
	level.vote_rightline fadeOverTime (1);
	level.vote_bottomline fadeOverTime (1);

	level.vote_headerText.alpha = 0;
	level.vote_hud_timeleft.alpha = 0;
	level.vote_hud_instructions.alpha = 0;
	for(i = 0; i < 5; i++)
		level.vote_map[i].alpha = 0;
	level.vote_hud_bgnd.alpha = 0;
	level.vote_header.alpha = 0;
	level.vote_leftline.alpha = 0;
	level.vote_rightline.alpha = 0;
	level.vote_bottomline.alpha = 0;

	players = getentarray("player", "classname");
	for(i = 0; i < players.size; i++)
	{
		if(isdefined(players[i].vote_indicator))
		{
			players[i].vote_indicator fadeOverTime (1);
			players[i].vote_indicator.alpha = 0;
		}
	}

	wait 4;
	level notify( "VotingComplete" );
}

//***********************************************************************************************************
// VOTACION DE MAPA EN PARTIDA: "Solicitar votacion > Cambiar Mapa" (callvote.menu cambiado) le avisa al script
// y se vota para TODOS: 5 mapas al azar del modo actual + "6. Seguir en este mapa", con el menu votarmapa.
// Gana el mas votado SI tiene mas de la mitad de los jugadores conectados; si no (o empate con "Seguir", o sin votos) se sigue. Entre una votacion y otra: kit_votacion_espera
// segundos (por defecto 120). Tiempo para votar: awe_map_vote_time (el mismo de fin de partida).
//***********************************************************************************************************

EnPartidaInit()
{
	if(getcvar("kit_votacion_espera") == "")
		setcvar("kit_votacion_espera", "120");
	level.kit_vm_activa = false;
	if(!isdefined(game["kit_vm_ultima"]))
		game["kit_vm_ultima"] = -1000000;
	level thread EnPartidaJugadores();
	maps\mp\gametypes\_kit_hud::init();	// tu partida y tu puesto en el top (HUD)
	logPrint("VOTACION;init\n");
	if(getcvar("kit_votacion_prueba") != "")
		level thread PruebaAutomatica();
}

EnPartidaJugadores()
{
	for(;;)
	{
		ps = getentarray("player", "classname");
		for(i = 0; i < ps.size; i++)
			if(!isdefined(ps[i].kit_vm_hilo))
			{
				ps[i].kit_vm_hilo = true;
				ps[i] TeclasNormales();
				if(level.kit_vm_activa)
					ps[i] TeclasVoto(level.kit_vm_nombre.size);
				else if(isdefined(level.kit_fin_activa) && level.kit_fin_activa)
					ps[i] TeclasVoto(5);
				ps[i] thread EscucharMenu();
			}
		wait 1;
	}
}

EscucharMenu()
{
	self endon("disconnect");
	for(;;)
	{
		self waittill("menuresponse", menu, response);
		// Teclas F1 a F6 PRIMERO: llegan con el nombre del menu numero 0 (que es "votarmapa", el primero que se
		// registra), asi que no se puede decidir por el nombre del menu.
		switch(response)
		{
			case "kit_v1": self VotoTecla(1); continue;
			case "kit_v2": self VotoTecla(2); continue;
			case "kit_v3": self VotoTecla(3); continue;
			case "kit_v4": self VotoTecla(4); continue;
			case "kit_v5": self VotoTecla(5); continue;
			case "kit_v6": self VotoTecla(6); continue;
		}
		if(menu == "callvote" && response == "votarmapa")
			level thread PedirVotacion(self, "mapa");
		else if(menu == "callvote" && response == "votarmodo")
			level thread PedirVotacion(self, "modo");
		else if(menu == "votarmapa")
			self VotoEnPartida(response);
	}
}

CandidatosMezclados(gt, actual)
{
	todos = MapasDelModo(gt);
	pool = [];
	for(i = 0; i < todos.size; i++)
		if(todos[i] != actual)
			pool[pool.size] = todos[i];
	for(i = pool.size - 1; i > 0; i--)
	{
		j = randomInt(i + 1);
		t = pool[i]; pool[i] = pool[j]; pool[j] = t;
	}
	return pool;
}

// tipo "mapa": 5 mapas del modo actual. tipo "modo": los otros modos que admite este mapa (hacen falta 2 jugadores
// o mas, y que gane con 2 votos o mas: con 1 solo jugador no se puede cambiar el modo)
PedirVotacion(quien, tipo)
{
	if(isdefined(level.mapended) && level.mapended)
		return;
	if(level.kit_vm_activa)
	{
		quien iprintlnbold("^7Ya hay una votacion: vota con ^3F1 a F" + level.kit_vm_nombre.size);
		return;
	}
	if(isdefined(level.kit_fin_activa) && level.kit_fin_activa)
		return;
	if(tipo == "modo" && getentarray("player", "classname").size < 2)
	{
		quien iprintlnbold("^7Para cambiar el modo de juego hacen falta ^3al menos 2 jugadores^7 y que voten los dos.");
		return;
	}
	espera = getcvarint("kit_votacion_espera") - (getTime() - game["kit_vm_ultima"]) / 1000;
	if(espera > 0)
	{
		quien iprintlnbold("^7Hubo una votacion hace poco: espera ^3" + (int)(espera + 1) + "^7 segundos.");
		return;
	}
	gt = getcvar("g_gametype");
	if(tipo == "modo")
	{
		todos = ModosDelMapa(getcvar("mapname"));
		pool = [];
		for(i = 0; i < todos.size; i++)
			if(todos[i] != gt)
				pool[pool.size] = todos[i];
		if(pool.size == 0)
		{
			quien iprintlnbold("^7Este mapa no tiene otros modos de juego.");
			return;
		}
	}
	else
	{
		pool = CandidatosMezclados(gt, getcvar("mapname"));
		if(pool.size == 0)
		{
			quien iprintlnbold("^7No hay otros mapas para este modo de juego.");
			return;
		}
	}
	level.kit_vm_activa = true;
	level.kit_vm_tipo = tipo;
	level.kit_vm_gt = gt;
	level.kit_vm_mapa = [];
	level.kit_vm_nombre = [];
	level.kit_vm_plano = [];
	for(i = 0; i < 5 && i < pool.size; i++)
	{
		level.kit_vm_mapa[i] = pool[i];
		if(tipo == "modo")
		{
			level.kit_vm_nombre[i] = "^7" + NombreModo(pool[i]);
			level.kit_vm_plano[i] = NombreModo(pool[i]);
		}
		else
		{
			level.kit_vm_nombre[i] = NombreMapa(pool[i]);
			level.kit_vm_plano[i] = NombrePlano(pool[i]);
		}
	}
	level.kit_vm_seguir = level.kit_vm_mapa.size;		// la ultima opcion: seguir como esta
	if(tipo == "modo")
	{
		level.kit_vm_nombre[level.kit_vm_seguir] = "^7Seguir con este modo";
		level.kit_vm_plano[level.kit_vm_seguir] = "Seguir con este modo";
	}
	else
	{
		level.kit_vm_nombre[level.kit_vm_seguir] = "^7Seguir en este mapa";
		level.kit_vm_plano[level.kit_vm_seguir] = "Seguir en este mapa";
	}
	level.kit_vm_votos = [];
	level.kit_vm_tiempo = level.awe_mapvotetime;
	if(!isdefined(level.kit_vm_tiempo) || level.kit_vm_tiempo < 10)
		level.kit_vm_tiempo = 20;
	level.kit_vm_resta = level.kit_vm_tiempo;

	ps = getentarray("player", "classname");
	for(i = 0; i < ps.size; i++)
		ps[i].kit_vm_voto = undefined;
	logPrint("VOTACION;pedida;" + quien.name + ";" + gt + ";" + tipo + "\n");
	que = "de mapa";
	if(tipo == "modo")
		que = "el modo de juego";
	iprintlnbold(quien.name + " ^7pidio cambiar " + que + ": ^3vota con F1 a F" + level.kit_vm_nombre.size + "^7 (" + level.kit_vm_tiempo + " segundos)");
	for(i = 0; i < ps.size; i++)
		ps[i] TeclasVoto(level.kit_vm_nombre.size);
	ActualizarTextos();

	for(t = level.kit_vm_tiempo; t > 0; t--)
	{
		level.kit_vm_resta = t;
		ActualizarTextos();
		wait 1;
		if(isdefined(level.mapended) && level.mapended)
		{
			level.kit_vm_activa = false;
			TodosTeclasNormales();
			return;
		}
	}
	level.kit_vm_resta = 0;

	// recuento
	n = level.kit_vm_nombre.size;
	cuenta = Contar(n);
	top = 0;
	for(i = 0; i < n; i++)
		if(cuenta[i] > top)
			top = cuenta[i];
	gana = level.kit_vm_seguir;
	if(top > 0 && cuenta[level.kit_vm_seguir] < top)
	{
		empatados = [];
		for(i = 0; i < n; i++)
			if(cuenta[i] == top)
				empatados[empatados.size] = i;
		gana = empatados[randomInt(empatados.size)];
	}

	// En partida hace falta MAS DE LA MITAD de los jugadores conectados (con 3 jugadores, 2 votos)
	jugadores = getentarray("player", "classname").size;
	sinMayoria = false;
	// el modo ademas necesita 2 votos o mas (con 2 jugadores, los dos)
	if(gana != level.kit_vm_seguir && (cuenta[gana] * 2 <= jugadores || (level.kit_vm_tipo == "modo" && cuenta[gana] < 2)))
	{
		sinMayoria = true;
		perdio = gana;
		gana = level.kit_vm_seguir;
	}

	level.kit_vm_activa = false;
	game["kit_vm_ultima"] = getTime();
	logPrint("VOTACION;resultado;" + level.kit_vm_nombre[gana] + ";" + cuenta[gana] + "\n");
	TodosTeclasNormales();

	sigue = "^7Se sigue en este mapa";
	if(level.kit_vm_tipo == "modo")
		sigue = "^7Se sigue con este modo";
	if(sinMayoria)
	{
		iprintlnbold("^7" + level.kit_vm_nombre[perdio] + " ^7tuvo " + cuenta[perdio] + " de " + jugadores + " votos:");
		if(level.kit_vm_tipo == "modo")
			iprintlnbold("^7hacen falta 2 votos o mas y mas de la mitad. " + sigue + ".");
		else
			iprintlnbold("^7hace falta mas de la mitad. " + sigue + ".");
		return;
	}
	if(gana == level.kit_vm_seguir)
	{
		if(top == 0)
			iprintlnbold("^7Nadie voto: " + sigue + ".");
		else
			iprintlnbold(sigue + " (" + cuenta[gana] + " votos).");
		return;
	}
	iprintlnbold("^7Gano " + level.kit_vm_nombre[gana] + " ^7(" + cuenta[gana] + " votos)");
	if(level.kit_vm_tipo == "modo")
		iprintlnbold("^7Cambiando el modo de juego en 3 segundos...");
	else
		iprintlnbold("^7Cambiando de mapa en 3 segundos...");
	wait 3;
	if(isdefined(level.mapended) && level.mapended)
		return;
	level.mapended = true;
	if(level.kit_vm_tipo == "modo")
		setcvar("sv_maprotationcurrent", " gametype " + level.kit_vm_mapa[gana] + " map " + getcvar("mapname"));
	else
		setcvar("sv_maprotationcurrent", " gametype " + level.kit_vm_gt + " map " + level.kit_vm_mapa[gana]);
	exitLevel(false);
}

Contar(n)
{
	cuenta = [];
	for(i = 0; i < n; i++)
		cuenta[i] = 0;
	ps = getentarray("player", "classname");
	for(i = 0; i < ps.size; i++)
		if(isdefined(ps[i].kit_vm_voto) && ps[i].kit_vm_voto < n)
			cuenta[ps[i].kit_vm_voto]++;
	return cuenta;
}

// Textos del menu votarmapa (los lee cada jugador: cvars ui_votar_*)
ActualizarTextos()
{
	n = level.kit_vm_nombre.size;
	cuenta = Contar(n);
	ps = getentarray("player", "classname");
	for(i = 0; i < ps.size; i++)
	{
		if(level.kit_vm_tipo == "modo")
			ps[i] setClientCvar("ui_votar_titulo", "VOTACION DE MODO  -  " + level.kit_vm_resta + " s  -  hacen falta 2 votos");
		else
			ps[i] setClientCvar("ui_votar_titulo", "VOTACION DE MAPA  -  " + level.kit_vm_resta + " s  -  " + NombreModo(level.kit_vm_gt));
		for(j = 0; j < 6; j++)
		{
			if(j < n)
			{
				texto = "F" + (j + 1) + ": " + level.kit_vm_plano[j] + "  (" + cuenta[j] + ")";
				if(isdefined(ps[i].kit_vm_voto) && ps[i].kit_vm_voto == j)
					texto = "^2" + texto + "  <";
				ps[i] setClientCvar("ui_votar_" + (j + 1), texto);
			}
			else
				ps[i] setClientCvar("ui_votar_" + (j + 1), "");
		}
	}
}

VotoTecla(n)
{
	if(level.kit_vm_activa)
		self VotoEnPartida("" + n);
	else if(isdefined(level.kit_fin_activa) && level.kit_fin_activa && n <= 5)
		self.kit_tecla_voto = n - 1;		// lo toma PlayerVote (votacion de fin de partida)
}

VotoEnPartida(r)
{
	if(!level.kit_vm_activa)
		return;
	switch(r)
	{
		case "1": v = 0; break;
		case "2": v = 1; break;
		case "3": v = 2; break;
		case "4": v = 3; break;
		case "5": v = 4; break;
		case "6": v = 5; break;
		default: return;
	}
	if(v >= level.kit_vm_nombre.size)
		return;
	self.kit_vm_voto = v;
	self iprintln("Votaste por ^2" + level.kit_vm_nombre[v]);
	ActualizarTextos();
}

// Solo para probar sin gente (kit_votacion_prueba 1 = nadie vota, 2 = todos votan el mapa 1, 3 = solo vota uno, 4 = todos con la tecla F2)
PruebaAutomatica()
{
	wait 20;
	ps = getentarray("player", "classname");
	logPrint("VOTACION;prueba;" + ps.size + "\n");
	if(!ps.size)
		return;
	tipo = "mapa";
	if(getcvar("kit_votacion_tipo") == "modo")
		tipo = "modo";
	level thread PedirVotacion(ps[0], tipo);
	wait 2;
	if(getcvar("kit_votacion_prueba") == "2")
	{
		ps = getentarray("player", "classname");
		for(i = 0; i < ps.size; i++)
			ps[i] VotoEnPartida("1");
	}
	if(getcvar("kit_votacion_prueba") == "3")
		ps[0] VotoEnPartida("1");
	if(getcvar("kit_votacion_prueba") == "4")
		for(i = 0; i < ps.size; i++)
			ps[i] VotoTecla(2);
	// 5 = como llega una tecla de verdad: menuresponse del menu 0 (votarmapa) con kit_v2
	if(getcvar("kit_votacion_prueba") == "5")
		for(i = 0; i < ps.size; i++)
			ps[i] notify("menuresponse", "votarmapa", "kit_v2");
}'''

if __name__ == "__main__":
    main()
