"""JARVIS Dashboard: a local, read-only web page showing live state, activity and the audit trail.

Run:  python dashboard.py        (or run_dashboard.bat)      Options: --port 8765 --no-browser
Security: listens on 127.0.0.1 only, rejects foreign Host headers (DNS rebinding), needs a per-run access token
(sent as an HttpOnly cookie), has no write endpoints, and sends a strict Content-Security-Policy.
Uses only the Python standard library."""
import argparse, http.server, json, os, secrets, socketserver, tempfile, threading, time, webbrowser
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIT = os.path.join(HERE, "jarvis_audit.jsonl")
LOG = os.path.join(HERE, "jarvis.log")
STATE = os.path.join(tempfile.gettempdir(), "jarvis_state.txt")
TOKEN_FILE = os.path.join(HERE, "dashboard_token.txt")


def load_token():
    """Keep the same access token between runs so bookmarks and open tabs keep working."""
    try:
        t = open(TOKEN_FILE, encoding="utf-8").read().strip()
        if len(t) >= 24:
            return t
    except OSError:
        pass
    t = secrets.token_urlsafe(24)
    try:
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(t)
    except OSError:
        pass
    return t


TOKEN = load_token()


def read_events():
    out = []
    for path in (AUDIT + ".1", AUDIT):
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        pass
        except OSError:
            pass
    for i, e in enumerate(out):
        e["id"] = i
    return out[-5000:]


def tail(path, n=80):
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 60_000))
            return f.read().decode("utf-8", "replace").splitlines()[-n:]
    except OSError:
        return []


def state():
    try:
        st = open(STATE, encoding="utf-8").read().strip() or "ONLINE"
        age = time.time() - os.path.getmtime(STATE)
        return {"state": "OFFLINE" if st == "CLOSE" or age > 600 else st, "age": int(age)}
    except OSError:
        return {"state": "OFFLINE", "age": None}


PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>JARVIS Dashboard</title><style>
:root{--bg:#0b1118;--card:#111b26;--line:#1e2f42;--tx:#d7e6f5;--mut:#7f97ad;--ac:#38bdf8;--ok:#34d399;--warn:#fbbf24;--bad:#f87171}
@media (prefers-color-scheme:light){:root{--bg:#f4f7fa;--card:#fff;--line:#d9e2ea;--tx:#14202b;--mut:#5b7083;--ac:#0369a1;--ok:#047857;--warn:#b45309;--bad:#b91c1c}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:14px/1.45 system-ui,Segoe UI,sans-serif}
header{display:flex;gap:12px;align-items:center;padding:14px 20px;border-bottom:1px solid var(--line);flex-wrap:wrap}
h1{font-size:18px;margin:0;letter-spacing:.12em}h1 b{color:var(--ac)}
.pill{padding:3px 12px;border-radius:99px;border:1px solid var(--line);font-weight:600;font-size:12px}
.s-LISTENING{color:var(--ok)}.s-THINKING{color:var(--warn)}.s-SPEAKING{color:var(--ac)}.s-OFFLINE{color:var(--mut)}
main{padding:18px 20px;max-width:1200px;margin:auto}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.card .n{font-size:26px;font-weight:700}.card .l{color:var(--mut);font-size:12px}
.bar{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;align-items:center}
button,input{background:var(--card);color:var(--tx);border:1px solid var(--line);border-radius:8px;padding:6px 12px;font:inherit}
button{cursor:pointer}button.on{border-color:var(--ac);color:var(--ac)}input{min-width:220px}
.wrap{overflow-x:auto;border:1px solid var(--line);border-radius:10px;background:var(--card)}
table{width:100%;border-collapse:collapse}th,td{padding:7px 12px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--mut);font-weight:600;font-size:12px}td.t{white-space:nowrap;color:var(--mut)}td.d{word-break:break-word}
.k{font-weight:600;font-size:12px}.k-command{color:var(--ac)}.k-tool{color:var(--ok)}.k-blocked{color:var(--bad)}.k-confirm{color:var(--warn)}
pre{margin:0;padding:12px;overflow:auto;max-height:340px;font:12px/1.4 ui-monospace,Consolas,monospace;color:var(--mut)}
h2{font-size:13px;color:var(--mut);letter-spacing:.1em;text-transform:uppercase;margin:22px 0 8px}
.empty{padding:26px;text-align:center;color:var(--mut)}
</style></head><body>
<header><h1>J.A.R.V.I.S <b>DASHBOARD</b></h1><span id="st" class="pill s-OFFLINE">OFFLINE</span>
<span style="color:var(--mut);margin-left:auto" id="upd">connecting...</span></header>
<main>
<div class="cards" id="cards"></div>
<div class="bar" id="chips"></div>
<div class="bar"><input id="q" placeholder="Search activity..."><button id="pause">Pause</button><button id="csv">Export CSV</button></div>
<div class="wrap"><table><thead><tr><th>Time</th><th>Type</th><th>Details</th></tr></thead><tbody id="rows"></tbody></table><div id="none" class="empty" hidden>No activity yet. Talk to JARVIS and it will show up here.</div></div>
<h2>Log (last lines)</h2><div class="wrap"><pre id="log"></pre></div>
</main>
<script>
const KINDS=["all","command","tool","blocked","confirm"];let kind="all",paused=false,data={events:[],log:[]};
const $=id=>document.getElementById(id);
function detail(e){const x={...e};delete x.t;delete x.kind;delete x.id;
 if(e.kind==="command")return e.text;
 if(e.kind==="tool")return e.tool+"("+(e.args||"")+") -> "+(e.result||"")+(e.tainted?"  [outside content read]":"");
 if(e.kind==="blocked")return "BLOCKED "+e.tool+": "+(e.reason||"");
 if(e.kind==="confirm")return (e.approved?"APPROVED":"DENIED")+(e.strict?" (strict)":"")+": "+e.question+(e.answer?"  / heard: "+e.answer:"");
 return JSON.stringify(x)}
function render(){
 const ev=data.events,c=k=>ev.filter(e=>e.kind===k).length;
 const ap=ev.filter(e=>e.kind==="confirm"&&e.approved).length,de=ev.filter(e=>e.kind==="confirm"&&!e.approved).length;
 const cards=[["Commands",c("command")],["Tool calls",c("tool")],["Blocked",c("blocked")],["Approved",ap],["Denied",de]];
 $("cards").replaceChildren(...cards.map(([l,n])=>{const d=document.createElement("div");d.className="card";
  const a=document.createElement("div");a.className="n";a.textContent=n;const b=document.createElement("div");b.className="l";b.textContent=l;d.append(a,b);return d}));
 $("chips").replaceChildren(...KINDS.map(k=>{const b=document.createElement("button");b.textContent=k;if(k===kind)b.className="on";b.onclick=()=>{kind=k;render()};return b}));
 const q=$("q").value.toLowerCase();
 const rows=ev.filter(e=>(kind==="all"||e.kind===kind)&&(!q||(detail(e)+e.kind).toLowerCase().includes(q))).slice(-300).reverse();
 $("none").hidden=rows.length>0;
 $("rows").replaceChildren(...rows.map(e=>{const tr=document.createElement("tr");
  const t=document.createElement("td");t.className="t";t.textContent=(e.t||"").replace("T"," ");
  const k=document.createElement("td");const s=document.createElement("span");s.className="k k-"+e.kind;s.textContent=e.kind;k.append(s);
  const d=document.createElement("td");d.className="d";d.textContent=detail(e);tr.append(t,k,d);return tr}));
 $("log").textContent=data.log.join("\n");
}
async function poll(){if(paused)return;
 try{const r=await fetch("/api/data",{credentials:"same-origin"});if(r.status===401){$("upd").textContent="Open the link printed by dashboard.py (it contains the access token).";return}
  data=await r.json();const st=$("st");st.textContent=data.state.state;st.className="pill s-"+data.state.state;
  $("upd").textContent="updated "+new Date().toLocaleTimeString();render()}catch(e){$("upd").textContent="dashboard stopped"}}
$("pause").onclick=()=>{paused=!paused;$("pause").textContent=paused?"Resume":"Pause";$("pause").className=paused?"on":""};
$("q").oninput=render;
$("csv").onclick=()=>{const esc=v=>'"'+String(v).replace(/"/g,'""')+'"';
 const f=s=>/^[=+\-@]/.test(s)?"'"+s:s;   // stop spreadsheet formula injection
 const csv=["time,type,details",...data.events.map(e=>[esc(e.t),esc(e.kind),esc(f(detail(e)))].join(","))].join("\n");
 const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([csv],{type:"text/csv"}));a.download="jarvis_activity.csv";a.click()};
poll();setInterval(poll,2000);
</script></body></html>"""


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, body, ctype, code=200, extra=None):
        b = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
                         "connect-src 'self'; img-src 'self' data: blob:")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.headers.get("Host", "").split(":")[0] not in ("127.0.0.1", "localhost"):
            return self._send("forbidden", "text/plain", 403)
        u = urlparse(self.path)
        if parse_qs(u.query).get("k", [""])[0] == TOKEN:                      # first visit: trade the token for a cookie
            return self._send("", "text/plain", 302, {"Location": "/", "Set-Cookie": f"jd={TOKEN}; HttpOnly; SameSite=Strict; Path=/"})
        if f"jd={TOKEN}" not in (self.headers.get("Cookie") or ""):
            return self._send("Unauthorized.\nOpen the full link printed in the dashboard window (it ends with ?k=...), or run run_dashboard.bat.\nTip: bookmark that full link; it keeps working between runs.", "text/plain", 401)
        if u.path in ("/", "/index.html"):
            return self._send(PAGE, "text/html; charset=utf-8")
        if u.path == "/api/data":
            return self._send(json.dumps({"events": read_events(), "log": tail(LOG), "state": state()}), "application/json")
        self._send("not found", "text/plain", 404)

    do_POST = do_PUT = do_DELETE = lambda self: self._send("read-only", "text/plain", 405)


class Srv(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    try:
        srv = Srv(("127.0.0.1", a.port), H)
    except OSError:
        srv = Srv(("127.0.0.1", 0), H)                                         # port busy: pick a free one
    url = f"http://127.0.0.1:{srv.server_address[1]}/?k={TOKEN}"
    print("JARVIS Dashboard (read-only, this PC only)\n  " + url + "\nBookmark this full link. Never share it. Press Ctrl+C to stop.")
    if not a.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
