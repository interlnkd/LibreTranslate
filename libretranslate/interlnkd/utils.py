import os 
from smart_open import open
import pandas as pd
from .aws.util import get_s3_client
import asyncio
from .constants import S3_URL, COLUMNS_TO_CHECK, FAILED_FOLDER, INTERLNKD_LOVELACE_PRIVATE
from flask import Blueprint, Flask, Response, abort, jsonify, render_template, request, send_file, session, url_for, make_response
from libretranslate.language import model2iso, iso2model, detect_languages, improve_translation_formatting

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
                
            with open(f"{S3_URL}{key}", 'rb') as s3_file:
                df = pd.read_csv(s3_file, low_memory=False)
                print(df.head(100), flush=True)

                # await delete_file_from_s3(key, folder_prefix=ML_READY_FILE_FOLDER + f'/{market}')
                # print(f"Deleted {key}", flush=True)
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


async def delete_file_from_s3(file_key, folder_prefix):
    try:
        s3_client = get_s3_client()
        if s3_client:
            s3_client.delete_object(Bucket=INTERLNKD_LOVELACE_PRIVATE, Key=file_key)
            print(f"The file '{file_key}' in the folder '{folder_prefix}' has been deleted.", flush=True)
        return
    except Exception as e:
        print(f"Error: {str(e)}")


def translate_batch(batch, source_lang, target_lang):
    payload = {
        "q": batch,
        "source": source_lang,
        "target": target_lang,
        "format": "text",
    }

    return translate(payload)

def translate(payload):
    q = payload.get("q")
    source_lang = iso2model(payload.get("source"))
    target_lang = iso2model(payload.get("target"))
    text_format = payload.get("format")
    num_alternatives = 0

    if not q:
        abort(400, description=_("Invalid request: missing %(name)s parameter", name='q'))
    if not source_lang:
        abort(400, description=_("Invalid request: missing %(name)s parameter", name='source'))
    if not target_lang:
        abort(400, description=_("Invalid request: missing %(name)s parameter", name='target'))

    try:
        num_alternatives = max(0, int(num_alternatives))
    except ValueError:
        abort(400, description=_("Invalid request: %(name)s parameter is not a number", name='alternatives'))

    if args.alternatives_limit != -1 and num_alternatives > args.alternatives_limit:
        abort(400, description=_("Invalid request: %(name)s parameter must be <= %(value)s", name='alternatives', value=args.alternatives_limit))

    if not request.is_json:
        # Normalize line endings to UNIX style (LF) only so we can consistently
        # enforce character limits.
        # https://www.rfc-editor.org/rfc/rfc2046#section-4.1.1
        q = "\n".join(q.splitlines())

    char_limit = get_char_limit(args.char_limit, api_keys_db)

    batch = isinstance(q, list)

    if batch and args.batch_limit != -1:
        batch_size = len(q)
        if args.batch_limit < batch_size:
            abort(
                400,
                description=_("Invalid request: request (%(size)s) exceeds text limit (%(limit)s)", size=batch_size, limit=args.batch_limit),
            )

    src_texts = q if batch else [q]

    if char_limit != -1:
        for text in src_texts:
            if len(text) > char_limit:
                abort(
                    400,
                    description=_("Invalid request: request (%(size)s) exceeds text limit (%(limit)s)", size=len(text), limit=char_limit),
                )

    if batch:
        request.req_cost = max(1, len(q))

    translatable = detect_translatable(src_texts)
    if translatable:
        if source_lang == "auto":
            candidate_langs = detect_languages(src_texts)
            detected_src_lang = candidate_langs[0]
        else:
            detected_src_lang = {"confidence": 100.0, "language": source_lang}
    else:
        detected_src_lang = {"confidence": 0.0, "language": "en"}

    src_lang = next(iter([l for l in languages if l.code == detected_src_lang["language"]]), None)

    if src_lang is None:
        abort(400, description=_("%(lang)s is not supported", lang=source_lang))

    tgt_lang = next(iter([l for l in languages if l.code == target_lang]), None)

    if tgt_lang is None:
        abort(400, description=_("%(lang)s is not supported",lang=target_lang))

    if not text_format:
        text_format = "text"

    if text_format not in ["text", "html"]:
        abort(400, description=_("%(format)s format is not supported", format=text_format))

    try:
        if batch:
            batch_results = []
            batch_alternatives = []
            for text in q:
                translator = src_lang.get_translation(tgt_lang)
                if translator is None:
                    abort(400, description=_("%(tname)s (%(tcode)s) is not available as a target language from %(sname)s (%(scode)s)", tname=_lazy(tgt_lang.name), tcode=tgt_lang.code, sname=_lazy(src_lang.name), scode=src_lang.code))

                if translatable:
                    if text_format == "html":
                        translated_text = unescape(str(translate_html(translator, text)))
                        alternatives = [] # Not supported for html yet
                    else:
                        hypotheses = translator.hypotheses(text, num_alternatives + 1)
                        translated_text = unescape(improve_translation_formatting(text, hypotheses[0].value))
                        alternatives = filter_unique([unescape(improve_translation_formatting(text, hypotheses[i].value)) for i in range(1, len(hypotheses))], translated_text)
                else:
                    translated_text = text # Cannot translate, send the original text back
                    alternatives = []

                batch_results.append(translated_text)
                batch_alternatives.append(alternatives)

            result = {"translatedText": batch_results}

            if source_lang == "auto":
                result["detectedLanguage"] = [model2iso(detected_src_lang)] * len(q)
            if num_alternatives > 0:
                result["alternatives"] = batch_alternatives

            return jsonify(result)
        else:
            translator = src_lang.get_translation(tgt_lang)
            if translator is None:
                abort(400, description=_("%(tname)s (%(tcode)s) is not available as a target language from %(sname)s (%(scode)s)", tname=_lazy(tgt_lang.name), tcode=tgt_lang.code, sname=_lazy(src_lang.name), scode=src_lang.code))

            if translatable:
                if text_format == "html":
                    translated_text = unescape(str(translate_html(translator, q)))
                    alternatives = [] # Not supported for html yet
                else:
                    hypotheses = translator.hypotheses(q, num_alternatives + 1)
                    translated_text = unescape(improve_translation_formatting(q, hypotheses[0].value))
                    alternatives = filter_unique([unescape(improve_translation_formatting(q, hypotheses[i].value)) for i in range(1, len(hypotheses))], translated_text)
            else:
                translated_text = q # Cannot translate, send the original text back
                alternatives = []

            result = {"translatedText": translated_text}

            if source_lang == "auto":
                result["detectedLanguage"] = model2iso(detected_src_lang)
            if num_alternatives > 0:
                result["alternatives"] = alternatives

            return jsonify(result)
    except Exception as e:
        raise e
        abort(500, description=_("Cannot translate text: %(text)s", text=str(e)))