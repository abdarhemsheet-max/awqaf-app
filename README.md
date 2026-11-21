# مراسلاتي — تطبيق ذكي لمراسلات مكتب الأوقاف

تكتب (أو تحكي) شن تبي بلهجتك، والذكاء الاصطناعي (Gemini أو Claude) يقرر نوع المراسلة ويكتبها على ورقة الأوقاف ويحللها في الخلفية. تعدّل مباشرة على الورقة، وتصدّر PDF أو ترسله واتساب. وفي تبويب «مراسلات معتادة» تحفظ قوالب بمتغيرات.

## طريقتان للتشغيل

### 1) GitHub Pages (الموقع الحالي، بلا خادم)
- الرابط: https://abdarhemsheet-max.github.io/awqaf-app/
- المتصفح يكلّم Gemini أو Claude مباشرة. المفتاح الافتراضي (Gemini) يدخل الصفحة وقت النشر من Secret في المستودع اسمه `GEMINI_API_KEY` (لا يُكتب في الكود): غيّره من Settings ← Secrets ← Actions ثم شغّل Actions ← Deploy to GitHub Pages.
- كل مستخدم يقدر يضع مفتاحه (Gemini أو Claude) من زر «🔑»، ويتحفظ في متصفحه فقط.
- تنبيه: المفتاح الافتراضي ظاهر لمن يفحص الصفحة. قيّده من Google AI Studio / Cloud بالنطاق `https://abdarhemsheet-max.github.io/*` وبواجهة Generative Language API فقط، أو استعمل الطريقة الثانية.

### 2) خادم Flask (مفتاح مخفي + كلمة مرور)
```
pip install -r requirements.txt
cp .env.example .env        # عدّل القيم
python app.py               # http://localhost:5000
```
للتجربة بدون Gemini: `MOCK=1 APP_PASSWORD=123 python app.py`

للنشر على Render: ارفع المستودع، وأنشئ Web Service (يقرأ `render.yaml`)، وأضف `GEMINI_API_KEY` و`APP_PASSWORD` في Environment. الخطة المجانية تنام عند عدم الاستعمال (أول فتحة ~دقيقة).

ملاحظة: خادم Flask يستعمل Gemini فقط (واجهة Claude في الصفحة الثابتة).

## الملفات
- `app.py` — خادم Flask: `/api/compose`، `/api/edit`، `/api/table`، `/api/tplvars`، `/api/transcribe`.
- `prompts/` — تعليمات الذكاء: `system_prompt.md` (الثوابت والتحليل)، `edit_prompt.md`، `table_prompt.md`، `tplvars_prompt.md`.
- `static/index.html` — الواجهة كاملة (ورقة A4 متعددة الصفحات، تحرير مباشر، جداول، قوالب، أرشيف، PDF).
- `static/fonts/` — الخطوط (سلطان، Amiri، Tajawal، Noto Naskh) داخل المستودع.
- `static/vendor/` — مكتبات PDF (html2canvas، jsPDF) داخل المستودع.
- `.github/workflows/pages.yml` — النشر التلقائي على Pages عند كل رفع إلى `main`.

## ملاحظات
- الأرشيف والقوالب محفوظة في متصفح كل جهاز (localStorage). للنقل بين الأجهزة: «مراسلات معتادة ← نسخة احتياطية (تصدير/استيراد)».
- مفتاح Gemini المجاني حدوده اليومية قليلة؛ لو وصلت للحد تظهر رسالة، والقوالب لا تستهلك أي رصيد.
- الورقة الرسمية: نص أسود فقط، والترويسة والرقم الإشاري والتاريخ تُترك فارغة. التفاصيل في `CLAUDE.md`.

## المزامنة السحابية (Supabase)
الاستعمال: زر ☁ فوق ← اكتب **اسمك** و**رمزك** (4 خانات أو أكثر) ← دخول. أول مرة ينشئ حسابك لوحده، وبعدها نفس الاسم والرمز على أي جهاز يرجّع المراسلات والقوالب وقوالب التنسيق والإعدادات. الأسماء العربية توحَّد (تشكيل/همزة/مسافات).

التركيب (مرة وحدة، بالـ CLI):
```
supabase login
supabase projects create marasilati --org-id <ORG> --region eu-central-1 --db-password <PASS>
supabase link --project-ref <REF> --password <PASS>
supabase db push                         # يطبّق supabase/migrations (جدول awq_store + RLS)
supabase functions deploy auth-name --project-ref <REF> --use-api --no-verify-jwt
```
ثم أضف `SUPABASE_URL` و`SUPABASE_ANON_KEY` (المفتاح العام/publishable) كـ Secrets في GitHub وشغّل Deploy ليدخلا في الصفحة. اختيارياً: `supabase secrets set AWQ_PEPPER=<نص عشوائي>`.

ملاحظات: الدالة `supabase/functions/auth-name` تحوّل الاسم لبريد داخلي والرمز لكلمة مرور مشتقة (لا يُخزَّن الرمز). أي شخص يكتب اسماً جديداً ينشئ حساباً منفصلاً لا يرى بياناتك؛ استعمل رمزاً أطول من 4 خانات. المشروع الحالي: `qpindseciwxoageaqdtf`. للتجربة المحلية يوجد `supabase/mock_server.py`.
