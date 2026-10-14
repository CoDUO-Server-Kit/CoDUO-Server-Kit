# CoDUO Server Kit

**A complete toolkit to run a private Call of Duty: United Offensive 1.51 community server with a custom mod** — a self-updating launcher for your players, bot practice on any map, a monthly leaderboard and the publishing tools behind it.

> 📖 **Full guide (Spanish):** [docs/GUIA.md](docs/GUIA.md) · License: [GPL v3](LICENSE) · Credits: [CREDITS.md](CREDITS.md)

![Launcher](imagenes/launcher.png)

## What it does

- **Self-updating launcher (C#, .NET 4, runs on Windows 7+)** — compares every mod file against a SHA-256 manifest and downloads only what changed from a **private GitHub release**. It updates itself, too.
- **Locked-down server** — `sv_pure 1` with in-game downloads disabled: only players with your exact pk3 files can join, and those files are never public.
- **Bot practice on any map** — a hidden local dedicated server with bots that **build their own navigation graph** for every map at load time (no hand-made waypoints), move smoothly and play real walking animations (ideas from MeatBot).
- **Monthly leaderboard** — a GitHub Actions job reads the server's `games_mp.log` every 30 minutes; the launcher shows top kills and match wins, reset every month.
- **One-click repair** — fixes the classic UO breakages: `EXE_...` strings (language reset), the "Safe Mode" prompt, slow map loads (vsync), white screen (gamma), stuck mouse focus.
- **Optional HD engine switch** — toggles between the stock engine and a 64-bit community engine (not included), keeping a backup of the originals.
- **Tools** — pk3 builder, pk3 priority/conflict auditor, release publisher, patcher for old launchers.

| Monthly leaderboard | Bot practice |
|---|---|
| ![Top](imagenes/top_del_mes.png) | ![Practice](imagenes/practica.png) |

![How it works](imagenes/arquitectura.svg)

## HD engine: honest before/after

Same view, same settings. The 3D scene is practically identical; the visible fix is that the **HUD and menus are no longer stretched** on 16:9 screens.

![Before/after](imagenes/hd_interfaz_antes_despues.jpg)

## Not included

This repository contains **only the kit's own code**. It does **not** include the game (Activision), any mod, maps, the HD engine or any community's data. Bring your own, and respect their authors.

## Quick start

1. Set up your Linux server with your mod folder, `sv_pure 1` and downloads off ([guide §5](docs/GUIA.md#5-paso-1--el-servidor-linux--tcadmin)).
2. Create a **private** GitHub repo and two fine-grained tokens (read-only for the launcher, read/write for you) ([§7](docs/GUIA.md#7-paso-3--github-repo-privado-tokens-y-release)).
3. Build the launcher with `launcher\build.bat` (no Visual Studio needed) and fill `config.json` ([§8](docs/GUIA.md#8-paso-4--compilar-y-configurar-el-launcher)).
4. Put your files in `maestro\` and run `herramientas\Publicar_Actualizacion.bat` ([§9](docs/GUIA.md#9-paso-5--publicar-actualizaciones)).

## License

GPL v3 — see [LICENSE](LICENSE). Parts derived from other mods (AWE bot script) keep their authors' rights — see [CREDITS.md](CREDITS.md).
