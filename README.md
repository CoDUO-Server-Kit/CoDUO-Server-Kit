# CoDUO Server Kit

**Kit completo para montar el servidor privado de tu comunidad de Call of Duty: United Offensive 1.51 con un mod propio**: un launcher que se actualiza solo para tus jugadores, práctica con bots en cualquier mapa, un top del mes y las herramientas para publicar todo.

> 📖 **Guía completa paso a paso:** [docs/GUIA.md](docs/GUIA.md) · Licencia: [GPL v3](LICENSE) · Créditos: [CREDITS.md](CREDITS.md) · *English summary at the end*

**Creado por Leandro Guzman** en colaboración con un grupo de técnicos aficionados al CoD — **GERARD!, Gaston, Miguel Soldier, Guille, Jubilado, Pyro y Sr-Oscuro** — en nuestro tiempo libre, en charlas de Zoom mientras jugábamos. Desarrollado con asistencia de herramientas de IA.

![Launcher](imagenes/launcher.png)

## Descargar y jugar ya

En **[Releases](https://github.com/CoDUO-Server-Kit/CoDUO-Server-Kit/releases/latest)** está el **paquete listo para jugar** (`CoDUO-Server-Kit-Paquete.zip`): launcher + mod T-FBB + mapas + bots de práctica + motor HD + **armas, soldados y la racha Harrier de eBus Hardline** (pestaña HARDLINE en el menú de armas).

1. Tené instalado Call of Duty + United Offensive **1.51** (original; el paquete no trae el juego).
2. Copiá el contenido del zip **dentro de la carpeta del juego** (donde está `CoDUOMP.exe`).
3. Abrí `Launcher\CoDUOKitLauncher.exe` → **JUGAR** o **PRÁCTICA** contra bots, sin internet.

Instrucciones completas dentro del zip (`LEEME.txt`). Para montar **tu propio servidor** con actualizaciones automáticas, seguí la [guía](docs/GUIA.md).

## Qué hace

- **Launcher que se actualiza solo** (C#, .NET 4, anda desde Windows 7): compara cada archivo del mod con una lista de huellas (SHA-256) y baja **solo lo que cambió** desde un **release privado de GitHub**. También se actualiza a sí mismo. Las actualizaciones pueden ir **firmadas**: el launcher solo acepta lo que firmaste con tu clave privada, aunque alguien consiga tu token de GitHub.
- **Servidor cerrado**: `sv_pure 1` y descargas del juego apagadas. Solo entra quien tiene tus pk3 **idénticos**, y esos archivos nunca son públicos.
- **Práctica con bots en cualquier mapa**: un servidor local oculto con bots que **arman solos la red de caminos** de cada mapa al cargarlo (sin grabar recorridos a mano), se mueven suave y tienen animación de caminar (ideas de MeatBot).
- **Top del mes**: una tarea de GitHub Actions lee cada 30 minutos el registro de partidas del servidor; el launcher muestra quién hizo más bajas y ganó más partidas, y se reinicia cada mes.
- **Botón Reparar** y arreglos automáticos de los problemas clásicos de UO: textos `EXE_...` (idioma), cartel de "Modo Seguro", cargas lentas (sincronización vertical), monitor blanco (brillo), mouse sin foco.
- **Motor HD opcional**: cambia entre el motor original y un motor alternativo de 64 bits (no incluido), guardando copia de los originales.
- **Armas modernas de otro mod (ejemplo: eBus Hardline)**: `Armar_Hardline.py` suma a tu mod AWE 27 armas modernas con su pestaña en el menú, soldados modernos y la racha **Harrier** (7 bajas seguidas) reescrita, **sin usar los scripts** del otro mod. Se puede apagar por cvar o por mapa ([guía §20](docs/GUIA.md#20-sumar-armas-soldados-y-rachas-de-otro-mod-ejemplo-hardline)).
- **Herramientas**: armado de pk3, auditoría de conflictos entre pk3, publicador de releases y un parche para launchers viejos.

| Top del mes | Práctica con bots |
|---|---|
| ![Top](imagenes/top_del_mes.png) | ![Práctica](imagenes/practica.png) |

![Cómo funciona](imagenes/arquitectura.svg)

## Requisitos

| Para | Qué necesitás |
|---|---|
| **El juego** | Call of Duty + United Offensive **1.51** (copia original; el kit no lo incluye) |
| **El servidor** | Servidor dedicado de CoD UO **1.51 para Linux** (por ejemplo con panel TCAdmin), acceso **SFTP**, y `game.mp.uo.i386.so` dentro de la carpeta del mod |
| **El mod** | Un mod tuyo en pk3. Los arreglos (`Armar_Pk3.py fixes`) y los bots de práctica requieren un mod basado en **AWE 2.x para UO** |
| **PC del administrador** | Windows 7 SP1 o superior · **.NET Framework 4.8** (trae el compilador `csc.exe`: **no hace falta Visual Studio**) · **PowerShell 5.1** (viene con Windows) · **Python 3.8+** · Git (opcional) |
| **Paquetes de Python** | `pip install paramiko pynacl` (solo para el top del mes) |
| **GitHub** | Cuenta gratis, un **repositorio privado** para tus archivos y dos tokens *fine-grained* (lectura para el launcher, escritura para vos) |
| **Jugadores** | El juego instalado y Windows 7 SP1+ con .NET 4.5 o superior (4.8 recomendado) |

## Cómo se compila y arma cada pieza

Todo se hace desde la carpeta del proyecto, en Windows. Los detalles están en la [guía](docs/GUIA.md#19-compilar-y-armar-cada-pieza).

| Pieza | Comando | Necesita | Genera |
|---|---|---|---|
| **Launcher** | `launcher\build.bat` | .NET 4.8 | `launcher\CoDUOKitLauncher.exe` (+ `config.json` al lado, ver `ejemplos\`) |
| **Parche** | `parche\build_parche.bat` | El launcher compilado antes | `Output\Parche_Launcher_CoDUOKit.exe` (lleva el launcher adentro) |
| **pk3 de arreglos** | `python herramientas\Armar_Pk3.py fixes` | El pk3 de tu mod (AWE) en `maestro\MiMod\` | `maestro\MiMod\zzzzzz_kit_fixes.pk3` (va al servidor y a los jugadores) |
| **pk3 de armas** | `python herramientas\Armar_Pk3.py armas` | Tus archivos en `armas_src\weapons\mp\` | `maestro\MiMod\z_zzz_kit_armas.pk3` (servidor y jugadores) |
| **pk3 de Hardline** (opcional) | `python herramientas\Armar_Hardline.py` (después de `Armar_Pk3.py armas`) | Los 4 pk3 de eBus Hardline en `mods_terceros\` | `maestro\MiMod\z_zzz_kit_hardline.pk3` (servidor y jugadores) |
| **pk3 de práctica (bots)** | `python herramientas\Armar_Pk3.py practica` | El pk3 de arreglos armado antes + el juego instalado | `maestro\MiMod\zzzzzz_kit_practica.pk3` (solo jugadores) |
| **Config de la práctica** | `powershell -File herramientas\Generar_Practica_cfg.ps1` | `servidor\MiMod\server.cfg` y `awe.cfg` | `maestro\MiMod\practica.cfg` |
| **Mapas sin repetir** | `python herramientas\Anular_Arenas_Repetidas.py` (y después `Armar_Pk3.py armas`) | Tu lista general `mp/CoDmaps.arena` en un pk3 de `maestro\MiMod\` | `armas_src\mp\*.arena` vacíos: cada mapa aparece una sola vez |
| **Auditoría de conflictos** | `python herramientas\Auditar_Conflictos.py` | Los pk3 en `maestro\MiMod\` | Informe (tiene que dar `total: 0`) |
| **Claves de firma** (una vez) | `powershell -File herramientas\Generar_Claves.ps1` | — | `privado\firma_privada.dat` (cifrada) + la clave pública para `config.json` |
| **Publicar a GitHub** | `herramientas\Publicar_Actualizacion.bat` | `privado\github.json` (ver `ejemplos\`) | Release `mod` + `manifest.json` (+ `manifest.sig` si hay claves) |
| **Top del mes** | `python estadisticas\subir_a_github.py` y `python estadisticas\poner_secretos.py` | Python + `paramiko` y `pynacl` | Tarea de GitHub Actions cada 30 min |

## Motor HD: antes y después

Mini Harbor, **mismo lugar, mismo ángulo y la misma configuración** (con el brillo tal como se ve en el monitor). Con el motor original, en pantallas 16:9 **toda la imagen sale estirada a lo ancho**; con el motor HD se ve con la **proporción correcta, más campo de visión** y el arma y los objetos **más definidos**. Jugando también se nota en la luz y los colores.

![Mini Harbor: original vs HD](imagenes/hd_miniharbor_m1.jpg)
![Mini Harbor: original vs HD](imagenes/hd_miniharbor_m2.jpg)

El arma de cerca (zoom x2):

![Arma: original vs HD](imagenes/hd_zoom_arma.jpg)
## Qué NO incluye

Este repositorio tiene **solo el código propio del kit**. **No** incluye el juego (Activision), ni mods, ni mapas, ni el motor HD, ni datos de ninguna comunidad. Cada uno pone los suyos y respeta a sus autores ([CREDITS.md](CREDITS.md)).

## Inicio rápido

1. Montá el servidor Linux con la carpeta de tu mod, `sv_pure 1` y descargas apagadas ([guía §5](docs/GUIA.md#5-paso-1--el-servidor-linux--tcadmin)).
2. Creá un repo **privado** en GitHub y dos tokens *fine-grained* ([§7](docs/GUIA.md#7-paso-3--github-repo-privado-tokens-y-release)).
3. Compilá el launcher con `launcher\build.bat` y completá su `config.json` ([§8](docs/GUIA.md#8-paso-4--compilar-y-configurar-el-launcher)).
4. Poné tus archivos en `maestro\` y corré `herramientas\Publicar_Actualizacion.bat` ([§9](docs/GUIA.md#9-paso-5--publicar-actualizaciones)).

## Seguridad

Lista de control en la [guía §17](docs/GUIA.md#17-seguridad): firma de actualizaciones, tokens con vencimiento, huella del servidor SFTP y los límites de `sv_pure`. Para comprobar el paquete descargado, compará su huella SHA-256 con la de las notas del *Release*. ¿Encontraste una vulnerabilidad? Reportala en privado según [SECURITY.md](SECURITY.md).

## Licencia

GPL v3 — ver [LICENSE](LICENSE). Las partes derivadas de otros mods (el script de bots de AWE) mantienen los derechos de sus autores — ver [CREDITS.md](CREDITS.md).

---

## English summary

**CoDUO Server Kit** is a complete toolkit to run a private Call of Duty: United Offensive 1.51 community server with a custom mod: a self-updating launcher (C#, .NET 4, Windows 7+) that syncs your mod from a private GitHub release using a SHA-256 manifest, optionally RSA-signed so only your private key can push updates; a locked-down server (`sv_pure 1`, downloads off); bot practice on any map with bots that build their own navigation graph at load time; a monthly leaderboard updated by GitHub Actions; one-click repair of classic UO issues; an optional HD-engine switch; a tool that adds another mod's content to an AWE-based mod without its scripts (example: 27 modern weapons, modern soldiers and a rewritten Harrier killstreak from eBus Hardline, plus the engine rules we found: max 127 weapon files, Linux needs new weapon names that sort after the stock ones); and the publishing tools behind it. Requirements and build steps are in the tables above; the full guide is in Spanish ([docs/GUIA.md](docs/GUIA.md)). Created by **Leandro Guzman** with GERARD!, Gaston, Miguel Soldier, Guille, Jubilado, Pyro and Sr-Oscuro, with the help of AI tools. It contains only the kit's own code (GPL v3) — no game files, mods, maps or engine. The ready-to-play package in *Releases* includes third-party content (mod, maps, HD engine, eBus Hardline weapons) with credits.
