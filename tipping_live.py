#!/usr/bin/env python3
"""
Live-visning av Radsoft-rekker mot dagens tippekupong hos Norsk Tipping.

Bruk:
    python3 tipping_live.py                 # bruker nyeste .fak-fil i samme mappe
    python3 tipping_live.py LFulltid_xxx.fak

Starter en liten webserver på http://localhost:8765 og åpner siden i nettleseren.
Siden henter resultater via /api/live hvert minutt; skriptet henter dem fra
Norsk Tippings åpne resultat-API (det samme som norsk-tipping.no bruker).
Stopp med Ctrl+C.

Kun standardbiblioteket brukes (ingen pip install).
"""
import glob
import http.server
import json
import os
import socketserver
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser

NT_URL = ("https://api.norsk-tipping.no/PoolGamesSportInfo/v1/api/tipping/game/"
          "resulted-and-closest-before-date")
HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "rekker_mal.html")
PORT = 8765
CACHE_SECONDS = 30


# ---------- Les Radsoft-fila ----------
def _fix(line):
    # Radsoft-fila er Latin-1, men enkelte lagnavn ligger som UTF-8-bytes
    try:
        return line.encode("latin-1").decode("utf-8")
    except UnicodeDecodeError:
        return line


def parse_fak(path):
    lines = [_fix(l.rstrip("\r\n")) for l in open(path, encoding="latin-1")]

    def section(name):
        i = lines.index("#" + name)
        j = i + 1
        while j < len(lines) and not lines[j].startswith("#"):
            j += 1
        return lines[i + 1:j]

    opp = section("oppsett")
    names = [s.strip() for s in opp[12:36]]
    home, away = names[:12], names[12:]
    nums = opp[36:]
    folk = [[int(nums[k * 12 + i]) for k in range(3)] for i in range(12)]
    times = opp[36 + 84:36 + 96]
    weekdays = ("Lørdag", "Søndag", "Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag", "Midtuke")
    kupong = next((l for l in opp if l.startswith(weekdays)), "")

    rows = [r.strip() for r in section("rader") if r.strip()]
    bad = [r for r in rows if len(r) != 12 or not set(r) <= set("123")]
    if bad:
        raise ValueError(f"Uventet radformat, f.eks. {bad[0]!r}")

    return {
        "kupong": kupong,
        "file": os.path.basename(path),
        "matches": [{"h": home[i], "b": away[i], "t": times[i].strip(), "folk": folk[i]}
                    for i in range(12)],
        "rows": "".join(rows),
    }


def build_page(fak_path):
    data = parse_fak(fak_path)
    html = open(TEMPLATE, encoding="utf-8").read()
    return html.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False)), data


# ---------- Hent fra Norsk Tipping ----------
_cache = {"t": 0.0, "body": None}
_lock = threading.Lock()


def _fetch_nt():
    req = urllib.request.Request(NT_URL, headers={
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh) tipping_live.py",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read()
    except Exception as e:
        # Python fra python.org mangler ofte sertifikater på macOS – fall tilbake til curl
        if "CERTIFICATE" in str(e).upper() or "SSL" in str(e).upper():
            return subprocess.run(["curl", "-sSf", "-m", "15", NT_URL],
                                  check=True, capture_output=True).stdout
        raise


def get_live():
    with _lock:
        if _cache["body"] is None or time.time() - _cache["t"] > CACHE_SECONDS:
            _cache["body"] = _fetch_nt()
            _cache["t"] = time.time()
        return _cache["body"]


# ---------- Webserver ----------
def make_handler(page_bytes):
    class Handler(http.server.BaseHTTPRequestHandler):
        def _send(self, code, body, ctype, head=False):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if not head:
                self.wfile.write(body)

        def _route(self, head=False):
            path = self.path.split("?")[0]
            if path in ("/", "/index.html"):
                self._send(200, page_bytes, "text/html; charset=utf-8", head)
            elif path == "/api/live":
                if head:
                    return self._send(200, b"", "application/json", True)
                try:
                    self._send(200, get_live(), "application/json")
                except Exception as e:
                    msg = json.dumps({"error": str(e)}).encode()
                    self._send(502, msg, "application/json")
            else:
                self._send(404, b"Ikke funnet", "text/plain; charset=utf-8", head)

        def do_GET(self):
            self._route()

        def do_HEAD(self):
            self._route(head=True)

        def log_message(self, fmt, *args):
            pass  # hold terminalen ren

    return Handler


def main():
    if len(sys.argv) > 1:
        fak = sys.argv[1]
    else:
        files = sorted(glob.glob(os.path.join(HERE, "*.fak")), key=os.path.getmtime)
        if not files:
            sys.exit("Fant ingen .fak-fil. Bruk: python3 tipping_live.py <fil.fak>")
        fak = files[-1]

    html, data = build_page(fak)
    print(f"Fil:    {data['file']}  ({len(data['rows']) // 12} rekker)")
    print(f"Kupong: {data['kupong']}")

    try:
        live = json.loads(get_live())
        nt = sorted(live.get("matches", []), key=lambda m: m["gameEngineSortingNumber"])
        diff = []
        for i, (m, mine) in enumerate(zip(nt, data["matches"])):
            h = m.get("teams", {}).get("home", {})
            names = {(h.get(k) or "").strip().lower()[:3] for k in ("webName", "retailerName", "mobileName")}
            if mine["h"].strip().lower()[:3] not in names:
                diff.append(i + 1)
        if diff:
            print(f"NB: kamp {diff} på Norsk Tipping stemmer ikke med fila – er det riktig kupong?")
        else:
            print("Norsk Tipping: kupongen stemmer med fila.")
    except Exception as e:
        print(f"NB: fikk ikke hentet fra Norsk Tipping nå ({e}). Siden prøver igjen hvert minutt.")

    socketserver.TCPServer.allow_reuse_address = True
    port = PORT
    for port in range(PORT, PORT + 20):
        try:
            httpd = socketserver.ThreadingTCPServer(("127.0.0.1", port), make_handler(html.encode("utf-8")))
            break
        except OSError:
            continue
    else:
        sys.exit("Fant ingen ledig port.")

    url = f"http://localhost:{port}/"
    print(f"\nÅpne {url}   (Ctrl+C for å stoppe)")
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStoppet.")


if __name__ == "__main__":
    main()
