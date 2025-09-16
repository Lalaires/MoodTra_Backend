# Base image for Python
FROM python:3.12-slim

# Add AWS Lambda Web Adapter (no code changes in FastAPI needed)
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.8.4 /lambda-adapter /opt/extensions/lambda-adapter

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies
COPY ./requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt

# Copy application code
COPY ./api /app/api
COPY ./AI  /app/AI

# The web adapter forwards requests to this port
ENV PORT=8000

# Run Uvicorn; the adapter proxies API Gateway/Function URL to this server
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]