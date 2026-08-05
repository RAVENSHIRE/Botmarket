# BOTMARKET backend image
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install dependencies from the project metadata first, so a source-only change
# does not invalidate the dependency layer.
COPY backend/pyproject.toml ./backend/
RUN mkdir -p backend/src/botmarket && pip install -e "./backend[postgres]"

COPY backend/src ./backend/src

EXPOSE 8000

CMD ["uvicorn", "botmarket.main:app", "--host", "0.0.0.0", "--port", "8000"]
