FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
ENV PYTHONPATH=/app

COPY requirements-test.txt .

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential libffi-dev libssl-dev && \
    pip install --no-cache-dir -r requirements-test.txt && \
    apt-get purge -y build-essential && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

COPY . .

CMD ["pytest", "-q"]
