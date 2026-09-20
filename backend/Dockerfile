FROM python:3.12-slim
WORKDIR /app/backend
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 SERVER_HOST=0.0.0.0
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home creator
COPY --chown=creator:creator . .
RUN mkdir -p /app/backend/storage && chown -R creator:creator /app/backend
USER creator
EXPOSE 8000
CMD ["python", "start.py"]
