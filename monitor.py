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
    {"symbol": "CL=F", "name": "Nafta WTI"},
    {"symbol": "GC=F", "name": "Zlato"},
    {"symbol": "SI=F", "name": "Srebro"},
    {"symbol": "NG=F", "name": "Gas"},
    {"symbol": "ES=F", "name": "SP500"},
    {"symbol": "ZW=F", "name": "Psenica"},
    {"symbol": "ZC=F", "name": "Kukuruz"},
    {"symbol": "CC=F", "name": "Kakao"},
    {"symbol": "UUP", "name": "Dolar Index ETF"},
    {"symbol": "BTC=F", "name": "Bitcoin"},
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
        for i in range(len(result["timestamp"])):
            c = quotes["close"][i]
            v = quotes["volume"][i]
            if c and v:
                closes.append({"c": c, "v": v})
        if len(closes) < 5:
            return None
        last = closes[-1]
        prev = closes[-2]
        vols = [d["v"] for d in closes[:-1]][-9:]
        avg_vol = sum(vols) / len(vols)
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
            return "CEKAJ - API kljuc nije postavljen."
        price = data["price"]
        prev = data["prev_close"]
        change_pct = ((price - prev) / prev * 100) if prev else 0
        vol_ratio = data["vol_ratio"]
        currency = data["currency"]
        name = market["name"]
        symbol = market["symbol"]
        prompt = "Ekspert za futures. Kratka analiza na srpskom, max 3 linije.\n"
        prompt += "Instrument: " + name + " (" + symbol + ")\n"
        prompt += "Cena: " + str(round(price, 2)) + " " + currency + "\n"
        prompt += "Promena: " + str(round(change_pct, 2)) + "%\n"
        prompt += "Volume: " + str(round(vol_ratio, 1)) + "x iznad proseka\n\n"
        prompt += "Format odgovora (tacno ovako, kratko):\n"
        prompt += "ANALIZA: [max 10 reci]\n"
        prompt += "AKCIJA: KUPI/PRODAJ/CEKAJ - [max 8 reci]\n"
        prompt += "RIZIK: VISOK/SREDNJI/NIZAK"
        payload = {
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 150,
            "messages": [{"role": "user", "content": prompt}]
        }
        hdrs = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01"
        }
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=hdrs,
            json=payload,
            timeout=15
        )
        result = response.json()
        logging.info("AI keys: " + str(list(result.keys())))
        if "content" in result:
            return result["content"][0]["text"].strip()
        elif "error" in result:
            msg = result["error"].get("message", "nepoznata greska")
            logging.error("AI greska: " + msg)
            return "CEKAJ - AI privremeno nedostupan."
        else:
            return "CEKAJ - Neoceкivan odgovor."
    except Exception as e:
        logging.error("AI greska: " + str(e))
        return "CEKAJ - Greska."


def send_whatsapp(message):
    try:
        encoded = requests.utils.quote(message)
        wa_url = "https://api.callmebot.com/whatsapp.php"
        wa_url += "?phone=" + WHATSAPP_PHONE
        wa_url += "&text=" + encoded
        wa_url += "&apikey=" + WHATSAPP_API_KEY
        r = requests.get(wa_url, timeout=10)
        logging.info("WhatsApp: " + str(r.status_code))
        return True
    except Exception as e:
        logging.error("WhatsApp greska: " + str(e))
        return False


def check_markets():
    logging.info("=== Provera trzista ===")
    today = datetime.now().strftime("%Y-%m-%d")
    for market in MARKETS:
        symbol = market["symbol"]
        name = market["name"]
        data = fetch_quote(symbol)
        if not data:
            logging.warning("Nema podataka za " + name)
            continue
        vol_ratio = data["vol_ratio"]
        price = data["price"]
        prev = data["prev_close"]
        change_pct = ((price - prev) / prev * 100) if prev else 0
        logging.info(name + ": " + str(round(price, 2)) + " vol:" + str(round(vol_ratio, 2)) + "x")
        if vol_ratio >= SPIKE_THRESHOLD:
            key = symbol + "_" + today
            if key not in alerts_sent:
                alerts_sent[key] = True
                logging.info("AI analiza za " + name + "...")
                ai = get_ai_analysis(market, data)
                time.sleep(15)
                msg = name + " SPIKE " + str(round(vol_ratio, 1)) + "x\n"
                msg += "Cena: " + str(round(price, 2)) + " " + data["currency"] + "\n"
                msg += "Promena: " + str(round(change_pct, 2)) + "%\n"
                msg += datetime.now().strftime("%H:%M %d.%m.%Y") + "\n"
                msg += "---\n"
                msg += ai + "\n"
                msg += "---\nFuturesScout"
                logging.info("Saljem WhatsApp za " + name + "... Duzina: " + str(len(msg)))
                send_whatsapp(msg)
        time.sleep(1)


def main():
    logging.info("FuturesScout startovan")
    send_whatsapp("FuturesScout aktivan! Pratim 10 trzista 24/7.")
    while True:
        try:
            check_markets()
        except Exception as e:
            logging.error("Greska: " + str(e))
        logging.info("Sledeca provera za 30 minuta...")
        time.sleep(30 * 60)


if __name__ == "__main__":
    main()
