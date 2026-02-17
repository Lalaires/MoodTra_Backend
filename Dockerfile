FROM public.ecr.aws/lambda/python:3.12

# Add AWS Lambda Web Adapter
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.8.4 /lambda-adapter /opt/extensions/lambda-adapter

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp \
    HF_HOME=/tmp/hf \
    TRANSFORMERS_CACHE=/tmp/transformers \
    XDG_CACHE_HOME=/tmp \
    TORCH_HOME=/tmp/torch \
    NLTK_DATA=/tmp/nltk_data \
    MPLCONFIGDIR=/tmp/matplotlib \
    NUMBA_CACHE_DIR=/tmp/numba_cache \
    PORT=8000

# λ MUST run from /var/task
WORKDIR ${LAMBDA_TASK_ROOT}

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY api ./api
COPY AI  ./AI

# Run Uvicorn; web adapter handles Lambda events
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
