"""Suma las armas del mod eBus Hardline al mod el mod, sin pisar nada de el mod.

Genera maestro\\MiMod\\z_zzz_kit_hardline.pk3 con (correrlo DESPUES de Armar_Pk3.py armas: parte de sus menus):
  - Cada arma de Hardline con nombre propio hl_<arma> (weapons/mp/hl_bren_mp = la M4A1 de Hardline).
  - Sus modelos, animaciones, texturas, iconos, efectos y sonidos. Lo que choca con un archivo de el mod o
    del juego (mismo nombre, otro contenido) se renombra con hl_ (o, dentro de un modelo, con un nombre
    del mismo largo) para que las armas de el mod sigan viendose y sonando igual.
  - Sonidos: generic_mp_sound.csv de el mod + los alias hl_* (ese archivo lo cargan todos los mapas).
  - Scripts de el mod con parches minimos:
      _teams.gsc       precache de las hl_*, restrict() las deja elegir (cvar scr_allow_hardline, 1 por defecto)
                       y municion/granadas/nombre las tratan como el arma original de la que salen.
      _rank_gmi.gsc    municion con battle rank: idem.
      _bocoutility.gsc cargadores: idem.
      _kit_hl.gsc      (nuevo) lista de armas, precache y equivalencias.
  - Rachas de bajas Loki y Harrier (portadas de Hardline y reescritas, sin depender de scripts de Hardline):
      _kit_rachas.gsc, _kit_racha_loki.gsc, _kit_racha_harrier.gsc + armas hl_ac130_* (no elegibles en el menu),
      el Harrier AV-8B, overlays y sonidos. Se enganchan desde _kit_hl::precache() (primer frame del mapa) y
      _kit_hl::soldados() (cada ronda). Cvars scr_racha_* (ver el encabezado de _kit_rachas.gsc).
  - Menus de armas (los 4 bandos, espanol y por defecto): pestana HARDLINE con un boton por arma.

Uso:  python Armar_Hardline.py            (lee los 4 pk3 de Hardline de ..\\mods_terceros)
      python Armar_Hardline.py --salida <carpeta> --juego <carpeta del juego> --mods <carpeta> --maestro <carpeta>
"""
import argparse, collections, glob, io, os, re, sys, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
J = r"C:\Juegos\Call of Duty UO"                           # juego instalado (--juego)
MODS = os.path.join(ROOT, "mods_terceros")                  # pk3 de Hardline (--mods)
MAESTRO = os.path.join(ROOT, "maestro", "MiMod")      # pk3 del mod (--maestro)
SALIDA_PK3 = "z_zzz_kit_hardline.pk3"          # le gana a z_zzz_kit_armas (sus menus en espanol) y al mod base
MOD_PK3 = []                                                    # pk3 extra del mod base que esten en MODS (opcional)
VIEJOS = {SALIDA_PK3.lower()}                                   # no se lee a si mismo
HL_PK3 = ["z_ebus_hardline_main.pk3", "z_ebus_hardline_sound.pk3", "z_ebus_hardline_svr.pk3", "zz_ebus_hardline_weapons.pk3"]

# Opciones de carpetas (se leen antes de indexar los pk3)
_op = argparse.ArgumentParser(add_help=False)
for _o in ("--salida", "--juego", "--mods", "--maestro"):
    _op.add_argument(_o)
_args, _ = _op.parse_known_args()
J = _args.juego or J
MODS = _args.mods or MODS
MAESTRO = _args.maestro or MAESTRO

# Armas elegibles en el menu por categoria: (arma de Hardline, texto del boton). Sus modos alternativos
# (altWeapon) se suman solos. Sin pistolas, granadas, binoculares, AC-130 ni perro (etapas siguientes).
CATEGORIAS = [
    ("asalto", "Asalto", [
        ("bren_mp", "M4A1"), ("enfield_mp", "SCAR-H"), ("fg42_mp", "Steyr AUG"), ("kar98k_mp", "ARX-160"),
        ("m1carbine_mp", "CM-901"), ("m1garand_mp", "ACR"), ("mosin_nagant_mp", "Peacekeeper"), ("mp44_mp", "FAD"),
        ("mp44_semi_mp", "FN2000"), ("thompson_mp", "FAMAS"), ("dp28_mp", "SA-80")]),
    ("compactas", "Compactas", [
        ("mp40_mp", "Honey Badger"), ("bar_mp", "G36C SD"), ("gewehr43_mp", "MP7"), ("ppsh_mp", "MP5 SD"),
        ("sten_mp", "UMP-45"), ("sten_silenced_mp", "SC-2010")]),
    ("tirador", "Tirador", [
        # "Intervention 2" (intervention_sniper_mp) sacada el 27-10-2026: despues de cada disparo las tiras de la
        # ghillie del brazo derecho se deformaban (viene asi de Hardline; issue 2 del repo publico).
        ("springfield_mp", "Intervention"), ("kar98k_sniper_mp", "IA-2"),
        ("mosin_nagant_sniper_mp", "G-28"), ("svt40_mp", "Ballesta")]),
    ("pesadas", "Pesadas", [
        ("mg34_mp", "PKP Pecheneg"), ("minigun_mp", "Minigun"), ("bazooka_mp", "Bazooka"),
        ("panzerfaust_mp", "Panzerfaust"), ("panzerschreck_mp", "Panzerschreck")]),
]
ARMAS = [a for _, _, l in CATEGORIAS for a in l]
TIPO = {"asalto": "Fusil de asalto", "compactas": "Arma compacta", "tirador": "Arma de tirador", "pesadas": "Arma pesada"}
# Soldados modernos de Hardline por nacion (se elige uno al azar en cada aparicion). scr_hl_soldados 0 = los originales.
# Solo 2 por nacion: con 3-5 alpestra, lenin_square, mp_ponyri y mp_snowfield_a_a2 pasan el limite de modelos
# del motor (G_ModelIndex: overflow, probado 18-10-2026). Otros disponibles: us_shadow_co_assault, sas_recon,
# spetsnaz_engineer, spetsnaz_smg, spetsnaz_merc, militia_smg, bandits_smg, inner_circle_assault.
SOLDADOS = {
    "american": ["delta_assault", "spetsnaz_merc"],    # us_army_assault se veia muy blanco (cambiado 20-10-2026)
    "british": ["sas_assault", "sas_specops"],
    "russian": ["spetsnaz_assault", "spetsnaz_airborne"],
    "german": ["militia_assault", "bandits_assault"],
}
# Mapas donde Hardline se apaga solo (armas, soldados y rachas): ya estan cerca del limite de modelos y con las
# armas de Hardline lo pasan (probado 18-10-2026). Ahi se juega con el mod tal cual.
# alpestra, lenin_square, mp_ponyri y mp_snowfield_a_a2 pasan el limite con los soldados + el Harrier (sacarlos de aca
# solo despues de probar cada uno con publicar\..\scratchpad todos_los_mapas o un servidor local).
MAPAS_SIN_HL = ["mp_foy", "mp_nebelsbad", "alpestra", "lenin_square", "mp_ponyri", "mp_snowfield_a_a2"]
# Miniaturas para el menu (256x128 RGBA, fondo transparente): hardline_miniaturas\hl_<arma>.tga
MINIATURAS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hardline_miniaturas")
# Arma original de la que sale cada una (municion, granadas, clase). Las que no estan en el juego original
# se tratan como la mas parecida.
EQUIV = {"minigun_mp": "mg34_mp", "intervention_sniper_mp": "springfield_mp", "springfield_x2_mp": "springfield_mp"}

TEXTO = (".efx", ".csv", ".txt", ".str", ".shader")
IMAGEN = (".dds", ".tga", ".jpg")


# ------------------------------------------------------------------ indices de archivos
class Indice:
    """ruta en minusculas -> (crc, pk3, ruta real); gana el pk3 de mayor prioridad como en el juego."""

    def __init__(self, paths):
        self.d, self.z = {}, {}
        for p in sorted(paths, key=lambda x: os.path.basename(x).upper()):
            z = self.z[p] = zipfile.ZipFile(p)
            for i in z.infolist():
                if not i.is_dir():
                    self.d[i.filename.lower()] = (i.CRC, p, i.filename)

    def __contains__(self, k):
        return k.lower() in self.d

    def crc(self, k):
        return self.d[k.lower()][0]

    def leer(self, k):
        crc, p, real = self.d[k.lower()]
        return self.z[p].read(real)


def pk3s_mod():
    """Los pk3 del mod tal como van a quedar: maestro sin el mod v9/fix viejo + el mod v10/fix nuevo."""
    l = [os.path.join(MAESTRO, f) for f in os.listdir(MAESTRO) if f.lower().endswith(".pk3") and f.lower() not in VIEJOS]
    return l + [os.path.join(MODS, f) for f in MOD_PK3]


base = Indice(sorted(glob.glob(J + r"\main\*.pk3")) + sorted(glob.glob(J + r"\uo\*.pk3")))
tf = Indice(pk3s_mod())
hl = Indice([os.path.join(MODS, f) for f in HL_PK3])


def existe_fuera(k):
    return k in tf or k in base


def choca(k):
    """el archivo de Hardline tiene el mismo nombre que uno de el mod/juego con OTRO contenido."""
    for idx in (tf, base):
        if k in idx:
            return idx.crc(k) != hl.crc(k)
    return False


def igual_fuera(k):
    for idx in (tf, base):
        if k in idx:
            return idx.crc(k) == hl.crc(k)
    return False


salida = {}            # ruta -> bytes
avisos = []


def poner(ruta, datos):
    if ruta in salida and salida[ruta] != datos:
        raise SystemExit("dos contenidos distintos para " + ruta)
    if existe_fuera(ruta):
        raise SystemExit("BUG: se iba a pisar " + ruta)
    salida[ruta] = datos


def libre(ruta):
    return ruta.lower() not in salida and not existe_fuera(ruta) and ruta not in hl


def nombre_hl(ruta):
    """dir/archivo -> dir/hl_archivo (libre)."""
    d, f = ruta.rsplit("/", 1) if "/" in ruta else ("", ruta)
    for n in range(100):
        nuevo = (d + "/" if d else "") + ("hl_" if n == 0 else "hl%d_" % n) + f
        if libre(nuevo):
            return nuevo
    raise SystemExit("sin nombre libre para " + ruta)


def mismo_largo(ruta):
    """dir/archivo -> dir/hlchivo (mismo largo, para renombrar dentro de un binario)."""
    d, f = ruta.rsplit("/", 1)
    for pref in ["hl"] + ["h%d" % i for i in range(10)] + ["q%d" % i for i in range(10)]:
        nuevo = d + "/" + pref + f[len(pref):]
        if nuevo != ruta and libre(nuevo):
            return nuevo
    raise SystemExit("sin nombre del mismo largo para " + ruta)


# ------------------------------------------------------------------ archivos simples (anims, iconos, efectos)
hechos = {}


def buscar_hl(ruta):
    """ruta exacta o con otra extension de imagen (el juego busca .dds aunque diga .tga)."""
    if ruta in hl:
        return ruta.lower()
    raiz, ext = os.path.splitext(ruta)
    if ext.lower() in IMAGEN:
        for e in IMAGEN:
            if (raiz + e) in hl:
                return (raiz + e).lower()
    if not ext and (ruta + ".efx") in hl:
        return (ruta + ".efx").lower()
    return None


def archivo(ruta):
    """Incluye un archivo de Hardline (y lo que referencia). Devuelve la ruta a usar en la referencia."""
    ruta_l = ruta.lower()
    if ruta_l in hechos:
        return hechos[ruta_l]
    real = buscar_hl(ruta_l)
    if real is None or igual_fuera(real):
        hechos[ruta_l] = ruta                    # es del juego o de el mod, sin cambios
        return ruta
    datos = hl.leer(real)
    if real.endswith(TEXTO):
        datos = texto_refs(datos)
    destino = nombre_hl(real) if choca(real) else real
    poner(destino, datos)
    # la referencia conserva su extension original
    ref = destino if real == ruta_l else os.path.splitext(destino)[0] + os.path.splitext(ruta)[1]
    hechos[ruta_l] = ref
    return ref


def texto_refs(datos):
    """En un .efx u otro texto: incluye/renombra las rutas a archivos que trae."""
    t = datos.decode("latin-1")

    def rep(m):
        r = m.group(0)
        return archivo(r) if buscar_hl(r.lower()) else r
    t = re.sub(r"[A-Za-z0-9_@\-]+(?:/[A-Za-z0-9_@\-\.]+)+\.(?:dds|tga|jpg|efx)", rep, t)
    return t.encode("latin-1")


# ------------------------------------------------------------------ modelos (binarios)
def modelo(nombre):
    """xmodel/<nombre>: incluye partes, superficies y texturas. Devuelve el nombre a usar
    (algunas claves del arma ya traen el prefijo xmodel/: se respeta)."""
    pref = ""
    if nombre.lower().startswith("xmodel/"):
        pref, nombre = nombre[:7], nombre[7:]
    return pref + _modelo(nombre)


def _modelo(nombre):
    ruta = "xmodel/" + nombre.lower()
    if ruta in hechos:
        return hechos[ruta]
    if ruta not in hl or igual_fuera(ruta):
        hechos[ruta] = nombre
        return nombre
    datos = bytearray(hl.leer(ruta))
    for m in re.finditer(rb"[\x20-\x7e]{3,}", bytes(datos)):
        sl = m.group(0).decode().lower()
        if sl.endswith(IMAGEN):
            # texturas: skins/<nombre> o skins/<carpeta>@<nombre> (asi las guarda el motor)
            for k in [k for k in hl.d if k.startswith("skins/") and (k == "skins/" + sl or k.endswith("@" + sl))]:
                if k not in salida and not igual_fuera(k):
                    if choca(k):
                        avisos.append("textura que choca (queda la de el mod/juego): " + k)
                    else:
                        poner(k, hl.leer(k))
            continue
        dirs = ["xmodelparts/", "xmodelsurfs/"]
        grupo = [d for d in dirs if (d + sl) in hl]
        if not grupo:
            continue
        clave = "sub:" + sl
        if clave not in hechos:
            if any(choca(d + sl) for d in grupo):
                # mismo nombre nuevo para partes y superficies, del mismo largo (es un binario)
                nuevo = None
                for pref in ["hl"] + ["h%d" % i for i in range(10)] + ["q%d" % i for i in range(10)]:
                    cand = pref + sl[len(pref):]
                    if cand != sl and all(libre(d + cand) for d in dirs):
                        nuevo = cand
                        break
                if not nuevo:
                    raise SystemExit("sin nombre del mismo largo para " + sl)
                for d in grupo:
                    poner(d + nuevo, hl.leer(d + sl))
                hechos[clave] = nuevo
            else:
                for d in grupo:
                    if not igual_fuera(d + sl) and (d + sl) not in salida:
                        poner(d + sl, hl.leer(d + sl))
                hechos[clave] = sl
        if hechos[clave] != sl:
            datos[m.start():m.end()] = hechos[clave].encode()
    destino = nombre_hl(ruta) if choca(ruta) else ruta
    poner(destino, bytes(datos))
    hechos[ruta] = destino.split("/", 1)[1]
    return hechos[ruta]


# ------------------------------------------------------------------ sonidos
def csv_filas(datos):
    """(cabecera, {alias: [filas como dict]}) de un soundalias .csv."""
    cab, alias = None, collections.defaultdict(list)
    for linea in datos.decode("latin-1").splitlines():
        c = linea.split(",")
        if not c or not c[0] or c[0].startswith("#") or c[0].startswith('"#'):
            continue
        if cab is None:
            cab = [x.strip().lower() for x in c]
            continue
        alias[c[0].lower()].append(dict(zip(cab, c)))
    return cab, alias


hl_alias = collections.defaultdict(list)
for k in list(hl.d):
    if k.startswith("soundaliases/") and k.endswith(".csv"):
        cab, a = csv_filas(hl.leer(k))
        for n, filas in a.items():
            hl_alias[n] += filas
fuera_alias = collections.defaultdict(list)
for idx in (base, tf):
    for k in list(idx.d):
        if k.startswith("soundaliases/") and k.endswith(".csv"):
            cab, a = csv_filas(idx.leer(k))
            for n, filas in a.items():
                fuera_alias[n] = filas          # gana el de mayor prioridad


def firma(filas):
    return sorted(tuple(sorted((k, v) for k, v in f.items() if v)) for f in filas)


nuevos_alias = collections.OrderedDict()


def sonido(alias):
    a = alias.lower()
    if a not in hl_alias:
        return alias                                # alias del juego / el mod
    if a in fuera_alias and firma(fuera_alias[a]) == firma(hl_alias[a]):
        return alias
    nuevo = "hl_" + a
    if nuevo not in nuevos_alias:
        filas = []
        for f in hl_alias[a]:
            f = dict(f)
            f["name"] = nuevo
            arch = f.get("file", "")
            if arch:
                r = "sound/" + arch.lower()
                if r in hl and not igual_fuera(r):
                    if choca(r):
                        destino = "sound/hl/" + arch.lower()
                        poner(destino, hl.leer(r))
                        f["file"] = "hl/" + arch
                    elif r not in salida:
                        poner(r, hl.leer(r))
                elif r not in hl and not existe_fuera(r):
                    avisos.append("sonido inexistente %s (%s)" % (arch, alias))
            filas.append(f)
        nuevos_alias[nuevo] = filas
    return nuevo


# ------------------------------------------------------------------ armas
NUEVO = {}

# Sin retroceso, como las armas del mod base: retroceso (kick), dispersion (spread), balanceo (sway, bob) copiados
# de esta arma del mod (la M4: todo en 0). Se aplica a todas las armas de Hardline del menu y sus modos alternativos;
# no a las de las rachas (llevan "fijos"). REFERENCIA_SIN_RETROCESO = None deja el retroceso original de Hardline.
REFERENCIA_SIN_RETROCESO = "svt40_mp"

# Ajustes de balance por arma de Hardline (reemplazan el valor de su archivo; el menu de armas los muestra).
# Cuentas con la vida del servidor (kit_player_health 150) y el multiplicador por zona del juego
# (info/mp_lochit_dmgtable: cabeza 1.5, pecho 0.9, panza 0.8, brazos y piernas 0.4 a 0.6).
AJUSTES = {
    # Ballesta: 1 flecha en la cabeza (110 x 1.5 = 165) y 2 en el cuerpo (pecho 99, panza 88).
    # minDamagePercent 100 = no pierde dano con la distancia (si no, de lejos la cabeza no mataria de una).
    "svt40_mp": {"damage": "110", "minDamagePercent": "100"},
}
_SIN_RETROCESO = None


def sin_retroceso():
    global _SIN_RETROCESO
    if _SIN_RETROCESO is None:
        _SIN_RETROCESO = {}
        if REFERENCIA_SIN_RETROCESO:
            t = tf.leer("weapons/mp/" + REFERENCIA_SIN_RETROCESO).decode("latin-1").split("\\")
            for k, v in zip(t[1::2], t[2::2]):
                if re.search(r"(?i)kick|spread|sway|bob", k):
                    _SIN_RETROCESO[k.lower()] = v
            # claves que el arma de referencia no tiene pero Hardline si (dispersion apuntando agachado / cuerpo a tierra)
            for k in ("adsspreadducked", "adsspreadprone"):
                _SIN_RETROCESO.setdefault(k, _SIN_RETROCESO.get("adsspread", "0"))
    return _SIN_RETROCESO


def cargador(clave, v, kv):
    """clipName/ammoName de un arma de Hardline.
    - El motor exige el mismo tamano para un mismo cargador: no se comparten con las del juego (prefijo hl_).
    - El motor manda al jugador solo ~63 cargadores y ~63 municiones distintos (contando los del juego):
      con uno por arma, las ultimas en orden alfabetico (MP5-SD, UMP-45, SC-2010, ballesta, FAMAS) le
      llegaban vacias al jugador (recarga sin fin; la ballesta cambiaba a la pistola). Por eso las balas
      comparten cargador y municion segun el tamano del cargador (hl_c30 = todas las de 30), y los lanzadores
      comparten cargador (hl_p1) pero no municion (cada uno tiene su maximo)."""
    d = {kv[j].lower(): kv[j + 1] for j in range(0, len(kv) - 1, 2)}
    tam = d.get("clipsize", "0")
    if d.get("weapontype", "bullet").lower() == "bullet":
        return "hl_c" + tam
    return ("hl_p" + tam) if clave == "clipname" else ("hl_" + v)


def arma(w, fijos=None, cambios=None):
    """weapons/mp/<w> de Hardline -> weapons/mp/hl_<w>.
    fijos:   {clave: valor} que se ponen tal cual (algo del juego/el mod, no se busca en Hardline).
    cambios: {clave: valor} que reemplazan el valor de Hardline y despues se procesan como siempre."""
    if w in NUEVO:
        return NUEVO[w]
    NUEVO[w] = PREFIJO_ARMA + w
    t = hl.leer("weapons/mp/" + w).decode("latin-1").split("\\")
    if t[0] != "WEAPONFILE":
        raise SystemExit("formato raro en " + w)
    kv = t[1:]
    for i in range(0, len(kv) - 1, 2):
        k, v = kv[i], kv[i + 1]
        kl = k.lower()
        if fijos and k in fijos:
            kv[i + 1] = fijos[k]
            continue
        if fijos is None and kl in sin_retroceso():
            kv[i + 1] = sin_retroceso()[kl]
            continue
        if cambios and k in cambios:
            v = kv[i + 1] = cambios[k]
        if not v or v.lower() == "none":
            continue
        if kl in ("clipname", "ammoname"):
            kv[i + 1] = cargador(kl, v, kv)
        elif kl == "altweapon":
            kv[i + 1] = arma(v) if ("weapons/mp/" + v) in hl else v
        elif "model" in kl:
            kv[i + 1] = modelo(v)
        elif kl.endswith("anim"):
            kv[i + 1] = archivo("xanim/" + v).split("/", 1)[1]
        elif "sound" in kl:
            kv[i + 1] = sonido(v)
        elif "/" in v and buscar_hl(v.lower()):
            kv[i + 1] = archivo(v)
    sobran = set(fijos or {}) | set(cambios or {})
    sobran -= set(kv[0::2])
    if sobran:
        raise SystemExit("%s: claves que no estan en el arma: %s" % (w, sorted(sobran)))
    poner("weapons/mp/" + NUEVO[w],"\\".join(["WEAPONFILE"] + kv).encode("latin-1"))
    return NUEVO[w]


# ------------------------------------------------------------------ soldados
def personaje(nombre):
    """character/<nombre>.gsc de Hardline -> character/hl_<nombre>.gsc con sus modelos (renombrados si chocan)."""
    t = hl.leer("character/%s.gsc" % nombre).decode("latin-1")
    t = re.sub(r'"(xmodel/[^"]+)"', lambda m: '"%s"' % modelo(m.group(1)), t)
    t = t.replace("// THIS FILE IS AUTOGENERATED, DO NOT MODIFY", "// Soldado de Hardline (lo genera publicar\\Armar_Hardline.py)")
    poner("character/hl_%s.gsc" % nombre, t.encode("latin-1"))


def soldados():
    for nac, lista in SOLDADOS.items():
        for n in lista:
            personaje(n)
        casos = "".join("\tcase %d:\r\n\t\tcharacter\\hl_%s::main();\r\n\t\tbreak;\r\n" % (i, n) for i, n in enumerate(lista))
        pre = "".join("\tcharacter\\hl_%s::precache();\r\n" % n for n in lista)
        poner("mptype/hl_%s.gsc" % nac, ("// Soldados modernos de Hardline: %s\r\nmain()\r\n{\r\n\tswitch(randomint(%d))\r\n\t{\r\n%s\t}\r\n}\r\n\r\nprecache()\r\n{\r\n%s}\r\n"
                                          % (nac, len(lista), casos, pre)).encode("latin-1"))
    print("  soldados: %d personajes en 4 grupos" % sum(len(l) for l in SOLDADOS.values()))


def gsc_soldados():
    """funcion soldados() de _kit_hl: reemplaza el modelo de cada bando (la llama _teams::modeltype)."""
    def rama(var, lado, nacs):
        r = "\tswitch(game[\"%s\"])\r\n\t{\r\n" % lado
        for nac in nacs:
            r += "\tcase \"%s\":\r\n\t\tmptype\\hl_%s::precache();\r\n\t\tgame[\"%s_model\"] = mptype\\hl_%s::main;\r\n\t\tbreak;\r\n" % (nac, nac, lado, nac)
        return r + "\t}\r\n"
    # modeltype() corre en cada ronda (precache() en sd/bas/ctf solo en la primera): de aca arrancan las rachas
    rachas = ("\t// rachas: en sd/bas/ctf precache() corre solo en la primera ronda; esto las engancha en todas\r\n"
              "\tmaps\\mp\\gametypes\\_kit_rachas::kit_arrancar();\r\n") if RACHAS_ARMAS else ""
    return ("\r\n// Soldados modernos de Hardline en vez de los de la Segunda Guerra (scr_hl_soldados 0 = originales)\r\n"
            "soldados()\r\n{\r\n\tif(apagado())\r\n\t\treturn;\r\n" + rachas + "\tif(getcvar(\"scr_hl_soldados\") == \"0\")\r\n\t\treturn;\r\n"
            + rama("allies", "allies", ["american", "british", "russian"]) + rama("axis", "axis", ["german"]) + "}\r\n")

# ------------------------------------------------------------------ scripts
def gsc_kit_hl(todas):
    # las armas de las rachas no van aca: las precachea _kit_rachas (solo si estan prendidas) y no tienen que
    # pasar por esHL(), si no restrict() dejaria pedirlas con un scriptMenuResponse a mano
    pre = "\n".join('\tprecacheItem("%s");' % n for n in todas if n not in RACHAS_ARMAS.values())
    casos = "\n".join('\tcase "%s": return "%s";' % (NUEVO[w], EQUIV.get(w, w)) for w in NUEVO if w not in RACHAS_ARMAS)
    if RACHAS_ARMAS:
        pre += "\n\tmaps\\mp\\gametypes\\_kit_rachas::init();\t// rachas Loki/Harrier (precache + hilos)"
    return ("""// Armas de Hardline sumadas a el mod (lo genera publicar\\Armar_Hardline.py: no editar a mano)

precache()
{
	if(apagado())
		return;
%s
}

// Mapas donde Hardline no entra en el limite de modelos del motor: se juega con el mod tal cual
apagado()
{
	switch(getcvar("mapname"))
	{
%s
		return true;
	}
	return false;
}

// Arma original equivalente (municion, granadas, clase). Para las que no son hl_* devuelve lo mismo.
base(w)
{
	if(!isDefined(w))
		return w;
	switch(w)
	{
%s
	}
	return w;
}

esHL(w)
{
	if(!isDefined(w))
		return false;
	return base(w) != w;
}
""" % (pre, "".join('\tcase "%s":\n' % m for m in MAPAS_SIN_HL), casos)).replace("\n", "\r\n") + gsc_soldados()


def parchar_switch(t, funciones, archivo_):
    """En esas funciones: switch(X) -> switch(maps\\mp\\gametypes\\_kit_hl::base(X))."""
    n = 0
    for fn in funciones:
        i = t.find("\n" + fn + "(")
        if i < 0:
            raise SystemExit("%s: no encuentro la funcion %s" % (archivo_, fn))
        j = t.find("\n}", i)
        cuerpo = t[i:j]
        nuevo, k = re.subn(r"switch\s*\(\s*([A-Za-z_][A-Za-z0-9_\.]*)\s*\)", r"switch(maps\\mp\\gametypes\\_kit_hl::base(\1))", cuerpo)
        if k == 0:
            raise SystemExit("%s: %s no tiene switch" % (archivo_, fn))
        t = t[:i] + nuevo + t[j:]
        n += k
    return t, n


def una_vez(t, viejo, nuevo, archivo_):
    if t.count(viejo) != 1:
        raise SystemExit("%s: esperaba 1 coincidencia de %r y hay %d" % (archivo_, viejo[:60], t.count(viejo)))
    return t.replace(viejo, nuevo)


def scripts():
    r = "maps/mp/gametypes/_teams.gsc"
    t = tf.leer(r).decode("latin-1")
    t = re.sub(r"(\nprecache\(\)\s*\{)", r"\1\r\n\tmaps\\mp\\gametypes\\_kit_hl::precache();", t, count=1)
    if "_kit_hl::precache" not in t:
        raise SystemExit("_teams.gsc: no encontre precache()")
    t = re.sub(r"(\nrestrict\(response\)\s*\{)", lambda m: m.group(1) + (
        "\r\n\t// Armas de Hardline (hl_*): se eligen desde la pestana HARDLINE; scr_allow_hardline 0 las apaga"
        "\r\n\tif(maps\\mp\\gametypes\\_kit_hl::esHL(response))\r\n\t{"
        "\r\n\t\tif(getcvar(\"scr_allow_hardline\") == \"0\" || maps\\mp\\gametypes\\_kit_hl::apagado())\r\n\t\t{"
        "\r\n\t\t\tself iprintln(\"Las armas Hardline no estan disponibles en este mapa\");"
        "\r\n\t\t\treturn \"restricted\";\r\n\t\t}\r\n\t\treturn response;\r\n\t}"), t, count=1)
    if "_kit_hl::esHL" not in t:
        raise SystemExit("_teams.gsc: no encontre restrict()")
    i = t.find("\nmodeltype()")
    if i < 0:
        raise SystemExit("_teams.gsc: no encontre modeltype()")
    j = t.find("\n}", i)
    t = t[:j] + "\r\n\tmaps\\mp\\gametypes\\_kit_hl::soldados();\t// soldados modernos" + t[j:]
    t, n = parchar_switch(t, ["getWeaponBasedSmokeGrenadeCount", "getWeaponBasedGrenadeCount", "isPistolOrGrenade",
                              "purchase_ammo", "getWeaponName"], r)
    poner_script(r, t)
    r = "maps/mp/gametypes/_rank_gmi.gsc"
    t, n2 = parchar_switch(tf.leer(r).decode("latin-1"), ["GetGunAmmo"], r)
    poner_script(r, t)
    r = "maps/mp/gametypes/_bocoutility.gsc"
    t, n3 = parchar_switch(tf.leer(r).decode("latin-1"), ["getWeaponClip", "getWeaponClipB"], r)
    poner_script(r, t)
    print("  scripts: %d + %d + %d switch apuntados a _kit_hl::base" % (n, n2, n3))


def poner_script(ruta, t):
    salida[ruta] = t.encode("latin-1")             # pisa a el mod a proposito (z_ > T-)


# ------------------------------------------------------------------ rachas (Loki y Harrier)
# Prefijo de las armas de Hardline. Va DESPUES de todas las armas del juego en el alfabeto: el servidor de Linux
# numera las armas en orden alfabetico y su playeranim.script solo acepta las primeras; con "hl_" las armas originales
# (kar98k_sniper_mp...) se corrian de numero y el servidor no arrancaba ("unknown token", 18-10-2026).
PREFIJO_ARMA = "zhl_"
# Armas del AC-130 de Hardline -> zhl_ac130_*. Son 3 archivos de arma (limite del motor: 127 en total).
# Se arreglan las referencias que en Hardline no existen: proyectil, iconos, overlays, sonidos; y las manos,
# el modelo y la vista se fijan a los del juego (no se copia el viewmodel_hands_new de Hardline).
RACHAS_ARMAS = {}          # arma de Hardline -> nombre nuevo (lo llena rachas())
RACHAS_NAVE = "xmodel/hardline_a10_thunderbolt"     # pese al nombre es el AV-8B Harrier (zz_ebus_hardline_weapons)
RACHAS_GRANO = "gfx/swm/ac130_overlay_grain.dds"


def rachas():
    """Armas, modelo, overlay y alias de las rachas; devuelve los nombres que usan los scripts."""
    comunes = {"gunModel": "viewmodel_kar98k", "handModel": "viewmodel_hands_new", "worldModel": "xmodel/weapon_kAr98",
               "projectileModel": "xmodel/weapon_panzerfaust_rocket",
               "hudIcon": "gfx/icons/hud@bazooka.dds", "killIcon": "gfx/icons/hud@bazooka.dds"}
    # disparo del 25 mm: el mismo de la minigun de Hardline (ya va en el pk3); 40/105: los cohetes del juego
    t = hl.leer("weapons/mp/minigun_mp").decode("latin-1").split("\\")
    tiro25 = sonido(dict(zip(t[1::2], t[2::2]))["fireSound"])
    por_arma = {
        "ac130_25mm_mp": ({"fireSound": tiro25}, "25mm"),
        "ac130_40mm_mp": ({"fireSound": "weap_bazooka_fire", "reloadSound": "weap_panzerfaust_reload",
                           "rechamberSound": ""}, "40mm"),
        "ac130_105mm_mp": ({"fireSound": "weap_panzerfaust_fire", "projectileSoundBlend1": "weap_panzerfaust_projectile",
                            "projectileSoundBlend2": "weap_panzerfaust_projectile"}, "105mm"),
    }
    for w, (snd, cal) in por_arma.items():
        fijos = dict(comunes)
        fijos.update(snd)
        overlay = "gfx/swm/ac130_overlay_%s.dds" % cal                 # existe en z_ebus_hardline_main
        RACHAS_ARMAS[w] = arma(w, fijos=fijos, cambios={"adsOverlayShader": overlay, "adsOverlayWidth": "640",
                                                        "adsOverlayHeight": "480"})
    for a in ("weap_bazooka_fire", "weap_panzerfaust_reload", "weap_panzerfaust_fire", "weap_panzerfaust_projectile"):
        if a not in fuera_alias:
            raise SystemExit("rachas: falta el alias del juego " + a)
    for r in ("xmodel/viewmodel_kar98k", "xmodel/viewmodel_hands_new", "xmodel/weapon_kar98",
              "xmodel/weapon_panzerfaust_rocket", "gfx/icons/hud@bazooka.dds"):
        if not existe_fuera(r):
            raise SystemExit("rachas: falta en el juego " + r)
    nombres = {
        "A25": RACHAS_ARMAS["ac130_25mm_mp"], "A40": RACHAS_ARMAS["ac130_40mm_mp"], "A105": RACHAS_ARMAS["ac130_105mm_mp"],
        "NAVE": modelo(RACHAS_NAVE), "GRANO": archivo(RACHAS_GRANO),
        "SND_LOKI": sonido("streak04_ready"), "SND_HARRIER": sonido("streak05_ready"),
        "SND_LOOP": sonido("vehicle_harrier_loop"),
    }
    # en el csv de Hardline los streakNN_ready tienen volumen 0 (no se oirian): van a 1
    for a in (nombres["SND_LOKI"], nombres["SND_HARRIER"]):
        for f in nuevos_alias.get(a, []):
            for c in ("vol_min", "vol_max"):
                if f.get(c, "") in ("0", "0.0"):
                    f[c] = "1"
    if nombres["NAVE"].lower() not in salida:
        raise SystemExit("rachas: no se incluyo el modelo del Harrier")
    if nombres["GRANO"].lower() not in salida:
        raise SystemExit("rachas: no se incluyo " + RACHAS_GRANO)
    print("  rachas: %d armas (%s), Harrier %s" % (len(RACHAS_ARMAS), ", ".join(sorted(RACHAS_ARMAS.values())), nombres["NAVE"]))
    return nombres


def gsc_rachas(nombres):
    """Los 3 scripts de las rachas (autocontenidos: solo builtins del motor y funciones de estos archivos)."""
    def armar(t):
        for k, v in nombres.items():
            t = t.replace("@@%s@@" % k, v)
        if "@@" in t:
            raise SystemExit("rachas: quedo un @@ sin reemplazar")
        return t.replace("\r\n", "\n").replace("\n", "\r\n").encode("latin-1")
    poner("maps/mp/gametypes/_kit_rachas.gsc", armar(GSC_RACHAS))
    poner("maps/mp/gametypes/_kit_racha_loki.gsc", armar(GSC_LOKI))
    poner("maps/mp/gametypes/_kit_racha_harrier.gsc", armar(GSC_HARRIER))


GSC_RACHAS = r'''// Rachas de bajas LOKI y HARRIER (portadas de eBus Hardline y reescritas para el mod)
// Lo genera publicar\Armar_Hardline.py: no editar a mano.
//
// Cvars (se leen al empezar cada mapa/ronda; las armas se precachean solo si la racha esta prendida
// al cargar el mapa):
//   scr_racha_loki            bajas seguidas (en una misma vida) para el Loki     0   (0 = apagado; 5 recomendado)
//   scr_racha_harrier         bajas seguidas para el Harrier                       7   (0 = apagado)
//   scr_racha_loki_tiempo     segundos que dura el Loki                            20
//   scr_racha_harrier_tiempo  segundos que dura el Harrier                         30
//   scr_racha_proteger        1 = no recibe dano mientras esta en el aire          1
// Solo cuentan bajas de enemigos (no suicidio, ni companeros, ni el mundo, ni las hechas con una racha).
// La racha ganada se guarda hasta usarla o morir; si llega al Harrier reemplaza al Loki sin usar.
// Activacion: mantener USAR 1,5 s quieto, en el piso, fuera de vehiculos y sin cambiar de arma.

// Primer frame del mapa (desde _kit_hl::precache): todo el precache, despues los hilos.
init()
{
	kit_leerCvars();
	if(level.kit_loki > 0)
	{
		precacheItem("@@A25@@");
		precacheItem("@@A40@@");
		precacheItem("@@A105@@");
		game["kit_pre_loki"] = true;
	}
	if(level.kit_harrier > 0)
	{
		precacheItem("@@A40@@");
		precacheModel("@@NAVE@@");
		precacheShader("@@GRANO@@");
		game["kit_pre_harrier"] = true;
	}
	if(level.kit_loki > 0 || level.kit_harrier > 0)
	{
		precacheShader("white");
		precacheShader("black");
	}
	kit_arrancar();
}

// Cada ronda (desde _kit_hl::soldados, que llama _teams::modeltype). Una sola vez por ronda.
kit_arrancar()
{
	if(isdefined(level.kit_arrancado))
		return;
	level.kit_arrancado = true;
	level thread kit_enganchar();
}

kit_leerCvars()
{
	level.kit_loki = kit_cvardef("scr_racha_loki", 0, 0, 100, "int");	// apagado por ahora (pedido 18-10-2026)
	level.kit_harrier = kit_cvardef("scr_racha_harrier", 7, 0, 100, "int");
	level.kit_loki_tiempo = kit_cvardef("scr_racha_loki_tiempo", 20, 5, 120, "int");
	level.kit_harrier_tiempo = kit_cvardef("scr_racha_harrier_tiempo", 30, 5, 120, "int");
	level.kit_proteger = kit_cvardef("scr_racha_proteger", 1, 0, 1, "int");
}

// Copia de _awe::cvardef (acepta scr_x_<gametype> y scr_x_<mapa>)
kit_cvardef(nombre, defecto, minimo, maximo, tipo)
{
	otro = nombre + "_" + getcvar("g_gametype");
	if(getcvar(otro) != "")
		nombre = otro;
	otro = nombre + "_" + getcvar("mapname");
	if(getcvar(otro) != "")
		nombre = otro;
	if(getcvar(nombre) == "")
		valor = defecto;
	else if(tipo == "float")
		valor = getcvarfloat(nombre);
	else
		valor = getcvarint(nombre);
	if(valor < minimo)
		valor = minimo;
	if(valor > maximo)
		valor = maximo;
	return valor;
}

// Espera un frame (el gametype y AWE ya pusieron sus callbacks) y los envuelve guardando los originales.
kit_enganchar()
{
	wait 0.05;
	kit_leerCvars();
	if(!isdefined(game["kit_pre_loki"]))
		level.kit_loki = 0;			// prendida a mitad de mapa: sus armas no estan precacheadas
	if(!isdefined(game["kit_pre_harrier"]))
		level.kit_harrier = 0;
	if(level.kit_loki <= 0 && level.kit_harrier <= 0)
		return;
	if(!isdefined(level.callbackPlayerKilled) || !isdefined(level.callbackPlayerDamage) || !isdefined(level.callbackPlayerDisconnect))
		return;
	level.kit_muerte_original = level.callbackPlayerKilled;
	level.callbackPlayerKilled = ::kit_PlayerKilled;
	level.kit_dano_original = level.callbackPlayerDamage;
	level.callbackPlayerDamage = ::kit_PlayerDamage;
	level.kit_salida_original = level.callbackPlayerDisconnect;
	level.callbackPlayerDisconnect = ::kit_PlayerDisconnect;
}

// ------------------------------------------------------------------ callbacks envueltos
kit_PlayerKilled(eInflictor, attacker, iDamage, sMeansOfDeath, sWeapon, vDir, sHitLoc)
{
	// antes que el gametype/AWE: saca las armas del AC-130 (si no, se tirarian al piso) y limpia todo
	self kit_alMorir();
	if(isdefined(attacker) && isPlayer(attacker) && attacker != self)
	{
		if(attacker.sessionstate == "playing" && !isdefined(attacker.kit_enracha))
		{
			if(self.sessionteam == "none" || attacker.sessionteam != self.sessionteam)
				attacker kit_sumarKill();
		}
	}
	[[level.kit_muerte_original]](eInflictor, attacker, iDamage, sMeansOfDeath, sWeapon, vDir, sHitLoc);
}

kit_PlayerDamage(eInflictor, eAttacker, iDamage, iDFlags, sMeansOfDeath, sWeapon, vPoint, vDir, sHitLoc)
{
	if(isdefined(self.kit_enracha))
	{
		if(sMeansOfDeath == "MOD_FALLING" || sMeansOfDeath == "MOD_TRIGGER_HURT" || level.kit_proteger == 1)
			return;
	}
	else if(sMeansOfDeath == "MOD_FALLING" && isdefined(self.kit_sincaida) && getTime() < self.kit_sincaida)
		return;
	[[level.kit_dano_original]](eInflictor, eAttacker, iDamage, iDFlags, sMeansOfDeath, sWeapon, vPoint, vDir, sHitLoc);
}

kit_PlayerDisconnect()
{
	self notify("kit_racha_salir");
	self kit_borrarHud();
	self kit_borrarEntidades();
	[[level.kit_salida_original]]();
}

// ------------------------------------------------------------------ conteo y aviso
kit_sumarKill()
{
	if(!isdefined(self.kit_racha))
		self.kit_racha = 0;
	self.kit_racha++;
	n = self.kit_racha;
	if(level.kit_harrier > 0 && n == level.kit_harrier)
		self kit_otorgar("harrier");
	else if(level.kit_loki > 0 && n == level.kit_loki)
	{
		if(!isdefined(self.kit_lista) || self.kit_lista != "harrier")
			self kit_otorgar("loki");
	}
}

kit_otorgar(tipo)
{
	self.kit_lista = tipo;
	if(tipo == "loki")
	{
		self iprintlnbold("Racha: LOKI lista - mantene [USAR] 1,5 s");
		self playLocalSound("@@SND_LOKI@@");
	}
	else
	{
		self iprintlnbold("Racha: HARRIER listo - mantene [USAR] 1,5 s");
		self playLocalSound("@@SND_HARRIER@@");
	}
	if(!isdefined(self.kit_esperando))
		self thread kit_esperarActivacion();
}

// ------------------------------------------------------------------ activacion (USAR 1,5 s)
kit_esperarActivacion()
{
	self endon("kit_racha_muerte");
	self endon("kit_racha_salir");
	self.kit_esperando = true;
	while(isdefined(self.kit_lista))
	{
		wait 0.05;
		if(!self useButtonPressed())
			continue;
		if(self kit_puedeActivar(true) && self kit_mantenerUsar())
		{
			z = self kit_cielo(self.origin, 1500);
			if(!isdefined(z))
				self iprintln("Necesitas cielo abierto arriba tuyo para usar la racha");
			else
			{
				tipo = self.kit_lista;
				self.kit_lista = undefined;
				if(tipo == "loki")
					self maps\mp\gametypes\_kit_racha_loki::loki(z);
				else
					self maps\mp\gametypes\_kit_racha_harrier::harrier(z);
			}
		}
		while(isAlive(self) && self useButtonPressed())
			wait 0.05;
	}
	self.kit_esperando = undefined;
}

kit_puedeActivar(avisar)
{
	if(!isAlive(self) || self.sessionstate != "playing" || isdefined(self.kit_enracha))
		return false;
	if(isdefined(self.awe_usingturret) || isdefined(self.awe_carryingturret) || isdefined(self.awe_pickingturret) || isdefined(self.awe_placingturret) || isdefined(self.awe_isparachuting) || isdefined(self.progressbar))
		return false;
	if(self isInVehicle())
		return false;
	if(!self isOnGround())
	{
		if(avisar)
			self iprintln("Para usar la racha tenes que estar en el piso");
		return false;
	}
	return true;
}

kit_mantenerUsar()
{
	pos = self.origin;
	arma = self getCurrentWeapon();
	total = 30;			// 30 frames = 1,5 s
	self iprintln("Activando racha... no te muevas");
	ok = true;
	for(n = 0; n < total; n++)
	{
		self kit_barra(n, total);
		wait 0.05;
		if(!self useButtonPressed() || !self kit_puedeActivar(false))
		{
			ok = false;
			break;
		}
		if(self getCurrentWeapon() != arma || distance(self.origin, pos) > 16)
		{
			self iprintln("Racha cancelada");
			ok = false;
			break;
		}
	}
	self kit_borrarBarra();
	return ok;
}

kit_barra(n, total)
{
	if(!isdefined(self.kit_hud_fondo))
	{
		self.kit_hud_fondo = newClientHudElem(self);
		self.kit_hud_fondo.archived = false;
		self.kit_hud_fondo.x = 320;
		self.kit_hud_fondo.y = 330;
		self.kit_hud_fondo.alignX = "center";
		self.kit_hud_fondo.alignY = "middle";
		self.kit_hud_fondo.alpha = 0.5;
		self.kit_hud_fondo setShader("black", 104, 12);
	}
	if(!isdefined(self.kit_hud_barra))
	{
		self.kit_hud_barra = newClientHudElem(self);
		self.kit_hud_barra.archived = false;
		self.kit_hud_barra.x = 270;
		self.kit_hud_barra.y = 330;
		self.kit_hud_barra.alignX = "left";
		self.kit_hud_barra.alignY = "middle";
		self.kit_hud_barra.alpha = 0.9;
		self.kit_hud_barra.sort = 1;
	}
	ancho = (int)((n + 1) * 100 / total);
	if(ancho < 1)
		ancho = 1;
	self.kit_hud_barra setShader("white", ancho, 8);
}

kit_borrarBarra()
{
	if(isdefined(self.kit_hud_barra))
		self.kit_hud_barra destroy();
	if(isdefined(self.kit_hud_fondo))
		self.kit_hud_fondo destroy();
	self.kit_hud_barra = undefined;
	self.kit_hud_fondo = undefined;
}

// ------------------------------------------------------------------ comun a Loki y Harrier
// Altura z para la racha sobre pos (cielo abierto, al menos 384 arriba) o undefined.
kit_cielo(pos, maximo)
{
	arriba = pos[2] + maximo;
	if(isdefined(level.awe_vMax) && arriba > level.awe_vMax[2] - 32)
		arriba = level.awe_vMax[2] - 32;
	tr = bulletTrace(pos + (0, 0, 64), (pos[0], pos[1], arriba), false, self);
	z = tr["position"][2] - 48;
	if(z - pos[2] < 384)
		return undefined;
	return z;
}

// Punto en el piso cerca de pos (para bajarlo sin quedar en el aire ni enterrado).
kit_puntoSeguro(pos)
{
	tr = bulletTrace(pos + (0, 0, 32), pos - (0, 0, 256), false, self);
	if(tr["fraction"] < 1)
		return tr["position"] + (0, 0, 1);
	return pos;
}

kit_dentroMapa(v)
{
	if(!isdefined(level.awe_vMin) || !isdefined(level.awe_vMax))
		return v;
	x = v[0];
	y = v[1];
	if(x < level.awe_vMin[0] + 64)
		x = level.awe_vMin[0] + 64;
	if(x > level.awe_vMax[0] - 64)
		x = level.awe_vMax[0] - 64;
	if(y < level.awe_vMin[1] + 64)
		y = level.awe_vMin[1] + 64;
	if(y > level.awe_vMax[1] - 64)
		y = level.awe_vMax[1] - 64;
	return (x, y, v[2]);
}

kit_slots()
{
	s = [];
	s[0] = "primary";
	s[1] = "primaryb";
	s[2] = "pistol";
	s[3] = "grenade";
	s[4] = "smokegrenade";
	s[5] = "satchel";
	s[6] = "binocular";
	return s;
}

kit_guardarArmas()
{
	s = kit_slots();
	self.kit_arma = [];
	self.kit_municion = [];
	self.kit_cargador = [];
	for(i = 0; i < s.size; i++)
	{
		w = self getWeaponSlotWeapon(s[i]);
		if(!isdefined(w) || w == "")
			w = "none";
		self.kit_arma[s[i]] = w;
		if(w != "none")
		{
			self.kit_municion[s[i]] = self getWeaponSlotAmmo(s[i]);
			self.kit_cargador[s[i]] = self getWeaponSlotClipAmmo(s[i]);
		}
	}
}

kit_restaurarArmas(cambiar)
{
	if(!isdefined(self.kit_arma))
		return;
	s = kit_slots();
	for(i = 0; i < s.size; i++)
	{
		w = self.kit_arma[s[i]];
		if(!isdefined(w))
			w = "none";
		self setWeaponSlotWeapon(s[i], w);
		if(w != "none")
		{
			self setWeaponSlotAmmo(s[i], self.kit_municion[s[i]]);
			self setWeaponSlotClipAmmo(s[i], self.kit_cargador[s[i]]);
		}
	}
	if(cambiar)
	{
		if(self.kit_arma["primary"] != "none")
			self switchToWeapon(self.kit_arma["primary"]);
		else if(self.kit_arma["primaryb"] != "none")
			self switchToWeapon(self.kit_arma["primaryb"]);
		else if(self.kit_arma["pistol"] != "none")
			self switchToWeapon(self.kit_arma["pistol"]);
	}
	self.kit_arma = undefined;
	self.kit_municion = undefined;
	self.kit_cargador = undefined;
}

// Lo llaman loki()/harrier() despues de crear su entidad (self.kit_ancla o self.kit_nave).
kit_entrar(tipo)
{
	self kit_guardarArmas();
	self.kit_volver = self.origin;
	self.kit_volver_ang = self.angles;
	self.kit_enracha = tipo;
	self hide();
	self takeAllWeapons();
	self setClientCvar("cg_drawgun", "0");
	if(tipo == "loki")
		iprintln(self.name + "^7 pidio un ^3LOKI");
	else
		iprintln(self.name + "^7 pidio un ^3HARRIER");
}

kit_hudTiempo(seg)
{
	self.kit_hud_tiempo = newClientHudElem(self);
	self.kit_hud_tiempo.archived = false;
	self.kit_hud_tiempo.x = 320;
	self.kit_hud_tiempo.y = 70;
	self.kit_hud_tiempo.alignX = "center";
	self.kit_hud_tiempo.alignY = "middle";
	self.kit_hud_tiempo.fontScale = 2;
	self.kit_hud_tiempo.sort = 2;
	self.kit_hud_tiempo setValue(seg);
}

kit_hudTiempoValor(seg)
{
	if(isdefined(self.kit_hud_tiempo))
		self.kit_hud_tiempo setValue(seg);
}

kit_borrarHud()
{
	self kit_borrarBarra();
	if(isdefined(self.kit_hud_tiempo))
		self.kit_hud_tiempo destroy();
	if(isdefined(self.kit_hud_grano))
		self.kit_hud_grano destroy();
	self.kit_hud_tiempo = undefined;
	self.kit_hud_grano = undefined;
}

kit_borrarEntidades()
{
	if(isdefined(self.kit_nave))
	{
		self.kit_nave stopLoopSound();
		self.kit_nave delete();
	}
	if(isdefined(self.kit_ancla))
		self.kit_ancla delete();
	self.kit_nave = undefined;
	self.kit_ancla = undefined;
}

// Fin normal (tiempo, MELEE, intermision): lo baja a un punto seguro y le devuelve sus armas.
kit_salir()
{
	volver = (isAlive(self) && self.sessionstate == "playing");
	self kit_terminar(volver);
}

kit_terminar(volver)
{
	self kit_borrarHud();
	if(!isdefined(self.kit_enracha))
		return;
	self unlink();
	self kit_borrarEntidades();
	if(volver && isdefined(self.kit_volver))
	{
		self.kit_sincaida = getTime() + 3000;		// sin dano por caida 3 s despues de bajar
		self setOrigin(self kit_puntoSeguro(self.kit_volver));
		self setPlayerAngles(self.kit_volver_ang);
	}
	self show();
	self setClientCvar("cg_drawgun", "1");
	self takeAllWeapons();
	self kit_restaurarArmas(volver);
	self.kit_enracha = undefined;
	self.kit_volver = undefined;
	self.kit_volver_ang = undefined;
}

// Muerte (dentro del callback, antes del original): nada queda colgado ni en el piso.
kit_alMorir()
{
	enracha = isdefined(self.kit_enracha);
	self notify("kit_racha_muerte");
	self kit_terminar(false);
	self.kit_racha = 0;
	self.kit_lista = undefined;
	self.kit_esperando = undefined;
	self.kit_sincaida = undefined;
	if(enracha)
		level thread kit_borrarArmasTiradas();
}

// Red de seguridad: si igual se tiro al piso un arma del AC-130, se borra.
kit_borrarArmasTiradas()
{
	for(vuelta = 0; vuelta < 3; vuelta++)
	{
		kit_borrarClase("weapon_@@A25@@");
		kit_borrarClase("weapon_@@A40@@");
		kit_borrarClase("weapon_@@A105@@");
		wait 0.25;
	}
}

kit_borrarClase(clase)
{
	l = getentarray(clase, "classname");
	for(i = 0; i < l.size; i++)
		l[i] delete();
}
'''

GSC_LOKI = r'''// Racha LOKI: camara satelital con los tres canones del AC-130 (25 / 40 / 105 mm) apuntando para abajo.
// Reescrita de eBus Hardline (maps/mp/killstreaks/_loki.gsc); lo genera publicar\Armar_Hardline.py.
// Dura scr_racha_loki_tiempo segundos de verdad. USAR = mover la camara hacia donde se mira (hasta 1500
// unidades del punto de partida), mantener MELEE 1 s = salir antes. La limpieza por muerte/desconexion
// la hace _kit_rachas (kit_alMorir / kit_PlayerDisconnect).

loki(z)
{
	self endon("kit_racha_muerte");
	self endon("kit_racha_salir");

	inicio = (self.origin[0], self.origin[1], z);
	cam = spawn("script_model", inicio);
	cam.angles = (0, self.angles[1], 0);
	self.kit_ancla = cam;
	self maps\mp\gametypes\_kit_rachas::kit_entrar("loki");

	self setOrigin(inicio);
	self linkto(cam);
	self setPlayerAngles((80, self.kit_volver_ang[1], 0));

	self setWeaponSlotWeapon("primary", "@@A25@@");
	self setWeaponSlotAmmo("primary", 999);
	self setWeaponSlotClipAmmo("primary", 999);
	self setWeaponSlotWeapon("primaryb", "@@A40@@");
	self setWeaponSlotAmmo("primaryb", 999);
	self setWeaponSlotClipAmmo("primaryb", 3);
	self setWeaponSlotWeapon("pistol", "@@A105@@");
	self setWeaponSlotAmmo("pistol", 999);
	self setWeaponSlotClipAmmo("pistol", 999);
	self switchToWeapon("@@A25@@");

	tiempo = level.kit_loki_tiempo;
	self maps\mp\gametypes\_kit_rachas::kit_hudTiempo(tiempo);
	self iprintlnbold("LOKI: cambia de arma para elegir 25 / 40 / 105 mm");
	self iprintln("USAR = mover la camara  -  MELEE 1 s = salir");

	total = tiempo * 20;
	melee = 0;
	for(i = 1; i <= total; i++)
	{
		wait 0.05;
		if(!isAlive(self) || self.sessionstate != "playing" || !isdefined(cam))
			break;
		if(i % 20 == 0)
			self maps\mp\gametypes\_kit_rachas::kit_hudTiempoValor(tiempo - (int)(i / 20));
		if(self meleeButtonPressed())
		{
			melee++;
			if(melee >= 20)
				break;
		}
		else
			melee = 0;
		if(self useButtonPressed())
		{
			dir = anglesToForward((0, self.angles[1], 0));
			destino = cam.origin + (dir[0] * 20, dir[1] * 20, 0);
			destino = maps\mp\gametypes\_kit_rachas::kit_dentroMapa(destino);
			if(distance((destino[0], destino[1], 0), (inicio[0], inicio[1], 0)) <= 1500)
			{
				tr = bulletTrace(cam.origin, destino, false, self);
				if(tr["fraction"] == 1)
					cam moveTo(destino, 0.05);
			}
		}
	}
	self maps\mp\gametypes\_kit_rachas::kit_salir();
}
'''

GSC_HARRIER = r'''// Racha HARRIER: un AV-8B sobrevuela a los enemigos (re-leyendo la lista cada tramo) y el jugador
// dispara el canon de 40 mm desde abajo de la nave. Reescrita de eBus Hardline
// (maps/mp/killstreaks/_harrier.gsc); lo genera publicar\Armar_Hardline.py.
// Dura scr_racha_harrier_tiempo segundos. Mantener MELEE 1 s = salir antes.

harrier(z)
{
	self endon("kit_racha_muerte");
	self endon("kit_racha_salir");

	if(z > self.origin[2] + 1200)
		z = self.origin[2] + 1200;
	inicio = (self.origin[0], self.origin[1], z);
	nave = spawn("script_model", inicio);
	nave setModel("@@NAVE@@");
	nave.angles = (0, self.angles[1], 0);
	self.kit_nave = nave;
	nave playLoopSound("@@SND_LOOP@@");
	self maps\mp\gametypes\_kit_rachas::kit_entrar("harrier");

	self setOrigin(inicio - (0, 0, 72));
	self linkto(nave);
	self setPlayerAngles((45, self.kit_volver_ang[1], 0));

	self setWeaponSlotWeapon("primaryb", "@@A40@@");
	self setWeaponSlotAmmo("primaryb", 999);
	self setWeaponSlotClipAmmo("primaryb", 3);
	self switchToWeapon("@@A40@@");

	self.kit_hud_grano = newClientHudElem(self);
	self.kit_hud_grano.archived = false;
	self.kit_hud_grano.x = 0;
	self.kit_hud_grano.y = 0;
	self.kit_hud_grano.alpha = 0.3;
	self.kit_hud_grano setShader("@@GRANO@@", 640, 480);

	tiempo = level.kit_harrier_tiempo;
	self maps\mp\gametypes\_kit_rachas::kit_hudTiempo(tiempo);
	self iprintlnbold("HARRIER en camino: dispara el canon de 40 mm");
	self iprintln("MELEE 1 s = salir");

	total = tiempo * 20;
	proximo = 0;
	melee = 0;
	for(i = 1; i <= total; i++)
	{
		wait 0.05;
		if(!isAlive(self) || self.sessionstate != "playing" || !isdefined(nave))
			break;
		if(i % 20 == 0)
			self maps\mp\gametypes\_kit_rachas::kit_hudTiempoValor(tiempo - (int)(i / 20));
		if(self meleeButtonPressed())
		{
			melee++;
			if(melee >= 20)
				break;
		}
		else
			melee = 0;
		if(i >= proximo)
		{
			destino = self harrier_destino(inicio, z);
			t = distance(nave.origin, destino) / 600;
			if(t < 1)
				t = 1;
			giro = vectorToAngles(destino - nave.origin);
			nave rotateTo((0, giro[1], 0), 1);
			nave moveTo(destino, t, t * 0.2, t * 0.2);
			proximo = i + (int)(t * 20) + 40;		// 2 s sobre el objetivo
		}
	}
	self maps\mp\gametypes\_kit_rachas::kit_salir();
}

// Punto a altura z sobre un enemigo vivo a cielo abierto (al azar), o cerca del punto de partida.
harrier_destino(inicio, z)
{
	cand = [];
	jugadores = getentarray("player", "classname");
	for(i = 0; i < jugadores.size; i++)
	{
		p = jugadores[i];
		if(!isdefined(p) || p == self || !isAlive(p) || p.sessionstate != "playing" || isdefined(p.kit_enracha))
			continue;
		if(self.sessionteam != "none" && p.sessionteam == self.sessionteam)
			continue;
		if(z < p.origin[2] + 256)
			continue;
		arriba = (p.origin[0], p.origin[1], z);
		tr = bulletTrace(p.origin + (0, 0, 64), arriba, false, p);
		if(tr["fraction"] < 1)
			continue;			// bajo techo
		cand[cand.size] = arriba;
	}
	if(cand.size > 0)
	{
		d = cand[randomInt(cand.size)];
		d = (d[0] + randomInt(400) - 200, d[1] + randomInt(400) - 200, z);
	}
	else
		d = (inicio[0] + randomInt(1200) - 600, inicio[1] + randomInt(1200) - 600, z);
	return maps\mp\gametypes\_kit_rachas::kit_dentroMapa(d);
}
'''


# ------------------------------------------------------------------ menus
def datos_arma(w, tipo):
    """Texto del panel de la derecha, sacado del archivo del arma de Hardline (con los AJUSTES de abajo)."""
    t = hl.leer("weapons/mp/" + w).decode("latin-1").split("\\")
    kv = dict(zip(t[1::2], t[2::2]))
    kv.update(AJUSTES.get(w, {}))
    partes = [tipo + "."]
    if kv.get("damage"):
        partes.append("Daño: %s" % kv["damage"])
    if kv.get("clipSize"):
        partes.append("Cargador: %s" % kv["clipSize"])
    try:
        ft = float(kv.get("fireTime") or 0)
        if ft > 0:
            partes.append("Cadencia: %d disparos/min" % round(60 / ft))
    except ValueError:
        pass
    try:
        partes.append("Movilidad: %d%%" % round(float(kv.get("moveSpeedScale") or 1) * 100))
    except ValueError:
        pass
    if kv.get("altWeapon"):
        partes.append("Tiene modo de disparo alternativo.")
    return "  ".join(partes)


def menus():
    # Ventana del menu: 448x288 (ORIGIN_MENUWINDOW). Izquierda: 4 categorias + 3 columnas de miniaturas.
    # Derecha: nombre y datos del arma senalada (dos textos que leen cvars: no suman items por arma).
    xs, ancho, alto, paso, y0 = (8, 102, 196), 90, 45, 48, 62        # 3 columnas, miniaturas 2:1
    hay_mini = {}
    for w, _ in ARMAS:
        f = os.path.join(MINIATURAS, "hl_%s.tga" % w)
        if os.path.exists(f):
            hay_mini[w] = "ui_mp/assets/hud@hl_%s.tga" % w
            salida[hay_mini[w]] = open(f, "rb").read()
    for f in ("weapon_american", "weapon_british", "weapon_russian", "weapon_german"):
        for lang in ("", "spanish/"):
            r = "ui_mp/scriptmenus/%s%s.menu" % (lang, f)
            t = tf.leer(r).decode("latin-1")
            ocultar = sorted(set(re.findall(r'name\s+"((?:button_[a-z0-9]+)|(?:[a-z0-9]+_info))"', t)) -
                             {"button_mainmenu", "button_smg", "button_ar", "button_scoped", "button_team", "button_weapon",
                              "button_weapon_gray", "button_viewmap", "button_callvote"}) + ["weapon_propertiestext"]
            # pestanas de el mod: mismo ancho que la nueva y esconden lo de Hardline
            for k, (nombre, x) in enumerate((("smg", 8), ("ar", 116), ("scoped", 224))):
                t, n = re.subn(r'(name\s+"button_%s".*?rect\s+)\d+\s+\d+\s+\d+\s+\d+(.*?textalignx\s+)\d+' % nombre,
                               lambda m: m.group(1) + "%d 32 104 32" % x + m.group(2) + "52", t, count=1, flags=re.S)
                if n != 1:
                    raise SystemExit("%s: no pude acomodar la pestana %s" % (r, nombre))
            t, k = re.subn(r'(name\s+"button_(?:smg|ar|scoped)".*?action\s*\{\s*play "mouse_click";)',
                           lambda m: m.group(1) + "\r\n\t\t\thide hl_arma;\r\n\t\t\thide hl_info;", t, flags=re.S)
            if k != 3:
                raise SystemExit("%s: esperaba 3 pestanas y hay %d" % (r, k))
            t, k = re.subn(r"(onOpen\s*\{)", r"\1\r\n\t\t\thide hl_arma;\r\n\t\t\thide hl_info;", t, count=1)
            if k != 1:
                raise SystemExit("%s: sin onOpen" % r)
            items = []
            acciones = "".join("\r\n\t\t\t\thide %s;" % n for n in ocultar)
            items.append("""
		itemDef
		{
			name			"button_hardline"
			visible			1
			rect			332 32 104 32
			origin			ORIGIN_MENUTABS
			style			WINDOW_STYLE_FILLED
			forecolor		1 1 1 1
			type			ITEM_TYPE_BUTTON
			text			"^3HARDLINE"
			textfont		UI_FONT_NORMAL
			textscale		.28
			textalignx		52
			textaligny		24
			textalign		ITEM_ALIGN_CENTER
			action
			{
				play "mouse_click";%s
				show hl_arma;
				show hl_info;
				setcvar ui_hl_cat "asalto";
				setcvar ui_hl_nombre "^3Armas Hardline";
				setcvar ui_hl_datos "Elegí una categoría arriba y pasá el mouse por un arma para ver sus datos.";
			}
			onFocus
			{
				play "mouse_over";
			}
		}
		itemDef
		{
			name			"hl_info"
			visible			0
			rect			296 44 144 24
			origin			ORIGIN_MENUWINDOW
			cvar			"ui_hl_nombre"
			forecolor		1 1 1 1
			textfont		UI_FONT_NORMAL
			textscale		.32
			textstyle		ITEM_TEXTSTYLE_SHADOWED
			textaligny		20
			decoration
		}
		itemDef
		{
			name			"hl_info"
			visible			0
			rect			296 76 144 200
			origin			ORIGIN_MENUWINDOW
			cvar			"ui_hl_datos"
			autowrapped
			forecolor		1 1 1 0.85
			textfont		UI_FONT_NORMAL
			textscale		.22
			textaligny		12
			decoration
		}""" % acciones)
            for i, (cat, titulo, _) in enumerate(CATEGORIAS):
                items.append("""
		itemDef
		{
			name			"hl_arma"
			visible			0
			rect			%d 40 68 18
			origin			ORIGIN_MENUWINDOW
			style			WINDOW_STYLE_FILLED
			backcolor		1 1 1 0.10
			forecolor		0.4 0.9 1 1
			type			ITEM_TYPE_BUTTON
			text			"%s"
			textfont		UI_FONT_NORMAL
			textscale		.22
			textalign		ITEM_ALIGN_CENTER
			textalignx		34
			textaligny		14
			action
			{
				play "mouse_click";
				setcvar ui_hl_cat "%s";
			}
			onFocus
			{
				play "mouse_over";
			}
		}""" % (8 + i * 71, titulo, cat))
            for cat, titulo, lista in CATEGORIAS:
                for i, (w, etiqueta) in enumerate(lista):
                    x, y = xs[i % len(xs)], y0 + (i // len(xs)) * paso
                    if w in hay_mini:
                        estilo = 'style\t\t\tWINDOW_STYLE_SHADER\r\n\t\t\tbackground\t\t"%s"' % hay_mini[w]
                    else:
                        estilo = "style\t\t\tWINDOW_STYLE_FILLED\r\n\t\t\tbackcolor\t\t1 1 1 0.07"
                    items.append("""
		itemDef
		{
			name			"hl_arma"
			visible			0
			rect			%d %d %d %d
			origin			ORIGIN_MENUWINDOW
			%s
			forecolor		1 1 1 1
			type			ITEM_TYPE_BUTTON
			text			"%s"
			textfont		UI_FONT_NORMAL
			textscale		.18
			textstyle		ITEM_TEXTSTYLE_SHADOWED
			textalignx		3
			textaligny		%d
			cvartest		"ui_hl_cat"
			showCvar		{ "%s" }
			action
			{
				play "mouse_click";
				scriptMenuResponse "%s";
				close %s;
			}
			onFocus
			{
				play "mouse_over";
				setcvar ui_hl_nombre "%s";
				setcvar ui_hl_datos "%s";
			}
		}""" % (x, y, ancho, alto, estilo, etiqueta, alto - 3, cat, NUEVO[w], f, etiqueta, datos_arma(w, TIPO[cat])))
            fin = t.rstrip().rfind("}")
            fin = t.rstrip()[:fin].rstrip().rfind("}")        # cierre del menuDef
            t = t[:fin] + "".join(items).replace("\n", "\r\n").replace("\r\r\n", "\r\n") + "\r\n\t" + t[fin:]
            n_items = len(re.findall(r"\bitemDef\b", t))
            if n_items > 96:
                avisos.append("%s: %d itemDef (si faltan botones en el juego, el limite del motor es 96)" % (r, n_items))
            salida[r] = t.encode("latin-1")
    print("  menus: 8 con pestana HARDLINE (%d itemDef cada uno; %d miniaturas)" % (n_items, len(hay_mini)))


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description="Suma armas, soldados y rachas de Hardline al mod")
    for o in ("--juego", "--mods", "--maestro"):
        ap.add_argument(o, help="carpeta (ver arriba)")
    ap.add_argument("--salida", default=MAESTRO, help="donde dejar el pk3 (por defecto, la carpeta del mod)")
    a = ap.parse_args()
    print("1) armas")
    for w, _ in ARMAS:
        arma(w, cambios=AJUSTES.get(w))
    print("  %d armas hl_* (%d elegibles + modos alternativos)" % (len(NUEVO), len(ARMAS)))
    nombres_rachas = rachas()            # antes de los sonidos: suma alias hl_* al csv
    print("2) sonidos")
    cab, _ = csv_filas(tf.leer("soundaliases/generic_mp_sound.csv"))
    original = tf.leer("soundaliases/generic_mp_sound.csv").decode("latin-1").rstrip("\r\n")
    filas = [",".join(f.get(c, "") for c in cab) for fs in nuevos_alias.values() for f in fs]
    salida["soundaliases/generic_mp_sound.csv"] = (original + "\r\n# --- Armas de Hardline (Armar_Hardline.py) ---\r\n" +
                                                   "\r\n".join(filas) + "\r\n").encode("latin-1")
    print("  %d alias hl_* (%d filas)" % (len(nuevos_alias), len(filas)))
    print("3) soldados")
    soldados()
    print("4) scripts")
    salida["maps/mp/gametypes/_kit_hl.gsc"] = gsc_kit_hl(sorted(NUEVO.values())).encode("latin-1")
    gsc_rachas(nombres_rachas)
    scripts()
    print("5) menus")
    menus()
    print("6) arreglos")
    arreglos()
    destino = os.path.join(a.salida, SALIDA_PK3)
    os.makedirs(a.salida, exist_ok=True)
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for r in sorted(salida):
            z.writestr(r, salida[r])
    tam = os.path.getsize(destino)
    print("\nOK %s: %d archivos, %.1f MB" % (destino, len(salida), tam / 1048576))
    for x in avisos:
        print("  AVISO:", x)


def arreglos():
    """Vidrios de las miras (22-10-2026): la G-28 y la IA-2 usan texturas "glass_blend_in2@...", un tipo de material que
    no existe en el juego -> el motor las dibujaba opacas (gris). Se agrega shadertypes/model/glass_blend_in2.stype
    (igual al glass_blend_in del juego: vidrio transparente) y se ponen las texturas de Instalador\\hardline_arreglos\\skins
    (las del scopefix que paso un jugador, mas transparentes)."""
    base = tf.leer("shadertypes/model/glass_blend_in.stype")
    if base is None:
        raise SystemExit("no encuentro shadertypes/model/glass_blend_in.stype en el juego")
    salida["shadertypes/model/glass_blend_in2.stype"] = base
    carpeta = os.path.join(ROOT, "hardline_arreglos", "skins")
    for f in sorted(glob.glob(os.path.join(carpeta, "*"))):
        r = "skins/" + os.path.basename(f)
        if not os.path.basename(f).lower().endswith((".dds", ".tga", ".jpg")):
            continue
        if r not in salida:
            avisos.append("arreglo sin uso (ninguna arma usa %s)" % r)
        salida[r] = open(f, "rb").read()
        print("  " + r)
    # otros tipos de material que no existen (quedan opacos): solo se avisa
    tipos = {k[len("shadertypes/model/"):-len(".stype")] for k in salida if k.startswith("shadertypes/model/")}
    for k in sorted(salida):
        if k.startswith("skins/") and "@" in k:
            t = k[6:].split("@")[0].lower()
            if t not in tipos and not existe_fuera("shadertypes/model/" + t + ".stype"):
                avisos.append("el material %s no existe en el juego (se ve opaco): %s" % (t, k))


if __name__ == "__main__":
    main()
