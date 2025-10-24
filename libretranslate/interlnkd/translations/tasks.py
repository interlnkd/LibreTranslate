from celery import shared_task
import os
import asyncio
from ..utils import translate_csv_file

@shared_task
def generate_product_translations(key):
    try:
        parts = key.split('/') 
        market = parts[4]
        asyncio.run(translate_csv_file(key, market))
               
    except Exception as e:
        raise e