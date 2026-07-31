FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=8000
EXPOSE $PORT
CMD gunicorn main:app -w 2 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT 2>/dev/null || \
    gunicorn app:app --bind 0.0.0.0:$PORT 2>/dev/null || \
    gunicorn config.wsgi --bind 0.0.0.0:$PORT
