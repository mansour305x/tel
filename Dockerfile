FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update && apt-get install -y ffmpeg gcc libffi-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app
RUN mkdir -p downloads temp logs data

HEALTHCHECK --interval=60s --timeout=10s --start-period=30s CMD python -m bot.main --help >/dev/null 2>&1 || exit 1

CMD ["python", "-m", "bot.main"]
