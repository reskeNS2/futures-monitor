import requests
import time
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# ============================================================
# KONFIGURACIJA
# ============================================================
WHATSAPP_PHONE = "381603339783"
WHATSAPP_API_KEY = "8286403"

SPIKE_THRESHOLD = 2.0  # koliko puta iznad proseka = alarm

MARKETS = [
    {"symbol": "CL=F",  "name": "Nafta WTI",     "emoji": "🛢️"},
    {"symbol": "GC=F",  "name": "Zlato",           "emoji": "🥇"},
    {"symbol": "SI=F",  "name": "Srebro",           "emoji": "🥈"},
    {"symbol": "NG=F",  "name": "Gas (Prirodni)",   "emoji": "🔥"},
    {"symbol": "ES=F",  "name": "S&P 500",          "emoji": "📈"},
    {"symbol": "ZW=F",  "name": "Pšenica",          "emoji": "🌾"},
    {"symbol": "ZC=F",  "name": "Kukuruz",          "emoji": "🌽"},
    {"symbol": "CC=F",  "name": "Kakao",            "emoji": "🍫"},
    {"symbol": "BTC=F", "name": "Bitcoin",          "emoji": "₿"},
]

# Pamti koje alarme smo već poslali danas
alerts_sent = {}

# ============================================================
# YAHOO FINANCE
# ============================================================
def fetch_quote(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=20d"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        result = data["chart"]["result"][0]
        meta = result["meta"]
        quotes = result["indicators"]["quote"][0]

        closes = [
            {"c": quotes["close"][i], "v": quotes["volume"][i]}
            for i, t in enumerate(result["timestamp"])
            if quotes["close"][i] and quotes["volume"][i]
        ]

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
        logging.warning(f"Greška za {symbol}: {e}")
        return None

# ============================================================
# WHATSAPP
# ============================================================
def send_whatsapp(message):
    try:
        url = (
            f"https://api.callmebot.com/whatsapp.php"
            f"?phone={WHATSAPP_PHONE}"
            f"&text={requests.utils.quote(message)}"
            f"&apikey={WHATSAPP_API_KEY}"
        )
        r = requests.get(url, timeout=10)
        logging.info(f"WhatsApp poslat: {r.status_code}")
        return True
    except Exception as e:
        logging.error(f"WhatsApp greška: {e}")
        return False

# ============================================================
# GLAVNI LOOP
# ============================================================
def check_markets():
    logging.info("=== Provera tržišta ===")
    today = datetime.now().strftime("%Y-%m-%d")

    for market in MARKETS:
        symbol = market["symbol"]
        name = market["name"]
        emoji = market["emoji"]

        data = fetch_quote(symbol)
        if not data:
            logging.warning(f"Nema podataka za {name}")
            continue

        vol_ratio = data["vol_ratio"]
        price = data["price"]
        change_pct = ((price - data["prev_close"]) / data["prev_close"] * 100) if data["prev_close"] else 0

        logging.info(
            f"{emoji} {name}: {price:.2f} {data['currency']} | "
            f"Promena: {change_pct:+.2f}% | Vol ratio: {vol_ratio:.2f}x"
        )

        # Provjeri spike
        if vol_ratio >= SPIKE_THRESHOLD:
            alert_key = f"{symbol}_{today}"
            if alert_key not in alerts_sent:
                alerts_sent[alert_key] = True
                msg = (
                    f"🔺 VOLUME SPIKE DETEKTOVAN!\n\n"
                    f"{emoji} {name} ({symbol})\n"
                    f"📊 Vol ratio: {vol_ratio:.1f}x iznad proseka\n"
                    f"💰 Cena: {price:.2f} {data['currency']}\n"
                    f"📈 Promena: {change_pct:+.2f}%\n"
                    f"🕐 Vreme: {datetime.now().strftime('%H:%M %d.%m.%Y')}\n\n"
                    f"⚡ FuturesScout Monitor"
                )
                logging.info(f"🔺 SPIKE! Šaljem WhatsApp za {name}...")
                send_whatsapp(msg)

        time.sleep(1)  # pauza između zahteva


def main():
    logging.info("🚀 FuturesScout Monitor startovan")
    send_whatsapp("✅ FuturesScout Monitor je aktivan! Pratim 9 tržišta 24/7.")

    while True:
        try:
            check_markets()
        except Exception as e:
            logging.error(f"Greška u loop-u: {e}")

        # Čekaj 30 minuta do sledeće provere
        logging.info("⏳ Sledeća provera za 30 minuta...")
        time.sleep(30 * 60)


if __name__ == "__main__":
    main()
