"""Evita que los mapas aparezcan REPETIDOS en la lista del juego (crear servidor, votaciones).

Por que pasa: el juego arma la lista leyendo TODOS los archivos mp/*.arena de todos los pk3. Si un mapa esta en la
lista general del mod (mp/CoDmaps.arena) y ademas en su propio .arena (ej. mp/mp_miniharbor.arena), sale dos veces.

Que hace: por cada .arena propio de un mapa que YA figura en la lista general, crea en armas_src/mp/ un archivo
vacio con la misma ruta. Al armar el pk3 de armas (el de mayor prioridad: z_zzz_...), ese archivo vacio pisa al del
mapa y el mapa queda una sola vez, con el nombre de la lista general. No se modifica ningun pk3 de mapas.

Uso:
    python Anular_Arenas_Repetidas.py
    python Armar_Pk3.py armas        (despues: subir el pk3 de armas al servidor, reiniciar y publicar)
"""
import glob, os, re, sys, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(ROOT, "maestro", "MiMod")          # carpeta maestra del mod
JUEGO = r"C:\Juegos\Call of Duty UO"                         # para revisar tambien los .arena de uo\
DEST = os.path.join(ROOT, "armas_src", "mp")


def arenas_de(pk3):
    try:
        z = zipfile.ZipFile(pk3)
    except Exception:
        return []
    return [(n, z.read(n).decode("latin-1", "replace")) for n in z.namelist()
            if n.lower().startswith("mp/") and n.lower().endswith(".arena")]


def mapas_en(txt):
    return {m.lower() for m in re.findall(r'map\s+"([^"]+)"', re.sub(r"//[^\n]*", "", txt), re.I)}


# 1) la lista general: el CoDmaps.arena de mayor prioridad dentro de la carpeta del mod
pk3s = sorted(glob.glob(os.path.join(MOD, "*.pk3")), key=lambda f: os.path.basename(f).upper(), reverse=True)
general = None
for f in pk3s:
    for n, txt in arenas_de(f):
        if n.lower() == "mp/codmaps.arena":
            general = (os.path.basename(f), mapas_en(txt))
            break
    if general:
        break
if not general:
    raise SystemExit("No hay mp/CoDmaps.arena en " + MOD)
print("Lista general: %s (%d mapas)" % (general[0], len(general[1])))

# 2) los .arena propios de mapas que ya estan en la lista general
os.makedirs(DEST, exist_ok=True)
otros = pk3s + glob.glob(os.path.join(JUEGO, "uo", "*.pk3"))
anulados = 0
for f in otros:
    for n, txt in arenas_de(f):
        if n.lower() == "mp/codmaps.arena":
            continue
        m = mapas_en(txt)
        if m and m <= general[1]:
            with open(os.path.join(DEST, os.path.basename(n)), "w", newline="\n") as out:
                out.write("// Este mapa ya esta en mp/CoDmaps.arena: archivo vacio para que no aparezca repetido.\n")
            anulados += 1
            print("  anulado %-30s (de %s)" % (n, os.path.basename(f)))
print("Listo: %d .arena anulados en %s. Ahora: python Armar_Pk3.py armas" % (anulados, DEST))
