FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY scripts ./scripts
COPY data ./data
COPY docs ./docs
COPY README.md ./README.md

EXPOSE 8000

CMD ["python", "scripts/home_page.py", "--host", "0.0.0.0", "--port", "8000", "--data-dir", "data"]
