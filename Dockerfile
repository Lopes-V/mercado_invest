FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml requirements.lock.txt ./
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY app ./app
RUN useradd --create-home --uid 10001 appuser
USER appuser
CMD ["python", "-m", "app.worker"]
