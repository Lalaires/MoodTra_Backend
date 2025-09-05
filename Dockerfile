# Base image for Python
FROM python:3.12-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY ./requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt

# Copy application code
COPY ./api /app/api
COPY ./AI /app/AI

CMD ["fastapi", "run", "api/main.py", "--port", "80"]
