import os 
from smart_open import open
import pandas as pd
from .aws.util import get_s3_client
import asyncio
from .constants import S3_URL, COLUMNS_TO_CHECK, FAILED_FOLDER, INTERLNKD_LOVELACE_PRIVATE

async def translate_csv_file(key, market):
    file_name = os.path.basename(key)

    try:
        if is_csv_file(key):
            with open(f"{S3_URL}{key}", 'rb') as s3_file:
                header = pd.read_csv(s3_file, nrows=0).columns.tolist()
                missing_columns = [col for col in COLUMNS_TO_CHECK if col not in header]

                if missing_columns:
                    print(f"Missing required columns: {', '.join(missing_columns)}", flush=True)
                    await move_file_to_new_folder(
                        new_folder=FAILED_FOLDER + f'{market}/',
                        file_name=file_name,
                        bucket=INTERLNKD_LOVELACE_PRIVATE,
                        source_path=key
                    )

                    return None
        else:
            print("Please provide a valid csv file", flush=True)

        return key, market
    except Exception as e:
        print(f"Experienced an error: translate_csv_file", flush=True)
        await move_file_to_new_folder(
            new_folder=FAILED_FOLDER + f"{market}/",
            file_name=file_name,
            bucket=INTERLNKD_LOVELACE_PRIVATE,
            source_path=key
        )
        await asyncio.sleep(1)
        print("Failed to process, removing file from queued tasks folder", flush=True)
        raise e


async def move_file_to_new_folder(new_folder, file_name, bucket, source_path):
    s3_client = get_s3_client()
    # Specify the source and destination paths
    destination_path = f'{new_folder}{file_name}'

    try:
        if s3_client:
            # Move the file within the S3 bucket
            s3_client.copy_object(Bucket=bucket, CopySource={'Bucket': bucket, 'Key': source_path},
                                  Key=destination_path)
            s3_client.delete_object(Bucket=bucket, Key=source_path)
            print(f'File moved from {source_path} to {new_folder}', flush=True)
    except Exception as e:
        # Handle the exception
        print(f'Error moving file: {e}', flush=True)
        # Optionally, you can raise the exception again if you want the caller to handle it as well


def is_csv_file(file_name):
    _, file_extension = os.path.splitext(file_name)
    return file_extension.lower() == '.csv'
