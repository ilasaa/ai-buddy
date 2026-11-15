FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 EMBEDDING_CACHE_DIR=/cache/huggingface
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch && pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --create-home buddy && mkdir -p /cache/huggingface && chown -R buddy:buddy /cache /app
USER buddy
EXPOSE 8000
CMD ["sh", "scripts/start.sh"]
