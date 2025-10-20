# Builder stage
FROM python:3.11.11-slim-bullseye AS builder

WORKDIR /app

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update -qq \
  && apt-get -qqq install --no-install-recommends -y pkg-config gcc g++ \
  && apt-get upgrade --assume-yes \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv venv && ./venv/bin/pip install --no-cache-dir --upgrade pip

# Copy app code
COPY . .

# Install dependencies
RUN ./venv/bin/pip install --no-cache-dir \
      Babel==2.12.1 \
      torch==2.2.0 --extra-index-url https://download.pytorch.org/whl/cpu \
      "numpy<2" \
      celery \
      redis \
      . \
  && ./venv/bin/python scripts/compile_locales.py \
  && ./venv/bin/pip cache purge

# Final image
FROM python:3.11.11-slim-bullseye

RUN addgroup --system --gid 1032 libretranslate \
    && adduser --system --uid 1032 libretranslate \
    && mkdir -p /home/libretranslate/.local \
    && chown -R libretranslate:libretranslate /home/libretranslate/.local

USER libretranslate
WORKDIR /app

# Copy everything from builder
COPY --from=builder --chown=1032:1032 /app /app
COPY --from=builder --chown=1032:1032 /app/venv /app/venv

ARG with_models=false
ARG models=""

# Optional model installation
RUN if [ "$with_models" = "true" ]; then \
      if [ ! -z "$models" ]; then \
        ./venv/bin/python scripts/install_models.py --load_only_lang_codes "$models"; \
      else \
        ./venv/bin/python scripts/install_models.py; \
      fi \
    fi

EXPOSE 5000

# Default entrypoint for LibreTranslate API
ENTRYPOINT ["./venv/bin/libretranslate", "--host", "*"]
