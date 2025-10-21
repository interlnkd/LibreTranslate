# ----------------------------------------------------------------------
# Single-stage Dockerfile for LibreTranslate
# ----------------------------------------------------------------------
FROM python:3.11.11-slim-bullseye

# Set working directory
WORKDIR /app

# Set noninteractive frontend and install build/runtime tools
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update -qq \
  && apt-get install -y --no-install-recommends \
  pkg-config gcc g++ git ffmpeg libsm6 libxext6 \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY . .

# Install Python dependencies globally
RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir \
  Babel==2.12.1 \
  Flask-Babel \
  flask-session \
  flask-swagger \
  flask_swagger_ui \
  translatehtml \
  APScheduler \
  langdetect \
  packaging \
  LexiLang \
  expiringdict \
  torch==2.2.0 --extra-index-url https://download.pytorch.org/whl/cpu \
  "numpy<2" \
  uvicorn \
  gunicorn \
  flask \
  requests \
  celery \
  redis \
  python-dotenv \
  git+https://github.com/LibreTranslate/argos-translate-files.git \
  && python scripts/compile_locales.py \
  && pip cache purge

ARG with_models=false

ARG models=""

RUN if [ "$with_models" = "true" ]; then \
  if [ ! -z "$models" ]; then \
  python scripts/install_models.py --load_only_lang_codes "$models"; \
  else \
  python scripts/install_models.py; \
  fi \
  fi

ENV PYTHONPATH=/app

EXPOSE 5001

CMD ["gunicorn", "wsgi:app", "--workers", "6", "--worker-class", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:5001", "--timeout", "300000000", "--reload"]
