FROM python:3.10-slim

# 1. تثبيت FFmpeg لتعديل الصوت والفيديو وأدوات النظام الأساسية
RUN apt-get update && apt-get install -y \
    ffmpeg \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 2. تحديد مجلد العمل داخل السيرفر السحابي
WORKDIR /app

# 3. نسخ ملف المكتبات وتثبيتها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. نسخ باقي كود المشروع داخل الحاوية
COPY . .

# 5. أمر تشغيل السيرفر عبر Gunicorn مع زيادة الـ Timeout لـ 5 دقائق
# ⚠️ ملاحظة: استبدل "myproject" باسم مجلد مشروعك الرئيسي الذي يحتوي على ملف wsgi.py
CMD ["gunicorn", "dubbing_project.wsgi:application", "--bind", "0.0.0.0:10000", "--timeout", "300"]