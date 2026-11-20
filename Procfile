web: python manage.py migrate --noinput && python manage.py build_translations && uvicorn config.asgi:application --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips="*"
worker: celery -A config worker -B --loglevel=info --concurrency=2
