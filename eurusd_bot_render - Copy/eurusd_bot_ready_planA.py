import logging
import asyncio
import yfinance as yf
import pandas as pd
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from datetime import datetime

# ========== CONFIG ==========
TELEGRAM_BOT_TOKEN = "7912777524:AAGp7ibHEaGGFOU-XBIbKbwd6IDMqu-GtuU"
TELEGRAM_USER_ID = 7469299312
PAIRS = ["EURUSD=X", "USDCHF=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X"]
INTERVAL = "5m"
PERIOD = "2d"
# ============================

bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
logging.basicConfig(level=logging.INFO)

def fetch_data(pair):
    data = yf.download(pair, period=PERIOD, interval=INTERVAL)

    if data.empty:
        raise ValueError(f"❌ No data downloaded from Yahoo Finance for {pair}.")

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = [col[0] for col in data.columns]

    if "Close" not in data.columns:
        raise ValueError(f"❌ 'Close' column not found after flattening for {pair}.")

    close = data["Close"]
    data["EMA20"] = close.ewm(span=20, adjust=False).mean()

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss
    data["RSI"] = 100 - (100 / (1 + rs))

    data = data.tail(100)
    data.dropna(subset=["EMA20", "RSI"], inplace=True)

    return data

def generate_signal(df):
    if df.empty:
        raise ValueError("❌ No rows available after indicator calculation.")

    last = df.iloc[-1]
    entry = round(last["Close"], 5)
    tp, sl, strategy = None, None, ""

    if last["Close"] > last["EMA20"] and last["RSI"] < 30:
        strategy = "Buy"
        tp = round(entry + 0.0040, 5)
        sl = round(entry - 0.0020, 5)
    elif last["Close"] < last["EMA20"] and last["RSI"] > 70:
        strategy = "Sell"
        tp = round(entry - 0.0040, 5)
        sl = round(entry + 0.0020, 5)

    return strategy, entry, tp, sl

async def send_signal(pair):
    try:
        df = fetch_data(pair)
        strategy, entry, tp, sl = generate_signal(df)

        if strategy:
            name = pair.replace("=X", "")
            message = (
                f"📊 <b>{name} Signal</b> ({datetime.now().strftime('%Y-%m-%d %H:%M')}):\n"
                f"<b>Type:</b> {strategy}\n"
                f"<b>Entry:</b> {entry}\n"
                f"<b>Take Profit:</b> {tp}\n"
                f"<b>Stop Loss:</b> {sl}"
            )
            await bot.send_message(chat_id=TELEGRAM_USER_ID, text=message)
        else:
            logging.info(f"No valid signal for {pair} at this moment.")

    except Exception as e:
        logging.error(f"❌ Error during signal check for {pair}: {e}")

async def main_loop():
    while True:
        for pair in PAIRS:
            await send_signal(pair)
        await asyncio.sleep(300)

if __name__ == "__main__":
    asyncio.run(main_loop())
