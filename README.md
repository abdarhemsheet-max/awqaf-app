# مراسلات الأوقاف — تطبيق ذكي بـ Gemini

تكتب (أو تحكي) شن تبي بلهجتك، وGemini يقرر نوع المراسلة ويكتبها على ورقة الأوقاف ويحللها في الخلفية. تعدل مباشرة على الورقة، وتختار مكان التوقيع، وتصدر PDF.

## تشغيل محلي
```
pip install -r requirements.txt
cp .env.example .env        # عدّل القيم
export $(cat .env | xargs)  # أو اضبطها يدوياً
python app.py               # http://localhost:5000
```
للتجربة بدون Gemini: `MOCK=1 APP_PASSWORD=123 python app.py`

## النشر المجاني على Render
1. مفتاح Gemini: aistudio.google.com → Get API key.
2. ارفع المجلد كله إلى مستودع GitHub **خاص**.
3. render.com → New → Web Service → اختر المستودع (يقرأ render.yaml تلقائياً).
4. في Environment أضف: `GEMINI_API_KEY` و`APP_PASSWORD`.
5. Deploy → ياخذ رابط تفتحه من أي جهاز.

ملاحظة: الخطة المجانية تنام عند عدم الاستعمال (أول فتحة ~دقيقة). ومفتاح Gemini المجاني قد تُستعمل مدخلاته لتحسين منتجات جوجل، فلا تكتب معلومات حساسة جداً.

## الملفات
- `app.py` — خادم Flask: دخول بباسورد، `/api/compose`، `/api/edit`.
- `prompts/system_prompt.md` — **تعليمات Gemini**: الثوابت (الافتتاح، «عليه ،،،»، التحية…) والتحليل الصامت وشكل الرد JSON. هنا تعدّل القواعد.
- `prompts/edit_prompt.md` — تعليمات «عدّل جزء بالذكاء».
- `static/index.html` — الواجهة كاملة (ورقة A4 متعددة الصفحات، تحرير مباشر، كاشيدة «صورة إلى»، أرشيف محلي، طباعة PDF).
- `static/fonts/` — خط سلطان.
