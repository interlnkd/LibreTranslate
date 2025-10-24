import os
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.environ.get('AWS_REGION')
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
INTERLNKD_LOVELACE_PRIVATE = "interlnkd-lovelace-private"
FAILED_FOLDER = f'production/products/translations/failed/'
TRANSLATIONS_PENDING_FOLDER = f'production/products/translations/pending/'
TRANSLATIONS_COMPLETED_FOLDER = f'production/products/translations/completed/'

S3_URL = f's3://{AWS_ACCESS_KEY_ID}:{AWS_SECRET_ACCESS_KEY}@{INTERLNKD_LOVELACE_PRIVATE}/'
COLUMNS_TO_CHECK = [
    "product_name",
    "description",
    "raw_category",
]