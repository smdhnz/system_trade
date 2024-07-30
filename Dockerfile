FROM python:3.12-slim

ENV TZ=Asia/Tokyo

WORKDIR /app

RUN pip install \
  numpy<2 \
  yfinance \
  prophet \
  pandas \
  schedule \
  requests

COPY main.py .

CMD [ "python3", "main.py" ]
