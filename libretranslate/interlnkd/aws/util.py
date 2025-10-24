import os
import botocore
from .client import AWSClient
from ..constants import AWS_ACCESS_KEY_ID, AWS_REGION, AWS_SECRET_ACCESS_KEY

from botocore.exceptions import ClientError

def get_s3_client():
    aws_client = AWSClient(
        AWS_ACCESS_KEY_ID,
        AWS_SECRET_ACCESS_KEY,
        AWS_REGION
    )
    s3_client = aws_client.get_client("s3")
    return s3_client


def dowload_s3_file(bucket_name, object_key, download_path):
    try:
        s3_client = get_s3_client()
        s3_client.download_file(bucket_name, object_key, download_path)

        if os.path.exists(download_path):
            return download_path
        else:
            return None
    except botocore.exceptions.ClientError as e:
        print("Error downloading file:", e, flush=True)
        return None


def scan_s3_folder(bucket_name, folder):
    """Scans an s3 folder and returns a list of files"""

    files = []
    s3_client = get_s3_client()
    paginator = s3_client.get_paginator('list_objects_v2')

    try:
        for page in paginator.paginate(Bucket=bucket_name, Prefix=folder):
            if 'Contents' in page:
                for obj in page['Contents']:
                    files.append(obj['Key'])
    except ClientError as e:
        print("Error scanning S3 folder:", e, flush=True)
    
    return files



async def upload_to_s3(file_path, bucket, s3_key):
    try:
        s3_client = get_s3_client()
        print('upload_to_s3', flush=True)
        print(s3_client.upload_file(file_path, bucket, s3_key), flush=True)
    except Exception as e:
        print(e, flush=True)
        return None
