"""Top del mes del servidor Mi Comunidad.

Lee lo nuevo del registro de partidas del servidor (games_mp.log, por SFTP), suma por mes:
  - bajas: muertes que hizo cada jugador (sin suicidios, sin matar companeros de equipo, sin "el mundo")
  - ganadas: partidas ganadas (lineas W; del juego: en DM el ganador, en equipos cada jugador del equipo ganador)
y publica estadisticas.json en el release "stats" del repo de GitHub (el launcher lo muestra en "TOP DEL MES").

Corre solo en GitHub Actions cada 30 minutos (.github/workflows/estadisticas.yml) o a mano en la PC:
  python actualizar_estadisticas.py
Variables de entorno: SFTP_HOST, SFTP_PORT, SFTP_USER, SFTP_PASS, LOG_PATH, GH_TOKEN, GH_REPO (dueno/repo)
(en la PC, si faltan, se toman de ..\\privado\\github.json y de los valores de abajo).

El registro no tiene fechas: lo nuevo se cuenta en el mes en que se lee (hora de Argentina).
Los nombres cuentan EXACTOS (con colores): "^1Juan" y "Juan" son dos jugadores distintos.
"""
import datetime, hashlib, io, json, os, sys, urllib.request, urllib.error

TAG = "stats"
ASSET = "estadisticas.json"
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

    def leer(self, rel):
        for a in rel.get("assets", []):
            if a["name"] == ASSET:
                return json.loads(self.req(a["url"], accept="application/octet-stream").decode("utf-8"))
        return None

    def subir(self, rel, datos):
        for a in rel.get("assets", []):
            if a["name"] == ASSET:
                self.req(a["url"], method="DELETE")
        url = "https://uploads.github.com/repos/%s/releases/%d/assets?name=%s" % (self.repo, rel["id"], ASSET)
        self.req(url, datos, "POST", ctype="application/json")


# ---------------------------------------------------------------- registro
def leer_log_nuevo(estado):
    import paramiko
    host = env("SFTP_HOST", "123.45.67.89")
    port = int(env("SFTP_PORT", "22"))
    t = paramiko.Transport((host, port))
    t.connect(username=env("SFTP_USER"), password=env("SFTP_PASS"))
    s = paramiko.SFTPClient.from_transport(t)
    path = env("LOG_PATH", "123.45.67.89_28960/.callofduty/MiMod/games_mp.log")
    size = s.stat(path).st_size
    with s.open(path, "rb") as f:
        cabeza = hashlib.sha1(f.read(2048)).hexdigest()
        off = estado.get("offset", 0)
        # archivo nuevo o vaciado (el server lo recreo): empezar de cero
        if cabeza != estado.get("cabeza") or size < off:
            off = 0
        f.seek(off)
        nuevo = f.read(size - off)
    t.close()
    # solo lineas completas
    corte = nuevo.rfind(b"\n") + 1
    estado["offset"] = off + corte
    estado["cabeza"] = cabeza
    return nuevo[:corte].decode("latin-1")


def procesar(texto, mes):
    m = {"bajas": {}, "ganadas": {}, "partidas": 0}
    for linea in texto.splitlines():
        partes = linea.strip().split(" ", 1)
        if len(partes) < 2:
            continue
        c = partes[1].split(";")
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
    for k in ("bajas", "ganadas"):
        for n, v in nuevo[k].items():
            acc[k][n] = acc[k].get(n, 0) + v
    acc["partidas"] += nuevo["partidas"]


def main():
    local = cfg_local()
    token = env("GH_TOKEN", local.get("write_token"))
    repo = env("GH_REPO", "%s/%s" % (local.get("owner", "TU_USUARIO"), local.get("repo", "mi-mod")))
    if not env("SFTP_USER"):
        raise SystemExit("Faltan SFTP_USER / SFTP_PASS")
    gh = GitHub(token, repo)
    rel = gh.release()
    estado = gh.leer(rel) or {}
    texto = leer_log_nuevo(estado)
    ahora = datetime.datetime.now(TZ)
    mes = ahora.strftime("%Y-%m")
    nuevo = procesar(texto, mes)
    sumar(estado, mes, nuevo)
    estado["actualizado"] = ahora.strftime("%Y-%m-%d %H:%M")
    gh.subir(rel, json.dumps(estado, ensure_ascii=False, indent=1).encode("utf-8"))
    print("OK %s: +%d bajas, +%d ganadas, +%d partidas (offset %d)" % (
        mes, sum(nuevo["bajas"].values()), sum(nuevo["ganadas"].values()), nuevo["partidas"], estado["offset"]))


if __name__ == "__main__":
    main()
