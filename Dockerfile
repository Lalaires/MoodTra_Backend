# Base image for Python
FROM python:3.12-slim

# Add AWS Lambda Web Adapter (no code changes required in FastAPI)
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.8.4 /lambda-adapter /opt/extensions/lambda-adapter

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

    
WORKDIR /app

# Install deps
COPY ./requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy app
COPY ./api /app/api
COPY ./AI  /app/AI

# The web adapter forwards Lambda events to this local HTTP port
ENV PORT=8000

# Start Uvicorn HTTP server; the adapter will proxy API Gateway/Function URL events
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]