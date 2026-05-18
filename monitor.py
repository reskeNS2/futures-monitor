import requests
import time
import logging
import os
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

WHATSAPP_PHONE = "381603339783"
WHATSAPP_API_KEY = "8286403"
SPIKE_THRESHOLD = 0.1

MARKETS = [
    {"symbol": "CL=F", "name": "Nafta WTI", "emoji": "Nafta"},
    {"symbol": "GC=F", "name": "Zlato", "emoji": "Zlato"},
    {"symbol": "SI=F", "name": "Srebro", "emoji": "Srebro"},
    {"symbol": "NG=F", "name": "Gas", "emoji": "Gas"},
    {"symbol": "ES=F", "name": "S&P 500", "emoji": "SP500"},
    {"symbol": "ZW=F", "name": "Psenica", "emoji": "Psenica"},
    {"symbol": "ZC=F", "name": "Kukuruz", "emoji": "Kukuruz"},
    {"symbol": "CC=F", "name": "Kakao", "emoji": "Kakao"},
    {"symbol": "DX-Y.NYB", "name": "Dolar Index", "emoji": "Dolar"},
    {"symbol": "BTC=F", "name": "Bitcoin", "emoji": "Bitcoin"},
]

alerts_sent = {}


def fetch_quote(symbol):
    url = "https://query1.finance.yahoo.com/v8/finance/chart/" + symbol + "?interval=1d&range=20d"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        result = data["chart"]["result"][0]
        meta = result["meta"]
        quotes = result["indicators"]["quote"][0]
        closes = []
        for i, t in enumerate(result["timestamp"]):
            if quotes["close"][i] and quotes["volume"][i]:
                closes.append({"c": quotes["close"][i], "v": quotes["volume"][i]})
        if len(closes) < 5:
            return None
        last = closes[-1]
        prev = closes[-2]
        volumes = [d["v"] for d in closes[:-1]]
        avg_vol = sum(volumes[-9:]) / len(volumes[-9:])
        return {
            "symbol": symbol,
            "price": meta.get("regularMarketPrice", last["c"]),
            "prev_close": meta.get("chartPreviousClose", prev["c"]),
            "volume": last["v"],
            "avg_volume": avg_vol,
            "vol_ratio": last["v"] / avg_vol if avg_vol > 0 else 0,
            "currency": meta.get("currency", "USD"),
        }
    except Exception as e:
        logging.warning("Greska za " + symbol + ": " + str(e))
        return None


def get_ai_analysis(market, data):
    try:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return "ANALIZA: API kljuc nije postavljen.\nAKCIJA: CEKAJ\nRIZIK: VISOK"
        price = data["price"]
        change_pct = ((price - data["prev_close"]) / data["prev_close"] * 100) if data["prev_close"] else 0
        vol_ratio = data["vol_ratio"]
        prompt = "Ti si ekspert za futures trzista. Analiziraj signal i daj savet na srpskom.\n"
        prompt += "Instrument: " + market["name"] + " (" + market["symbol"] + ")\n"
        prompt += "Cena: " + str(round(price, 2)) + " " + data["currency"] + "\n"
        prompt += "Promena: " + str(round(change_pct, 2)) + "%\n"
        prompt += "Volume ratio: " + str(round(vol_ratio, 1)) + "x iznad proseka\n\n"
        prompt += "Odgovori TACNO ovako:\n"
        prompt += "ANALIZA: [sta se desava]\n"
        prompt += "AKCIJA: [KUPI/PRODAJ/CEKAJ] - [obrazlozenje]\n"
        prompt += "RIZIK: [VISOK/SREDNJI/NIZAK] - [upozorenje]\n"
        prompt += "Ovo je edukativna simulacija."
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01"
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 300,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=15
        )
        result = response.json()
        logging.info("AI response keys: " + str(list(result.keys())))
        if "content" in result:
            return result["content"][0]["text"].strip()
        elif "error" in result:
            err_msg = result["error"].get("message", "nepoznata greska")
            logging.error("AI API greska: " + err_msg)
            return "ANALIZA: API greska.\nAKCIJA: CEKAJ\nRIZIK: VISOK"
        else:
            return "ANALIZA: Neoceкivan odgovor.\nAKCIJA: CEKAJ\nRIZIK: VISOK"
    except Exception as e:
        logging.error("AI greska: " + str(e))
        return "ANALIZA: Greska: " + str(e) + "\nAKCIJA: CEKAJ\nRIZIK: VISOK"


def send_whatsapp(message):
    try:
        url = "https://api.callmebot.com/whatsapp.php?phone=" + WHATSAPP_PHONE + "&text=" + requests.utils.quote(message) + "&apikey=" + WHATSAPP_
