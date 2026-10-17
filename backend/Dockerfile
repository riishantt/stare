FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr && rm -rf /var/lib/apt/lists/*
WORKDIR /app/backend
COPY pyproject.toml ./
COPY stare ./stare
RUN pip install --no-cache-dir -e '.[postgres,presidio]' && python -m spacy download en_core_web_sm
ENV STARE_DATA_DIR=/app/data
EXPOSE 8000
CMD ["uvicorn", "stare.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
