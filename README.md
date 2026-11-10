# Astromind — محرك متعدد البروفايلات (Self + Partner + Children)

نظام تلقائي يبني **قراءة يومية / أسبوعية / شهرية**، ويحسب **السيناستري** بين خرائطك وخرائط من تضيفهم لاحقًا، ويولّد **أدلة تعامل تربوية وعاطفية** وتقويمًا زمنيًا قابلًا للاستيراد.

الفكرة المعمارية: **احسب مرة، رتّب مرة، واكتب فقط ما تغيّر.**

- الحساب الفلكي حتمي ومخزّن (لا يُعاد إلا عند تغيّر البيانات).
- طبقة إشارات ترتّب وتُلخّص وتُبقي **أعلى 3 إشارات** لكل مجال.
- طبقة سرد عربية قصيرة، قابلة للعمل، **بدون أي استدعاء LLM** في الوضع الافتراضي.
- كل التقارير مبنية على قوالب، لذلك تعمل حتى لو تعطّل أي API خارجي.

---

## ما الذي تحصل عليه؟

| المخرج | المسار | متى يُنتج |
|---|---|---|
| بطاقة اليوم (5–8 أسطر) | `outputs/today.md` | يوميًا |
| أرشيف البطاقة | `outputs/YYYY-MM/YYYY-MM-DD_card.md` | يوميًا |
| موجز الأسبوع + تقويم 7 أيام | `outputs/this_week.md` | أسبوعيًا (الأحد) |
| الدليل الشهري | `outputs/this_month.md` و `outputs/relational/YYYY-MM.md` | أول كل شهر |
| دليل الشريكة | `outputs/manuals/partner_<id>.md` | عند الطلب / شهريًا |
| دليل كل طفل | `outputs/manuals/child_<id>.md` | عند الطلب / شهريًا |
| تقويم `.ics` | `outputs/calendar.ics` | أسبوعيًا/شهريًا |
| حقائق JSON (للتوسعة) | `outputs/facts/YYYY-MM.json` | أسبوعيًا/شهريًا |
| فهرس | `outputs/index.md` | تلقائيًا |

**مزايا التصميم:**

- **ثلاثة أجواء منفصلة:** طقسك، طقس الشريكة/الطفل، وطقس العلاقة (Composite). هذا يمنع تفسير انسحاب الشريك بأنه «مشكلة في العلاقة» بينما هو ضغط شخصي عليه.
- **قاعدة الثلاثة:** لا تقرأ أكثر من 3 إشارات في المجال الواحد.
- **الجديد أو الدقيق فقط:** ذاكرة حالة تمنع تكرار نفس التحليل يوميًا.
- **الدليل مرة، والتعديل دائمًا:** أدلة العلاقة/الطفل تُبنى من الخريطة الثابتة، والتقارير الأسبوعية تضيف فقط ما تغيّر.
- **وضع «لاعب واحد»:** يعمل بكفاءة بملف `self` فقط، وتُفتح موديولات الشريكة/الأطفال تلقائيًا عند إضافتها.
- **بدون تسميات قدرية:** نصائح الطفل مصاغة كـ«ما تفعله أنت للدعم»، مع فلتر عمر ومراجعة سلوك أولًا.

---

## البنية

```text
.
├── .github/workflows/
│   ├── daily_personal_guide.yml
│   ├── weekly_synastry_report.yml
│   ├── monthly_report.yml
│   ├── build_manuals.yml
│   └── ci.yml
├── profiles/
│   ├── self.example.json
│   ├── partner.example.json
│   ├── kids/child_1.example.json
│   ├── kids/child_2.example.json
│   └── profiles.example.json      # حزمة كاملة للتجربة
├── src/astromind/
│   ├── engines/
│   │   ├── ephemeris.py           # Swiss Ephemeris + بيوت + تغيّرات القمر
│   │   ├── aspects.py             # الزوايا والـorbs
│   │   ├── charts.py              # الخريطة الأصلية + Composite
│   │   ├── transits.py            # العبور على خريطة ثابتة
│   │   ├── synastry.py            # التقاطع الثابت بين خريطتين
│   │   ├── signals.py             # الترتيب، منع التكرار، حالة القراءة
│   │   └── child_development.py   # نمط التعلم/الأمان/الطاقة/الموهبة
│   ├── generators/
│   │   ├── interpretations.py     # بنك النصوص العربية
│   │   ├── md_builder.py          # تقارير Markdown
│   │   └── calendar_ics.py        # تقويم ICS
│   ├── models.py                  # مخطط البروفايلات والتحقق
│   ├── profiles.py                # تحميل الأسرار (base64)
│   ├── state.py                   # ذاكرة «ما قيل سابقًا»
│   └── cli.py
├── tests/
├── pyproject.toml
└── requirements.txt
```

---

## تشغيل محلي سريع

> يُفضّل **Python 3.11** لأن `pyswisseph` يوفّر له wheel جاهزًا على Linux/Windows. الإصدارات الأحدث تعمل أيضًا لكنها قد تحتاج مترجم C.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate

pip install -e ".[dev]"

# تجربة ببيانات وهمية
python -m astromind validate --file profiles/profiles.example.json
python -m astromind daily --file profiles/profiles.example.json --date 2026-11-09 --no-state
python -m astromind weekly --file profiles/profiles.example.json --date 2026-11-09 --no-state
python -m astromind monthly --file profiles/profiles.example.json --month 2026-11 --no-state
python -m astromind manuals --file profiles/profiles.example.json --month 2026-11 --no-state
python -m astromind calendar --file profiles/profiles.example.json --month 2026-11 --no-state

# اختبارات
python -m pytest -q
```

> بيانات ملفات `*.example.json` **وهمية** لغرض العرض فقط.

---

## إعداد GitHub Secrets (البيانات الحقيقية)

البيانات لا تُرفع إلى المستودع. تُحمَّل وقت التشغيل من سر واحد:

```bash
# 1) انسخ القالب وعدّله
cp profiles/profiles.example.json profiles.local/profiles.json

# 2) تأكد من صحة البيانات
python -m astromind validate --file profiles.local/profiles.json

# 3) حوّله إلى base64
python -m astromind encode --file profiles.local/profiles.json
```

ثم في GitHub:

1. **Settings → Secrets and variables → Actions → New repository secret**
2. الاسم: `ASTROMIND_PROFILES`
3. القيمة: الناتج من أمر `encode`.

### رفع السر بأمر واحد (Windows)

بدل النسخ اليدوي، يمكن رفع السر مباشرة من الطرفية:

```powershell
# 1) انسخ القالب واملأ البيانات الحقيقية
Copy-Item profiles.local\profiles.template.json profiles.local\profiles.json

# 2) تحقق ثم ارفع السر تلقائيًا
.\scripts\publish_secret.ps1
```

السكربت يتحقق من الملف، يحوّله Base64، ويحدّث `ASTROMIND_PROFILES` في المستودع دون طباعة القيمة. يستخدم `GH_TOKEN` إن وُجد، وإلا يستخدم بيانات اعتماد Git المخزّنة.

`profiles.local/` مستثنى في `.gitignore`، ولا تحتوي التقارير/الحالة على بيانات الميلاد الخام.

### إضافة الشريكة أو الأطفال لاحقًا

أضف عنصرًا جديدًا إلى `profiles` في `profiles.local/profiles.json`:

```json
{
  "id": "child_3",
  "role": "child",
  "name": "الاسم",
  "gender": "male",
  "birth": {
    "date": "2026-01-15",
    "time": "09:20",
    "tz": "Asia/Riyadh",
    "lat": 24.7136,
    "lon": 46.6753,
    "time_known": true
  },
  "focus": ["parenting", "talent", "emotional_security"]
}
```

- `role`: `self` (واحد فقط) أو `partner` (واحد) أو `child` (متعدد).
- `time_known: false` عند جهل وقت الميلاد: سيتوقف حساب الطالع/البيوت وتُخفَّض درجة الثقة تلقائيًا.
- `gender` يؤثر فقط على صياغة الضمائر (`male` / `female`).

أعد تشغيل أمر `encode` وحدّث السر. لا حاجة لتعديل الكود.

### وضع «الأبراج فقط» (بدون تاريخ ميلاد)

إذا كنت تعرف الأبراج والبيوت فقط، يمكنك تعريف البروفايل بدون `birth`:

```json
{
  "name": "مثال",
  "role": "self",
  "gender": "male",
  "sun": { "sign": "Cancer", "house": 4 },
  "ascendant": { "sign": "Aries" },
  "moon": { "sign": "Aries", "house": 1 },
  "mercury": { "sign": "Gemini", "house": 2 },
  "venus": { "sign": "Gemini", "house": 2 },
  "mars": { "sign": "Pisces", "house": 12 },
  "jupiter": { "sign": "Taurus", "house": 2 },
  "saturn": { "sign": "Sagittarius", "house": 9 },
  "uranus": { "sign": "Sagittarius", "house": 9 },
  "neptune": { "sign": "Capricorn", "house": 10 },
  "pluto": { "sign": "Scorpio", "house": 8 }
}
```

- `id` اختياري: يُشتق تلقائيًا (`self` / `partner` / `child_N`).
- `house` اختياري لكل كوكب؛ الطالع يكفي لاشتقاق **البيوت الكاملة**.
- `tz` اختياري (الافتراضي `Asia/Riyadh`) ويُستخدم لعرض التواريخ.
- في هذا الوضع: لا يوجد تاريخ/وقت ميلاد، لذلك **الدقة منخفضة** والتوقيت اليومي تقريبي.
  النظام يوسم كل تقرير بذلك، ويستبعد خريطة Composite تلقائيًا.

### وضع المواضع اليدوية مع تاريخ ميلاد

إذا كانت لديك قائمة أبراج/بيوت من مصدر موثوق وتريد الاحتفاظ بها كما هي مع إضافة تاريخ الميلاد:

```json
{
  "name": "مثال",
  "role": "self",
  "chart_source": "signs",
  "house_system": "whole-sign",
  "birth": {
    "date": "1988-07-07",
    "time": "00:00",
    "tz": "Asia/Riyadh",
    "lat": 24.7136,
    "lon": 46.6753,
    "time_known": true
  },
  "sun": { "sign": "Cancer", "house": 4 },
  "ascendant": { "sign": "Aries" },
  "moon": { "sign": "Aries", "house": 1 }
}
```

- `chart_source: "signs"`: يستخدم الأبراج/البيوت المذكورة كما هي، ولا يعيد حساب الخريطة من تاريخ الميلاد.
- `house_system: "whole-sign"`: يوضح أن البيوت كاملة انطلاقًا من الطالع.
- تاريخ الميلاد يظهر في الصفحة ويُستخدم للعمر، لكن التوقيت اليومي يظل **على مستوى الأبراج** (ثقة متوسطة).

### صفحة عرض ثابتة (docs/index.html)

لتوليد صفحة HTML عربية تعرض المواضع والتقارير اليومية/الأسبوعية/الشهرية:

```powershell
.\.venv\Scripts\python.exe scripts\build_docs.py --file profiles.local\profiles.json --date 2026-11-09
```

تكتب الصفحة إلى `docs/index.html`. يمكنك معاينتها محليًا بفتح الملف في المتصفح، أو نشرها عبر GitHub Pages.

تستخدم الصفحة خط **ثمانية** من `docs/font/` (Sans للنصوص وSerif Display للعناوين)، دون الاعتماد على خطوط خارجية.

الصفحة المنشورة حاليًا: <https://muxd22-alt.github.io/ASTR/>

> `docs/index.html` يحتوي بيانات شخصية مشتقة. الصفحة الحالية تعرض الاسم المستعار «مثال» وتاريخ الميلاد المذكور؛ راجع محتواها قبل أي نشر إضافي.


---

## الجدولة

| Workflow | التوقيت | ماذا يفعل |
|---|---|---|
| `daily_personal_guide.yml` | يوميًا 06:00 بتوقيت الرياض | بطاقة اليوم |
| `weekly_synastry_report.yml` | الأحد 07:00 | موجز الأسبوع + تقويم |
| `monthly_report.yml` | أول الشهر 08:00 | الدليل الشهري + الأدلة + التقويم |
| `build_manuals.yml` | يدويًا | إعادة بناء الأدلة |
| `ci.yml` | عند الدفع/PR | اختبارات + smoke test |

كل تقرير يظهر أيضًا في صفحة الـ run (`GITHUB_STEP_SUMMARY`) ويُرفع كـ Artifact.

### حفظ التقارير داخل المستودع

افتراضيًا لا تُحفظ، لأنها تحتوي معلومات شخصية. إذا كان المستودع **خاصًا**:

- أضف Variable باسم `COMMIT_OUTPUTS` وقيمته `true`.
- سيقوم الـ workflow بعمل commit لـ `outputs/` و `state/`.

> لا تفعّل هذا في مستودع عام.

---

## أوامر الـ CLI

```bash
python -m astromind validate
python -m astromind daily [--date YYYY-MM-DD]
python -m astromind weekly [--date YYYY-MM-DD]
python -m astromind monthly [--month YYYY-MM]
python -m astromind manuals [--month YYYY-MM]
python -m astromind calendar [--month YYYY-MM]
python -m astromind compute [--month YYYY-MM]   # حقائق JSON فقط
python -m astromind story [--mode short|standard|deep] [--no-ai]  # قراءة سردية
python -m astromind ask "ماذا أقول لها الليلة؟"  # من إشارات هذا الأسبوع
python -m astromind encode --file profiles.local/profiles.json
python -m astromind run-all
```

خيارات مشتركة: `--file` لملف محلي، `--out` لمجلد الإخراج، `--no-state` لتعطيل ذاكرة التكرار.

### القراءة السردية عبر OpenRouter (اختياري)

الطبقة السردية لا تغيّر الحسابات الفلكية إطلاقًا؛ она تحوّل الحقائق المحسوبة مسبقًا إلى نص.

- **المفتاح:** أضف GitHub Secret باسم `OPENROUTER_API_KEY`.
- **الموديل الافتراضي:** `google/gemma-4-31b-it:free`، ويمكن تغييره عبر `OPENROUTER_MODEL` أو `--model`.
- **الأمر:**
  ```bash
  python -m astromind story --mode short       # 60 ثانية
  python -m astromind story --mode standard    # قراءة كاملة
  python -m astromind story --mode deep --month 2026-11
  ```
- **دون مفتاح:** يعمل النظام بقراءة محلية مبنية على القواعد، ويظهر تنبيه بذلك.
- **`--no-ai`:** يجبر القراءة المحلية حتى لو وُجد المفتاح.
- **صفحة `docs/index.html`:** تُحدَّث تلقائيًا من `daily_personal_guide.yml` عند وجود المفتاح.
- **الأسلوب التحريري:** موثّق في `skills/intuitive-astrology-storytelling/SKILL.md`.

> القراءة السردية تأملية ورمزية، وليست تشخيصًا أو تنبؤًا مؤكدًا. جميع التواريخ تلتزم بـ `as_of`.

---

## كيف يعمل الحساب؟

- **Swiss Ephemeris** عبر `pyswisseph`. عند غياب ملفات `.se1` يتحول تلقائيًا إلى **Moshier** (دقة كافية للاستخدام الشخصي).
- **البيوت:** Placidus، مع تراجع إلى Whole Sign عند فشل الحساب (خطوط العرض العالية).
- **Chiron** غير مفعّل افتراضيًا لأنه يحتاج `seas_18.se1`؛ كل شيء آخر يعمل بدونه.
- **السيناستري:** تقاطع كامل بين كواكب/زوايا الخريطتين، مرتّب بوزن الكوكب والزاوية وضيق الـorb.
- **طقس العلاقة:** عبور الكواكب على خريطة **Composite** (نقاط المنتصف)، وليس مجرد تكرار لطقس أحد الطرفين.
- **الترتيب:** `وزن الكوكب × وزن الهدف × وزن الزاوية × ضيق الـorb × مكافأة التزايد`.
- **منع التكرار:** مفتاح الإشارة = المجال + الكوكب + الهدف + الزاوية، مع الاحتفاظ بأضيق orb.
- **الحالة:** `state/state.json` تُحفظ عبر `actions/cache`، وتُنقّى تلقائيًا بعد 90 يومًا.
- **التنبيهات:** نوافذ التواصل وتواريخ الحذر تبدأ من تاريخ التوليد (`as_of`) ولا تعرض أيامًا ماضية.
- **الطبقة السردية:** `src/astromind/reading/` تبني الحقائق من الخريطة والعبور، ثم تستدعي OpenRouter اختياريًا. لا تتدخل في `engines/` ولا في التواريخ.

---

## الخصوصية

- لا تُخزَّن بيانات الميلاد الخام في الكود المصدري؛ السر `ASTROMIND_PROFILES` هو المصدر الوحيد للمحرك.
- `profiles.local/`, `state/`, `outputs/` مستثناة من Git.
- المستودع `ASTR` عام، وصفحة `docs/index.html` تعرض الاسم المستعار «مثال» وتاريخ الميلاد المذكور. إذا أردت إخفاء التاريخ أيضًا، عدّل `scripts/build_docs.py` أو أزل السطر من الصفحة.
- مخرجات Actions (Artifacts) قد تكون قابلة للتنزيل من أي شخص يملك صلاحية قراءة المستودع العام. لا تضع بيانات خام أو أسماء حقيقية في التقارير.
- لتشغيل خاص: استخدم مستودعًا خاصًا وأعد تفعيل `COMMIT_OUTPUTS` فقط عند الحاجة.

---

## حدود ومبادئ

- هذه أداة **تأمل وتنظيم**، وليست تشخيصًا طبيًا أو نفسيًا، ولا بديلًا عن مختص.
- وقت الميلاد غير الدقيق يجعل الطالع/البيوت/القمر تقريبية؛ النظام يصرّح بذلك.
- نصائح الطفل تُصاغ كدعم للوالد، لا كحكم على الطفل أو قدره.
- راقب السلوك الواقعي أولًا، واستخدم الخريطة كعدسة ثانية.

---

## الترخيص والاعتماد

- المحرك يعتمد على **Swiss Ephemeris** عبر `pyswisseph`. Swiss Ephemeris متاح بترخيص **AGPL** أو ترخيص تجاري. الاستخدام الشخصي/المحلي عادةً لا يمثل مشكلة، لكن قبل النشر أو التوزيع راجع الترخيص.
- الكود الموجود هنا ملكك؛ عدّله كما تشاء مع مراعاة ترخيص المكتبة.

---

## التوسعة المقترحة لاحقًا (اختيارية)

- طبقة LLM اختيارية فوق `outputs/facts/YYYY-MM.json` لصياغة أكثر nuance، مع الإبقاء على القوالب كـfallback.
- إشعار Telegram/بريد لبطاقة اليوم فقط.
- لوحة ويب تقرأ `facts` و`signals` مباشرة.
- إضافة `profiles` متعددة للشريك/الطفل عبر `relationship graph` بدل ملف واحد.
