import os, json, hmac, re
from functools import wraps
import requests
from flask import Flask, request, session, redirect, jsonify, send_from_directory, render_template_string

BASE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview")
FALLBACK_MODELS = ["gemini-3.1-flash-lite", "gemini-flash-latest"]
PASSWORD = os.environ.get("APP_PASSWORD", "")
MOCK = os.environ.get("MOCK") == "1"

def read(p):
    with open(os.path.join(BASE, p), encoding="utf-8") as f:
        return f.read()

SYSTEM = read("prompts/system_prompt.md")
EDIT = read("prompts/edit_prompt.md")
TABLE = read("prompts/table_prompt.md")

LOGIN = """<!doctype html><html lang=ar dir=rtl><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>دخول</title><body style="font-family:sans-serif;background:#eef1ee;display:grid;place-items:center;height:100vh;margin:0">
<form method=post style="background:#fff;padding:26px;border-radius:14px;box-shadow:0 4px 18px #0002;width:300px;text-align:center">
<h2 style="color:#17392b;margin-top:0">مراسلات الأوقاف</h2>
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
    return send_from_directory("static", "index.html")

def gemini(system, user, temperature=0.4):
    if not GEMINI_KEY:
        raise RuntimeError("GEMINI_API_KEY غير مضبوط")
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {"temperature": temperature, "responseMimeType": "application/json"},
    }
    # الموديل المضبوط أولاً ثم بدائل؛ وإعادة محاولة عند الانشغال (429/5xx) أو JSON غير صالح
    models = [MODEL] + [m for m in FALLBACK_MODELS if m != MODEL]
    last = "تعذر الاتصال بـ Gemini"
    for m in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
        try:
            r = requests.post(url, params={"key": GEMINI_KEY}, json=body, timeout=60)
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
            txt = "".join(p.get("text", "") for p in parts).strip()
            txt = re.sub(r"^```(?:json)?|```$", "", txt).strip()
            return json.loads(txt)
        except (KeyError, IndexError, ValueError) as e:
            last = f"رد غير صالح من {m}: {e}"
    raise RuntimeError(last)

MOCK_LETTER = {
    "type": "تكليف",
    "blocks": [
        {"role": "to", "html": "السيد / محمد لطرش"},
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
        return jsonify(MOCK_LETTER if MOCK else gemini(SYSTEM, text))
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
        return jsonify(gemini(EDIT, user, 0.5))
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
        return jsonify(gemini(TABLE, "\n".join(["السياق (المراسلة):", ctx, "", "المطلوب: " + req]), 0.3))
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
        return jsonify(text="نبي نكلف محمد لطرش يغطي زيارة رئيس الهيئة")
    if not GEMINI_KEY:
        return jsonify(error="GEMINI_API_KEY غير مضبوط"), 500
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

TPLVARS = read("prompts/tplvars_prompt.md")

@app.post("/api/tplvars")
@need_login
def tplvars():
    text = (request.json or {}).get("text", "").strip()
    if not text:
        return jsonify(error="النص فارغ"), 400
    try:
        if MOCK:
            return jsonify(variables=[{"name": "اسم الموظف", "text": "محمد لطرش"}])
        return jsonify(gemini(TPLVARS, text, 0.2))
    except Exception as e:
        return jsonify(error=str(e)), 500

@app.get("/health")
def health():
    return "ok"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
