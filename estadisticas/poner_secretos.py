"""Guarda la conexion SFTP como secretos cifrados del repo (los usa la tarea de GitHub Actions).
Uso: set SFTP_USER=... & set SFTP_PASS=... & python poner_secretos.py
Opcionales: SFTP_HOST, SFTP_PORT, LOG_PATH (ruta de games_mp.log en el servidor)."""
import base64, json, os, urllib.request
from nacl import encoding, public

AQUI = os.path.dirname(os.path.abspath(__file__))
cfg = json.load(open(os.path.join(AQUI, "..", "privado", "github.json"), encoding="utf-8-sig"))
API = "https://api.github.com/repos/%s/%s/actions/secrets/" % (cfg["owner"], cfg["repo"])


def req(url, data=None, method=None):
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Authorization", "Bearer " + cfg["write_token"])
    r.add_header("Accept", "application/vnd.github+json")
    r.add_header("User-Agent", "kit")
    if data is not None:
        r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=60) as resp:
        return resp.read()


key = json.loads(req(API + "public-key"))
box = public.SealedBox(public.PublicKey(key["key"].encode(), encoding.Base64Encoder()))
for name in ("SFTP_USER", "SFTP_PASS", "SFTP_HOST", "SFTP_PORT", "LOG_PATH"):
    valor = os.environ.get(name)
    if not valor:
        if name in ("SFTP_USER", "SFTP_PASS"):
            raise SystemExit("Falta " + name)
        continue      # opcionales: SFTP_HOST, SFTP_PORT, LOG_PATH
    cifrado = base64.b64encode(box.encrypt(valor.encode())).decode()
    req(API + name, json.dumps({"encrypted_value": cifrado, "key_id": key["key_id"]}).encode(), "PUT")
    print("OK secreto", name)
