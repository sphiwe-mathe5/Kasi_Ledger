from pathlib import Path
import os
from decouple import Csv, config
from dotmap import DotMap
ENV = DotMap({'config': config, 'Csv': Csv})
BASE_DIR = Path(__file__).resolve().parent.parent