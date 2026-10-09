FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pinger.py config.json ./

RUN useradd --create-home appuser \
    && mkdir /logs \
    && chown appuser /logs
USER appuser

STOPSIGNAL SIGINT

CMD ["python", "pinger.py"]
