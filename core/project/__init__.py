from pathlib import Path
from core.celery import app as celery_app
import os
from decouple import Csv, config
from dotmap import DotMap
__all__ = ('celery_app',)
ENV = DotMap({'config': config, 'Csv': Csv})
BASE_DIR = Path(__file__).resolve().parent.parent