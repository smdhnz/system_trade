import hashlib
import hmac
import json
import os
import sys
import time
from contextlib import contextmanager
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
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

position = None
take_profit_count = 0
stop_loss_count = 0
jpy_amount = 100000
btc_amount = 0.0


def job_1():
    global position, take_profit_count, stop_loss_count, jpy_amount, btc_amount
    current_datetime = datetime.now()

    data = fetch_data(
        start=current_datetime - timedelta(days=1),
        end=current_datetime,
        interval="5m",
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
            print(f"{current_datetime}, BUY, {jpy_amount + TRADE_PRICE}")
        else:
            print(f"{current_datetime}, HOLD, {jpy_amount}")
    elif position == "long":
        if trend == "down":
            jpy_amount += order("sell", btc_amount)
            btc_amount = 0.0
            position = None
            take_profit_count = 0
            stop_loss_count = 0
            print(f"{current_datetime}, SELL, {jpy_amount}")
        else:
            print(f"{current_datetime}, HOLD, {get_sell_rate(btc_amount) + jpy_amount}")


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
                print(f"{current_datetime}, TAKE PROFIT, {jpy_amount}")
        else:
            take_profit_count = 0

        if (TRADE_PRICE - jpy) >= STOP_LOSS:
            stop_loss_count += 1
            if stop_loss_count >= 3 or (TRADE_PRICE - jpy) >= STOP_LOSS * 3:
                jpy_amount += order("sell", btc_amount)
                btc_amount = 0.0
                position = None
                stop_loss_count = 0
                print(f"{current_datetime}, STOP LOSS, {jpy_amount}")
        else:
            stop_loss_count = 0


@contextmanager
def suppress_output():
    # 標準出力と標準エラーを一時的に無効化
    with open(os.devnull, "w") as f:
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = f
        sys.stderr = f
        try:
            yield
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr


def fetch_data(start, end, interval="5m"):
    with suppress_output():
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
    with suppress_output():
        model = Prophet()
        model.fit(df)
    return model


def predict_trend(model):
    with suppress_output():
        future = model.make_future_dataframe(periods=1, freq="h")  # 1時間先を予測
        forecast = model.predict(future)
    last_price = forecast.iloc[-2]["yhat"]  # 最後の予測値の1時間前の価格
    future_price = forecast.iloc[-1]["yhat"]  # 最後の予測値
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
            return float(res["amount"])
        elif order_type == "sell":
            return float(res["price"])


def get_sell_rate(amount):
    params = {"pair": "btc_jpy", "order_type": "sell", "amount": amount}
    res = requests.get(ENDPOINT + "/exchange/orders/rate", params=params).json()
    return float(res["price"])


schedule.every().hour.at(":00").do(job_1)
for minute in range(0, 60, 5):
    schedule.every().hour.at(f"{minute:02d}").do(job_2)

while True:
    schedule.run_pending()
    time.sleep(1)
