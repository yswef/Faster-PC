<p align="center">
  <img src="assets/icon_256.png" width="96" alt="Faster PC icon">
</p>

<h1 align="center">Faster PC</h1>
<p align="center">
  Windows maintenance &amp; performance tool — cleaning, process/service control, real performance tweaks, and repair, in one desktop app.<br>
  <a href="#-arabic">النسخة العربية أدناه ⬇</a>
</p>

---

## English

### What it does

Faster PC is a PySide6 desktop app for Windows that helps you:

- **Clean** — temporary files, Recycle Bin, old Windows Update cache.
- **Optimize** — terminate a curated kill-list, or terminate *everything except an exclusion list you control* (with Windows boot-critical processes always protected, since killing them crashes the OS instantly).
- **Manage services & startup** — stop/start common resource-heavy Windows services (SysMain, WSearch, DiagTrack…) and safely disable/re-enable startup programs (renamed, not deleted — fully reversible).
- **Tweak performance** — High Performance / hidden Ultimate Performance power plan, visual effects tuned for performance, background (UWP) apps disabled, Hardware-Accelerated GPU Scheduling, and an explicitly-gated Memory Integrity toggle for advanced users who understand the security trade-off.
- **Repair** — DNS flush, non-disruptive disk scan, System Restore point creation, SFC and DISM.
- **Watch live usage** — a dashboard tab shows CPU/RAM/disk usage updating every 2 seconds.

Every action that touches disk, registry, services, or processes respects a global **Test Mode** — flip it on in Settings and every action just logs what it *would* do, without doing it.

### Accounts

On first launch you create an admin account. The admin can add more accounts from Settings. Every account currently sees every feature — multi-user support exists today for attribution in the activity log, and the codebase ships a `feature_flags` structure in `config.json` ready for a future free/paid tier system (nothing is gated by it yet).

### Getting started

```bash
pip install -r requirements.txt
python main.py
```

Run as Administrator for full functionality — service management, SFC/DISM, restore points, and some registry tweaks require elevated privileges and will tell you clearly if they're missing.

### Project structure

```
src/
  config/settings.py     SettingsManager — atomic, merge-safe config.json persistence
  core/cleaner.py         SystemCleaner — symlink-safe temp/recycle-bin/update-cache cleanup
  core/optimizer.py       SystemOptimizer — process/service/startup control
  core/tweaks.py          PerformanceTweaks — power plan / visual fx / HAGS / VBS toggle
  core/repair.py          SystemRepair — SFC / DISM / restore point / DNS / chkdsk
  gui/main_window.py      MainWindow — tabs, live dashboard, background task workers
  gui/settings_window.py  SettingsWindow + admin user management
  gui/login_window.py     LoginWindow — first-run setup + authentication
  utils/auth.py           AuthManager — local PBKDF2-HMAC-SHA256 accounts
  utils/logger.py         Thread-safe UI log handler + rotating file log
  utils/workers.py        TaskWorker — QThread wrapper so the UI never blocks
docs/docs.html            Bilingual user + developer documentation
assets/                   App icon (icon.ico, PNGs)
main.py                   Entry point
config.json                Persisted settings, accounts, feature flags
```

### A note on scope

This project intentionally does **not** include any feature that extracts, decrypts, or exports credentials stored by a browser or any other application. That is a hard boundary for the project, not a missing feature — everything here operates on the local machine's own performance characteristics (files, processes, services, registry performance keys), never on someone else's stored secrets.

### License

Add your preferred license here (MIT is a common default for a project like this).

---

## <a name="-arabic"></a>العربية

### وش يسوي البرنامج

Faster PC أداة سطح مكتب مبنية بـ PySide6 لنظام ويندوز تساعدك على:

- **التنظيف** — ملفات مؤقتة، سلة المحذوفات، ذاكرة تحديثات ويندوز القديمة.
- **التحسين** — إنهاء قائمة عمليات محددة، أو إنهاء **كل شي ما عدا قائمة استثناءات تتحكم فيها بنفسك** (مع حماية دائمة للعمليات الحرجة لإقلاع ويندوز، لأن إنهاءها يسبب توقف النظام فورًا — هذا حد تقني وليس قرار).
- **إدارة الخدمات وبدء التشغيل** — إيقاف/تشغيل خدمات ويندوز الثقيلة الشائعة (SysMain, WSearch, DiagTrack...)، وتعطيل/تفعيل برامج بدء التشغيل بأمان (بإعادة تسمية القيمة، مو حذفها — رجعي بالكامل).
- **تحسينات الأداء** — خطة الأداء العالي/المطلق (المخفية)، مؤثرات بصرية لأفضل أداء، تعطيل تطبيقات الخلفية (UWP)، جدولة GPU بالعتاد (HAGS)، وخيار متقدم مقفل بتأكيد صريح لتعطيل Memory Integrity لمن يفهم المقايضة الأمنية.
- **الإصلاح** — تفريغ DNS، فحص قرص بدون تعطيل، إنشاء نقطة استعادة، SFC وDISM.
- **رؤية مباشرة للاستهلاك** — تبويب لوحة رئيسية يعرض استهلاك المعالج/الذاكرة/القرص محدّث كل ثانيتين.

أي عملية تلمس القرص أو الريجستري أو الخدمات أو العمليات تحترم **الوضع التجريبي** العام — فعّله من الإعدادات وكل عملية تسجّل بس "كنت سأفعل..." بدون تنفيذ فعلي.

### الحسابات

عند أول تشغيل تنشئ حساب مدير. يقدر المدير يضيف حسابات ثانية من الإعدادات. كل الحسابات تشوف كل الميزات حاليًا — تعدد المستخدمين موجود الآن لتتبّع من نفّذ كل عملية بالسجل، والمشروع فيه بنية `feature_flags` جاهزة بـ`config.json` لنظام مجاني/مدفوع مستقبلي (غير مفعّلة حاليًا).

### التشغيل

```bash
pip install -r requirements.txt
python main.py
```

شغّله كـ Administrator للوظائف الكاملة — إدارة الخدمات، SFC/DISM، نقاط الاستعادة، وبعض تعديلات الريجستري تحتاج صلاحيات مرتفعة وبتقولك بوضوح لو ناقصة.

### ملاحظة عن نطاق المشروع

هذا المشروع **لا يحتوي** ولن يحتوي أي ميزة تستخرج أو تفك تشفير أو تصدّر بيانات اعتماد محفوظة بمتصفح أو أي تطبيق ثاني. هذا خط ثابت بالمشروع، مو ميزة ناقصة — كل شي هنا يشتغل على خصائص أداء الجهاز نفسه (ملفات، عمليات، خدمات، مفاتيح ريجستري خاصة بالأداء)، أبدًا على أسرار محفوظة تخص شخص ثاني.

### الترخيص

ضيف الترخيص اللي تفضله هنا (MIT خيار شائع لمشروع مثل هذا).
