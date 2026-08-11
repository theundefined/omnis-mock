FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

EXPOSE 8000

# Shell form (nie exec-array) celowo — Render wstrzykuje port przez zmienną $PORT, a exec form nie robi
# ekspansji zmiennych. Lokalnie (docker run bez -e PORT) spada na domyślne 8000.
CMD uvicorn omnis_mock.main:app --host 0.0.0.0 --port ${PORT:-8000}
