FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app/backend
COPY backend/requirements.txt ./requirements.txt
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install -r requirements.txt
COPY backend/ ./
RUN useradd --create-home buddy && mkdir -p /app/.cache/huggingface \
    && chown -R buddy:buddy /app
USER buddy
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
