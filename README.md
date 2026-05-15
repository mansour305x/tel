# Telegram Video Downloader Bot

بوت Telegram مخصص لتحميل الفيديو من YouTube وTikTok وInstagram وSnapchat باستخدام `aiogram v3` و`yt-dlp` و`FFmpeg`.

## الميزات

- دعم الروابط من YouTube وTikTok وInstagram Reels/Posts وSnapchat
- فحص الرابط والتحقق من المنصة تلقائياً
- جلب معلومات الفيديو قبل التحميل
- خيارات التحميل: فيديو بأفضل جودة، جودة متوسطة، أو MP3
- طابور تحميل احترافي مع نظام إدارة وظائف
- حد الطلبات لكل مستخدم، منع سبام، وإلغاء الطلبات
- تخزين SQLite عبر SQLAlchemy Async
- تنظيف الملفات المؤقتة بعد التنفيذ
- سجلات قابلة للتدوير باستخدام `loguru`
- إعدادات قابلة للتعديل للمسؤولين
- Docker وGitHub Actions للـ CI

## المتطلبات

- Python 3.11+
- FFmpeg
- yt-dlp
- Telegram Bot Token

## التثبيت

1. استنساخ المستودع:
   ```bash
   git clone https://github.com/mansour305x/tel.git
   cd tel
   ```
2. إنشاء ملف `.env` من المثال:
   ```bash
   cp .env.example .env
   ```
3. تعديل الإعدادات في `.env`:
   - `BOT_TOKEN`
   - `ADMIN_IDS`

4. تثبيت الاعتمادات:
   ```bash
   python -m pip install -r requirements.txt
   ```

5. تشغيل التطبيق:
   ```bash
   python -m bot.main
   ```

## الأوامر المتاحة

- `/start` - تفعيل البوت
- `/help` - إرشادات الاستخدام
- `/status` - عرض حالة الطلبات
- `/cancel` - إلغاء الطلب الحالي
- `/settings` - عرض إعدادات المسؤول

### أوامر الإدارة

- `/admin_stats` - إحصائيات عامة
- `/admin_users` - قائمة المستخدمين
- `/admin_broadcast <النص>` - إرسال رسالة لجميع المستخدمين
- `/admin_queue` - عرض حالة قائمة الانتظار

## باستخدام Docker

```bash
docker build -t telegram-video-downloader-bot .
docker run --env-file .env -v $(pwd)/downloads:/app/downloads -v $(pwd)/temp:/app/temp -v $(pwd)/logs:/app/logs -v $(pwd)/data:/app/data telegram-video-downloader-bot
```

أو عبر `docker-compose`:

```bash
docker compose up -d --build
```

## الاختبارات

```bash
pytest -q
```

## هيكل المشروع

- `bot/` - التعليمات البرمجية الأساسية للبوت
- `tests/` - اختبارات الوحدة
- `downloads/` - مجلد تخزين الملفات النهائية
- `temp/` - الملفات المؤقتة
- `logs/` - سجلات التطبيق
- `.github/workflows/` - إعدادات CI

## ملاحظة

يحترم البوت حقوق النشر ويعتمد على `yt-dlp` لدعم المنصات. تأكد من احترام قيود المنصة وشروط الاستخدام عند تحميل المحتوى.
