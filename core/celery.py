from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

# set default Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.project.settings')

app = Celery('your_project')

# read Celery settings from Django settings, using "CELERY_" namespace
app.config_from_object('django.conf:settings', namespace='CELERY')

# auto-discover tasks.py in all apps
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
