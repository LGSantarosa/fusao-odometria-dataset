"""Baixa um arquivo de um link público do OneDrive (1drv.ms) em blocos paralelos, com retomada.

O link é resolvido pelo token anônimo de compartilhamento ("Badger") usado pelo próprio site do OneDrive. O arquivo
é gravado em `<dest>.part`; os blocos concluídos ficam em `<dest>.part.done`, de modo que uma interrupção retoma do
ponto em que parou. No fim, confere o tamanho e o sha256 informados pelo OneDrive e os hashes declarados no manifesto
de aquisição (md5 da SJTU, quando existe; sha256). Não abre nem interpreta o conteúdo. Com `--item gt`, o GT baixado é
lacrado (permissão 000) assim que verificado, e a aquisição fica registrada em `CUSTODY.log`, ao lado do arquivo.

    python -m tools.fetch_onedrive configs/botanic/g0_acquisition/1005-01.json [--item bag|gt] [--workers 8]
"""
import argparse
import base64
import hashlib
import json
import os
import sys
import threading
import subprocess
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

TOKEN_URL = "https://api-badgerp.svc.ms/v1.0/token"
APP_ID = "5cbed6ac-a083-4e14-b191-b4ba07653de2"
API = "https://my.microsoftpersonalcontent.com/_api/v2.0/shares/u!{}/driveitem"
CHUNK = 64 << 20


def _json(req):
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def resolve(link):
    """Link de compartilhamento -> (nome, tamanho, sha256 do OneDrive, URL temporária de download)."""
    tok = _json(urllib.request.Request(TOKEN_URL, data=json.dumps({"appId": APP_ID}).encode(),
                                       headers={"Content-Type": "application/json"}))["token"]
    enc = base64.urlsafe_b64encode(link.encode()).decode().rstrip("=")
    url = API.format(enc) + "?$select=name,size,file,@content.downloadUrl"
    d = _json(urllib.request.Request(url, headers={"Authorization": f"Badger {tok}", "Prefer": "autoredeem"}))
    return d["name"], int(d["size"]), d["file"]["hashes"]["sha256Hash"].lower(), d["@content.downloadUrl"]


class Downloader:
    def __init__(self, link, dest, workers):
        self.link, self.dest, self.workers = link, Path(dest), workers
        self.part, self.done_path = Path(f"{dest}.part"), Path(f"{dest}.part.done")
        self.lock = threading.Lock()
        self.name, self.size, self.sha256, self.url = resolve(link)
        self.done = set(json.loads(self.done_path.read_text())) if self.done_path.exists() else set()
        self.got = 0

    def refresh(self):
        with self.lock:
            self.url = resolve(self.link)[3]

    def fetch(self, i):
        a, b = i * CHUNK, min((i + 1) * CHUNK, self.size) - 1
        for attempt in range(8):
            try:
                req = urllib.request.Request(self.url, headers={"Range": f"bytes={a}-{b}"})
                with urllib.request.urlopen(req, timeout=120) as r:
                    if r.status != 206:
                        raise OSError(f"HTTP {r.status} sem Range")
                    buf = r.read()
                if len(buf) != b - a + 1:
                    raise OSError("bloco incompleto")
                fd = os.open(self.part, os.O_WRONLY)
                try:
                    os.pwrite(fd, buf, a)
                finally:
                    os.close(fd)
                with self.lock:
                    self.done.add(i)
                    self.got += len(buf)
                    self.done_path.write_text(json.dumps(sorted(self.done)))
                return
            except Exception as e:  # noqa: BLE001 — rede: tenta de novo com URL renovada
                print(f"{self.name} bloco {i}: {e!r}; tentativa {attempt + 1}", file=sys.stderr, flush=True)
                time.sleep(5 * (attempt + 1))
                try:
                    self.refresh()
                except Exception:  # noqa: BLE001
                    pass
        raise RuntimeError(f"{self.name}: bloco {i} falhou após 8 tentativas")

    def run(self):
        if not self.part.exists():
            with open(self.part, "wb") as f:
                f.truncate(self.size)
        n = -(-self.size // CHUNK)
        todo = [i for i in range(n) if i not in self.done]
        t0 = time.time()
        with ThreadPoolExecutor(self.workers) as ex:
            futs = [ex.submit(self.fetch, i) for i in todo]
            while any(not f.done() for f in futs):
                time.sleep(30)
                print(f"{self.name}: {len(self.done)}/{n} blocos, {self.got / (time.time() - t0) / 1e6:.1f} MB/s",
                      flush=True)
            for f in futs:
                f.result()


def file_hashes(path):
    md5, sha = hashlib.md5(), hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            md5.update(chunk)
            sha.update(chunk)
    return md5.hexdigest(), sha.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest")
    ap.add_argument("--item", choices=("bag", "gt"), default="bag")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    manifest = json.loads(Path(a.manifest).read_text())
    m = manifest[a.item]
    dest = Path(m["path"])
    if dest.exists():
        print(f"{dest} já existe; nada a fazer")
        return
    d = Downloader(m["onedrive"], dest, a.workers)
    if d.name != dest.name:
        sys.exit(f"link aponta para {d.name}, esperado {dest.name}")
    d.run()
    md5, sha = file_hashes(d.part)
    if (sha != d.sha256 or sha != m.get("sha256", sha).lower() or md5 != m.get("md5", md5).lower()
            or d.part.stat().st_size != d.size):
        sys.exit(f"{dest.name}: hash divergente (md5 {md5}, sha256 {sha}); .part mantido para inspeção")
    d.part.rename(dest)
    d.done_path.unlink()
    if a.item == "gt":
        dest.chmod(0)
        commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        with open(dest.parent / "CUSTODY.log", "a") as f:
            f.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(), "file": dest.name, "action": "acquire_seal",
                                "seq": manifest["seq"], "commit": commit, "by": "tools.fetch_onedrive"}) + "\n")
    print(f"{dest.name} OK md5 {md5} sha256 {sha}")


if __name__ == "__main__":
    main()
