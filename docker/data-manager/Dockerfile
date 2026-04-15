FROM python:3.12-slim-bookworm

ARG APT_MIRROR
ARG UV_INDEX_URL

# Optionally override apt mirror
RUN if [ -n "${APT_MIRROR}" ]; then \
      sed -i "s|deb.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources 2>/dev/null || true; \
      sed -i "s|deb.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list 2>/dev/null || true; \
    fi

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:0.7.20 /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first for cache
COPY pyproject.toml ./

# Install dependencies
RUN uv pip install --system -r pyproject.toml

# Copy application code
COPY app/ ./app/

EXPOSE 8003

CMD ["uvicorn", "app.app:app", "--host", "0.0.0.0", "--port", "8003"]
