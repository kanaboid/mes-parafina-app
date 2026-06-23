FROM python:3.12-slim

WORKDIR /app

RUN useradd --create-home --uid 10001 appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY templates/ templates/

USER appuser

EXPOSE 3080

CMD ["gunicorn", "--bind", "0.0.0.0:3080", "--workers", "1", "--threads", "2", "app:app"]
