FROM python:3.12-slim

WORKDIR /app

ENV PIP_NO_CACHE_DIR=1

COPY pyproject.toml poetry.lock* README.md /app/
COPY src /app/src
COPY examples /app/examples

RUN pip install --upgrade pip && \
    pip install "/app[postgres,observability]"

CMD ["python", "examples/production-template/demo_worker.py"]
