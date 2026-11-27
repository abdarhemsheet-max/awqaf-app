import os, json, hmac, re, glob, shutil, subprocess, tempfile, hashlib, sys, time
from functools import wraps
import requests
from flask import Flask, request, session, redirect, jsonify, send_from_directory, render_template_string

BASE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# المحلي (start.bat) = الافتراضي عند التشغيل المباشر: بدون باسورد، Claude عبر Claude Code، أرشيف وPDF على الكمبيوتر
LOCAL = os.environ.get("LOCAL", "1" if __name__ == "__main__" else "0") == "1"
AI = os.environ.get("AI", "claude").lower()            # claude (اشتراكك عبر Claude Code) أو gemini (احتياطي)
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "sonnet")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview")
FALLBACK_MODELS = ["gemini-3.1-flash-lite", "gemini-flash-latest"]
PASSWORD = "" if LOCAL else os.environ.get("APP_PASSWORD", "")
MOCK = os.environ.get("MOCK") == "1"
ARCHIVE = os.path.join(BASE, "archive")
SB_URL = os.environ.get("SUPABASE_URL", "https://qpindseciwxoageaqdtf.supabase.co")
SB_KEY = os.environ.get("SUPABASE_ANON_KEY", "sb_publishable_OpnTN4pma05OquJKtZPuDg_2e-m5HM7")
WIN = sys.platform == "win32"

def read(p):
    with open(os.path.join(BASE, p), encoding="utf-8") as f:
        return f.read()

PROMPT_FILES = {k: f"prompts/{k}.md" for k in ("system_prompt", "edit_prompt", "table_prompt", "review_prompt", "tplvars_prompt")}
SYSTEM = read(PROMPT_FILES["system_prompt"])
EDIT = read(PROMPT_FILES["edit_prompt"])
TABLE = read(PROMPT_FILES["table_prompt"])
REVIEW = read(PROMPT_FILES["review_prompt"])
TPLVARS = read(PROMPT_FILES["tplvars_prompt"])

LOGIN = """<!doctype html><html lang=ar dir=rtl><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>دخول</title><body style="font-family:sans-serif;background:#eef1ee;display:grid;place-items:center;height:100vh;margin:0">
<form method=post style="background:#fff;padding:26px;border-radius:14px;box-shadow:0 4px 18px #0002;width:300px;text-align:center">
<h2 style="color:#1b4b5f;margin-top:0">مراسلاتي</h2>
<input type=password name=p placeholder="كلمة المرور" autofocus style="width:100%;padding:10px;font-size:16px;border:1px solid #ccc;border-radius:8px;box-sizing:border-box">
<button style="margin-top:12px;width:100%;padding:10px;font-size:16px;background:#2d6a4f;color:#fff;border:0;border-radius:8px">دخول</button>
<p style="color:#b3261e;font-size:13px">{{e}}</p></form>"""

def need_login(f):
    @wraps(f)
    def w(*a, **k):
        if PASSWORD and not session.get("ok"):
            if request.path.startswith("/api/"):
                return jsonify(error="غير مسجل"), 401
            return redirect("/login")
        return f(*a, **k)
    return w

def local_only(f):
    @wraps(f)
    def w(*a, **k):
        if not LOCAL:
            return jsonify(error="متاح في النسخة المحلية فقط"), 404
        return f(*a, **k)
    return w

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if hmac.compare_digest(request.form.get("p", ""), PASSWORD):
            session["ok"] = True
            session.permanent = True
            return redirect("/")
        return render_template_string(LOGIN, e="كلمة المرور غلط")
    return render_template_string(LOGIN, e="")

@app.route("/")
@need_login
def index():
    # مزامنة الأرشيف مع الهاتف: نفس مشروع Supabase اللي في الموقع (الرابط والمفتاح العام publishable، ليسا سرّاً)
    html = read("static/index.html").replace("__SB_URL__", SB_URL).replace("__SB_KEY__", SB_KEY)
    return html, 200, {"Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store"}

@app.route("/prompts/<path:p>")
def prompts_file(p):
    return send_from_directory("prompts", p)

# ---------------- Claude عبر Claude Code (اشتراكك، بدون مفتاح) ----------------
def claude_exe():
    e = os.environ.get("CLAUDE_EXE") or shutil.which("claude")
    if e:
        return e
    # النسخة المرفقة مع تطبيق Claude لسطح المكتب (المسار يتغير مع التحديثات: نأخذ الأحدث)
    pats = [os.path.join(os.environ.get("LOCALAPPDATA", ""), "Claude-Data", "*", "claude-code", "*", "*", "claude.exe"),
            os.path.join(os.path.expanduser("~"), ".local", "bin", "claude.exe")]
    found = [p for pat in pats for p in glob.glob(pat)]
    if not found:
        raise RuntimeError("ما لقيتش Claude Code على الكمبيوتر. ثبّته أو حط مساره في CLAUDE_EXE")
    return max(found, key=os.path.getmtime)

_SYS_DIR = os.path.join(tempfile.gettempdir(), "awqaf_claude")

def _sys_file(system):
    os.makedirs(_SYS_DIR, exist_ok=True)
    p = os.path.join(_SYS_DIR, hashlib.sha1(system.encode("utf-8")).hexdigest()[:16] + ".md")
    if not os.path.exists(p):
        with open(p, "w", encoding="utf-8") as f:
            f.write(system)
    return p

def _json_from(txt):
    txt = re.sub(r"^```(?:json)?|```$", "", (txt or "").strip()).strip()
    m = re.search(r"\{[\s\S]*\}", txt)
    return json.loads(m.group(0) if m else txt)

def ask_claude(system, user):
    """يشغّل Claude Code بدون واجهة: النص عبر stdin، والتعليمات من ملف (لا حدود لطول سطر الأوامر في ويندوز)."""
    exe = claude_exe()
    env = {k: v for k, v in os.environ.items()
           if not (k.startswith("CLAUDE_CODE") or k in ("CLAUDECODE", "ANTHROPIC_BASE_URL"))}
    cmd = [exe, "-p", "--output-format", "json", "--model", CLAUDE_MODEL, "--system-prompt-file", _sys_file(system),
           "--tools", "", "--no-session-persistence", "--strict-mcp-config", "--setting-sources", ""]
    last = "تعذر الاتصال بـ Claude"
    for attempt in range(2):  # إعادة محاولة مرة واحدة إذا رجع JSON غير صالح
        try:
            r = subprocess.run(cmd, input=user, capture_output=True, text=True, encoding="utf-8", errors="replace",
                               cwd=_SYS_DIR, env=env, timeout=240,
                               creationflags=subprocess.CREATE_NO_WINDOW if WIN else 0)
        except subprocess.TimeoutExpired:
            raise RuntimeError("Claude طوّل في الرد، أعد المحاولة")
        try:
            out = json.loads(r.stdout)
        except ValueError:
            raise RuntimeError(f"Claude Code: {(r.stderr or r.stdout)[:300]}")
        res = out.get("result") or ""
        if out.get("is_error"):
            if re.search(r"auth|log ?in|OAuth|credential", res, re.I):
                raise RuntimeError("Claude مش مسجّل دخول. سكّر التطبيق وشغّله من جديد، وسجّل دخولك في النافذة اللي تطلع (مرة وحدة بس)")
            if re.search(r"limit|rate|usage", res, re.I):
                raise RuntimeError("⏳ اشتراك Claude وصل حد الاستعمال، استنى شوية: " + res[:160])
            raise RuntimeError("Claude: " + res[:300])
        try:
            return _json_from(res)
        except ValueError as e:
            last = f"رد غير صالح من Claude: {e}"
    raise RuntimeError(last)

def claude_status():
    try:
        exe = claude_exe()
        env = {k: v for k, v in os.environ.items() if not (k.startswith("CLAUDE_CODE") or k in ("CLAUDECODE", "ANTHROPIC_BASE_URL"))}
        r = subprocess.run([exe, "auth", "status"], capture_output=True, text=True, encoding="utf-8", env=env, timeout=30,
                           creationflags=subprocess.CREATE_NO_WINDOW if WIN else 0)
        return bool(json.loads(r.stdout).get("loggedIn"))
    except Exception:
        return False

# ---------------- Gemini (احتياطي فقط: AI=gemini مع GEMINI_API_KEY) ----------------
def gemini(system, user, temperature=0.4, thinking="minimal"):
    if not GEMINI_KEY:
        raise RuntimeError("GEMINI_API_KEY غير مضبوط")
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {"temperature": temperature, "responseMimeType": "application/json"},
    }
    models = [MODEL] + [m for m in FALLBACK_MODELS if m != MODEL]
    last = "تعذر الاتصال بـ Gemini"
    for m in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
        gc = dict(body["generationConfig"])
        if m.startswith("gemini-3"):
            gc["thinkingConfig"] = {"thinkingLevel": thinking}
        try:
            r = requests.post(url, params={"key": GEMINI_KEY}, json={**body, "generationConfig": gc}, timeout=60)
        except requests.RequestException as e:
            last = f"Gemini: {e}"
            continue
        if r.status_code != 200:
            last = f"Gemini {r.status_code}: {r.text[:300]}"
            if r.status_code in (400, 401, 403):
                break
            continue
        try:
            parts = r.json()["candidates"][0]["content"]["parts"]
            return _json_from("".join(p.get("text", "") for p in parts))
        except (KeyError, IndexError, ValueError) as e:
            last = f"رد غير صالح من {m}: {e}"
    raise RuntimeError(last)

def ask(system, user, temperature=0.4, thinking="minimal"):
    if AI == "gemini" and GEMINI_KEY:
        return gemini(system, user, temperature, thinking)
    return ask_claude(system, user)

def today_line():
    """تاريخ اليوم (بتوقيت ليبيا UTC+2) ليحسب الذكاء «الأحد القادم» وأمثالها."""
    from datetime import datetime, timedelta, timezone
    d = datetime.now(timezone.utc) + timedelta(hours=2)
    days = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
    return f"[اليوم: {days[d.weekday()]} {d.year}/{d.month:02d}/{d.day:02d}م]"

MOCK_LETTER = {
    "type": "تكليف",
    "blocks": [
        {"role": "to", "html": "السيد / محمد الفلاني"},
        {"role": "greeting", "html": "السلام عليكم ورحمة الله وبركاته"},
        {"role": "body", "html": "نكلفك بـ<b>التغطية الإعلامية</b> لزيارة <b>السيد / رئيس الهيئة العامة للأوقاف والشؤون الإسلامية</b>، وذلك يوم {{فراغ}} الموافق {{تاريخ}}م، بـ {{فراغ}}، على أن تتولى <b>نشر المادة مباشرةً</b> على صفحة المكتب."},
        {"role": "closing", "html": "نأمل المباشرة في التنفيذ."},
        {"role": "farewell", "html": "والسلام عليكم ورحمة الله وبركاته"},
    ],
    "cc": ["مدير مكتب الأوقاف القره بوللي", "قسم الشؤون الإدارية", "قسم المتابعة", "قسم الإعلام", "الملف الدوري العام"],
    "analysis": {"الفكرة": "تجريبي"}, "missing": [],
}

@app.post("/api/compose")
@need_login
def compose():
    text = (request.json or {}).get("text", "").strip()
    if not text:
        return jsonify(error="النص فارغ"), 400
    try:
        return jsonify(MOCK_LETTER if MOCK else ask(SYSTEM, today_line() + "\n" + text, 0.4, "low"))
    except Exception as e:
        return jsonify(error=str(e)), 500

@app.post("/api/edit")
@need_login
def edit():
    d = request.json or {}
    sel, req, ctx = d.get("selection", ""), d.get("request", ""), d.get("context", "")
    if not sel or not req:
        return jsonify(error="ناقص"), 400
    try:
        if MOCK:
            return jsonify(text=sel + " (معدّل: " + req + ")")
        user = f"السياق (المراسلة كاملة):\n{ctx}\n\nالجزء المطلوب تعديله:\n{sel}\n\nالطلب: {req}"
        return jsonify(ask(EDIT, user, 0.5))
    except Exception as e:
        return jsonify(error=str(e)), 500

@app.post("/api/table")
@need_login
def table():
    d = request.json or {}
    req, ctx = d.get("request", "").strip(), d.get("context", "")
    if not req:
        return jsonify(error="ناقص"), 400
    try:
        if MOCK:
            return jsonify(headers=["م", "الاسم", "الملاحظات"], rows=[["1", "{{فراغ}}", ""], ["2", "{{فراغ}}", ""]])
        return jsonify(ask(TABLE, "\n".join(["السياق (المراسلة):", ctx, "", "المطلوب: " + req]), 0.3))
    except Exception as e:
        return jsonify(error=str(e)), 500

TX_PROMPT = ("فرّغ هذا التسجيل الصوتي إلى نص عربي مكتوب. المتحدث ليبي يتكلم بلهجته المحلية. "
             "اكتب ما قيل بدقة وبإملاء سليم وعلامات ترقيم بسيطة، دون أي تعليق أو شرح أو مقدمة. "
             "الأسماء والأرقام كما قيلت. إن لم يكن في التسجيل كلام واضح فأعد نصاً فارغاً.")

@app.post("/api/transcribe")
@need_login
def transcribe():
    d = request.json or {}
    audio, mime = d.get("audio", ""), d.get("mime", "audio/webm")
    if not audio:
        return jsonify(error="التسجيل فاضي"), 400
    if MOCK:
        return jsonify(text="نبي نكلف محمد الفلاني يغطي زيارة رئيس الهيئة")
    if not GEMINI_KEY:
        return jsonify(error="التفريغ الصوتي على الخادم يحتاج GEMINI_API_KEY؛ استعمل ميكروفون المتصفح"), 500
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
        body = {"contents": [{"role": "user", "parts": [{"text": TX_PROMPT}, {"inlineData": {"mimeType": mime, "data": audio}}]}],
                "generationConfig": {"temperature": 0}}
        r = requests.post(url, params={"key": GEMINI_KEY}, json=body, timeout=100)
        if r.status_code != 200:
            raise RuntimeError(f"Gemini {r.status_code}: {r.text[:300]}")
        parts = r.json()["candidates"][0]["content"]["parts"]
        return jsonify(text="".join(p.get("text", "") for p in parts).strip())
    except Exception as e:
        return jsonify(error=str(e)), 500

@app.post("/api/tplvars")
@need_login
def tplvars():
    text = (request.json or {}).get("text", "").strip()
    if not text:
        return jsonify(error="النص فارغ"), 400
    try:
        if MOCK:
            return jsonify(variables=[{"name": "اسم الموظف", "text": "محمد الفلاني"}])
        return jsonify(ask(TPLVARS, text, 0.2))
    except Exception as e:
        return jsonify(error=str(e)), 500

@app.post("/api/review")
@need_login
def review():
    text = (request.json or {}).get("text", "").strip()
    if not text:
        return jsonify(error="النص فارغ"), 400
    try:
        if MOCK:
            return jsonify(blocks=[], add=[], changes=["ما لقيت أخطاء، النص سليم"])
        return jsonify(ask(REVIEW, text, 0.3, "low"))
    except Exception as e:
        return jsonify(error=str(e)), 500

# ---------------- النسخة المحلية: معلومات، تحديث حي، أرشيف، PDF ----------------
@app.get("/api/info")
def info():
    return jsonify(local=LOCAL, ai="gemini" if (AI == "gemini" and GEMINI_KEY) else "claude", model=CLAUDE_MODEL)

@app.get("/api/claude-status")
@local_only
def claude_status_api():
    return jsonify(loggedIn=claude_status())

@app.get("/api/version")
@local_only
def version():
    """أحدث وقت تعديل لملفات الواجهة والتعليمات: الصفحة تعيد التحميل لما يتغيّر (التعديل الحي)."""
    m = 0
    for d in ("static", "prompts"):
        for root, _, files in os.walk(os.path.join(BASE, d)):
            if "vendor" in root or "fonts" in root:
                continue
            for f in files:
                m = max(m, os.path.getmtime(os.path.join(root, f)))
    return jsonify(v=int(m * 1000))

def _arc_path(i):
    i = str(i)
    if not re.fullmatch(r"\d{1,20}", i):
        raise ValueError("معرّف غير صالح")
    return os.path.join(ARCHIVE, i + ".json")

@app.get("/api/archive")
@local_only
def arc_list():
    os.makedirs(ARCHIVE, exist_ok=True)
    items = []
    for p in glob.glob(os.path.join(ARCHIVE, "*.json")):
        try:
            with open(p, encoding="utf-8") as f:
                items.append(json.load(f))
        except (OSError, ValueError):
            pass
    items.sort(key=lambda x: x.get("u", 0), reverse=True)
    return jsonify(items=items)

@app.post("/api/archive")
@local_only
def arc_save():
    os.makedirs(ARCHIVE, exist_ok=True)
    n = 0
    for it in (request.json or {}).get("items", []):
        try:
            p = _arc_path(it.get("id"))
        except ValueError:
            continue
        txt = json.dumps(it, ensure_ascii=False, indent=1)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                if f.read() == txt:
                    continue
        with open(p, "w", encoding="utf-8") as f:
            f.write(txt)
        n += 1
    return jsonify(saved=n)

@app.delete("/api/archive/<i>")
@local_only
def arc_del(i):
    try:
        p = _arc_path(i)
    except ValueError:
        return jsonify(error="معرّف غير صالح"), 400
    if os.path.exists(p):
        os.remove(p)
    return jsonify(ok=True)

def documents_dir():
    if WIN:
        try:
            import ctypes, uuid
            from ctypes import wintypes
            fid = uuid.UUID("{FDD39AD0-238F-46AF-ADB4-6C85480369C7}")  # FOLDERID_Documents (يتبع OneDrive لو محوّل)
            class GUID(ctypes.Structure):
                _fields_ = [("d1", wintypes.DWORD), ("d2", wintypes.WORD), ("d3", wintypes.WORD), ("d4", ctypes.c_ubyte * 8)]
            g = GUID(fid.fields[0], fid.fields[1], fid.fields[2], (ctypes.c_ubyte * 8)(*fid.bytes[8:]))
            out = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(out)) == 0:
                path = out.value
                ctypes.windll.ole32.CoTaskMemFree(out)
                return path
        except Exception:
            pass
    return os.path.join(os.path.expanduser("~"), "Documents")

def _render_pdfs(docs, base):
    from playwright.sync_api import sync_playwright
    outs = []
    with sync_playwright() as p:
        b = None
        for ch in ("msedge", "chrome", None):
            try:
                b = p.chromium.launch(channel=ch) if ch else p.chromium.launch()
                break
            except Exception:
                continue
        if not b:
            raise RuntimeError("ما لقيتش متصفح Edge أو Chrome لصنع الـPDF")
        try:
            pg = b.new_page()
            for html in docs:
                pg.goto(base + "health")  # نفس الأصل: الخطوط static/fonts تتحمّل من الخادم
                pg.set_content(html, wait_until="networkidle")
                pg.evaluate("document.fonts.ready.then(()=>1)")
                n = pg.evaluate("document.querySelectorAll('#pages .a4').length") or 1  # بدون صفحة فاضية زائدة في الآخر
                outs.append(pg.pdf(format="A4", print_background=True, prefer_css_page_size=True, page_ranges=f"1-{n}",
                                   margin={"top": "0", "right": "0", "bottom": "0", "left": "0"}))
        finally:
            b.close()
    return outs

@app.post("/api/pdf")
@local_only
def make_pdf():
    d = request.json or {}
    docs = [x for x in d.get("docs", []) if isinstance(x, str) and x.strip()]
    if not docs:
        return jsonify(error="ما فيه ورقة"), 400
    name = re.sub(r'[\\/:*?"<>|\r\n]+', "", d.get("name") or "مراسلة").strip()[:90] or "مراسلة"
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    try:
        pdfs = _render_pdfs(docs, request.host_url)
        if len(pdfs) == 1:
            data = pdfs[0]
        else:
            import io
            from pypdf import PdfWriter, PdfReader
            w, buf = PdfWriter(), io.BytesIO()
            for x in pdfs:
                for pg in PdfReader(io.BytesIO(x)).pages:
                    w.add_page(pg)
            w.write(buf)
            data = buf.getvalue()
        folder = os.path.join(documents_dir(), "مراسلات الأوقاف")
        os.makedirs(folder, exist_ok=True)
        path, k = os.path.join(folder, name), 2
        while os.path.exists(path):
            path = os.path.join(folder, f"{name[:-4]} ({k}).pdf")
            k += 1
        with open(path, "wb") as f:
            f.write(data)
        if WIN and d.get("open", True):
            subprocess.Popen(["explorer", "/select,", path])
        return jsonify(path=path, name=os.path.basename(path))
    except Exception as e:
        return jsonify(error=f"تعذر صنع الـPDF: {e}"), 500

@app.get("/health")
def health():
    return "ok"

if __name__ == "__main__":
    # محلي فقط: 127.0.0.1، ومع debug + reloader يعيد التشغيل لما يتغيّر app.py أو ملفات prompts/ (التعديل الحي)
    extra = [os.path.join(BASE, p) for p in PROMPT_FILES.values()]
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=True, use_reloader=True,
            extra_files=extra, threaded=True)
