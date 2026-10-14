"""Sube al repo (rama main) el programa del TOP DEL MES y su tarea programada de GitHub Actions."""
import base64, json, os, urllib.request, urllib.error

AQUI = os.path.dirname(os.path.abspath(__file__))
cfg = json.load(open(os.path.join(AQUI, "..", "privado", "github.json"), encoding="utf-8-sig"))
API = "https://api.github.com/repos/%s/%s/contents/" % (cfg["owner"], cfg["repo"])


def req(url, data=None, method=None):
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Authorization", "Bearer " + cfg["write_token"])
    r.add_header("Accept", "application/vnd.github+json")
    r.add_header("User-Agent", "kit")
    if data is not None:
        r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=60) as resp:
        return json.loads(resp.read() or b"{}")


def subir(local, remoto):
    contenido = open(os.path.join(AQUI, local), "rb").read()
    sha = None
    try:
        sha = req(API + remoto)["sha"]
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    body = {"message": "TOP DEL MES: " + remoto, "content": base64.b64encode(contenido).decode(), "branch": "main"}
    if sha:
        body["sha"] = sha
    try:
        req(API + remoto, json.dumps(body).encode(), "PUT")
        print("OK", remoto)
    except urllib.error.HTTPError as e:
        print("ERROR", remoto, e.code, e.read().decode()[:200])


subir("actualizar_estadisticas.py", "estadisticas/actualizar_estadisticas.py")
subir("estadisticas.yml", ".github/workflows/estadisticas.yml")
