import hashlib
import hmac
import os
import sys
import time
from datetime import datetime, timedelta
from time import sleep

import pandas as pd
import requests
import schedule
import yfinance as yf
from prophet import Prophet

ENDPOINT = os.environ.get("ENDPOINT")
TRADE_PRICE = int(os.environ.get("TRADE_PRICE"))
TAKE_PROFIT = int(os.environ.get("TAKE_PROFIT"))
STOP_LOSS = int(os.environ.get("STOP_LOSS"))
API_KEY = os.environ.get("API_KEY")
API_SECRET = os.environ.get("API_SECRET")

position = None
take_profit_count = 0
stop_loss_count = 0
jpy_amount = 100000
btc_amount = 0.0


def job_1():
    global position, take_profit_count, stop_loss_count, jpy_amount, btc_amount
    current_datetime = datetime.now()

    data = fetch_data(
        start=current_datetime - timedelta(days=365),
        end=current_datetime,
        interval="1h",
    )
    if data.empty:
        return

    model = fit_model(data)
    trend = predict_trend(model)

    if position is None:
        if trend == "up":
            btc_amount = order("buy", TRADE_PRICE)
            jpy_amount -= TRADE_PRICE
            position = "long"
            print(f"{current_datetime} BUY: {jpy_amount}")
    elif position == "long":
        if trend == "down":
            jpy_amount += order("sell", btc_amount)
            btc_amount = 0.0
            position = None
            take_profit_count = 0
            stop_loss_count = 0
            print(f"{current_datetime} SELL: {jpy_amount}")


def job_2():
    global position, take_profit_count, stop_loss_count, jpy_amount, btc_amount
    current_datetime = datetime.now()

    if position == "long":
        jpy = get_sell_rate(btc_amount)
        if (jpy - TRADE_PRICE) >= TAKE_PROFIT:
            take_profit_count += 1
            if take_profit_count >= 3 or (jpy - TRADE_PRICE) >= TAKE_PROFIT * 3:
                jpy_amount += order("sell", btc_amount)
                btc_amount = 0.0
                position = None
                take_profit_count = 0
                print(f"{current_datetime} TAKE PROFIT: {jpy_amount}")
        else:
            take_profit_count = 0

        if (TRADE_PRICE - jpy) >= STOP_LOSS:
            stop_loss_count += 1
            if stop_loss_count >= 3 or (TRADE_PRICE - jpy) >= STOP_LOSS * 3:
                jpy_amount += order("sell", btc_amount)
                btc_amount = 0.0
                position = None
                stop_loss_count = 0
                print(f"{current_datetime} STOP LOSS: {jpy_amount}")
        else:
            stop_loss_count = 0


def fetch_data(start, end, interval="5m"):
    df = yf.download(
        tickers="BTC-JPY",
        start=start,
        end=end,
        interval=interval,
        ignore_tz=True,
    )
    df = pd.DataFrame({"ds": df.index, "y": df["Adj Close"]}).reset_index(drop=True)
    return df


def fit_model(df):
    model = Prophet()
    model.fit(df)
    return model


def predict_trend(model):
    future = model.make_future_dataframe(periods=24, freq="h")
    forecast = model.predict(future)
    last_price = forecast.iloc[-25]["yhat"]
    future_price = forecast.iloc[-1]["yhat"]
    return "up" if future_price > last_price else "down"


def create_headers(url, key, secret):
    nonce = str(int(time.time()))
    message = nonce + url
    signature = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()
    return {
        "ACCESS-KEY": key,
        "ACCESS-NONCE": nonce,
        "ACCESS-SIGNATURE": signature,
    }


# TEST ORDER
def order(order_type, amount):
    params = {"pair": "btc_jpy", "order_type": order_type}

    if order_type == "buy":
        params["price"] = amount
    elif order_type == "sell":
        params["amount"] = amount

    res = requests.get(ENDPOINT + "/exchange/orders/rate", params=params).json()

    if res["success"] is True:
        if order_type == "buy":
            return res["amount"]
        elif order_type == "sell":
            return res["price"]


def get_sell_rate(amount):
    params = {"pair": "btc_jpy", "order_type": "sell", "amount": amount}
    res = requests.get(ENDPOINT + "/exchange/orders/rate", params=params).json()
    return res["price"]


schedule.every().day.at("00:00").do(job_1)
schedule.every(5).minutes.do(job_2)

while True:
    schedule.run_pending()
    time.sleep(1)
