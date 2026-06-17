FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends tzdata && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py *.csv ./

VOLUME /app/data

ENV TZ=Asia/Shanghai
ENV AH_LOG_ROOT=/app/data/
ENV PORT=5000

EXPOSE 5000

CMD gunicorn bot:app -b 0.0.0.0:$PORT -w 1
