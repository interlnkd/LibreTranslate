#!/bin/bash
set -eo pipefail

__dirname=$(cd "$(dirname "$0")"; pwd -P)
cd "${__dirname}"

usage(){
  echo "Usage: $0 [--file COMPOSE_FILE] [--port N] [--worker] [--update-models]"
  echo
  echo "Run LibreTranslate API or Celery worker using Docker Compose."
  echo
  echo "Options:"
  echo "  --file FILE           Specify docker-compose file (default: docker-compose.yml)"
  echo "  --port PORT           Port for LibreTranslate API (default: 5001)"
  echo "  --worker              Run only Celery worker service"
  echo "  --update-models       Download or update translation models before starting"
  echo "  --help                Show this message"
  echo
  exit
}

# --- Configuration Variables ---
COMPOSE_FILE="docker-compose.yml"
LT_PORT=5001
RUN_WORKER=false
UPDATE_MODELS=false

# --- Argument Parsing ---
while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    --file)
      COMPOSE_FILE="$2"
      shift 2
      ;;
    --port)
      LT_PORT="$2"
      shift 2
      ;;
    --worker)
      RUN_WORKER=true
      shift
      ;;
    --update-models|--update_models)
      UPDATE_MODELS=true
      shift
      ;;
    --help)
      usage
      ;;
    *)
      echo "Unknown option: $1"
      usage
      ;;
  esac
done

# --- Prerequisite Checks ---
hash docker 2>/dev/null || { echo "Docker not found! Install Docker first."; exit 1; }
hash docker-compose 2>/dev/null || { echo "Docker Compose not found! Install Docker Compose first."; exit 1; }

export LT_PORT=$LT_PORT
COMPOSE_CMD="docker-compose -f $COMPOSE_FILE"

# --- Update Models (Proper Entrypoint Override) ---
if [ "$UPDATE_MODELS" = true ]; then
  echo "🔄 Updating LibreTranslate models..."
  $COMPOSE_CMD run --rm --entrypoint "./venv/bin/python" libretranslate scripts/install_models.py
  echo "✅ Model update complete."
fi

# --- Start Services ---
if [ "$RUN_WORKER" = true ]; then
  echo "🚀 Starting Celery worker service from $COMPOSE_FILE..."
  $COMPOSE_CMD up libretranslate_celery
else
  echo "🚀 Starting LibreTranslate API and dependencies from $COMPOSE_FILE..."
  $COMPOSE_CMD up
fi
