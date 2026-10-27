// Practica local: cambiar de mapa y de modo de juego al instante, sin votacion (los bots no votan).
// "Solicitar votacion > Cambiar Mapa / Cambiar Modo de Juego" abre el menu practica_mapas (lo genera
// publicar\Armar_Pk3.py practica): pestanas por modo y 64 lugares cuyos nombres manda este script (ui_pm_1..64)
// segun el modo elegido. La lista de mapas y modos esta en _kit_practica_lista.gsc, mas los mapas que no estan en
// la lista oficial (propios del jugador en uo\, etc.): el launcher los pasa en practica_mis_mapas.cfg
// (kit_mm_<n>_mapa / _modo / _nombre) y van primero, en celeste.
// En el servidor real nada de esto existe: el pk3 de practica no se carga online (sv_pure).
//
// Bots: si cambia solo el mapa, los mismos bots siguen. Si cambia el MODO, el juego reinicia el servidor y los bots
// quedan "fantasmas" ocupando su lugar para siempre (no hay forma de liberarlos: ni kick desde el script, ni
// clientkick, que tambien deja el lugar tomado). La practica pone bots nuevos; por eso el launcher abre el servidor
// de practica con 64 lugares (alcanza para varios cambios de modo).

// la lista completa: los mapas extra del launcher primero y despues la fija (level.kit_pl_m / _g / _n)
CargarLista()
{
	if(isdefined(level.kit_pl_m))
		return;
	level.kit_pl_m = [];
	level.kit_pl_g = [];
	level.kit_pl_n = [];
	for(i = 1; i <= 48; i++)
	{
		mapa = getcvar("kit_mm_" + i + "_mapa");
		if(mapa == "")
			break;
		k = level.kit_pl_m.size;
		level.kit_pl_m[k] = mapa;
		level.kit_pl_g[k] = getcvar("kit_mm_" + i + "_modo");
		level.kit_pl_n[k] = "^5" + getcvar("kit_mm_" + i + "_nombre");
	}
	m = maps\mp\gametypes\_kit_practica_lista::Mapas();
	g = maps\mp\gametypes\_kit_practica_lista::Modos();
	n = maps\mp\gametypes\_kit_practica_lista::Nombres();
	for(i = 0; i < m.size; i++)
	{
		k = level.kit_pl_m.size;
		level.kit_pl_m[k] = m[i];
		level.kit_pl_g[k] = g[i];
		level.kit_pl_n[k] = n[i];
	}
}

Abrir()
{
	self openMenu("practica_mapas");
	self thread MostrarModo(getcvar("g_gametype"));
}

// llena los lugares del menu con los mapas de ese modo (self.kit_pm[k] = entrada de la lista del lugar k+1)
MostrarModo(gt)
{
	self endon("disconnect");
	CargarLista();
	m = level.kit_pl_m;
	g = level.kit_pl_g;
	n = level.kit_pl_n;
	self.kit_pm = [];
	for(i = 0; i < m.size && self.kit_pm.size < 64; i++)
		if(g[i] == gt)
			self.kit_pm[self.kit_pm.size] = i;
	self setClientCvar("ui_practica_modo", gt);
	antes = 64;
	if(isdefined(self.kit_pm_antes))
		antes = self.kit_pm_antes;
	self.kit_pm_antes = self.kit_pm.size;
	// de a 8 por cuadro: muchos comandos juntos al jugador lo pueden desconectar
	for(k = 0; k < 64; k++)
	{
		if(k < self.kit_pm.size)
		{
			texto = n[self.kit_pm[k]];
			if(m[self.kit_pm[k]] == getcvar("mapname") && gt == getcvar("g_gametype"))
				texto = texto + " ^3(actual)";
			self setClientCvar("ui_pm_" + (k + 1), texto);
		}
		else if(k < antes)
			self setClientCvar("ui_pm_" + (k + 1), "");
		else
			continue;
		if(k % 8 == 7)
			wait 0.05;
	}
}

// prueba automatica (+set kit_practica_prueba <entrada>): a los 10 s elige esa entrada de la lista.
// kit_practica_prueba_veces N = N cambios seguidos; kit_practica_prueba2 = entrada para los cambios pares
Prueba()
{
	wait 10;
	logPrint("PRACTICA;prueba;" + getcvar("kit_practica_prueba") + "\n");
	setcvar("kit_practica_prueba_hecha", getcvar("kit_practica_prueba"));
	if(getcvar("kit_practica_prueba2") != "" && getcvarint("kit_practica_prueba_veces") % 2 == 0)
		setcvar("kit_practica_prueba_hecha", getcvar("kit_practica_prueba2"));
	if(getcvarint("kit_practica_prueba_veces") > 1)
		setcvar("kit_practica_prueba_veces", getcvarint("kit_practica_prueba_veces") - 1);
	else
		setcvar("kit_practica_prueba", "");
	Cambiar(getcvarint("kit_practica_prueba_hecha"));
}

// respuestas del menu: "m_<modo>" = pestana, "s<lugar>" = mapa
Elegir(response)
{
	CargarLista();
	g = level.kit_pl_g;
	for(i = 0; i < g.size; i++)
		if(response == "m_" + g[i])
		{
			self MostrarModo(g[i]);
			return;
		}
	if(!isdefined(self.kit_pm))
		return;
	for(k = 0; k < self.kit_pm.size; k++)
		if(response == "s" + (k + 1))
		{
			Cambiar(self.kit_pm[k]);
			return;
		}
}

// pasa a la entrada i de la lista (modo + mapa)
Cambiar(i)
{
	if(isdefined(level.kit_practica_cambiando))
		return;
	CargarLista();
	m = level.kit_pl_m;
	g = level.kit_pl_g;
	n = level.kit_pl_n;
	if(i < 0 || i >= m.size)
		return;
	level.kit_practica_cambiando = true;	// la practica deja de agregar bots hasta el mapa nuevo
	iprintlnbold("^7Cambiando a " + n[i] + " ^7(" + g[i] + ")...");
	wait 1;
	level.mapended = true;
	setcvar("sv_maprotationcurrent", " gametype " + g[i] + " map " + m[i]);
	exitLevel(false);
}
