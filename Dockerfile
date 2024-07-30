FROM python:3.12-slim

ENV TZ=Asia/Tokyo

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY main.py .

CMD [ "python3", "main.py" ]
