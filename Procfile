web: python manage.py collectstatic --noinput && python manage.py migrate && gunicorn core.project.wsgi --bind 0.0.0.0:$PORT --timeout 120 --workers 2
worker: python manage.py rqworker default