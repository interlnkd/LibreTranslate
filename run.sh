#!/bin/bash
set -eo pipefail

__dirname=$(cd "$(dirname "$0")"; pwd -P)
cd "${__dirname}"

usage(){
  echo "Usage: $0 [--file COMPOSE_FILE] [--port N] [--worker] [--update-models] [--download-models] [--rebuild] [--all] [--langs LANGS]"
  echo
  echo "Run LibreTranslate API or Celery worker using Docker Compose."
  echo
  echo "Options:"
  echo "  --file FILE           Specify docker-compose file (default: docker-compose.yml)"
  echo "  --port PORT           Port for LibreTranslate API (default: 5001)"
  echo "  --worker              Run only Celery worker service"
  echo "  --update-models       Download or update translation models before starting"
  echo "  --download-models     Download models only (no server start)"
  echo "  --rebuild             Rebuild Docker image before starting"
  echo "  --all                 Start both API and Celery worker"
  echo "  --langs LANGS         Comma-separated language codes to download (default: all)"
  echo "  --help                Show this message"
  echo
  exit
}

COMPOSE_FILE="docker-compose.yml"
LT_PORT=5001
RUN_WORKER=false
RUN_API=false
UPDATE_MODELS=false
DOWNLOAD_MODELS=false
REBUILD=false
LANGS=""

while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    --file) COMPOSE_FILE="$2"; shift 2 ;;
    --port) LT_PORT="$2"; shift 2 ;;
    --worker) RUN_WORKER=true; shift ;;
    --update-models|--update_models) UPDATE_MODELS=true; shift ;;
    --download-models) DOWNLOAD_MODELS=true; shift ;;
    --rebuild) REBUILD=true; shift ;;
    --all) RUN_WORKER=true; RUN_API=true; shift ;;
    --langs) LANGS="$2"; shift 2 ;;
    --help) usage ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
done

hash docker 2>/dev/null || { echo "Docker not found! Install Docker first."; exit 1; }
hash docker-compose 2>/dev/null || hash docker 2>/dev/null && docker compose version >/dev/null 2>&1 || { echo "Docker Compose not found! Install Docker Compose first."; exit 1; }

export LT_PORT=$LT_PORT
if hash docker compose >/dev/null 2>&1; then
  COMPOSE_CMD="docker compose -f $COMPOSE_FILE"
else
  COMPOSE_CMD="docker-compose -f $COMPOSE_FILE"
fi

# --- Stop and remove old containers ---
echo "🧹 Stopping and removing existing containers..."
$COMPOSE_CMD down

# --- Rebuild image if requested ---
if [ "$REBUILD" = true ]; then
  echo "🔨 Rebuilding LibreTranslate Docker image..."
  $COMPOSE_CMD build libretranslate
  echo "✅ Rebuild complete."
fi

# --- Download or update models ---
if [ "$UPDATE_MODELS" = true ] || [ "$DOWNLOAD_MODELS" = true ]; then
  echo "🔄 Downloading LibreTranslate models..."
  if [ -n "$LANGS" ]; then
    echo "📦 Downloading only models for languages: $LANGS"
    $COMPOSE_CMD run --rm --entrypoint "./venv/bin/python" libretranslate scripts/install_models.py --load_only_lang_codes "$LANGS"
  else
    $COMPOSE_CMD run --rm --entrypoint "./venv/bin/python" libretranslate scripts/install_models.py
  fi
  echo "✅ Model download complete."

  if [ "$DOWNLOAD_MODELS" = true ]; then
    echo "🚀 Models downloaded. Exiting as requested by --download-models."
    exit 0
  fi
fi

# --- Start containers ---
if [ "$RUN_WORKER" = true ] && [ "$RUN_API" = true ]; then
  echo "🚀 Starting API and Celery worker..."
  $COMPOSE_CMD up -d
elif [ "$RUN_WORKER" = true ]; then
  echo "🚀 Starting Celery worker..."
  $COMPOSE_CMD up -d libretranslate_celery
else
  echo "🚀 Starting API..."
  $COMPOSE_CMD up -d libretranslate
fi
