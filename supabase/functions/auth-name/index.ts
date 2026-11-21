// «مراسلاتي»: دخول بسيط بالاسم + رمز. ينشئ الحساب أول مرة تلقائياً (بدون بريد ولا تأكيد) ويرجع جلسة Supabase عادية.
// الاسم يتحوّل إلى بريد داخلي ثابت (هاش) والرمز يتحوّل إلى كلمة مرور مشتقة؛ لا يُحفظ الرمز نفسه.
import { createClient } from "npm:@supabase/supabase-js@2";

const URL_ = Deno.env.get("SUPABASE_URL")!;
const SERVICE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const ANON = Deno.env.get("SUPABASE_ANON_KEY")!;
const PEPPER = Deno.env.get("AWQ_PEPPER") || "marasilati-v1";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const json = (o: unknown, status = 200) =>
  new Response(JSON.stringify(o), { status, headers: { ...cors, "Content-Type": "application/json" } });

async function sha(s: string) {
  const b = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(b)].map((x) => x.toString(16).padStart(2, "0")).join("");
}
// توحيد بسيط للاسم العربي: بدون تشكيل ولا تطويل، وتوحيد الألف والياء
const norm = (n: string) =>
  n.normalize("NFKC").replace(/[ً-ٰٟـ]/g, "").replace(/[أإآٱ]/g, "ا").replace(/ى/g, "ي")
    .replace(/\s+/g, " ").trim().toLowerCase();

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  try {
    const body = await req.json();
    const name = String(body.name ?? "");
    const code = String(body.code ?? "");
    const n = norm(name);
    if (n.length < 2) return json({ error: "اكتب اسمك (حرفين على الأقل)" }, 400);
    if (code.length < 4) return json({ error: "الرمز لازم 4 خانات على الأقل" }, 400);

    const email = `u${(await sha("e|" + n + "|" + PEPPER)).slice(0, 24)}@marasilati.app`;
    const password = await sha("p|" + n + "|" + code + "|" + PEPPER);
    const admin = createClient(URL_, SERVICE, { auth: { persistSession: false } });
    const anon = createClient(URL_, ANON, { auth: { persistSession: false } });

    let created = false;
    let r = await anon.auth.signInWithPassword({ email, password });
    if (r.error) {
      const c = await admin.auth.admin.createUser({ email, password, email_confirm: true, user_metadata: { display_name: name.trim() } });
      if (c.error) return json({ error: "الرمز غلط لهذا الاسم" }, 401);
      created = true;
      r = await anon.auth.signInWithPassword({ email, password });
      if (r.error) return json({ error: r.error.message }, 500);
    }
    const s = r.data.session!;
    return json({
      access_token: s.access_token,
      refresh_token: s.refresh_token,
      expires_in: s.expires_in,
      user: { id: r.data.user!.id, email, name: name.trim() },
      created,
    });
  } catch (e) {
    return json({ error: String((e as Error).message ?? e) }, 500);
  }
});
