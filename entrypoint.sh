# تنفيذ الهجرات فوراً عند تشغيل الحاوية
echo "Applying database migrations..."
python manage.py migrate

# تشغيل السيرفر بعد اكتمال الهجرات
echo "Starting server..."
exec "$@"