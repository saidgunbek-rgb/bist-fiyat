# XAU/XAG orani icin saatlik/gunluk OHLC kaynak testi. Sonuc: oran-test.json
import json, urllib.request, datetime
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
def yahoo(sym, interval, rng):
    u = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval={interval}&range={rng}"
    r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40)
    j = json.loads(r.read().decode())
    res = j["chart"]["result"][0]; q = res["indicators"]["quote"][0]; t = res["timestamp"]
    n = sum(1 for i in range(len(t)) if None not in (q["open"][i], q["high"][i], q["low"][i], q["close"][i]))
    f = lambda x: datetime.datetime.utcfromtimestamp(x).isoformat()
    return {"adet": len(t), "tam_ohlc": n, "ilk": f(t[0]), "son": f(t[-1]),
            "son_bar": [q["open"][-1], q["high"][-1], q["low"][-1], q["close"][-1]]}
def stooq(sym):
    u = f"https://stooq.com/q/d/l/?s={sym}&i=d"
    s = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40).read().decode()
    sat = s.strip().splitlines()
    return {"satir": len(sat), "ilk": sat[:2], "son": sat[-2:]}
deneme = [("yahoo", "XAUXAG=X", "60m", "1mo"), ("yahoo", "XAUXAG=X", "1d", "1mo"),
          ("yahoo", "XAUUSD=X", "60m", "1mo"), ("yahoo", "XAGUSD=X", "60m", "1mo"),
          ("yahoo", "GC=F", "60m", "1mo"), ("yahoo", "SI=F", "60m", "1mo"),
          ("stooq", "xauxag"), ("stooq", "xauusd"), ("stooq", "xagusd")]
out = {"tarih": datetime.datetime.utcnow().isoformat() + "Z", "sonuclar": {}}
for d in deneme:
    ad = "|".join(d[1:])
    try:
        out["sonuclar"][ad] = yahoo(*d[1:]) if d[0] == "yahoo" else stooq(d[1])
    except Exception as e:
        out["sonuclar"][ad] = {"hata": str(e)[:200]}
json.dump(out, open("oran-test.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1)[:3000])
