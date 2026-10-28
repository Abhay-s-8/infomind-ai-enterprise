FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --create-home appuser && mkdir -p /data/uploads /data/models && chown -R appuser /data /app
# No USER line on purpose: start.sh begins as root to fix mounted-volume ownership, then drops to appuser.
EXPOSE 8000
CMD ["sh", "start.sh"]
