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
تحفظ المراسلات (الأرشيف)، قوالب المراسلات، قوالب التنسيق، والإعدادات في حسابك وتزامنها بين الأجهزة. التطبيق يشتغل بدونها (التخزين المحلي) وهي اختيارية.

1. أنشئ مشروعاً مجانياً على https://supabase.com (Project name: marasilati).
2. SQL Editor ← New query ← الصق محتوى `supabase/schema.sql` ← Run.
3. Project Settings ← API: انسخ **Project URL** و**anon public key** (هذا المفتاح عام بطبيعته، والحماية من Row Level Security).
4. في «مراسلاتي»: زر ☁ فوق (أو خصائص متقدمة ← الحفظ والمزامنة) ← ألصق الرابط والمفتاح ← أدخل بريدك وكلمة مرور ← «إنشاء حساب» ثم «دخول».
5. بعد إنشاء حسابك: Authentication ← Sign In / Providers ← Email ← عطّل **Allow new users to sign up** حتى لا يُنشئ غيرك حسابات.
6. على الجهاز الثاني: نفس الرابط والمفتاح والبريد فتنزل كل بياناتك.

اختياري: لإدخال الرابط والمفتاح تلقائياً في الصفحة المنشورة أضفهما كـ Secrets في GitHub باسم `SUPABASE_URL` و`SUPABASE_ANON_KEY` ثم شغّل Deploy.

طريقة التزامن: التخزين المحلي أولاً ثم رفع التغييرات بعد ثانية ونصف، وآخر تعديل يفوز، والحذف يُنقل كعلامة حذف. للتجربة بدون حساب حقيقي يوجد خادم محاكاة بسيط (`supabase/mock_server.py`).
