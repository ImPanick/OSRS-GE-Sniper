FROM python:3.11-slim
WORKDIR /app

# Backend deps
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

# Copy backend + utils
COPY backend/ .
COPY backend/utils/ ./utils/

# Make cache updater executable
RUN chmod +x utils/cache_updater.py

CMD ["python", "app.py"]