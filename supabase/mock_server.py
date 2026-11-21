import json, uuid, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

USERS = {}     # email -> {id, pw}
TOKENS = {}    # access token -> user id
REFRESH = {}   # refresh token -> user id
ROWS = {}      # (uid, kind, id) -> row
N = [0]

def issue(uid, email):
    N[0] += 1
    at, rt = f"at-{uid}-{N[0]}", f"rt-{uid}-{N[0]}"
    TOKENS[at] = uid; REFRESH[rt] = uid
    return {"access_token": at, "refresh_token": rt, "expires_in": 3600, "user": {"id": uid, "email": email}}

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "apikey, authorization, content-type, prefer, x-client-info")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, PATCH, DELETE")
    def _send(self, code, obj=None):
        body = b"" if obj is None else json.dumps(obj).encode()
        self.send_response(code); self._cors()
        self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)
    def do_OPTIONS(self): self.send_response(204); self._cors(); self.end_headers()
    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"null") if n else None
    def _uid(self):
        a = self.headers.get("Authorization", "")
        return TOKENS.get(a.replace("Bearer ", ""))
    def do_POST(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        if not self.headers.get("apikey"): return self._send(401, {"message": "No API key"})
        if u.path == "/auth/v1/signup":
            b = self._body(); e = b["email"]
            if e in USERS: return self._send(422, {"msg": "User already registered"})
            USERS[e] = {"id": str(uuid.uuid4()), "pw": b["password"]}
            return self._send(200, issue(USERS[e]["id"], e))
        if u.path == "/auth/v1/token":
            gt = q.get("grant_type", [""])[0]; b = self._body()
            if gt == "password":
                us = USERS.get(b["email"])
                if not us or us["pw"] != b["password"]: return self._send(400, {"error_description": "Invalid login credentials"})
                return self._send(200, issue(us["id"], b["email"]))
            if gt == "refresh_token":
                uid = REFRESH.get(b["refresh_token"])
                if not uid: return self._send(400, {"error_description": "Invalid Refresh Token"})
                em = next(k for k, v in USERS.items() if v["id"] == uid)
                return self._send(200, issue(uid, em))
        if u.path == "/rest/v1/awq_store":
            uid = self._uid()
            if not uid: return self._send(401, {"message": "JWT expired"})
            for r in self._body():
                ROWS[(uid, r["kind"], r["id"])] = {"kind": r["kind"], "id": r["id"], "data": r.get("data", {}), "deleted": r.get("deleted", False), "updated_at": r["updated_at"]}
            return self._send(201)
        self._send(404, {"message": "not found"})
    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/rest/v1/awq_store":
            uid = self._uid()
            if not uid: return self._send(401, {"message": "JWT expired"})
            return self._send(200, [v for (x, k, i), v in ROWS.items() if x == uid])
        if u.path == "/__dump":
            return self._send(200, {"rows": [{"u": k[0][:6], "kind": k[1], "id": k[2], "deleted": v["deleted"], "name": (v["data"].get("name") or v["data"].get("s") or "")[:30]} for k, v in ROWS.items()]})
        self._send(404, {"message": "not found"})

ThreadingHTTPServer(("127.0.0.1", 5057), H).serve_forever()
