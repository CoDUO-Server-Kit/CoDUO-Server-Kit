"""Audita conflictos entre pk3 de la carpeta maestra del mod.
Regla de prioridad del juego (verificada con la consola del server): los pk3 de una carpeta se ordenan
comparando los nombres en MAYUSCULAS, de mayor a menor; el primero gana. Ej: "Zzz_mapa_ejemplo" > "MiMod_v1".
Uso: python Auditar_Conflictos.py [carpeta]   (por defecto ../maestro/MiMod)
"""
import os, sys, zipfile, hashlib
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
carpeta = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "maestro", "MiMod")
pk3s = sorted((f for f in os.listdir(carpeta) if f.lower().endswith(".pk3")), key=lambda n: n.upper(), reverse=True)
print("Orden de prioridad (1 = gana):")
for i, n in enumerate(pk3s, 1):
    print(f"  {i:2}. {n}")

files = defaultdict(list)   # ruta -> [(prioridad, pk3, md5)]
for prio, n in enumerate(pk3s):
    with zipfile.ZipFile(os.path.join(carpeta, n)) as z:
        for info in z.infolist():
            if info.is_dir() or info.file_size == 0:
                continue
            files[info.filename.lower()].append((prio, n, hashlib.md5(z.read(info.filename)).hexdigest()))

MOD = {"MiMod_v1.pk3", "MiMod_parche.pk3", "z_zzz_kit_hardline.pk3", "zzzzzz_kit_fixes.pk3", "z_zzz_kit_armas.pk3", "zzzzzz_kit_practica.pk3"}
importantes = (".gsc", "weapons/", ".menu", ".shader", "vehicles/", ".str", ".csv", ".cfg", "xmodel/", ".efx")
print("\nArchivos que un pk3 de MAPAS le pisa al MOD (contenido distinto):")
n_conf = 0
for ruta, lst in sorted(files.items()):
    if len(lst) < 2:
        continue
    lst.sort()
    ganador = lst[0]
    distintos = len({h for _, _, h in lst}) > 1
    mod_perdedores = [p for _, p, h in lst[1:] if p in MOD and h != ganador[2]]
    if distintos and ganador[1] not in MOD and mod_perdedores and ruta.startswith(importantes) or (distintos and ganador[1] not in MOD and mod_perdedores and ruta.endswith(importantes)):
        n_conf += 1
        print(f"  {ruta}\n      gana: {ganador[1]}   pisa a: {', '.join(mod_perdedores)}")
print(f"  total: {n_conf}")

print("\nOtros archivos repetidos con contenido distinto entre pk3 de mapas (informativo):")
n_otros = 0
for ruta, lst in sorted(files.items()):
    if len(lst) < 2 or not ruta.endswith(importantes) and not ruta.startswith(importantes):
        continue
    lst.sort()
    if len({h for _, _, h in lst}) > 1 and lst[0][1] not in MOD and not any(p in MOD for _, p, _ in lst):
        n_otros += 1
        if n_otros <= 40:
            print(f"  {ruta}: gana {lst[0][1]} sobre {', '.join(p for _, p, _ in lst[1:])}")
print(f"  total: {n_otros}")
