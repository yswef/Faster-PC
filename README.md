<p align="center">
  <img src="assets/icon_256.png" width="110" alt="Faster PC icon">
</p>

<h1 align="center">Faster PC</h1>
<p align="center">
  أداة صيانة وتسريع ويندوز متكاملة — تنظيف، تحسين، حماية للبرامج، مراقبة أداء وأعطال، وإصلاح نظام،<br>
  بواجهة عربية داكنة، وتشغيل صامت تمامًا بدون أي نوافذ أوامر.
  <br><a href="#-english">English section below ⬇</a>
</p>

<p align="center">
  <img alt="Version" src="https://img.shields.io/badge/version-2.0.0-27ae60">
  <img alt="Platform" src="https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-4a90e2">
  <img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-3776ab">
  <img alt="License" src="https://img.shields.io/badge/license-Proprietary-e74c3c">
</p>

---

## العربية

### ما هو Faster PC؟

تطبيق سطح مكتب (PySide6) لويندوز يجمع في مكان واحد ما تحتاجه لصيانة الجهاز وتسريعه:
تنظيف آمن، إدارة عمليات وخدمات وبرامج بدء تشغيل، تحسينات أداء حقيقية قابلة للتراجع،
إصلاح ملفات النظام، **ومراقبة مباشرة للأداء والأعطال** — كل ذلك مع سجل تغييرات
يمكن الرجوع عنه بنقرة، وطبقات حماية تمنع إغلاق البرامج المهمة أو تعطيل النظام.

### أهم المزايا

**التثبيت والإعداد الأولي (جديد)**
- معالج إعداد أولي يظهر عند أول تشغيل: إنشاء حساب المدير، اختيار البرامج المحمية،
  إنشاء اختصار سطح المكتب وقائمة ابدأ، تسجيل التشغيل مع ويندوز، واستثناءات Defender.
- أيقونة البرنامج الرسمية تظهر في الاختصار وشريط المهام ونافذة البرنامج.
- وضع محمول (Portable): ضع ملف `portable.flag` بجانب البرنامج فتُكتب كل البيانات بجانبه.

**تشغيل صامت تمامًا (جديد)**
- لا تظهر أي نوافذ `cmd` أو PowerShell أبدًا — لا عند التشغيل ولا أثناء تنفيذ الأوامر
  (`sc` / `powercfg` / `DISM` / `sfc` / `chkdsk` / `netsh` / استعلامات سجل الأحداث)
  لأنها تُنفَّذ بـ `CREATE_NO_WINDOW` و`STARTUPINFO(SW_HIDE)`.
- ملف البناء `FasterPC.exe` يعمل بوضع `console=False` (بدون نافذة نهائيًا) ويطلب
  صلاحيات المدير تلقائيًا.

**مراقبة الأداء (مطوّرة بالكامل)**
- بطاقات مباشرة للمعالج والذاكرة والقرص والشبكة، مع رسوم بيانية زمنية مصغّرة.
- أعلى العمليات استهلاكًا (معالج وذاكرة) مع بيان أي عملية محمية.
- رصد فتح/إغلاق العمليات لاكتشاف البرامج الثقيلة.
- تنبيهات ذكية عند استمرار تجاوز الحدود (وليس عند القفزات اللحظية)، بحدود قابلة للضبط.

**مراقبة الأعطال وصحة النظام (جديد)**
- قراءة سجل أحداث ويندوز (Application: 1000/1001/1002/1026، وSystem: أخطاء المستوى 1/2)
  لعرض **انهيارات التطبيقات وتعليقها** خلال 24 ساعة.
- متابعة المساحة الحرة لكل الأقراص والتنبيه قبل امتلائها.
- تقرير صحة كامل قابل للتصدير، وسجل أخطاء منفصل (`logs/errors.log`) وسجل انهيارات
  (`logs/crash.log`) لأي خطأ غير متوقع داخل البرنامج نفسه.

**الحماية والاستثناءات (مطوّرة)**
- ثلاث طبقات حماية: طبقة **دائمة** (عمليات النواة والإقلاع — غير قابلة للاستثناء)،
  طبقة **افتراضية** (مكوّنات واجهة ويندوز + تطبيق الصور + العمليات الشائعة)،
  وطبقة **خاصة بك** (أي برنامج تضيفه).
- شاشة "الحماية والاستثناءات" تتيح اختيار برامج من قائمة العمليات الجارية أو ملف
  `.exe` أو إدخال اسم يدويًا — والإضافة تنطبق على قائمة الاستثناءات وقائمة الحماية معًا.
- البرنامج **لا يغلق تطبيق الصور** ولا مكوّنات ويندوز الأساسية إطلاقًا، ولا يقتل نفسه
  أو العمليات التي يشغّلها.

**سجل التغييرات مع التراجع (جديد)**
- كل تغيير (خدمة، برنامج بدء تشغيل، ريجستري، خطة طاقة) يُسجَّل مع قيمته السابقة،
  ويمكن الرجوع عنه بنقرة واحدة من تبويب "سجل التغييرات".

**التنظيف**
- ملفات مؤقتة (ويندوز + %TEMP% بموافقة صريحة)، سلة محذوفات، مخلفات تحديثات ويندوز
  (مع إيقاف/إعادة تشغيل الخدمة تلقائيًا)، تقارير أعطال (WER/CrashDumps).
- كل عملية حذف تتحقق أن المسار الحقيقي داخل المجلد المستهدف (حماية من الروابط الرمزية)،
  وتتخطى الملفات المقفلة، وتعرض المساحة المحرّرة الفعلية.
- لا تُمس بيانات الاعتماد أو كلمات المرور أو الكوكيز في أي متصفح — أبدًا.

**التحسين**
- إنهاء قائمة محددة أو إنهاء كل العمليات غير المستثناة (بعد تأكيد صريح وبحماية كاملة).
- إدارة خدمات ويندوز المعروفة بالاستهلاك المرتفع (حالتها ونوع تشغيلها من النظام مباشرة).
- تعطيل/إعادة تفعيل برامج بدء التشغيل (بإعادة التسمية فقط — رجعي بالكامل).
- تحسينات حقيقية: خطط الطاقة (العالي/المطلق/المتوازن)، المؤثرات البصرية، تعطيل الشفافية
  والحركات، تسريع القوائم، تعطيل تطبيقات الخلفية، الإقلاع السريع، HAGS، تقليل كتابات
  NTFS، وتعديل متقدم اختياري (Memory Integrity) بتأكيد صريح.
- **الوضع التجريبي**: يسجّل كل إجراء بدون تنفيذ فعلي.

**الإصلاح**
- تفريغ DNS، إعادة تعيين مكدس الشبكة، فحص قرص غير معطّل (`/scan`)، نقطة استعادة،
  SFC و DISM — بصلاحيات مدير وبرسائل نتائج واضحة.

**أخرى**
- تشغيل نسخة واحدة فقط، وينشط النافذة الموجودة عند إعادة الفتح.
- بقاء البرنامج في شريط المهام عند إغلاق النافذة (اختياري) مع أيقونة وقائمة سريعة.
- مركز تنبيهات داخل البرنامج + تنبيهات شريط المهام.

### التشغيل

```bash
pip install -r requirements.txt
python main.py
```

- أول تشغيل: يظهر معالج الإعداد.
- يفضَّل تشغيل البرنامج كمسؤول (Administrator) لتفعيل كل الميزات (الخدمات، SFC/DISM،
  نقطة الاستعادة، بعض تحسينات الريجستري). البرنامج يوضح دائمًا متى تكون الصلاحيات ناقصة.

### بناء نسخة تنفيذية

**الطريقة الأسهل (ويندوز):** دبل-كلك على `build_exe.bat` → ينتج `dist\FasterPC.exe`
و `dist\install.bat`.

**يدويًا:**

```bash
pip install -r requirements-dev.txt
pyinstaller --noconfirm --clean faster_pc.spec
```

ثم للتثبيت على الجهاز: شغّل `dist\install.bat` (أو `packaging\install.bat`) فينسخ البرنامج
إلى `%LOCALAPPDATA%\Programs\Faster PC` وينشئ الاختصارات بالصورة الرسمية.

ملاحظات:
- بعض برامج الحماية تعطي إنذارًا كاذبًا ضد أي ملف PyInstaller غير موقّع. البرنامج يتضمن
  خيارًا لإضافة مجلداته إلى استثناءات Defender، والتوقيع الرقمي (Code Signing) هو الحل
  الجذري عند التوزيع العام.

### موقع البيانات

| النوع | المسار |
|---|---|
| الإعدادات | `%LOCALAPPDATA%\FasterPC\config.json` (ونسخة `.bak` تلقائية) |
| سجل التغييرات | `%LOCALAPPDATA%\FasterPC\changes.json` |
| السجلات | `%LOCALAPPDATA%\FasterPC\logs\` (faster_pc.log / errors.log / crash.log) |
| الوضع المحمول | بجانب `FasterPC.exe` عند وجود `portable.flag` |

أثناء التطوير (تشغيل من المصدر) تُكتب هذه الملفات في جذر المشروع.

### الاختبارات والجودة

```bash
pip install -r requirements-dev.txt
pytest            # 55+ اختبارًا للوحدات الأساسية (إعدادات، حماية، تنظيف، سجل، مراقبة)
ruff check .      # فحص التنسيق والأخطاء الشائعة
```

للمعاينة البصرية لكل التبويبات بدون شاشة:

```bash
QT_QPA_PLATFORM=offscreen python tools/ui_preview.py
```

### بنية المشروع

```
main.py                     نقطة التشغيل (--minimized / --headless)
src/version.py              الإصدار وبيانات المشروع
src/config/settings.py      SettingsManager: كتابة ذرية + نسخ احتياطي + ترقية البنية
src/core/
  app_context.py            تجميع كل الخدمات (قابل للتشغيل بدون واجهة)
  exclusions.py             ProtectionManager — ثلاث طبقات حماية للعمليات والخدمات
  monitor.py                مراقبة الأداء المباشرة + الرسوم + حدود التنبيه
  health.py                 مراقبة الأعطال من سجل الأحداث + صحة الأقراص
  notifications.py          مركز التنبيهات (Toast + داخل البرنامج)
  journal.py                سجل التغييرات القابلة للتراجع
  cleaner.py                تنظيف آمن (حماية من الروابط الرمزية + قياس المساحة)
  optimizer.py              عمليات/خدمات/بدء تشغيل + تراجع
  tweaks.py                 تحسينات الأداء (قابلة للتراجع بالكامل)
  repair.py                 SFC/DISM/نقطة استعادة/DNS/فحص القرص
  installer.py              الاختصارات، التشغيل مع ويندوز، استثناءات Defender
  results.py                ActionResult الموحّد
src/gui/
  app.py                    التشغيل، نسخة واحدة، الأيقونة، معالجة الأخطاء الفادحة
  setup_wizard.py           معالج الإعداد الأولي
  login_window.py           الدخول (مع قفل مؤقت بعد محاولات خاطئة)
  main_window.py            التبويبات، اللوحات، شريط المهام، المهام الخلفية
  settings_window.py        كل الإعدادات
  dialogs.py                حوارات التأكيد/الحماية/التنبيهات/التقارير/حول
  widgets.py theme.py       عناصر واجهة وألوان مشتركة
src/utils/
  winapi.py                 كل استدعاءات ويندوز: تشغيل صامت، اختصارات، سلة، معلومات
  registry.py + winreg_stub.py   وصول آمن للريجستري يعمل على أي نظام
  paths.py logger.py auth.py workers.py
packaging/                  install/uninstall + version_info
tests/                      اختبارات الوحدات
tools/ui_preview.py         معاينة الواجهة بدون شاشة
docs/docs.html              التوثيق الكامل (مستخدم + مطوّر)
```

### الخصوصية والأمان

- لا اتصال بأي خادم، ولا إرسال بيانات، ولا حسابات سحابية — كل شيء محلي.
- كلمات المرور تُخزَّن بـ PBKDF2-HMAC-SHA256 (260,000 تكرار + salt لكل مستخدم).
- لا يوجد أي كود لاستخراج أو فك تشفير بيانات اعتماد محفوظة في المتصفحات أو غيرها —
  هذا خط ثابت في المشروع.
- كل عملية تلمس النظام تحترم الوضع التجريبي، ومعظمها قابل للتراجع.

### الترخيص

هذا المشروع مملوك ومحمي بحقوق النشر — راجع ملف [LICENSE](LICENSE).
© 2026 Yousef Alhamzy. جميع الحقوق محفوظة.

---

<a name="-english"></a>

## English

### What is Faster PC?

A Windows desktop app (PySide6) that bundles everything you need to maintain and speed up
a PC: safe cleaning, process/service/startup management, real reversible performance tweaks,
system-file repair, and **live performance & crash monitoring** — with a one-click undo
journal and protection layers that prevent closing important apps or destabilizing Windows.

### Highlights

**Setup & installation (new)**
- First-run wizard: create the admin account, pick apps to protect, create desktop &
  Start Menu shortcuts, register run-with-Windows, and add optional Defender exclusions.
- The official app icon appears in shortcuts, the taskbar, and the app window.
- Portable mode: drop a `portable.flag` file next to the executable to keep all data local.

**Fully silent operation (new)**
- No `cmd`/PowerShell windows ever appear — not at launch and not while running commands
  (`sc`, `powercfg`, `DISM`, `sfc`, `chkdsk`, `netsh`, event-log queries), thanks to
  `CREATE_NO_WINDOW` + hidden `STARTUPINFO`.
- The frozen `FasterPC.exe` is built with `console=False` and requests elevation automatically.

**Performance monitoring (rebuilt)**
- Live CPU/RAM/disk/network cards with sparkline history.
- Top processes by CPU and memory, with protection status.
- Process start/exit tracking to spot heavy background apps.
- Smart sustained-threshold alerts (configurable), not momentary spikes.

**Crash & system-health monitoring (new)**
- Reads the Windows Event Log (Application 1000/1001/1002/1026 and System level 1/2) to
  list application crashes/hangs from the last 24 hours.
- Disk free-space tracking with low-space warnings.
- Exportable health report, plus `logs/errors.log` and `logs/crash.log` for the app itself.

**Protection & exclusions (improved)**
- Three protection layers: **hard** (kernel/boot processes — never overridable),
  **default** (Windows shell components + the Photos app + common processes), and
  **yours** (any app you add).
- The protection tab lets you pick running apps, browse for an `.exe`, or type a name;
  adding an app protects it and excludes it in one step.
- Faster PC never closes the Photos app or core Windows components, and never kills itself
  or the processes it spawns.

**Undo journal (new)**
- Every change (service state, startup item, registry tweak, power plan) records its previous
  value and can be reverted with one click from the "Change journal" tab.

**Cleaning**
- Temp files (Windows, and user `%TEMP%` only with explicit consent), Recycle Bin, Windows
  Update cache (stops/restarts services automatically), and crash-report leftovers.
- Symlink-safe deletion, locked files are skipped, and the freed space is reported.
- Browser credentials, cookies, and passwords are never touched.

**Optimization**
- Terminate a curated list, or everything except your exclusions (explicit confirmation,
  full protection).
- Manage well-known heavy Windows services (status/start-type read straight from the OS).
- Disable/re-enable startup programs by renaming only — fully reversible.
- Real tweaks: power plans (High/Ultimate/Balanced), visual effects, transparency and
  animations off, menu delay, background apps off, Fast Startup, HAGS, NTFS last-access
  reduction, and an explicitly-confirmed Memory Integrity toggle.
- **Test Mode**: log every action without performing it.

**Repair**
- DNS flush, network stack reset, non-disruptive disk scan, System Restore point, SFC
  and DISM — with admin checks and clear result messages.

**Other**
- Single-instance: re-launching activates the existing window.
- Optional minimize-to-tray on close, with tray icon and quick actions.
- In-app notification center + Windows tray toasts.

### Getting started

```bash
pip install -r requirements.txt
python main.py
```

Run as Administrator for full functionality (services, SFC/DISM, restore points, some
registry tweaks). The app always tells you when elevation is missing.

### Building

```bash
pip install -r requirements-dev.txt
pyinstaller --noconfirm --clean faster_pc.spec
```

On Windows you can simply double-click `build_exe.bat`, then run `dist\install.bat` to
install with desktop/Start Menu shortcuts.

### Notes

- Fresh unsigned PyInstaller executables are often flagged by antivirus engines as a
  generic false positive. Faster PC ships an optional Defender-exclusion helper; code
  signing is the proper fix when distributing publicly.
- This project contains no code that extracts, decrypts, or exports credentials stored by
  browsers or other applications. That is a permanent project boundary.

### License

Proprietary — see [LICENSE](LICENSE). © 2026 Yousef Alhamzy. All rights reserved.
