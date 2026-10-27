"""Arma el modo de juego CARRERA DE JEEPS (26-10-2026).

maps/mp/gametypes/carrera.gsc se arma desde el dm.gsc del mod (maestro/MiMod/MiMod_v1.pk3: mismos menus, AWE,
fin de mapa y votacion) mas la logica de la carrera. Sale en carrera_src/ y en el pk3
maestro/MiMod/zzzzzz_kit_carrera.pk3 (va a los jugadores por el launcher Y al servidor que tenga pistas).
Es un pk3 aparte para no cambiar zzzzzz_kit_fixes.pk3 (sv_pure: cambiarlo obliga a reiniciar los dos servidores).
Probar: scratchpad probar_srv.py (servidor aparte en la mini PC, con bots que recorren los controles).
"""
import os, re, zipfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAESTRO = os.path.join(ROOT, 'maestro', 'MiMod')
dm = zipfile.ZipFile(os.path.join(MAESTRO, 'MiMod_v1.pk3')).read('maps/mp/gametypes/dm.gsc').decode('latin1').replace('\r\n', '\n')
dm = '\n'.join(l.rstrip() for l in dm.split('\n'))
t = dm
def limpio(s): return '\n'.join(l.rstrip() for l in s.split('\n'))
def R(a, b, n=1):
    global t
    a = limpio(a); b = limpio(b)
    assert t.count(a) == n, (t.count(a), a[:80]); t = t.replace(a, b)

R('''/*
	Deathmatch
	Objective: 	Score points by eliminating other players''', '''/*
	CARRERA (Mi Comunidad, 26-10-2026): carrera de jeeps a N vueltas, sin disparos.
	Lo arma publicar\\armar_carrera.py desde el dm.gsc del mod (mismos menus, AWE, fin de mapa y votacion).
	El mapa (editor de mapas) trae:
	  script_vehicle  targetname "jeep", script_noteworthy = lugar en la grilla (1, 2, ...)
	  trigger_multiple targetname "carrera_meta"            la linea de salida / meta
	  trigger_multiple targetname "carrera_control", script_noteworthy = 1..N, los controles en orden
	  script_origin   targetname "carrera_reaparece", script_noteworthy = 0 (meta) o 1..N: donde se reaparece
	  level.carrera_vueltas en el gsc del mapa (scr_carrera_vueltas lo cambia si es > 0)
	Cvars: scr_carrera_vueltas 0 | scr_carrera_largada 15 (segundos de espera antes del 3,2,1) |
	       scr_carrera_espera 45 (segundos que tienen los demas despues del ganador) | scr_carrera_timelimit 20
	       scr_carrera_prueba 0 (1 = bots que recorren solos los controles, para probar en un servidor aparte)

	Deathmatch (lo de abajo viene del dm.gsc)
	Objective: 	Score points by eliminating other players''')

# cvars propias
t = t.replace('scr_dm_timelimit', 'scr_carrera_timelimit').replace('scr_dm_scorelimit', 'scr_carrera_scorelimit')
R('''	if(getCvar("scr_carrera_timelimit") == "")		// Time limit per map
		setCvar("scr_carrera_timelimit", "30");''', '''	if(getCvar("scr_carrera_timelimit") == "")		// Time limit per map
		setCvar("scr_carrera_timelimit", "20");''')
R('''	if(getCvar("scr_carrera_scorelimit") == "")		// Score limit per map
		setCvar("scr_carrera_scorelimit", "50");''', '''	if(getCvar("scr_carrera_scorelimit") == "")		// Score limit per map
		setCvar("scr_carrera_scorelimit", "0");''')
R('''	setCvar("scr_killcam", killcam, true);
	level.killcam = getCvarInt("scr_killcam");''', '''	setCvar("scr_killcam", killcam, true);
	level.killcam = 0;	// carrera: sin killcam''')

# AWE: que vea un modo "todos contra todos" (sino lo toma como por equipos)
R('''	maps\\mp\\gametypes\\_awe::Callback_StartGameType();
///////////////////////////////////////
''', '''	setcvar("g_gametype", "dm");
	maps\\mp\\gametypes\\_awe::Callback_StartGameType();
	setcvar("g_gametype", "carrera");
	level.awe_gametype = "carrera";
///////////////////////////////////////
''')
R('''	game["menu_serverinfo"] = "serverinfo_" + getCvar("g_gametype");''', '''	game["menu_serverinfo"] = "serverinfo_dm";	// carrera: el cliente no tiene un serverinfo_carrera (el menu sale del modo)''')
R('''	thread startGame();
//	thread addBotClients(); // For development testing''', '''	thread startGame();
	thread Carrera();
	if(getCvarInt("scr_carrera_prueba") > 0)
		thread PruebaBots();
	if(getCvarInt("scr_carrera_prueba_subir") > 0)
		thread PruebaSubir();
	if(getCvarInt("scr_carrera_prueba_sonido") > 0)
		thread PruebaSonidoAltura();''')

# equipo elegido: se larga sin elegir arma
ini = t.index('				// if there are weapons the user can select then open the weapon menu')
fin = t.index('self menu_spawn("none");', ini)
fin = t.index('}', fin) + 1
t = t[:ini] + '''				// carrera: no se elige arma (se corre sin armas)
				self setClientCvar("ui_weapontab", "0");
				self menu_spawn("none");''' + t[fin:]

# dano: nadie lastima a otro jugador (solo correr)
R('''Callback_PlayerDamage(eInflictor, eAttacker, iDamage, iDFlags, sMeansOfDeath, sWeapon, vPoint, vDir, sHitLoc)
{
	if(self.sessionteam == "spectator")
		return;
''', '''Callback_PlayerDamage(eInflictor, eAttacker, iDamage, iDFlags, sMeansOfDeath, sWeapon, vPoint, vDir, sHitLoc)
{
	if(self.sessionteam == "spectator")
		return;

	// carrera: solo correr. Otro jugador nunca lastima. PERO si el jeep en el que va explota, el juego lo mata
	// (10000 de dano): eso no se frena nunca (vivo adentro de un vehiculo destruido el servidor se cae)
	if(iDamage < 10000 && isPlayer(eAttacker) && eAttacker != self)
		return;
''')

# muerte: sin puntos ni killcam; reaparece solo
R('''	attackerNum = -1;
	if(isPlayer(attacker))
	{
		if(attacker == self) // killed himself
		{
			doKillcam = false;

			attacker.score--;
		}
		else
		{
			attackerNum = attacker getEntityNumber();
			doKillcam = true;

			attacker.score++;
			attacker checkScoreLimit();
		}
''', '''	attackerNum = -1;
	if(isPlayer(attacker))
	{
		doKillcam = false;	// carrera: los puntos son por puesto
''')
R('''		doKillcam = false;

		self.score--;

		lpattacknum = -1;''', '''		doKillcam = false;

		lpattacknum = -1;''')
R('''	// Make the player drop health
	self dropHealth();
''', '''	// carrera: sin botiquines
''')
R('''	delay = 2;	// Delay the player becoming a spectator till after he's done dying''', '''	delay = 1.5;	// Delay the player becoming a spectator till after he's done dying''')

# reaparece solo (sin apretar usar)
ini = t.index('respawn()\n{\n\tself endon("end_respawn");')
fin = t.index('waitForceRespawnTime()\n{')
t = t[:ini] + '''respawn()
{
	self endon("end_respawn");

	// carrera: vuelve solo, en un jeep nuevo en el ultimo control
	wait 0.5;
	self thread spawnPlayer();
}

''' + t[fin:]

# spawnPlayer: a la grilla o al ultimo control, sin armas, sentado en el jeep
R('''	spawnpointname = "mp_deathmatch_spawn";
	spawnpoints = getentarray(spawnpointname, "classname");
	spawnpoint = maps\\mp\\gametypes\\_spawnlogic::getSpawnpoint_DM(spawnpoints);

	if(isDefined(spawnpoint))
		self spawn(spawnpoint.origin, spawnpoint.angles);
	else
		maps\\mp\\_utility::error("NO " + spawnpointname + " SPAWNPOINTS IN MAP");
''', '''	// carrera: el lugar lo da la carrera (grilla de largada o el ultimo control que paso)
	self LugarDeSalida();
	// al costado del jeep, en el piso (encima del jeep el juego lo baja enseguida)
	if(getCvarInt("scr_carrera_prueba_modo") == 1)
		self spawn(self.car_l_origin + (0, 0, 64), self.car_l_angles);
	else
		self spawn(self.car_l_origin + maps\\mp\\_utility::vectorScale(anglesToRight(self.car_l_angles), -70) + (0, 0, 8), self.car_l_angles);
''')
R('''	// setup all the weapons
	self maps\\mp\\gametypes\\_loadout_gmi::PlayerSpawnLoadout();

	self setClientCvar("cg_objectiveText", &"DM_KILL_OTHER_PLAYERS");
''', '''	// carrera: sin armas
''')
R('''	self maps\\mp\\gametypes\\_awe::spawnPlayer();
/////////////////////////////////////////////

}''', '''	self maps\\mp\\gametypes\\_awe::spawnPlayer();
/////////////////////////////////////////////

	self takeAllWeapons();
	self giveWeapon("binoculars_mp");
	self switchToWeapon("binoculars_mp");
	self thread SubirAlJeep();
}''')
t = t.replace('''	self setClientCvar("cg_objectiveText", &"DM_KILL_OTHER_PLAYERS");
}''', '''}''')

# nunca se reubica a alguien que sigue adentro de un vehiculo (tira el servidor)
R('''spawnPlayer()
{
	self notify("spawned");''', '''spawnPlayer()
{
	// carrera: el que llega despues de la largada mira como espectador hasta la proxima carrera
	if(isDefined(level.car_estado) && (level.car_estado == "carrera" || level.car_estado == "fin") && !isDefined(self.car_inscripto))
	{
		self iprintlnbold("^7La carrera ya largo: miras como espectador hasta la proxima");
		self thread spawnSpectator();
		return;
	}
	// carrera: nunca se reubica a alguien que sigue adentro de un vehiculo (tira el servidor)
	if(self isinvehicle())
	{
		self Bajar();
		if(self isinvehicle())
			return;
	}
	self notify("spawned");''')

# la carrera
t += r'''

// =====================================================================================================================
// CARRERA
// =====================================================================================================================

Entero(s)
{
	return EnteroDesde(s, 0);
}

EnteroDesde(s, i0)
{
	if(!isDefined(s))
		return 0;
	n = 0;
	for(i = i0; i < s.size; i++)
	{
		c = s[i];
		d = -1;
		switch(c)
		{
			case "0": d = 0; break;
			case "1": d = 1; break;
			case "2": d = 2; break;
			case "3": d = 3; break;
			case "4": d = 4; break;
			case "5": d = 5; break;
			case "6": d = 6; break;
			case "7": d = 7; break;
			case "8": d = 8; break;
			case "9": d = 9; break;
		}
		if(d < 0)
			break;
		n = n * 10 + d;
	}
	return n;
}

// entidades ordenadas por su script_noteworthy (1, 2, 3...)
Ordenar(a)
{
	for(i = 0; i < a.size; i++)
		for(j = i + 1; j < a.size; j++)
			if(Entero(a[j].script_noteworthy) < Entero(a[i].script_noteworthy))
			{
				x = a[i];
				a[i] = a[j];
				a[j] = x;
			}
	return a;
}

Carrera()
{
	level.car_explota = loadfx("fx/explosions/vehicles/t34_mp_n/1st_exp_v2.efx");
	level.car_mina_fx = loadfx("fx/impacts/newimps/minefield.efx");
	precacheModel("xmodel/minen1");
	if(getCvar("scr_carrera_minas") == "")
		setCvar("scr_carrera_minas", "6");
	if(getCvar("scr_carrera_dano") == "")
		setCvar("scr_carrera_dano", "4");	// % de vida por cada 100 de golpe entre jeeps (un choque fuerte = 500 de golpe = 20%)
	// sin la red de caminos de los bots de la practica (en mapas grandes congelaba el arranque ~20 s; en la carrera no manejan)
	level.bnav_started = true;
	level.car_estado = "espera";
	level.car_llegados = 0;
	level.car_total = getCvarInt("scr_carrera_vueltas");
	if(level.car_total <= 0 && isDefined(level.carrera_vueltas))
		level.car_total = level.carrera_vueltas;
	if(level.car_total <= 0)
		level.car_total = 3;
	if(getCvar("scr_carrera_largada") == "")
		setCvar("scr_carrera_largada", "30");
	if(getCvar("scr_carrera_cuenta") == "")
		setCvar("scr_carrera_cuenta", "5");
	if(getCvar("scr_carrera_espera") == "")
		setCvar("scr_carrera_espera", "45");

	level.car_meta = getent("carrera_meta", "targetname");
	level.car_ctrl = Ordenar(getentarray("carrera_control", "targetname"));
	reap = getentarray("carrera_reaparece", "targetname");
	level.car_reap = [];
	for(i = 0; i < reap.size; i++)
		level.car_reap[Entero(reap[i].script_noteworthy)] = reap[i];

	jeeps = getentarray("script_vehicle", "classname");
	grilla = [];
	for(i = 0; i < jeeps.size; i++)
		if(isDefined(jeeps[i].targetname) && jeeps[i].targetname == "jeep")
			grilla[grilla.size] = jeeps[i];
	level.car_grilla = Ordenar(grilla);
	level.car_grilla_pos = [];
	level.car_grilla_ang = [];
	level.car_grilla_usada = [];
	for(i = 0; i < level.car_grilla.size; i++)
	{
		level.car_grilla_pos[i] = level.car_grilla[i].origin;
		level.car_grilla_ang[i] = level.car_grilla[i].angles;
		level.car_grilla_usada[i] = false;
	}

	if(!isDefined(level.car_meta) || !level.car_grilla.size || !isDefined(level.car_reap[0]))
	{
		level.car_estado = "sin pista";
		logPrint("CARRERA;el mapa no tiene meta, jeeps o lugar de reaparicion\n");
		return;
	}
	level.car_piso = level.car_reap[0].origin[2];
	for(i = 0; i < reap.size; i++)
		if(reap[i].origin[2] < level.car_piso)
			level.car_piso = reap[i].origin[2];
	for(i = 0; i < level.car_grilla_pos.size; i++)
		if(level.car_grilla_pos[i][2] < level.car_piso)
			level.car_piso = level.car_grilla_pos[i][2];
	logPrint("CARRERA;pista: " + level.car_ctrl.size + " controles, " + level.car_grilla.size + " jeeps, " + level.car_total + " vueltas\n");

	wait 2;
	// los jeeps no son de ningun bando (fuera de dm/tdm/hq el script del juego los hace de un bando y el juego baja a
	// los que no son de ese bando: en la carrera nadie tiene bando)
	todos = getentarray("script_vehicle", "classname");
	for(i = 0; i < todos.size; i++)
		todos[i].team = "all";

	setCvar("scr_selfDestructJeepTime", "-1");
	for(i = 0; i < level.car_grilla.size; i++)
		level.car_grilla[i] Esconder();
	thread Hud();
	thread MarcarJeeps();
	thread LimpiarJeeps();

	// grilla: el que entra aparece sentado en un jeep de la largada (el primero adelante, los demas atras), frenado
	while(Corredores().size == 0)
		wait 1;
	level.car_estado = "cuenta";
	for(s = getCvarInt("scr_carrera_largada"); s > 0; s--)
	{
		level.car_cuenta = s;
		if(s <= 3)
			iprintlnbold("^3" + s);
		else if(s % 10 == 0 || s == 5)
			iprintlnbold("^7La carrera larga en ^3" + s + "^7 segundos (" + level.car_total + " vueltas)");
		wait 1;
	}
	// todos aparecen manejando su jeep de la grilla
	ps = Corredores();
	for(i = 0; i < ps.size; i++)
	{
		ps[i].car_largar = true;
		ps[i] thread spawnPlayer();
	}
	wait 0.5;
	barreras = getentarray("carrera_barrera", "targetname");
	for(i = 0; i < barreras.size; i++)
	{
		barreras[i] notsolid();
		barreras[i] delete();
	}
	level.car_inicio = getTime();
	level.car_estado = "carrera";
	thread Minas();
	iprintlnbold("^2YA!");
	logPrint("CARRERA;largada\n");
	ps = Corredores();
	for(i = 0; i < ps.size; i++)
	{
		ps[i].car_inicio = level.car_inicio;
		if(isDefined(ps[i].car_jeep))
			ps[i].car_jeep.car_reservado = undefined;
	}
}

// todos a la grilla sin bajarse: el jeep de cada uno se lleva a su lugar de largada con el adentro; el que no tiene jeep
// recibe uno nuevo. Los jeeps que quedan sin nadie se esconden (borrarlos los hace explotar). Hasta el YA cada jeep queda
// clavado en su lugar (Fijar)
Reagrupar()
{
	ps = Corredores();
	for(k = 0; k < ps.size; k++)
	{
		ps[k] freezeControls(true);
		ps[k] Bajar();
	}
	wait 0.5;
	for(i = 0; i < level.car_grilla_usada.size; i++)
		level.car_grilla_usada[i] = false;
	ps = Corredores();
	for(k = 0; k < ps.size; k++)
	{
		p = ps[k];
		p.car_grilla = undefined;
		p.car_jeep = undefined;
		p thread spawnPlayer();
	}
}

// hasta el YA el jeep no se mueve de su lugar de largada
// hasta el YA el jeep no se mueve de su lugar de largada
FijarHastaLargada(j, pos, ang)
{
	while(isDefined(j) && !isDefined(j.car_muerto) && isDefined(level.car_estado) && (level.car_estado == "cuenta" || level.car_estado == "espera"))
	{
		// cada cuadro en su lugar, apenas levantado: sin traccion no avanza ni retrocede (paredes no: el juego destruye
		// el jeep trabado contra una pared, MOD_CRUSH_JEEP)
		j.origin = pos + (0, 0, 1);
		j.angles = ang;
		wait 0.05;
	}
}

// cada segundo: los jeeps vacios sin nadie a menos de 400 se esconden (abandonados, los que repone el juego, el que
// quedo cuando alguien volvio a la pista)
LimpiarJeeps()
{
	for(;;)
	{
		wait 1;
		js = getentarray("script_vehicle", "classname");
		ps = getentarray("player", "classname");
		for(i = 0; i < js.size; i++)
		{
			j = js[i];
			if(!isDefined(j.vehicletype) || isDefined(j.car_oculto) || !Vacio(j) || (isDefined(j.car_reservado) && getTime() < j.car_reservado))
				continue;
			cerca = false;
			for(k = 0; k < ps.size; k++)
				if(ps[k].sessionstate == "playing" && distance(ps[k].origin, j.origin) < 400)
					cerca = true;
			if(!cerca)
				j Esconder();
		}
	}
}

// cada jeep (tambien los que repone el juego) avisa cuando explota
MarcarJeeps()
{
	for(;;)
	{
		js = getentarray("script_vehicle", "classname");
		for(i = 0; i < js.size; i++)
			if(!isDefined(js[i].car_mirado))
			{
				js[i].car_mirado = true;
				js[i] thread MarcarMuerte();
				js[i] thread Irrompible();
				js[i] thread DanoChoques();
			}
		wait 0.25;
	}
}

// choques entre jeeps: el jeep va perdiendo vida (golpes con otro jeep cerca; las paredes no cuentan). Sin vida explota
// y el que maneja vuelve al ultimo control en otro jeep (cuenta como muerte)
DanoChoques()
{
	self endon("death");
	if(!isDefined(self.car_vida))
		self.car_vida = 100;
	for(;;)
	{
		self waittill("damage", cant);
		if(!isDefined(level.car_estado) || level.car_estado != "carrera" || isDefined(self.car_oculto))
			continue;
		otro = false;
		js = getentarray("script_vehicle", "classname");
		for(i = 0; i < js.size; i++)
			if(js[i] != self && !isDefined(js[i].car_oculto) && distance(js[i].origin, self.origin) < 260)
				otro = true;
		if(!otro)
			continue;
		perdida = (int)(cant * getCvarInt("scr_carrera_dano") / 100);
		if(perdida < 1)
			perdida = 1;
		self.car_vida -= perdida;
		if(self.car_vida > 0)
			continue;
		self.car_vida = 100;
		pl = self.driver;
		playfx(level.car_explota, self.origin);
		earthquake(0.5, 1, self.origin, 600);
		if(isDefined(pl) && isPlayer(pl))
		{
			pl iprintlnbold("^1Tu jeep se rompio de tanto chocar: ^7volves al ultimo control");
			logPrint("CARRERA;" + pl.name + " jeep roto por choques\n");
			pl.deaths++;
			pl Bajar();
			pl thread spawnPlayer();
		}
	}
}

// solo correr: los jeeps no se rompen chocando (se les repone la vida)
Irrompible()
{
	self endon("death");
	for(;;)
	{
		// vida infinita, repuesta cada cuadro: un choque fuerte o apretarse contra la pared de la grilla (el juego lo
		// "aplasta", MOD_CRUSH_JEEP) lo hacia explotar
		if(getCvar("scr_carrera_vida") != "")
			v = getCvarInt("scr_carrera_vida");
		else
			v = 2900;
		if(self.health < v)
			self.health = v;
		wait 0.05;
	}
}

MarcarMuerte()
{
	self waittill("death");
	self.car_muerto = true;
}

Corredores()
{
	r = [];
	ps = getentarray("player", "classname");
	for(i = 0; i < ps.size; i++)
		if(isDefined(ps[i].pers["team"]) && ps[i].pers["team"] != "spectator"
			&& (ps[i].sessionstate == "playing" || (isDefined(ps[i].car_inscripto) && (ps[i].sessionstate == "intermission" || ps[i].sessionstate == "spectator"))))
			r[r.size] = ps[i];
	return r;
}

// donde sale el jugador (car_l_origin, car_l_angles, car_l_grilla): antes de la largada, su lugar en la grilla;
// despues, el ultimo control que paso
LugarDeSalida()
{
	if(!isDefined(level.car_estado) || level.car_estado == "sin pista")
	{
		sp = maps\mp\gametypes\_spawnlogic::getSpawnpoint_DM(getentarray("mp_deathmatch_spawn", "classname"));
		self.car_l_origin = sp.origin;
		self.car_l_angles = sp.angles;
		self.car_l_grilla = -1;
		return;
	}
	if(!isDefined(self.car_vuelta) || level.car_estado != "carrera")
	{
		// datos nuevos de carrera
		self.car_vuelta = 0;
		self.car_sig = 1;
		if(!level.car_ctrl.size)
			self.car_sig = 0;
		self.car_ultimo = 0;
		self.car_enmeta = false;
		self.car_llego = undefined;
		self.car_inicio = getTime();
		if(isDefined(level.car_inicio) && level.car_estado == "carrera")
			self.car_inicio = level.car_inicio;
	}
	// se cayo del mapa: un poco antes del ultimo lugar firme (en la cuenta, a la grilla)
	if(isDefined(self.car_caida) && self.car_caida)
	{
		self.car_caida = false;
		if(level.car_estado != "cuenta" && isDefined(self.car_hist) && self.car_hist.size)
		{
			k = self.car_hist.size - 4;
			if(k < 0)
				k = 0;
			self.car_l_origin = self.car_hist[k];
			self.car_l_angles = self.car_hist_ang[k];
			self.car_l_grilla = -1;
			self.car_hist = undefined;
			self.car_hist_ang = undefined;
			self.car_seg_z = undefined;
			return;
		}
	}
	if(level.car_estado != "carrera" && level.car_estado != "fin")
	{
		// un lugar libre de la grilla
		if(!isDefined(self.car_grilla))
		{
			for(i = 0; i < level.car_grilla_usada.size; i++)
				if(!level.car_grilla_usada[i])
				{
					level.car_grilla_usada[i] = true;
					self.car_grilla = i;
					break;
				}
		}
		if(isDefined(self.car_grilla))
		{
			self.car_l_origin = level.car_grilla_pos[self.car_grilla];
			self.car_l_angles = level.car_grilla_ang[self.car_grilla];
			self.car_l_grilla = self.car_grilla;
			return;
		}
	}
	r = level.car_reap[self.car_ultimo];
	if(!isDefined(r))
		r = level.car_reap[0];
	self.car_l_origin = r.origin;
	self.car_l_angles = r.angles;
	self.car_l_grilla = -1;
}

// un jeep nuevo en ese lugar (si esta ocupado, al costado)
// un jeep vacio del mapa llevado a ese lugar (no se crean ni se borran jeeps: copiarlos o borrar uno ocupado tira el
// servidor). Se mueve como lo hace el juego al reponer un jeep: se saca del mundo, se ubica y se vuelve a poner
NuevoJeep(pos, ang)
{
	for(;;)
	{
		j = JeepLibre(pos);
		if(isDefined(j))
			break;
		wait 0.5;
	}
	j.car_reservado = getTime() + 4000;
	der = anglesToRight(ang);
	desv = [];
	desv[0] = 0; desv[1] = 110; desv[2] = -110;
	j unlinkfromworld();
	ok = false;
	for(k = 0; k < desv.size && !ok; k++)
	{
		p = pos + (der[0] * desv[k], der[1] * desv[k], 16);
		tr = bulletTrace(p + (0, 0, 8), p - (0, 0, 200), false, j);
		if(tr["fraction"] >= 1)
			continue;	// sin piso abajo (afuera de la pista)
		j.origin = p;
		j.angles = ang;
		if(j verifyposition(1))
			ok = true;
	}
	if(!ok)
	{
		j.origin = pos + (0, 0, 48);
		j.angles = ang;
	}
	wait 0.2;
	j clearvehicleposition();
	j linkintoworld();
	j.team = "all";
	j.car_oculto = undefined;
	j.car_vida = 100;
	j startEngineSound();
	return j;
}

// un jeep sin nadie adentro y sin reservar (el mas lejos de los jugadores, para no sacarle el jeep a nadie de al lado)
JeepLibre(pos)
{
	js = getentarray("script_vehicle", "classname");
	ps = getentarray("player", "classname");
	mejor = undefined;
	lejos = -1;
	for(i = 0; i < js.size; i++)
	{
		j = js[i];
		if(!isDefined(j.vehicletype) || !Vacio(j) || (isDefined(j.car_reservado) && getTime() < j.car_reservado))
			continue;
		if(isDefined(j.waiting_for_respawn) && j.waiting_for_respawn)
			continue;
		// el que esta en un lugar de largada ocupado es de ese corredor
		suyo = false;
		for(g = 0; g < level.car_grilla_pos.size; g++)
			if(level.car_grilla_usada[g] && distance(j.origin, level.car_grilla_pos[g]) < 32)
				suyo = true;
		if(suyo && level.car_estado != "carrera")
			continue;
		d = 1000000;
		for(k = 0; k < ps.size; k++)
		{
			dd = distance(ps[k].origin, j.origin);
			if(dd < d)
				d = dd;
		}
		// nadie cerca: si alguien se esta subiendo (el juego lo anota 0,1 s tarde) y el jeep se mueve, el servidor se cae
		// (ClientThink_real: "aborting player positioning on turret")
		if(d < 300)
			continue;
		if(d > lejos)
		{
			lejos = d;
			mejor = j;
		}
	}
	return mejor;
}

// sienta al jugador en su jeep (el de su lugar en la grilla o uno nuevo)
SubirAlJeep()
{
	self endon("spawned");
	self endon("disconnect");
	if(!isDefined(level.car_estado) || level.car_estado == "sin pista")
		return;
	self freezeControls(false);
	wait 0.1;
	// el jeep anterior, si quedo vacio, se saca
	if(isDefined(self.car_jeep))
		self thread SacarJeep(self.car_jeep);
	j = undefined;
	g = self.car_l_grilla;
	if(g >= 0 && isDefined(level.car_grilla[g]) && Vacio(level.car_grilla[g]) && distance(level.car_grilla[g].origin, self.car_l_origin) < 32)
	{
		j = level.car_grilla[g];
		if(isDefined(j.car_oculto))
			j Mostrar(self.car_l_origin, self.car_l_angles);
	}
	if(!isDefined(j))
		j = NuevoJeep(self.car_l_origin, self.car_l_angles);
	if(g >= 0)
		level.car_grilla[g] = j;
	self.car_jeep = j;
	if(!isDefined(self.car_vigila))
	{
		self.car_vigila = true;
		self thread Vigilar();
	}
	if((level.car_estado == "cuenta" || level.car_estado == "espera") && !isDefined(self.car_largar))
	{
		// espera: su jeep queda en su lugar de la grilla y el mira la largada desde la camara (nadie maneja antes del YA)
		self.car_inscripto = true;
		j.car_reservado = getTime() + 600000;
		self thread MirarLargada();
		return;
	}
	self.car_largar = undefined;
	self Subir();
}

Subir()
{
	self endon("spawned");
	self endon("disconnect");
	j = self.car_jeep;
	if(!isDefined(j))
		return;
	// (usar el jeep otra vez lo baja: se espera bien antes de reintentar)
	for(intento = 0; intento < 3; intento++)
	{
		if(self isinvehicle())
			break;
		if(getCvarInt("scr_carrera_prueba_modo") == 1)
			self setOrigin(j.origin + (0, 0, 64));
		j useby(self);
		for(w = 0; w < 20 && !(self isinvehicle()); w++)
			wait 0.05;
		if(self isinvehicle())
			break;
		wait 0.5;
	}
	self.car_desde = getTime() + 1000;
	self.car_seg_z = undefined;
	if((self isinvehicle()) && isDefined(j))
		j startEngineSound();
	logPrint("CARRERA;" + self.name + " en jeep: " + (self isinvehicle()) + "\n");
	if(getCvarInt("scr_carrera_prueba") > 0)
		self thread PruebaSeguir();
}

SacarJeep(j)
{
	wait 1;
	if(isDefined(j) && !isDefined(j.car_oculto))
		j Esconder();
}

// espera de la largada: mira la grilla desde la camara del mapa, quieto (espectador congelado: sin tabla de puntajes)
MirarLargada()
{
	self endon("disconnect");
	cams = getentarray("mp_deathmatch_intermission", "classname");
	if(cams.size)
		self spawnSpectator(cams[0].origin, cams[0].angles);
	else
		self spawnSpectator();
	self freezeControls(true);
}

// ---- minas: van apareciendo al azar sobre el camino (entre un control y el siguiente); pisar una = explota y se
// vuelve al ultimo control en otro jeep. Cada una dura 45 s. scr_carrera_minas = cuantas a la vez (0 = sin minas)
Minas()
{
	wait 5;
	level.car_minas = [];
	while(level.car_estado == "carrera")
	{
		vivas = [];
		for(i = 0; i < level.car_minas.size; i++)
			if(isDefined(level.car_minas[i]))
				vivas[vivas.size] = level.car_minas[i];
		level.car_minas = vivas;
		if(level.car_minas.size < getCvarInt("scr_carrera_minas"))
			PonerMina();
		wait 3;
	}
	for(i = 0; i < level.car_minas.size; i++)
		if(isDefined(level.car_minas[i]))
			level.car_minas[i] delete();
}

PonerMina()
{
	// sobre el camino de verdad: cerca de un lugar por donde ya paso un jeep (lo anota Vigilar)
	if(!isDefined(level.car_camino) || level.car_camino.size < 20)
		return;
	p = level.car_camino[randomInt(level.car_camino.size)] + (randomFloat(160) - 80, randomFloat(160) - 80, 0);
	tr = bulletTrace(p + (0, 0, 100), p - (0, 0, 300), false, undefined);
	if(tr["fraction"] >= 1 || isDefined(tr["entity"]))
		return;	// sin piso, o cae arriba de un jeep
	p = tr["position"];
	// nunca debajo de alguien
	ps = Corredores();
	for(i = 0; i < ps.size; i++)
		if(distance(ps[i].origin, p) < 400)
			return;
	m = spawn("script_model", p);
	m setModel("xmodel/minen1");
	m.angles = (0, randomInt(360), 0);
	m.car_hasta = getTime() + 45000;
	level.car_minas[level.car_minas.size] = m;
	m thread MinaVigilar();
	if(getCvarInt("scr_carrera_prueba") > 0)
		logPrint("CARRERA;mina en " + (int)p[0] + " " + (int)p[1] + " " + (int)p[2] + "\n");
}

MinaVigilar()
{
	while(isDefined(self) && level.car_estado == "carrera" && getTime() < self.car_hasta)
	{
		ps = Corredores();
		for(i = 0; i < ps.size; i++)
		{
			pl = ps[i];
			if(pl.sessionstate != "playing" || isDefined(pl.car_llego))
				continue;
			ent = pl;
			mj = pl MiJeep();
			if(isDefined(mj))
				ent = mj;
			dx = ent.origin[0] - self.origin[0];
			dy = ent.origin[1] - self.origin[1];
			dz = ent.origin[2] - self.origin[2];
			if(dx * dx + dy * dy < 75 * 75 && dz < 100 && dz > -60)
			{
				self Explotar(pl);
				return;
			}
		}
		wait 0.05;
	}
	if(isDefined(self))
		self delete();
}

Explotar(pl)
{
	o = self.origin;
	playfx(level.car_mina_fx, o);
	playfx(level.car_explota, o);
	earthquake(0.6, 1.2, o, 800);
	s = spawn("script_model", o);	// (un script_origin no suena en este juego)
	s playsound("explo_mine");
	s thread BorrarEn(4);
	self delete();
	pl iprintlnbold("^1Pisaste una mina! ^7Volves al ultimo control");
	logPrint("CARRERA;" + pl.name + " piso una mina\n");
	pl Bajar();
	pl thread spawnPlayer();
}

BorrarEn(seg)
{
	wait seg;
	self delete();
}

// un jeep vacio sale del mundo (no se ve ni estorba); vuelve cuando alguien lo necesita (NuevoJeep / Mostrar)
Esconder()
{
	if(!Vacio(self))
		return;
	ps = getentarray("player", "classname");
	for(i = 0; i < ps.size; i++)
		if(distance(ps[i].origin, self.origin) < 150)
			return;
	self unlinkfromworld();
	self.car_oculto = true;
}

// un jeep escondido vuelve al mundo en ese lugar
Mostrar(pos, ang)
{
	self.car_reservado = getTime() + 4000;
	self unlinkfromworld();
	self.origin = pos + (0, 0, 16);
	self.angles = ang;
	wait 0.2;
	self clearvehicleposition();
	self linkintoworld();
	self.team = "all";
	self.car_oculto = undefined;
	self.car_vida = 100;
	self startEngineSound();
}

// lo baja del vehiculo en el que este (manejando o de acompaniante) antes de moverlo a otro lado
Bajar()
{
	if(!(self isinvehicle()))
		return;
	js = getentarray("script_vehicle", "classname");
	for(i = 0; i < js.size; i++)
		if((isDefined(js[i].driver) && js[i].driver == self) || (isDefined(js[i].gunner) && js[i].gunner == self))
		{
			js[i] useby(self);
			break;
		}
	wait 0.3;
}

// nadie adentro: ni manejando ni de acompaniante (borrar un vehiculo ocupado tira el servidor). Y vivo y listo: un jeep
// que exploto sigue unos segundos hasta que el juego lo borra, y la copia que prepara el juego para reponerlo todavia no
// esta armada (riding_count sin definir). Si se sienta a alguien en uno de esos, al borrarse el servidor se cae
// (ClientThink_real: el jugador queda "adentro" de un vehiculo que ya no existe)
Vacio(j)
{
	if(!isDefined(j) || isDefined(j.driver) || isDefined(j.gunner))
		return false;
	if(isDefined(j.car_muerto) || !isDefined(j.riding_count))
		return false;
	if(isDefined(j.waiting_for_respawn) && j.waiting_for_respawn)
		return false;
	if(isDefined(j.riding_count) && j.riding_count > 0)
		return false;
	return true;
}

// adentro de un vehiculo el jugador "toca" cualquier disparador, y un jeep recien puesto tambien (sumaba todos los
// controles de golpe): se mira el jeep, y ademas tiene que estar cerca de la franja (radio en "target" del punto de
// reaparicion de esa franja, lo escribe el editor: "r300")
// el jeep en el que va manejando (en el calentamiento se puede subir a cualquiera)
MiJeep()
{
	if(!(self isinvehicle()))
		return undefined;
	if(isDefined(self.car_jeep) && isDefined(self.car_jeep.driver) && self.car_jeep.driver == self)
		return self.car_jeep;
	js = getentarray("script_vehicle", "classname");
	for(i = 0; i < js.size; i++)
		if(isDefined(js[i].driver) && js[i].driver == self)
		{
			self.car_jeep = js[i];
			return js[i];
		}
	return undefined;	// va de acompaniante: no maneja
}

Toca(trig, num)
{
	if(isDefined(self.car_desde) && getTime() < self.car_desde)
		return false;
	ent = self;
	if(self isinvehicle())
	{
		ent = self MiJeep();
		if(!isDefined(ent))
			return false;
	}
	r = level.car_reap[num];
	if(isDefined(r) && isDefined(r.target) && r.target.size > 1 && r.target[0] == "r")
	{
		radio = EnteroDesde(r.target, 1) + 150;
		d = ent.origin - r.origin;
		if(d[0] * d[0] + d[1] * d[1] > radio * radio)
			return false;
		// pistas de 2 pisos: el control de abajo no cuenta pasando por arriba (y al reves)
		if(d[2] * d[2] > 250 * 250)
			return false;
		// sentido unico: cruzando la franja para el lado que se corre (de contramano no cuenta)
		if(isDefined(r.angles) && vectordot(anglestoforward((0, r.angles[1], 0)), anglestoforward((0, ent.angles[1], 0))) < 0)
			return false;
	}
	return ent istouching(trig);
}

// controles en orden y vueltas; si se baja del jeep (o queda trabado), vuelve al ultimo control en un jeep nuevo
Vigilar()
{
	self endon("disconnect");
	afuera = 0;
	aviso = 0;
	pisada = 0;
	aire = 0;
	for(;;)
	{
		wait 0.05;
		// el ultimo lugar donde piso (cada medio segundo, con algo firme abajo): ahi vuelve si se cae
		pisada++;
		if(pisada >= 10 && self.sessionstate == "playing")
		{
			pisada = 0;
			ent = self;
			mio = self MiJeep();
			if(isDefined(mio))
				ent = mio;
			tr = bulletTrace(ent.origin + (0, 0, 2), ent.origin - (0, 0, 40), false, ent);
			if(tr["fraction"] < 1 && (!isDefined(level.car_piso) || ent.origin[2] > level.car_piso - 200))
			{
				// los ultimos lugares firmes (cada medio segundo): al caerse vuelve a uno de hace ~1,5 s, lejos del borde
				if(!isDefined(self.car_hist))
					self.car_hist = [];
				if(self.car_hist.size >= 8)
				{
					for(h = 0; h < 7; h++)
					{
						self.car_hist[h] = self.car_hist[h + 1];
						self.car_hist_ang[h] = self.car_hist_ang[h + 1];
					}
					self.car_hist[7] = undefined;
					self.car_hist_ang[7] = undefined;
				}
				self.car_hist[self.car_hist.size] = ent.origin;
				// lugares del camino (para las minas): solo en carrera, manejando
				if(level.car_estado == "carrera" && isDefined(mio))
				{
					if(!isDefined(level.car_camino))
						level.car_camino = [];
					if(level.car_camino.size < 600)
						level.car_camino[level.car_camino.size] = ent.origin;
					else
						level.car_camino[randomInt(600)] = ent.origin;
				}
				if(!isDefined(self.car_hist_ang))
					self.car_hist_ang = [];
				self.car_hist_ang[self.car_hist.size - 1] = (0, ent.angles[1], 0);
				self.car_seg_z = ent.origin[2];
			}
		}
		// se cayo del mapa (3 metros abajo del ultimo lugar firme, o debajo de toda la pista): cuenta como una muerte y
		// vuelve enseguida en un jeep un poco antes del ultimo lugar firme
		// en el aire: sin piso abajo (un salto de una rampa no es caida: tiene que estar 0,8 s en el aire y 2 m abajo)
		aire += 0.05;
		if(self.sessionstate == "playing")
		{
			ea = self;
			mj = self MiJeep();
			if(isDefined(mj))
				ea = mj;
			tra = bulletTrace(ea.origin + (0, 0, 2), ea.origin - (0, 0, 60), false, ea);
			if(tra["fraction"] < 1)
				aire = 0;
		}
		else
			aire = 0;
		if(self.sessionstate == "playing" && isDefined(level.car_estado) && level.car_estado == "carrera"
			&& ((aire >= 0.4 && isDefined(self.car_seg_z) && self.origin[2] < self.car_seg_z - 120) || aire >= 1.5
			|| (isDefined(level.car_piso) && self.origin[2] < level.car_piso - 200)))
		{
			aire = 0;
			self.car_caida = true;
			self.deaths++;
			playfx(level.car_explota, self.origin);
			self iprintlnbold("^7Te caiste: volves a la pista");
			self thread spawnPlayer();
			wait 1;
			continue;
		}
		// en la grilla (cuenta): si se bajo, de vuelta a su jeep
		if(self.sessionstate == "playing" && isDefined(level.car_estado) && level.car_estado == "cuenta" && !(self isinvehicle())
			&& isDefined(self.car_jeep) && Vacio(self.car_jeep))
		{
			self.car_jeep useby(self);
			wait 0.5;
			continue;
		}
		if(self.sessionstate != "playing" || !isDefined(level.car_estado) || level.car_estado != "carrera" || !isDefined(self.car_vuelta))
		{
			afuera = 0;
			continue;
		}
		if(isDefined(self.car_llego))
			continue;
		// sin manejar mas de 2,5 s (se bajo, o va de acompaniante): a otro jeep en el ultimo control
		if(!isDefined(self MiJeep()))
		{
			afuera += 0.05;
			if(afuera > 2.5 && getCvar("scr_carrera_vigilar") != "0")
			{
				afuera = 0;
				self iprintlnbold("^7Volves al ultimo control");
				self Bajar();
				self thread spawnPlayer();
			}
		}
		else
			afuera = 0;
		if(isDefined(self.car_llego))
			continue;
		// la meta: cuenta al entrar
		enmeta = self Toca(level.car_meta, 0);
		if(enmeta && !self.car_enmeta)
		{
			if(self.car_sig == 0)
			{
				self.car_vuelta++;
				self.car_ultimo = 0;
				logPrint("CARRERA;" + self.name + " vuelta " + self.car_vuelta + "\n");
				if(self.car_vuelta >= level.car_total)
					self Llegar();
				else
				{
					self iprintlnbold("^7Vuelta ^3" + (self.car_vuelta + 1) + "^7 de " + level.car_total);
					if(level.car_ctrl.size)
						self.car_sig = 1;
				}
			}
			else if(self.car_sig > 1 && getTime() > aviso)
			{
				aviso = getTime() + 3000;
				self iprintlnbold("^1Te falta el control " + self.car_sig);
			}
		}
		self.car_enmeta = enmeta;
		// el control que sigue
		if(self.car_sig > 0 && self Toca(level.car_ctrl[self.car_sig - 1], self.car_sig))
		{
			self.car_ultimo = self.car_sig;
			logPrint("CARRERA;" + self.name + " control " + self.car_sig + "\n");
			self.car_sig++;
			if(self.car_sig > level.car_ctrl.size)
				self.car_sig = 0;
		}
	}
}

Tiempo(ms)
{
	d = (int)(ms / 100);
	s = (int)(d / 10);
	d = d % 10;
	m = (int)(s / 60);
	s = s % 60;
	if(s < 10)
		return m + ":0" + s + "." + d;
	return m + ":" + s + "." + d;
}

Llegar()
{
	level.car_llegados++;
	self.car_llego = level.car_llegados;
	self.car_tiempo = getTime() - self.car_inicio;
	self.score = 20 - self.car_llego;
	if(self.score < 1)
		self.score = 1;
	iprintln(self.name + "^7 llego en el puesto ^3" + self.car_llego + "^7 (" + Tiempo(self.car_tiempo) + ")");
	self iprintlnbold("^7Llegaste en el puesto ^3" + self.car_llego + "^7 - " + Tiempo(self.car_tiempo));
	logPrint("CARRERA;" + self.name + " llego " + self.car_llego + " " + Tiempo(self.car_tiempo) + "\n");
	if(self.car_llego == 1)
		level thread FinCarrera(self);
}

FinCarrera(ganador)
{
	iprintlnbold("^3" + ganador.name + "^7 gano la carrera!");
	espera = getCvarInt("scr_carrera_espera");
	for(t = espera; t > 0; t--)
	{
		faltan = 0;
		ps = Corredores();
		for(i = 0; i < ps.size; i++)
			if(!isDefined(ps[i].car_llego))
				faltan++;
		if(!faltan)
			break;
		if(t == 30 || t == 15 || t == 10 || t <= 5)
			iprintln("^7La carrera termina en ^3" + t + "^7 segundos");
		wait 1;
	}
	level.car_estado = "fin";
	wait 3;
	if(level.mapended)
		return;
	level.mapended = true;
	level thread endMap();
}

// cuanto avanzo (para los puestos): vueltas, controles y distancia al que sigue
Progreso()
{
	if(isDefined(self.car_llego))
		return 1000000 - self.car_llego;
	if(!isDefined(self.car_vuelta))
		return 0;
	n = level.car_ctrl.size + 1;
	pasados = self.car_sig - 1;
	if(self.car_sig == 0)
		pasados = level.car_ctrl.size;
	sig = level.car_reap[self.car_sig];
	f = 0;
	if(isDefined(sig))
	{
		f = 1 - distance(self.origin, sig.origin) / 100000;
		if(f < 0)
			f = 0;
	}
	return self.car_vuelta * n + pasados + f;
}

// arriba a la izquierda (los textos que muestra ui_mp/hud_votar.menu): vuelta, puesto y tiempo
Hud()
{
	for(;;)
	{
		ps = Corredores();
		// puestos
		for(i = 0; i < ps.size; i++)
			ps[i].car_prog = ps[i] Progreso();
		for(i = 0; i < ps.size; i++)
			for(j = i + 1; j < ps.size; j++)
				if(ps[j].car_prog > ps[i].car_prog)
				{
					x = ps[i];
					ps[i] = ps[j];
					ps[j] = x;
				}
		for(i = 0; i < ps.size; i++)
		{
			p = ps[i];
			if(level.car_estado == "espera" && isDefined(level.car_cuenta))
				a = "^7Calentamiento: en ^3" + level.car_cuenta + "^7 s todos a la linea de salida (" + level.car_total + " vueltas)";
			else if(level.car_estado == "espera")
				a = "^7Carrera a ^3" + level.car_total + "^7 vueltas: esperando corredores";
			else if(level.car_estado == "cuenta")
				a = "^7Carrera a ^3" + level.car_total + "^7 vueltas: larga en ^3" + level.car_cuenta + "^7 s. Al YA apareces manejando tu jeep";
			else if(isDefined(p.car_llego))
				a = "^7Llegaste en el puesto ^3" + p.car_llego + "^7 de " + ps.size + "   Tiempo ^3" + Tiempo(p.car_tiempo);
			else
			{
				v = p.car_vuelta + 1;
				if(v > level.car_total)
					v = level.car_total;
				a = "^7Vuelta ^3" + v + "/" + level.car_total + "^7   Puesto ^3" + (i + 1) + "/" + ps.size + "^7   Tiempo ^3" + Tiempo(getTime() - p.car_inicio);
			}
			b = "";
			if(level.car_estado == "carrera" && !isDefined(p.car_llego) && isDefined(p.car_sig))
			{
				if(p.car_sig == 0)
					b = "^7Ahora: ^3la meta";
				else
					b = "^7Ahora: ^3control " + p.car_sig + "^7 de " + level.car_ctrl.size;
				mj = p MiJeep();
				if(isDefined(mj))
					b = "^7Velocidad ^3" + (int)(mj getspeedmph() * 1.609) + "^7 km/h   " + b;
				if(isDefined(mj) && isDefined(mj.car_vida))
					b = b + "^7   Jeep ^3" + mj.car_vida + "%";
			}
			if(!isDefined(p.car_hud_a) || p.car_hud_a != a)
			{
				p.car_hud_a = a;
				p setClientCvar("ui_kit_partida", a);
			}
			if(!isDefined(p.car_hud_b) || p.car_hud_b != b)
			{
				p.car_hud_b = b;
				p setClientCvar("ui_kit_top", b);
			}
		}
		wait 0.25;
	}
}

PruebaSeguir()
{
	self endon("disconnect");
	self endon("spawned");
	if(isDefined(self.car_jeep))
		self.car_jeep thread PruebaBajada(self);
	for(k = 0; k < 4; k++)
	{
		wait 0.5;
		logPrint("CARRERA;botones " + self.name + " usar " + self useButtonPressed() + " ataque " + self attackButtonPressed() + " melee " + self meleeButtonPressed() + "\n");
		logPrint("CARRERA;seguir " + self.name + " t" + k + " estado " + level.car_estado + " en jeep " + (self isinvehicle()) + " vivo " + isAlive(self) + " ses " + self.sessionstate + "\n");
	}
}

PruebaBajada(p)
{
	self waittill("deactivated", quien);
	logPrint("CARRERA;jeep deactivated por " + quien.name + " (de " + p.name + ") t=" + getTime() + "\n");
}

// ---- prueba sin gente (servidor aparte): bots que se suben solos y recorren los controles saltando de uno a otro
PruebaBots()
{
	if(getCvarInt("scr_carrera_prueba_acomp") > 0)
		thread PruebaAcompaniante();
	thread PruebaAlturas();
	wait 3;
	for(i = 0; i < getCvarInt("scr_carrera_prueba"); i++)
	{
		b = addtestclient();
		wait 0.5;
		if(isPlayer(b))
		{
			b notify("menuresponse", game["menu_team"], "allies");
			b thread PruebaManejar();
		}
	}
}

// prueba de sonido: alterna un motor sonando a ras del piso (donde esta el jeep) y 60 mas arriba, cada 3 s
PruebaSonidoAltura()
{
	for(;;)
	{
		wait 1;
		ps = getentarray("player", "classname");
		if(ps.size && ps[0].sessionstate == "playing")
			break;
	}
	wait 3;
	o = spawn("script_model", ps[0].origin + (0, 0, 60));
	al = [];
	al[0] = "jeep_idle_high"; al[1] = "sherman_idle_high"; al[2] = "tank_hotwire"; al[3] = "jeep_engine_high"; al[4] = "explo_mine"; al[5] = "bt_motor_3"; al[6] = "jugador_explo_mine"; al[7] = "jugador_bt_motor_3";
	for(;;)
		for(k = 0; k < al.size; k++)
		{
			o.origin = ps[0].origin + (0, 0, 60);
			if(al[k] == "explo_mine" || al[k] == "bt_motor_3")
				o playsound(al[k]);
			else if(al[k] == "jugador_explo_mine")
				ps[0] playsound("explo_mine");
			else if(al[k] == "jugador_bt_motor_3")
			{
				for(r = 0; r < 7; r++)
				{
					ps[0] playsound("bt_motor_3");
					wait 0.4;
				}
			}
			else
				o playloopsound(al[k]);
			logPrint("CARRERA;prueba sonido " + al[k] + " " + ps[0].sessionstate + " " + (ps[0] isinvehicle()) + "\n");
			wait 3;
			o stoploopsound();
			wait 1;
		}
}

// prueba de sonido: sube a cada jugador (a pie) al jeep mas cercano
PruebaSubir()
{
	for(;;)
	{
		wait 0.5;
		ps = getentarray("player", "classname");
		js = getentarray("script_vehicle", "classname");
		for(i = 0; i < ps.size; i++)
		{
			if(!isDefined(ps[i].pers["team"]) || ps[i].pers["team"] == "spectator")
			{
				ps[i] closeMenu();
				ps[i] notify("menuresponse", game["menu_team"], "allies");
			}
			ps[i] closeMenu();
			if(ps[i].sessionstate != "playing" || (ps[i] isinvehicle()) || getCvarInt("scr_carrera_prueba_subir") != 1)
				continue;
			mejor = undefined;
			for(k = 0; k < js.size; k++)
				if(Vacio(js[k]) && !isDefined(js[k].car_oculto) && (!isDefined(mejor) || distance(js[k].origin, ps[i].origin) < distance(mejor.origin, ps[i].origin)))
					mejor = js[k];
			if(!isDefined(mejor))
				continue;
			ps[i] setOrigin(mejor.origin + (0, 0, 90));
			wait 0.2;
			mejor useby(ps[i]);
			logPrint("CARRERA;prueba subir " + ps[i].name + " en jeep " + (ps[i] isinvehicle()) + " z " + mejor.origin[2] + "\n");
		}
	}
}

PruebaAcompaniante()
{
	wait 8;
	ps = getentarray("player", "classname");
	if(ps.size < 2)
		return;
	j = undefined;
	for(k = 0; k < 100 && !isDefined(j); k++)
	{
		j = ps[0] MiJeep();
		if(!isDefined(j))
		{
			ps[0] thread Subir();
			wait 0.2;
		}
	}
	logPrint("CARRERA;acomp: " + ps[1].name + " al jeep de " + ps[0].name + " (hay jeep " + isDefined(j) + ")\n");
	if(!isDefined(j))
		return;
	ps[1] Bajar();
	ps[1] setOrigin(j.origin + (0, 0, 80));
	wait 0.2;
	j useby(ps[1]);
	wait 0.5;
	logPrint("CARRERA;acomp: en vehiculo " + (ps[1] isinvehicle()) + " gunner " + isDefined(j.gunner) + "\n");
}

PruebaAlturas()
{
	for(k = 0; k < 12; k++)
	{
		j = getentarray("script_vehicle", "classname");
		s = "";
		for(i = 0; i < j.size; i++)
			s = s + " " + (int)j[i].origin[2];
		logPrint("CARRERA;alturas" + s + "\n");
		wait 2;
	}
}

PruebaManejar()
{
	self endon("disconnect");
	for(;;)
	{
		wait 1.5;
		if(!isDefined(level.car_estado) || level.car_estado != "carrera" || self.sessionstate != "playing" || !isDefined(self.car_sig) || isDefined(self.car_llego))
			continue;
		// al proximo control (o a la meta), con el jeep si esta adentro
		if(self.car_sig == 0)
			destino = level.car_meta;
		else
			destino = level.car_ctrl[self.car_sig - 1];
		r = level.car_reap[self.car_sig];
		if(!isDefined(r))
			continue;
		logPrint("CARRERA;prueba " + self.name + " va a " + self.car_sig + " en jeep " + (self isinvehicle()) + "\n");
		if(getCvar("scr_carrera_prueba_mover") == "0")
			continue;
		mio = self MiJeep();
		if(isDefined(mio))
			mio.origin = r.origin + (0, 0, 16);
		else if(!(self isinvehicle()))
			self setOrigin(r.origin + (0, 0, 16));
	}
}
'''

out = os.path.join(ROOT, 'carrera_src', 'maps', 'mp', 'gametypes')
os.makedirs(out, exist_ok=True)
txt = '"^7Carrera de jeeps"\n'
open(os.path.join(out, 'carrera.gsc'), 'w', encoding='latin1', newline='\r\n').write(t)
open(os.path.join(out, 'carrera.txt'), 'w', encoding='latin1', newline='\r\n').write(txt)
MAPAS_CARRERA = []   # (cada pista exportada con el editor ya trae su soundloadspecs; aca solo para pistas viejas que no lo tengan)
pk3 = os.path.join(MAESTRO, 'zzzzzz_kit_carrera.pk3')
with zipfile.ZipFile(pk3, 'w', zipfile.ZIP_DEFLATED) as z:
    for n in ('carrera.gsc', 'carrera.txt'):
        zi = zipfile.ZipInfo('maps/mp/gametypes/' + n, (2026, 10, 26, 0, 0, 0)); zi.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(zi, open(os.path.join(out, n), 'rb').read())
    mod = zipfile.ZipFile(os.path.join(MAESTRO, 'MiMod_v1.pk3'))
    b = chr(92)
    veh = mod.read('vehicles/willyjeep_mp').decode('latin1')
    a = b + 'maxSpeed' + b + '70' + b + 'accel' + b + '50' + b
    assert a in veh
    veh = veh.replace(a, b + 'maxSpeed' + b + '94' + b + 'accel' + b + '25' + b)
    # (con la entrada de la carpeta, como los pk3 del juego: el juego lista vehicles/ para saber que vehiculos hay)
    z.writestr(zipfile.ZipInfo('vehicles/', (2026, 10, 26, 0, 0, 0)), b'')
    zi = zipfile.ZipInfo('vehicles/bt_jeep_carrera', (2026, 10, 26, 0, 0, 0)); zi.compress_type = zipfile.ZIP_DEFLATED
    z.writestr(zi, veh.encode('latin1'))
    jd = mod.read('maps/mp/_jeepdrive_gmi.gsc').decode('latin1')
    for quien in ('jeeps[i]', 'self'):
        a = quien + '.vehicletype == "willyjeep_mp"'
        assert a in jd, a
        jd = jd.replace(a, '(' + a + ' || ' + quien + '.vehicletype == "bt_jeep_carrera")')
    zi = zipfile.ZipInfo('maps/mp/_jeepdrive_gmi.gsc', (2026, 10, 26, 0, 0, 0)); zi.compress_type = zipfile.ZIP_DEFLATED
    z.writestr(zi, jd.encode('latin1'))
    # Sonidos: UO solo carga en cada mapa los csv de alias que lista soundloadspecs/mp/<mapa>.csv (si no hay, el
    # default.csv del mod, que no trae vehiculos): sin esto los jeeps no tienen motor ni bocina. Mapas de carrera:
    base = zipfile.ZipFile(os.path.join(MAESTRO, 'MiMod_v1.pk3')).read('soundloadspecs/mp/default.csv').decode('latin1').replace('\r\n', '\n').rstrip('\n')
    spec = (base + '\ngmi_mp_vehicles_us.csv\ngmi_mp_vehicles_ge.csv\ngmi_mp_vehicles_ru.csv\n').replace('\n', '\r\n')
    for mapa in MAPAS_CARRERA:
        zi = zipfile.ZipInfo('soundloadspecs/mp/' + mapa + '.csv', (2026, 10, 26, 0, 0, 0)); zi.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(zi, spec.encode('latin1'))
print('OK', pk3, len(t.splitlines()), 'lineas')

