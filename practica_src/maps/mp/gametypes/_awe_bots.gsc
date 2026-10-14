// AWE bots + cambios CoDUOKit para la practica local:
//  - awe_bots_allies / awe_bots_axis: cuantos bots van a cada equipo (0/0 = reparto automatico como antes)
//  - awe_bots_health: vida de los bots. 0 = la normal de los jugadores
//  - awe_bots_skill: 0 facil, 1 normal, 2 dificil (reaccion, punteria, cadencia y alcance)
//  - inteligencia basica: se quedan en su lugar, giran hacia el enemigo que ven y le disparan
//  - reaparecen a los 3 s en lugar de 10
// En el servidor real awe_bots es 0, asi que nada de esto se usa ahi.

addBotClients()
{
	level endon("awe_boot");

	if(!isdefined(level.bnav_started))
	{
		level.bnav_started = true;
		thread bnav_build();
	}

	wait 2;

	if(level.awe_debug)
		iprintln(level.awe_allplayers.size + " players found.");

	numbots = 0;
	// Catch & count running bots and start their think threads.
	for(i=0;i<level.awe_allplayers.size;i++)
	{
		if(isdefined(level.awe_allplayers[i]))
		{
			player = level.awe_allplayers[i];
			if(player.name.size==4 || player.name.size==5)
			{
				if(player.name[0] == "b" && player.name[1] == "o" && player.name[2] == "t")
				{
					player thread bot_think();
					numbots++;
				}
			}
		}
	}

	// Reparto por equipo (se guarda en game[] para que sobreviva a los reinicios de ronda)
	if(!isdefined(game["kit_bots_init"]))
	{
		game["kit_bots_init"] = true;
		game["kit_allies_left"] = getcvarint("awe_bots_allies");
		game["kit_axis_left"] = getcvarint("awe_bots_axis");
	}

	for(;;)
	{
		wait 3;

		// Solo para pruebas (+set kit_test_autojoin 1): mete en la partida a los humanos que estan de espectador
		if(getcvarint("kit_test_autojoin"))
		{
			ps = getentarray("player", "classname");
			for(i = 0; i < ps.size; i++)
			{
				if(ps[i].sessionstate == "playing")
				{
					// capturas comparables: el humano queda fijo en un punto y angulo (cvars kit_test_x/y/z/yaw)
					if(getcvar("kit_test_x") != "")
					{
						n = ps[i].name;
						if(!(n.size >= 3 && n[0] == "b" && n[1] == "o" && n[2] == "t"))
						{
							ps[i] setorigin((getcvarfloat("kit_test_x"), getcvarfloat("kit_test_y"), getcvarfloat("kit_test_z")));
							ps[i] setplayerangles((0, getcvarfloat("kit_test_yaw"), 0));
						}
					}
					continue;
				}
				n = ps[i].name;
				if(n.size >= 3 && n[0] == "b" && n[1] == "o" && n[2] == "t")
					continue;	// los bots se anotan solos
				if(getcvarint("kit_test_autojoin") == 3)
				{
					// solo cerrar el menu: queda de espectador en la vista panoramica del mapa (para capturas)
					ps[i] closeMenu();
					continue;
				}
				if(getcvarint("kit_test_autojoin") == 2)
				{
					// espectador siguiendo al primer bot (para mirar como se mueven)
					for(j = 0; j < ps.size; j++)
						if(ps[j] != ps[i] && ps[j].sessionstate == "playing")
						{
							ps[i] closeMenu();
							ps[i].spectatorclient = ps[j] getEntityNumber();
							break;
						}
					continue;
				}
				ps[i] notify("menuresponse", game["menu_team"], "allies");
				wait 0.5;
				if(isPlayer(ps[i]))
					ps[i] notify("menuresponse", game["menu_weapon_allies"], "m1carbine_mp");
				wait 0.5;
				if(isPlayer(ps[i]))
					ps[i] closeMenu();
			}
		}

		// Any new bots to add?
		newbots = level.awe_bots - numbots;

		// Any new bots to add?
		if(newbots<=0)
			continue;

		for(i = 0; i < newbots; i++)
		{
			bot = addtestclient();
			wait 0.5;
			if(isdefined(bot) && isPlayer(bot))
			{
				if(game["kit_allies_left"] > 0)
				{
					bot.kit_team = "allies";
					game["kit_allies_left"] = game["kit_allies_left"] - 1;
				}
				else if(game["kit_axis_left"] > 0)
				{
					bot.kit_team = "axis";
					game["kit_axis_left"] = game["kit_axis_left"] - 1;
				}
				bot thread bot_think();
			}
			numbots++;
		}
	}
}

bot_think()
{
	level endon("awe_boot");

	if(level.awe_debug)
		iprintln("Starting think thread for: " + self.name);

	if(getcvar("g_gametype") == "bel" || getcvar("g_gametype") == "mc_bel")
		bel = "_only";
	else
		bel = "";

	if(isPlayer(self))
	{
		self thread kit_bot_health();
		self thread kit_bot_ai();
		self thread kit_bot_move();

		for(;;)
		{
			if(!isAlive(self) && self.sessionstate != "playing")
			{
				if(level.awe_debug)
					iprintln(self.name + " is sending menu responses.");

				team = "autoassign";
				if(isdefined(self.kit_team))
					team = self.kit_team;
				if(bel != "")
					team = "axis";

				self notify("menuresponse", game["menu_team"], team);
				wait 0.5;

				// CoDUOKit: arma al azar de la lista del menu del mod (sin la AUG, que en manos de
				// los bots largaba proyectiles explosivos y se mataban solos)
				if(isdefined(self.pers["team"]) && self.pers["team"] == "axis")
				{
					self notify("menuresponse", game["menu_weapon_axis" + bel], kit_random_weapon());
				}
				else
				{
					if(team == "autoassign")
					{
						self notify("menuresponse", game["menu_team"], "allies");
						wait 0.5;
					}
					self notify("menuresponse", game["menu_weapon_allies" + bel], kit_random_weapon());
				}
			}
			wait 3;
		}
	}
}

// ------------------------------------------------------------------------------------------
// Inteligencia basica: apuntar y disparar al enemigo visible mas cercano
// ------------------------------------------------------------------------------------------
kit_bot_ai()
{
	level endon("awe_boot");

	skill = getcvarint("awe_bots_skill");
	if(skill == 0)      { reaction = 1200; accuracy = 0.20; interval = 500; range = 1600; dhead = 60;  dchest = 36; dleg = 24; lookdelay = 3000; turnrate = 20; }
	else if(skill == 2) { reaction = 350;  accuracy = 0.55; interval = 200; range = 4000; dhead = 105; dchest = 63; dleg = 42; lookdelay = 1200; turnrate = 55; }
	else                { reaction = 700;  accuracy = 0.35; interval = 300; range = 2600; dhead = 83;  dchest = 50; dleg = 33; lookdelay = 2000; turnrate = 35; }
	// Punteria elegida en el launcher (awe_bots_accuracy en %). 0 = la de la dificultad
	acc = getcvarint("awe_bots_accuracy");
	if(acc > 0)
		accuracy = acc * 0.01;
	nextlook = 0;
	alertuntil = 0;
	lasthealth = 0;

	self.kit_target = undefined;
	nextshot = 0;
	readyat = 0;
	self.dbg_rng = 0; self.dbg_fov = 0; self.dbg_los = 0; dbg_shots = 0; dbg_hits = 0; dbg_tick = 0;
	self.dbg_frac = -1; self.dbg_ent = "-";

	for(;;)
	{
		wait 0.1;

		if(!isPlayer(self))
			return;

		// diagnostico (awe_bots_debug 1): resumen cada 5 s en el log de partida
		dbg_tick++;
		if(dbg_tick >= 50)
		{
			if(getcvarint("awe_bots_debug"))
				logprint("BOTDBG " + self.name + " equipo=" + self.pers["team"] + " estado=" + self.sessionstate + " arma=" + self getcurrentweapon() + " rango=" + self.dbg_rng + " fov=" + self.dbg_fov + " vista=" + self.dbg_los + " disparos=" + dbg_shots + " impactos=" + dbg_hits + " yaw=" + self.angles[1] + " frac=" + self.dbg_frac + " ent=" + self.dbg_ent + " z=" + self.origin[2] + "\n");
			dbg_tick = 0; self.dbg_rng = 0; self.dbg_fov = 0; self.dbg_los = 0; dbg_shots = 0; dbg_hits = 0;
		}
		if(!isAlive(self) || self.sessionstate != "playing")
		{
			self.kit_target = undefined;
			lasthealth = 0;
			continue;
		}

		// si le pegaron, durante 3 s ve en todas direcciones (se da vuelta hacia quien le dispara)
		if(lasthealth > 0 && self.health < lasthealth)
			alertuntil = gettime() + 3000;
		lasthealth = self.health;
		self.kit_alert = (gettime() < alertuntil);

		target = self kit_find_target(range);
		if(!isdefined(target))
		{
			self.kit_target = undefined;
			// mirar alrededor cada tanto (si esta caminando, mira hacia donde va: lo maneja kit_bot_move)
			if(gettime() > nextlook && !(isdefined(self.kit_walking) && self.kit_walking))
			{
				self setplayerangles((0, self.angles[1] + randomint(240) - 120, 0));
				nextlook = gettime() + lookdelay + randomint(800);
			}
			continue;
		}
		nextlook = gettime() + lookdelay;

		eye = self.origin + (0,0,56);
		aimpos = target.origin + (0,0,40);		// al pecho

		// apuntar como una persona: gira de a poco y con error segun la punteria.
		// (los bots ademas aprietan "disparar" solos: si la vista apunta perfecto, esas balas reales pegan siempre)
		want = vectortoangles(aimpos - eye);
		err = (1 - accuracy) * 12;			// grados de error: punteria 10% -> ~11, 75% -> 3
		diff = kit_angle_diff(want[1], self.angles[1]);
		if(diff > turnrate) diff = turnrate;
		if(diff < 0 - turnrate) diff = 0 - turnrate;
		ontarget = (kit_abs(kit_angle_diff(want[1], self.angles[1])) < 15);
		self setplayerangles((want[0] + randomfloat(err * 2) - err, self.angles[1] + diff + randomfloat(err * 2) - err, 0));

		// tiempo de reaccion cuando cambia de objetivo
		if(!isdefined(self.kit_target) || self.kit_target != target)
		{
			self.kit_target = target;
			readyat = gettime() + reaction + randomint(250);
		}
		if(!ontarget || gettime() < readyat || gettime() < nextshot)
			continue;
		nextshot = gettime() + interval + randomint(100);

		// disparo (sonido del arma)
		weapon = self getcurrentweapon();
		if(!isdefined(weapon) || weapon == "none" || (isdefined(self.kit_walkweapon) && weapon == self.kit_walkweapon))
			continue;
		self playsound(kit_fire_sound(weapon));
		dbg_shots++;

		// pegar o no: la punteria baja con la distancia
		dist = distance(eye, aimpos);
		chance = accuracy * (1 - (dist / range) * 0.5);
		if(randomfloat(1) > chance)
			continue;

		r = randomint(100);
		if(r < 8)       { loc = "head";        dmg = dhead; }
		else if(r < 70) { loc = "torso_upper"; dmg = dchest; }
		else            { loc = "right_leg_upper"; dmg = dleg; }

		dbg_hits++;
		dir = vectornormalize(aimpos - eye);
		target thread [[level.callbackPlayerDamage]](self, self, dmg, 0, "MOD_RIFLE_BULLET", weapon, aimpos, dir, loc);
	}
}

// ------------------------------------------------------------------------------------------
// Movimiento con recorridos (ideas tomadas de MeatBot para CoD UO):
//  - Red de caminos propia de cada mapa, armada sola al cargar el mapa: desde los puntos de
//    aparicion se explora el terreno en una grilla (bullettrace: piso, escalones y paredes).
//    Sirve para TODOS los mapas, tambien los custom.
//  - Ruta por la red (busqueda en anchura) hacia un enemigo o un punto del mapa.
//  - El bot va enganchado (linkto) a un script_origin que se desliza con moveto: movimiento suave.
//  - Mientras camina lleva un arma "bwalk_*" cuya pose de quieto es correr (playeranim.script del
//    pk3 de practica): se lo ve caminar con su arma. Al ver a un enemigo cambia a su arma real.
// ------------------------------------------------------------------------------------------

// Armas de caminar: se registran en el primer instante del mapa (lo llama _awe.gsc del pk3 de practica)
kit_precache()
{
	if(getcvarint("awe_bots") <= 0)
		return;
	w = kit_weapon_list();
	for(i = 0; i < w.size; i++)
		precacheItem("bwalk_" + w[i]);
}

kit_waypoints()
{
	if(isdefined(level.kit_wp))
		return level.kit_wp;

	wp = [];
	classes = [];
	classes[0] = "mp_deathmatch_spawn";
	classes[1] = "mp_teamdeathmatch_spawn";
	classes[2] = "mp_searchanddestroy_spawn_allied";
	classes[3] = "mp_searchanddestroy_spawn_axis";
	classes[4] = "mp_retrieval_spawn_allied";
	classes[5] = "mp_retrieval_spawn_axis";
	classes[6] = "mp_uo_spawn_allies";
	classes[7] = "mp_uo_spawn_axis";
	classes[8] = "mp_gmi_ctf_spawn_allies";
	classes[9] = "mp_gmi_ctf_spawn_axis";
	classes[10] = "mp_gmi_bas_allies_spawn";
	classes[11] = "mp_gmi_bas_axis_spawn";
	for(c = 0; c < classes.size; c++)
	{
		ents = getentarray(classes[c], "classname");
		for(i = 0; i < ents.size; i++)
			wp[wp.size] = ents[i].origin;
	}
	level.kit_wp = wp;
	return wp;
}

// ---- Red de caminos ----------------------------------------------------------------------
// level.bnav_org[i]  posicion del nodo (apoyado en el piso)
// level.bnav_ix/iy/iz[i]  celda de la grilla
// level.bnav_n[i*4+d]  vecino en la direccion d (0 +x, 1 -x, 2 +y, 3 -y) o -1
// level.bnav_key["ix iy iz"]  indice del nodo de esa celda

bnav_round(v, step)
{
	// redondeo a entero sin int() (no existe en UO)
	n = 0;
	if(v >= 0)
	{
		while(v >= (n + 0.5) * step) n++;
	}
	else
	{
		while(v < (n - 0.5) * step) n--;
	}
	return n;
}

bnav_trace(a, b)
{
	return bullettrace(a, b, false, level.bnav_ignore);
}

// Piso bajo (x, y) buscando cerca de la altura z. Devuelve la posicion o undefined.
bnav_ground(x, y, z)
{
	t = bnav_trace((x, y, z + 40), (x, y, z - 120));
	if(t["fraction"] >= 1)
		return undefined;
	return t["position"];
}

bnav_add(pos, ix, iy)
{
	iz = bnav_round(pos[2] - level.bnav_z0, 64);
	key = ix + " " + iy + " " + iz;
	if(isdefined(level.bnav_key[key]))
		return level.bnav_key[key];
	if(level.bnav_size >= level.bnav_max)
		return -1;

	i = level.bnav_size;
	level.bnav_org[i] = pos;
	level.bnav_ix[i] = ix;
	level.bnav_iy[i] = iy;
	for(d = 0; d < 4; d++)
		level.bnav_n[i * 4 + d] = -1;
	level.bnav_key[key] = i;
	level.bnav_queue[level.bnav_queue.size] = i;
	level.bnav_size++;
	return i;
}

// Se puede caminar de "from" hasta (x, y)? Revisa el piso y las paredes cada 24 unidades.
// Devuelve la posicion de llegada (en el piso) o undefined.
bnav_walk(from, x, y)
{
	steps = 5;
	cur = from;
	dropped = 0;
	for(s = 1; s <= steps; s++)
	{
		px = from[0] + (x - from[0]) * s / steps;
		py = from[1] + (y - from[1]) * s / steps;
		g = bnav_ground(px, py, cur[2]);
		level.bnav_traces++;
		if(!isdefined(g))
		{
			// borde: se puede bajar saltando? (hasta 200 de caida, sin dano; solo de bajada)
			g = undefined;
			t = bnav_trace((px, py, cur[2] + 40), (px, py, cur[2] - 200));
			level.bnav_traces++;
			if(t["fraction"] < 1)
				g = t["position"];
			if(!isdefined(g))
				return undefined;		// pozo
		}
		rise = g[2] - cur[2];
		if(rise > 36)
			return undefined;			// escalon demasiado alto
		dropped = dropped - rise;
		if(rise < -200 || dropped > 200)
			return undefined;			// caida demasiado alta
		if(rise < -36)
		{
			// salto hacia abajo: libre adelante a la altura del borde y libre hacia abajo
			w = bnav_trace(cur + (0,0,40), (px, py, cur[2] + 40));
			level.bnav_traces++;
			if(w["fraction"] < 1)
				return undefined;
			w = bnav_trace((px, py, cur[2] + 40), g + (0,0,40));
		}
		else
			w = bnav_trace(cur + (0,0,40), g + (0,0,40));
		level.bnav_traces++;
		if(w["fraction"] < 1)
			return undefined;			// pared
		cur = g;
	}
	// lugar para pararse (techo bajo?)
	h = bnav_trace(cur + (0,0,4), cur + (0,0,64));
	level.bnav_traces++;
	if(h["fraction"] < 1)
		return undefined;
	return cur + (0,0,1);
}

bnav_build()
{
	level endon("awe_boot");

	level.bnav_size = 0;
	level.bnav_max = 3000;
	level.bnav_grid = 120;
	level.bnav_org = [];
	level.bnav_ix = [];
	level.bnav_iy = [];
	level.bnav_n = [];
	level.bnav_key = [];
	level.bnav_queue = [];
	level.bnav_traces = 0;
	level.bnav_ignore = spawn("script_origin", (0,0,0));

	seeds = kit_waypoints();
	if(!seeds.size)
		return;
	level.bnav_x0 = seeds[0][0];
	level.bnav_y0 = seeds[0][1];
	level.bnav_z0 = seeds[0][2];
	grid = level.bnav_grid;		// (ojo: en los scripts del juego G y g serian la misma variable)
	start = gettime();

	// cada punto de aparicion es una semilla (asi tambien se exploran zonas separadas por saltos/escaleras)
	for(i = 0; i < seeds.size; i++)
	{
		ix = bnav_round(seeds[i][0] - level.bnav_x0, grid);
		iy = bnav_round(seeds[i][1] - level.bnav_y0, grid);
		gp = bnav_ground(level.bnav_x0 + ix * grid, level.bnav_y0 + iy * grid, seeds[i][2] + 8);
		if(isdefined(gp))
			bnav_add(gp + (0,0,1), ix, iy);
	}

	dx = []; dy = [];
	dx[0] = 1;  dy[0] = 0;
	dx[1] = -1; dy[1] = 0;
	dx[2] = 0;  dy[2] = 1;
	dx[3] = 0;  dy[3] = -1;

	q = 0;
	budget = 0;
	while(q < level.bnav_queue.size)
	{
		n = level.bnav_queue[q];
		q++;
		p = level.bnav_org[n];
		for(d = 0; d < 4; d++)
		{
			ix = level.bnav_ix[n] + dx[d];
			iy = level.bnav_iy[n] + dy[d];
			to = bnav_walk(p, level.bnav_x0 + ix * grid, level.bnav_y0 + iy * grid);
			if(!isdefined(to))
				continue;
			m = bnav_add(to, ix, iy);
			if(m >= 0 && m != n)
				level.bnav_n[n * 4 + d] = m;
		}
		// repartir el trabajo: unos 300 trazados por cuadro
		if(level.bnav_traces - budget > 300)
		{
			budget = level.bnav_traces;
			wait 0.05;
		}
	}
	level.bnav_queue = undefined;
	level.bnav_done = true;
	logprint("KIT NAV " + getcvar("mapname") + " nodos=" + level.bnav_size + " trazados=" + level.bnav_traces + " ms=" + (gettime() - start) + "\n");
}

// Nodo mas cercano a una posicion (busca en la celda y alrededor, y que se vea desde ahi)
bnav_nearest(pos)
{
	if(!isdefined(level.bnav_size) || level.bnav_size < 1)
		return -1;
	grid = level.bnav_grid;
	cx = bnav_round(pos[0] - level.bnav_x0, grid);
	cy = bnav_round(pos[1] - level.bnav_y0, grid);
	cz = bnav_round(pos[2] - level.bnav_z0, 64);
	best = -1;
	bestd = 999999;
	for(ax = -1; ax <= 1; ax++)
	{
		for(ay = -1; ay <= 1; ay++)
		{
			for(az = -1; az <= 1; az++)
			{
				key = (cx + ax) + " " + (cy + ay) + " " + (cz + az);
				if(!isdefined(level.bnav_key[key]))
					continue;
				i = level.bnav_key[key];
				d = distance(pos, level.bnav_org[i]);
				if(d < bestd)
				{
					best = i;
					bestd = d;
				}
			}
		}
	}
	return best;
}

// Ruta de a hasta b (busqueda en anchura). Devuelve el arreglo de nodos o undefined.
bnav_path(a, b)
{
	if(a < 0 || b < 0)
		return undefined;
	prev = [];
	prev[a] = a;
	queue = [];
	queue[0] = a;
	q = 0;
	found = (a == b);
	work = 0;
	while(!found && q < queue.size)
	{
		n = queue[q];
		q++;
		for(d = 0; d < 4; d++)
		{
			m = level.bnav_n[n * 4 + d];
			if(!isdefined(m) || m < 0 || isdefined(prev[m]))
				continue;
			prev[m] = n;
			if(m == b) { found = true; break; }
			queue[queue.size] = m;
		}
		work++;
		if(work >= 400) { work = 0; wait 0.05; }
	}
	if(!found)
		return undefined;

	rev = [];
	n = b;
	while(n != a)
	{
		rev[rev.size] = n;
		n = prev[n];
	}
	rev[rev.size] = a;
	path = [];
	for(i = rev.size - 1; i >= 0; i--)
		path[path.size] = rev[i];
	return path;
}

// ---- Enganche al punto movil y armas --------------------------------------------------------

kit_link()
{
	if(isdefined(self.kit_mover))
		return;
	self.kit_mover = spawn("script_origin", self.origin);
	self linkto(self.kit_mover);
}

kit_unlink()
{
	if(!isdefined(self.kit_mover))
		return;
	if(isPlayer(self))
		self unlink();
	self.kit_mover delete();
	self.kit_mover = undefined;
}

// Arma real que eligio en el menu y su version "de caminar"
kit_setup_weapons()
{
	real = self getweaponslotweapon("primary");
	if(!isdefined(real) || real == "none" || real == "")
		return;
	self.kit_realweapon = real;
	self.kit_walkweapon = undefined;
	w = kit_weapon_list();
	for(i = 0; i < w.size; i++)
		if(w[i] == real)
			self.kit_walkweapon = "bwalk_" + real;
}

kit_hold(weapon)
{
	if(!isdefined(weapon) || self getcurrentweapon() == weapon)
		return;
	// como MeatBot: los bots de prueba mandan su propia eleccion de arma y switchtoweapon no alcanza;
	// se le deja SOLO esa arma y se la pone en la mano al instante
	self takeallweapons();
	self giveweapon(weapon);
	if(isdefined(self.kit_walkweapon) && weapon == self.kit_walkweapon)
	{
		self setweaponslotammo("primary", 999);	// con reserva (si no, no la toma) pero cargador 0: no dispara
		self setweaponslotclipammo("primary", 0);
	}
	else
		self givemaxammo(weapon);
	self setspawnweapon(weapon);
	self switchtoweapon(weapon);
	if(getcvarint("awe_bots_debug"))
		self thread kit_dbg_switch(weapon);
}

// Borra del piso las armas de caminar que suelta un bot al morir (el mod tira el arma que tenia en la mano)
kit_clear_walk_drops()
{
	wait 0.2;
	w = kit_weapon_list();
	for(i = 0; i < w.size; i++)
	{
		ents = getentarray("weapon_bwalk_" + w[i], "classname");
		for(j = 0; j < ents.size; j++)
			ents[j] delete();
	}
}

kit_dbg_switch(weapon)
{
	wait 1;
	if(isPlayer(self))
		logprint("BOTSWITCH " + self.name + " pedida=" + weapon + " actual=" + self getcurrentweapon() + " primary=" + self getweaponslotweapon("primary") + " primaryb=" + self getweaponslotweapon("primaryb") + "\n");
}

kit_bot_move()
{
	level endon("awe_boot");

	skill = getcvarint("awe_bots_skill");
	if(skill == 0) speed = 150; else if(skill == 2) speed = 220; else speed = 185;	// unidades por segundo
	wasalive = false;
	self.kit_walking = false;

	for(;;)
	{
		wait 0.05;
		if(!isPlayer(self))
			return;
		if(!isAlive(self) || self.sessionstate != "playing")
		{
			if(wasalive)
			{
				self kit_unlink();
				level thread kit_clear_walk_drops();
			}
			wasalive = false;
			self.kit_walking = false;
			continue;
		}
		if(!wasalive)
		{
			// recien aparecio: esperar que el modo de juego le de las armas
			wasalive = true;
			wait 0.5;
			if(!isPlayer(self) || !isAlive(self))
				continue;
			self kit_setup_weapons();
		}
		self kit_link();

		// combate: quieto y con el arma real (kit_bot_ai apunta y dispara)
		if(isdefined(self.kit_target))
		{
			self.kit_walking = false;
			self kit_hold(self.kit_realweapon);
			continue;
		}

		// todavia se esta armando la red de caminos del mapa
		if(!isdefined(level.bnav_size) || level.bnav_size < 2)
			continue;

		start = bnav_nearest(self.origin);
		if(start < 0)
		{
			wait 0.5;
			continue;
		}

		// destino: la mayoria de las veces un enemigo (salen a buscarte); si no, un lugar cualquiera
		goal = -1;
		if(randomint(100) < 65)
		{
			enemies = [];
			humans = [];
			players = getentarray("player", "classname");
			for(i = 0; i < players.size; i++)
			{
				p = players[i];
				if(p == self || !isAlive(p) || p.sessionstate != "playing")
					continue;
				if(isdefined(level.awe_teamplay) && isdefined(p.pers["team"]) && isdefined(self.pers["team"]) && p.pers["team"] == self.pers["team"])
					continue;
				enemies[enemies.size] = p;
				n = p.name;
				if(!(n.size >= 3 && n[0] == "b" && n[1] == "o" && n[2] == "t"))
					humans[humans.size] = p;
			}
			// es una practica: casi siempre van a buscar a los jugadores de verdad
			if(humans.size && randomint(100) < 80)
				goal = bnav_nearest(humans[randomint(humans.size)].origin);
			else if(enemies.size)
				goal = bnav_nearest(enemies[randomint(enemies.size)].origin);
		}
		if(goal < 0)
			goal = randomint(level.bnav_size);

		path = bnav_path(start, goal);
		if(!isdefined(path) || path.size < 2)
		{
			wait 0.3;
			continue;
		}

		self kit_hold(self.kit_walkweapon);
		// caminar como mucho ~12 tramos y volver a decidir (el enemigo se mueve)
		last = path.size;
		if(last > 13) last = 13;
		for(k = 1; k < last; k++)
		{
			if(!isPlayer(self) || !isAlive(self) || self.sessionstate != "playing" || isdefined(self.kit_target) || !isdefined(self.kit_mover))
				break;
			to = level.bnav_org[path[k]];
			from = self.kit_mover.origin;
			d = distance(from, to);
			if(d < 2)
				continue;
			ang = vectortoangles((to[0] - from[0], to[1] - from[1], 0));
			self setplayerangles((0, ang[1], 0));
			self.kit_walking = true;
			t = d / speed;
			self.kit_mover moveto(to, t);
			end = gettime() + t * 1000;
			while(gettime() < end)
			{
				wait 0.05;
				if(!isPlayer(self) || !isAlive(self) || isdefined(self.kit_target) || !isdefined(self.kit_mover))
					break;
			}
		}
		// frenar donde quedo
		if(isdefined(self.kit_mover))
			self.kit_mover moveto(self.kit_mover.origin, 0.05);
		self.kit_walking = false;
	}
}

// diferencia entre dos angulos, en el rango -180..180
kit_angle_diff(a, b)
{
	d = a - b;
	while(d > 180) d = d - 360;
	while(d < -180) d = d + 360;
	return d;
}

kit_abs(x)
{
	if(x < 0) return 0 - x;
	return x;
}

// Enemigo vivo, a la vista y dentro del rango. Si no esta siguiendo a nadie, solo ve hacia adelante (~120 grados)
kit_find_target(range)
{
	eye = self.origin + (0,0,56);
	forward = anglestoforward(self.angles);
	best = undefined;
	bestdist = range;

	players = getentarray("player", "classname");
	for(i = 0; i < players.size; i++)
	{
		p = players[i];
		if(p == self || !isAlive(p) || p.sessionstate != "playing")
			continue;
		if(isdefined(level.awe_teamplay) && isdefined(p.pers["team"]) && isdefined(self.pers["team"]) && p.pers["team"] == self.pers["team"])
			continue;

		aimpos = p.origin + (0,0,44);
		d = distance(eye, aimpos);
		if(d > bestdist)
			continue;
		self.dbg_rng++;

		// campo de vision para objetivos nuevos (al que ya sigue lo sigue viendo)
		if(!self.kit_alert && (!isdefined(self.kit_target) || self.kit_target != p))
			if(vectordot(forward, vectornormalize(aimpos - eye)) < 0.5)
				continue;

		self.dbg_fov++;
		trace = bullettrace(eye, aimpos, true, self);
		self.dbg_frac = trace["fraction"];
		if(isdefined(trace["entity"])) self.dbg_ent = trace["entity"].classname; else self.dbg_ent = "ninguna";
		if(trace["fraction"] < 0.98 && (!isdefined(trace["entity"]) || trace["entity"] != p))
			continue;

		self.dbg_los++;
		best = p;
		bestdist = d;
	}
	return best;
}

// Armas del menu del mod que pueden usar los bots (todas de balas; sin springfield_mp = AUG)
kit_random_weapon()
{
	w = kit_weapon_list();
	return w[randomint(w.size)];
}

kit_weapon_list()
{
	w = [];
	w[0] = "m1carbine_mp";		// MP5
	w[1] = "enfield_mp";		// BM12
	w[2] = "m1garand_mp";		// Uzi
	w[3] = "mosin_nagant_mp";	// SIG552
	w[4] = "kar98k_mp";			// AK47
	w[5] = "mp44_mp";			// MP44
	w[6] = "svt40_mp";			// M4
	w[7] = "sten_mp";			// SOCOM M4
	w[8] = "mp40_mp";			// G36
	w[9] = "bren_mp";			// M16
	w[10] = "gewehr43_mp";		// SAKO
	return w;
}

kit_fire_sound(weapon)
{
	switch(weapon)
	{
		case "m1carbine_mp":	return "weap_m1carbine_fire";
		case "enfield_mp":		return "weap_enfield_fire";
		case "m1garand_mp":		return "weap_m1garand_fire";
		case "mosin_nagant_mp":	return "weap_nagant_fire";
		case "mp44_mp":			return "weap_mp44_fire";
		case "svt40_mp":		return "weap_svt40_fire";
		case "sten_mp":			return "weap_sten_fire";
		case "mp40_mp":			return "weap_mp40_fire";
		case "bren_mp":			return "weap_bren_fire";
		case "gewehr43_mp":		return "weap_kar98k_fire";
	}
	return "weap_gewehr43_fire";
}

// Dificultad: cambia la vida del bot cada vez que reaparece
kit_bot_health()
{
	level endon("awe_boot");

	for(;;)
	{
		self waittill("awe_spawned");
		wait 0.5;		// dejar que el modo de juego termine de ponerle la vida normal

		hp = getcvarint("awe_bots_health");
		if(hp > 0 && isPlayer(self) && isAlive(self))
		{
			self.maxhealth = hp;
			self.health = hp;
		}
	}
}
