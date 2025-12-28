FROM python:3.12-slim

WORKDIR /app

COPY ingest_service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# copy project files needed (database.py + ingest_service)
COPY database.py /app/database.py
COPY ingest_service /app/ingest_service

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "ingest_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
