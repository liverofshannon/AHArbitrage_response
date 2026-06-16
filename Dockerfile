FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py *.csv ./

VOLUME /app/data

ENV TZ=Asia/Shanghai
ENV AH_LOG_ROOT=/app/data/

EXPOSE 5000

CMD ["gunicorn", "bot:app", "-b", "0.0.0.0:5000", "-w", "2"]
