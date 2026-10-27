"""Top del mes del servidor Mi Comunidad.

Lee lo nuevo del registro de partidas del servidor (games_mp.log, por SFTP), suma por mes:
  - bajas: muertes que hizo cada jugador (sin suicidios, sin matar companeros de equipo, sin "el mundo")
  - ganadas: partidas ganadas (lineas W; del juego: en DM el ganador, en equipos cada jugador del equipo ganador)
  - cabeza / cabeza_recibidos: impactos en la cabeza que dio / que recibio cada uno (lineas D; y K;, maten o no)
y publica estadisticas.json en el release "stats" del repo de GitHub (el launcher lo muestra en "TOP DEL MES").

Corre solo en GitHub Actions cada 30 minutos (.github/workflows/estadisticas.yml) o a mano en la PC:
  python actualizar_estadisticas.py
Variables de entorno: SFTP_HOST, SFTP_PORT, SFTP_USER, SFTP_PASS, SFTP_HOSTKEY, LOG_PATH, GH_TOKEN, GH_REPO (dueno/repo)
SFTP_HOSTKEY = huella del servidor (SHA256:...): la primera corrida sin ella la muestra en el registro.
(en la PC, si faltan, se toman de ..\\privado\\github.json y de los valores de abajo).

VARIOS SERVIDORES (los mismos jugadores en todos): cada servidor es una "fuente" con su propio archivo en el
release (fuente_<nombre>.json: hasta donde leyo y lo que sumo cada mes). Cada corrida actualiza SU fuente y
vuelve a sumar todas en estadisticas.json (lo que lee el launcher). Cada fuente la escribe un solo lugar:
  - FUENTE=alquilado (por defecto): GitHub Actions, leyendo por SFTP.
  - FUENTE=casa LOG_FILE=/srv/.../games_mp.log: el propio servidor, leyendo su archivo (no necesita SFTP).


El registro no tiene fechas: lo nuevo se cuenta en el mes en que se lee (hora de Argentina).
Los nombres cuentan EXACTOS (con colores): "^1Juan" y "Juan" son dos jugadores distintos.
"""
import base64, datetime, hashlib, io, json, os, sys, time, urllib.request, urllib.error

TAG = "stats"
ASSET = "estadisticas.json"
FUENTE_DEFECTO = "alquilado"            # la que corre en GitHub Actions (servidor alquilado, por SFTP)
TZ = datetime.timezone(datetime.timedelta(hours=-3))      # Argentina (sin horario de verano)


def env(name, default=None):
    v = os.environ.get(name)
    return v if v else default


def cfg_local():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "privado", "github.json")
    if os.path.exists(p):
        with open(p, encoding="utf-8-sig") as f:
            return json.load(f)
    return {}


# ---------------------------------------------------------------- GitHub
class GitHub:
    def __init__(self, token, repo):
        self.token, self.repo = token, repo

    def req(self, url, data=None, method=None, ctype="application/json", accept="application/vnd.github+json"):
        if not url.startswith("http"):
            url = "https://api.github.com/repos/" + self.repo + url
        r = urllib.request.Request(url, data=data, method=method)
        r.add_header("Authorization", "Bearer " + self.token)
        r.add_header("Accept", accept)
        r.add_header("User-Agent", "kit-estadisticas")
        if data is not None:
            r.add_header("Content-Type", ctype)
        with urllib.request.urlopen(r, timeout=60) as resp:
            return resp.read()

    def release(self):
        try:
            return json.loads(self.req("/releases/tags/" + TAG))
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
        body = json.dumps({"tag_name": TAG, "name": "Estadisticas",
                           "body": "Top del mes (lo actualiza actualizar_estadisticas.py). No borrar.",
                           "prerelease": True}).encode()
        return json.loads(self.req("/releases", body, "POST"))

    def leer(self, rel, nombre=ASSET):
        for a in rel.get("assets", []):
            if a["name"] == nombre:
                return json.loads(self.req(a["url"], accept="application/octet-stream").decode("utf-8"))
        return None

    def subir(self, rel, datos, nombre=ASSET):
        # borra la version anterior y sube la nueva (si otra corrida la subio en el medio, reintenta)
        for intento in range(3):
            rel = json.loads(self.req("/releases/%d" % rel["id"]))
            for a in rel.get("assets", []):
                if a["name"] == nombre:
                    try:
                        self.req(a["url"], method="DELETE")
                    except urllib.error.HTTPError as e:
                        if e.code != 404:
                            raise
            url = "https://uploads.github.com/repos/%s/releases/%d/assets?name=%s" % (self.repo, rel["id"], nombre)
            try:
                self.req(url, datos, "POST", ctype="application/json")
                return
            except urllib.error.HTTPError as e:
                if e.code != 422 or intento == 2:
                    raise
                time.sleep(5)


# ---------------------------------------------------------------- registro
def huella(clave):
    """Huella de la clave SSH del servidor, en el mismo formato que ssh-keygen -lf (SHA256:...)."""
    return "SHA256:" + base64.b64encode(hashlib.sha256(clave.asbytes()).digest()).decode().rstrip("=")


def cortar_nuevo(f, size, estado):
    """Lee de f lo que se agrego desde la ultima vez (solo lineas completas) y actualiza offset/cabeza."""
    cabeza = hashlib.sha1(f.read(2048)).hexdigest()
    off = estado.get("offset", 0)
    # archivo nuevo o vaciado (el server lo recreo): empezar de cero
    if cabeza != estado.get("cabeza") or size < off:
        off = 0
    f.seek(off)
    nuevo = f.read(size - off)
    corte = nuevo.rfind(b"\n") + 1
    estado["offset"] = off + corte
    estado["cabeza"] = cabeza
    return nuevo[:corte].decode("latin-1")


def leer_log_local(estado, path):
    """El servidor lee su propio registro (sin SFTP)."""
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        return cortar_nuevo(f, size, estado)


def leer_log_nuevo(estado):
    import paramiko
    host = env("SFTP_HOST", "123.45.67.89")
    port = int(env("SFTP_PORT", "22"))
    t = paramiko.Transport((host, port))
    t.start_client(timeout=30)
    # Antes de mandar la contrasena se comprueba que el servidor sea el de siempre (huella de su clave SSH)
    recibida = huella(t.get_remote_server_key())
    esperada = env("SFTP_HOSTKEY")
    if esperada and recibida != esperada.strip():
        t.close()
        raise SystemExit("La huella del servidor SFTP (%s) no coincide con SFTP_HOSTKEY: posible suplantacion, "
                         "no se envio la contrasena. Si cambiaste de servidor, actualiza el secreto." % recibida)
    if not esperada:
        print("AVISO: no se verifica la identidad del servidor SFTP. Guarda esta huella en el secreto SFTP_HOSTKEY: " + recibida)
    t.auth_password(env("SFTP_USER"), env("SFTP_PASS"))
    s = paramiko.SFTPClient.from_transport(t)
    path = env("LOG_PATH", "123.45.67.89_28960/.callofduty/MiMod/games_mp.log")
    size = s.stat(path).st_size
    with s.open(path, "rb") as f:
        texto = cortar_nuevo(f, size, estado)
    t.close()
    return texto


# Contadores por jugador que se suman por mes (el launcher muestra los rankings)
CLAVES = ("bajas", "ganadas", "cabeza", "cabeza_recibidos")


def impacto_cabeza(c):
    """D; (dano) y K; (baja): D/K;guid;num;equipo;nombre(victima);guid;num;equipo;nombre(atacante);arma;dano;modo;zona.
    Devuelve (atacante, victima) si fue un impacto en la cabeza entre rivales; si no, None."""
    if len(c) < 13 or (c[12] != "head" and c[11] != "MOD_HEAD_SHOT"):
        return None
    v_num, v_team, v_name, at_num, at_team, at_name = c[2], c[3], c[4], c[6], c[7], c[8]
    if not at_name or at_num in ("-1", "") or at_num == v_num:
        return None                                    # el mundo o a si mismo
    if v_team and at_team and v_team == at_team:
        return None                                    # companero de equipo
    return at_name, v_name


def procesar(texto, mes, solo=None):
    m = {"bajas": {}, "ganadas": {}, "cabeza": {}, "cabeza_recibidos": {}, "partidas": 0}
    for linea in texto.splitlines():
        partes = linea.strip().split(" ", 1)
        if len(partes) < 2:
            continue
        c = partes[1].split(";")
        if c[0] in ("D", "K"):
            h = impacto_cabeza(c)
            if h:
                m["cabeza"][h[0]] = m["cabeza"].get(h[0], 0) + 1
                m["cabeza_recibidos"][h[1]] = m["cabeza_recibidos"].get(h[1], 0) + 1
        if solo:
            continue                                   # recuento de una sola estadistica (ver recontar_cabeza.py)
        if c[0] == "K" and len(c) >= 9:
            # K;guid;num;equipo;nombre;guid_at;num_at;equipo_at;nombre_at;arma;dano;modo;zona
            v_num, v_team, at_num, at_team, at_name = c[2], c[3], c[6], c[7], c[8]
            if not at_name or at_num in ("-1", "") or at_num == v_num:
                continue                                   # el mundo o suicidio
            if v_team and at_team and v_team == at_team:
                continue                                   # companero de equipo
            m["bajas"][at_name] = m["bajas"].get(at_name, 0) + 1
        elif c[0] == "W" and len(c) >= 4 and c[3]:
            m["ganadas"][c[3]] = m["ganadas"].get(c[3], 0) + 1
        elif partes[1].startswith("ExitLevel"):
            m["partidas"] += 1
    return m


def sumar(estado, mes, nuevo):
    meses = estado.setdefault("meses", {})
    acc = meses.setdefault(mes, {"bajas": {}, "ganadas": {}, "partidas": 0})
    for k in CLAVES:
        acc.setdefault(k, {})
        for n, v in nuevo[k].items():
            acc[k][n] = acc[k].get(n, 0) + v
    acc["partidas"] += nuevo["partidas"]


def combinar(fuentes):
    """Suma los meses de todas las fuentes (los mismos jugadores juegan en todos los servidores)."""
    total = {}
    for est in fuentes:
        for mes, m in est.get("meses", {}).items():
            acc = total.setdefault(mes, {"bajas": {}, "ganadas": {}, "partidas": 0})
            for k in CLAVES:
                if k not in m:
                    continue
                acc.setdefault(k, {})
                for n, v in m[k].items():
                    acc[k][n] = acc[k].get(n, 0) + v
            acc["partidas"] += m.get("partidas", 0)
    return total


def rcon(destino, comando):
    """destino = "host:puerto:clave". Manda un comando rcon por UDP (sin esperar mucho la respuesta)."""
    import socket
    host, puerto, clave = destino.split(":", 2)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(3)
    try:
        s.sendto(b"\xff\xff\xff\xffrcon " + clave.encode("latin-1") + b" " + comando.encode("latin-1"), (host, int(puerto)))
        try:
            s.recv(4096)
        except socket.timeout:
            pass
    finally:
        s.close()


def empujar_top(total):
    """Manda a los servidores el ranking de bajas del mes (cvars kit_top_bajas1..3 = "nombre\\bajas\\..."),
    para el HUD de cada jugador ("Top del mes: puesto 3 en bajas"). RCON_DESTINOS = "host:puerto:clave;host:puerto:clave"."""
    destinos = [d for d in (env("RCON_DESTINOS") or "").split(";") if d.strip()]
    if not destinos:
        return
    mes = datetime.datetime.now(TZ).strftime("%Y-%m")
    bajas = total.get("meses", {}).get(mes, {}).get("bajas", {})
    orden = sorted(((n, v) for n, v in bajas.items() if '"' not in n and "\\" not in n and ";" not in n),
                   key=lambda x: (-x[1], x[0].lower()))[:30]
    partes = ["".join("%s\\%d\\" % (n, v) for n, v in orden[i:i + 10]) for i in (0, 10, 20)]
    for d in destinos:
        try:
            for i, p in enumerate(partes, 1):
                rcon(d, 'set kit_top_bajas%d "%s"' % (i, p))
                time.sleep(0.3)        # el servidor limita las consultas por segundo
        except Exception as e:
            print("No pude mandar el top a %s: %s" % (d.split(":")[0], e))
    print("Top mandado a %d servidor(es): %d jugadores" % (len(destinos), len(orden)))


def main():
    local = cfg_local()
    if env("SOLO_EMPUJAR"):
        # solo reenviar el top a los servidores (cada 5 minutos: si un servidor se reinicio, lo recupera enseguida)
        gh = GitHub(env("GH_TOKEN", local.get("write_token")),
                    env("GH_REPO", "%s/%s" % (local.get("owner", "TU_USUARIO"), local.get("repo", "mi-mod"))))
        empujar_top(gh.leer(gh.release()) or {})
        return
    token = env("GH_TOKEN", local.get("write_token"))
    repo = env("GH_REPO", "%s/%s" % (local.get("owner", "TU_USUARIO"), local.get("repo", "mi-mod")))
    fuente = env("FUENTE", FUENTE_DEFECTO)
    log_file = env("LOG_FILE")
    if not log_file and not env("SFTP_USER"):
        raise SystemExit("Faltan SFTP_USER / SFTP_PASS (o LOG_FILE para leer un archivo local)")
    gh = GitHub(token, repo)
    rel = gh.release()
    nombre = "fuente_%s.json" % fuente
    estado = gh.leer(rel, nombre)
    if estado is None:
        estado = {}
        if fuente == FUENTE_DEFECTO:
            # primera vez con fuentes: lo contado hasta ahora (un solo servidor) pasa a ser de esta fuente
            viejo = gh.leer(rel) or {}
            if "offset" in viejo:
                estado = {k: viejo[k] for k in ("offset", "cabeza", "meses") if k in viejo}
                print("Migrado: lo contado hasta ahora pasa a la fuente '%s'" % fuente)
    texto = leer_log_local(estado, log_file) if log_file else leer_log_nuevo(estado)
    ahora = datetime.datetime.now(TZ)
    mes = ahora.strftime("%Y-%m")
    nuevo = procesar(texto, mes)
    sumar(estado, mes, nuevo)
    estado["actualizado"] = ahora.strftime("%Y-%m-%d %H:%M")
    gh.subir(rel, json.dumps(estado, ensure_ascii=False, indent=1).encode("utf-8"), nombre)

    # estadisticas.json = suma de todas las fuentes (con la nuestra recien actualizada)
    rel = json.loads(gh.req("/releases/%d" % rel["id"]))
    todas = [estado]
    for a in rel.get("assets", []):
        if a["name"].startswith("fuente_") and a["name"].endswith(".json") and a["name"] != nombre:
            todas.append(gh.leer(rel, a["name"]) or {})
    total = {"meses": combinar(todas), "actualizado": estado["actualizado"],
             "fuentes": sorted([nombre[7:-5]] + [a["name"][7:-5] for a in rel.get("assets", [])
                                if a["name"].startswith("fuente_") and a["name"] != nombre])}
    gh.subir(rel, json.dumps(total, ensure_ascii=False, indent=1).encode("utf-8"))
    empujar_top(total)
    print("OK %s [%s]: +%d bajas, +%d ganadas, +%d partidas (offset %d) - total de %d fuente(s)" % (
        mes, fuente, sum(nuevo["bajas"].values()), sum(nuevo["ganadas"].values()), nuevo["partidas"],
        estado["offset"], len(todas)))


if __name__ == "__main__":
    main()
