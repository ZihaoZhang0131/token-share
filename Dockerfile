FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
RUN addgroup --system tokenstation && adduser --system --ingroup tokenstation tokenstation
COPY pyproject.toml alembic.ini ./
COPY app/__init__.py ./app/__init__.py
RUN pip install --upgrade pip && pip install .
COPY app ./app
COPY alembic ./alembic

USER tokenstation
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
