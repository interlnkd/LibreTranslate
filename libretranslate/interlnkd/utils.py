import os 
from smart_open import open
import pandas as pd
from .aws.util import get_s3_client
import asyncio
from .constants import S3_URL, COLUMNS_TO_CHECK, FAILED_FOLDER, INTERLNKD_LOVELACE_PRIVATE, TRANSLATIONS_PENDING_FOLDER, TRANSLATIONS_COMPLETED_FOLDER
from libretranslate.language import model2iso, iso2model, detect_languages, improve_translation_formatting
from libretranslate.language import load_languages
from html import unescape
from translatehtml import translate_html
import time
import concurrent.futures
from io import StringIO
import traceback
import uuid
# Rough map of emoji characters
emojis = {e: True for e in \
  [ord(' ')] +                    # Spaces
  list(range(0x1F600,0x1F64F)) +  # Emoticons
  list(range(0x1F300,0x1F5FF)) +  # Misc Symbols and Pictographs
  list(range(0x1F680,0x1F6FF)) +  # Transport and Map
  list(range(0x2600,0x26FF)) +    # Misc symbols
  list(range(0x2700,0x27BF)) +    # Dingbats
  list(range(0xFE00,0xFE0F)) +    # Variation Selectors
  list(range(0x1F900,0x1F9FF)) +  # Supplemental Symbols and Pictographs
  list(range(0x1F1E6,0x1F1FF)) +  # Flags
  list(range(0x20D0,0x20FF))      # Combining Diacritical Marks for Symbols
}

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


async def delete_file_from_s3(file_key, folder_prefix):
    try:
        s3_client = get_s3_client()
        if s3_client:
            s3_client.delete_object(Bucket=INTERLNKD_LOVELACE_PRIVATE, Key=file_key)
            print(f"The file '{file_key}' in the folder '{folder_prefix}' has been deleted.", flush=True)
        return
    except Exception as e:
        print(f"Error: {str(e)}")


async def upload_data_to_s3(csv_buffer, bucket, s3_key):
    try:
        s3_client = get_s3_client()

        if s3_client:
            s3_client.put_object(
                Bucket=bucket,
                Key=s3_key,
                Body=csv_buffer.getvalue()
            )
        return
    except Exception as e:
        print(f"Failed to upload {s3_key} to {bucket}", flush=True)


async def upload_csv_to_bucket(final_df, destination_folder, file_name):
    try:
        csv_buffer = StringIO()
        final_df.to_csv(csv_buffer, index=False)

        await upload_data_to_s3(csv_buffer, INTERLNKD_LOVELACE_PRIVATE, destination_folder + file_name)
        print(f"Uploaded to {destination_folder}", flush=True)
        return
    except Exception as e:
        # Log the exception or handle it as needed
        print(f"An error occurred: {str(e)}")
        traceback.print_exc()  # This prints the traceback to help debug
        # You might want to raise or return an appropriate value here


async def translate_csv_file(key, market):
    start_time = time.time()
    file_name = os.path.basename(key)

    print([l.code for l in load_languages()], flush=True)

    try:
        if not is_csv_file(key):
            print("Please provide a valid csv file", flush=True)
            return None

        # Read header first
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

        # Read full CSV
        with open(f"{S3_URL}{key}", 'rb') as s3_file:
            df = pd.read_csv(s3_file, low_memory=False)

            df["description"] = df["description"].fillna("oov").astype(str)
            df["product_name"] = df["product_name"].fillna("oov").astype(str)
            # df["raw_category"] = df["raw_category"].fillna("oov").astype(str)

            max_workers = 5
            chunk_size = 500

            # df = translate_column(
            #     df,
            #     column="raw_category",
            #     target_column="raw_category_en",
            #     source_lang=market,
            #     target_lang="en",
            #     chunk_size=chunk_size,
            #     max_workers=max_workers
            # )

            df = translate_column(
                df,
                column="product_name",
                target_column="product_name_en",
                source_lang=market,
                target_lang="en",
                chunk_size=chunk_size,
                max_workers=max_workers
            )

            df = translate_column(
                df,
                column="description",
                target_column="description_en",
                source_lang=market,
                target_lang="en",
                chunk_size=chunk_size,
                max_workers=max_workers
            )

            destination_folder = TRANSLATIONS_COMPLETED_FOLDER + f'{market}/'
            random_uuid = uuid.uuid4()
            new_file_name = f"{str(random_uuid)}.csv"

            await upload_csv_to_bucket(df, destination_folder, file_name)

        # Optional: delete original file after processing
        await delete_file_from_s3(key, folder_prefix=TRANSLATIONS_PENDING_FOLDER + f'{market}')
        print(f"Deleted {key}", flush=True)
        elapsed = time.time() - start_time
        print(f"Translated {len(df)} rows in {elapsed / 60:.2f} minutes", flush=True)

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
    

def translate_column(
    df,
    column: str,
    target_column: str,
    source_lang: str,
    target_lang: str,
    chunk_size,
    max_workers
):
    def executor_translate(batch):
        payload = {
            "q": batch,
            "source": source_lang,
            "target": target_lang,
            "format": "text",
        }
        
        result_dict = translate_batch(payload) 
        return result_dict.get("translatedText", [])

    texts_to_translate = df[column].tolist()
    chunks = [texts_to_translate[i:i + chunk_size] for i in range(0, len(texts_to_translate), chunk_size)]

    translated_texts = []

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(executor_translate, chunk) for chunk in chunks]
            
            for future in futures: 
                try:
                    result = future.result()
                    translated_texts.extend(result)
                except Exception as e:
            
                    print(f"A chunk failed: {e}. Cannot reliably determine length for placeholders.", flush=True)
        
                    raise e

    except Exception as e:
        print(f"Batch failed: {e}", flush=True)
        raise # Re-raise to ensure error is propagated to translate_csv_file

    if len(translated_texts) != len(df):
         raise ValueError(
             f"Translation length mismatch: Got {len(translated_texts)} results for {len(df)} rows."
         )
         
    df[target_column] = translated_texts

    return df


def detect_translatable(src_texts):
  if isinstance(src_texts, list):
    return any(detect_translatable(t) for t in src_texts)

  for ch in src_texts:
    if not (ord(ch) in emojis):
      return True

  # All emojis
  return False


def filter_unique(seq, extra):
    seen = set({extra, ""})
    seen_add = seen.add
    return [x for x in seq if not (x in seen or seen_add(x))]


def translate_batch(payload):
    """
    Performs translation for a batch payload without using Flask context.
    Returns the raw Python dictionary result.
    """
    q = payload.get("q")
    source_lang = iso2model(payload.get("source"))
    target_lang = iso2model(payload.get("target"))
    text_format = payload.get("format")
    num_alternatives = 0 
    
    if not isinstance(q, list) or not q:
        # If it's not a batch (list) or the list is empty, treat as an error for a batch processor
        return {"translatedText": []} 
        
    src_texts = q
    
    translatable = detect_translatable(src_texts)
    
    if translatable:
        # Language Detection Logic (kept as in original)
        if source_lang == "auto":
            candidate_langs = detect_languages(src_texts)
            detected_src_lang = candidate_langs[0]
        else:
            detected_src_lang = {"confidence": 100.0, "language": source_lang}
    else:
        detected_src_lang = {"confidence": 0.0, "language": "en"}
    
    languages = load_languages()

    # 2. Language Code Check (Replaced abort with raise)
    src_lang = next(iter([l for l in languages if l.code == detected_src_lang["language"]]), None)

    if src_lang is None:
        print([l.code for l in languages], 'available languages', flush=True)
        raise ValueError(f"{source_lang} is not supported")

    tgt_lang = next(iter([l for l in languages if l.code == target_lang]), None)

    if tgt_lang is None:
        raise ValueError(f"{target_lang} is not supported")

    # 3. Format Check (Replaced abort with raise)
    if not text_format:
        text_format = "text"

    if text_format not in ["text", "html"]:
        raise ValueError(f"{text_format} format is not supported")

    result = translate_inner_batch(
        q,
        src_lang,
        tgt_lang,
        translatable,
        num_alternatives,
        max_workers=100,
    )

    return result


def translate_inner_batch(q, src_lang, tgt_lang, translatable, num_alternatives, max_workers=5, inner_group_size=50):
    batch_results = []
    
    groups = [q[i:i + inner_group_size] for i in range(0, len(q), inner_group_size)]

    def executor_translate(text):
        translator = src_lang.get_translation(tgt_lang)

        if translator is None:
            raise ValueError(
                f"{tgt_lang.name} ({tgt_lang.code}) is not available as a target language "
                f"from {src_lang.name} ({src_lang.code})"
            )

        if translatable:
            hypotheses = translator.hypotheses(text, num_alternatives + 1)
            translated_text = unescape(improve_translation_formatting(text, hypotheses[0].value))
        else:
            translated_text = text

        return translated_text

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            for group in groups:
                group_results = list(executor.map(executor_translate, group))
                batch_results.extend(group_results)

    except Exception as e:
        print(f"Batch failed: {e}", flush=True)
        raise

    return {
        "translatedText": batch_results,
    }