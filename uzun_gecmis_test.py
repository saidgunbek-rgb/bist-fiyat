# TUM ZAMANLAR fiyat gecmisi testi: hangi kaynak ne kadar geriye gidiyor, eski veri tutarli mi? Panele yazmaz.
import json, datetime, urllib.request, time
UA = {"User-Agent": "Mozilla/5.0"}
OUT = {"tarih": datetime.date.today().isoformat(), "kaynaklar": {}, "notlar": []}

def get(url):
    for i in range(4):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40))
        except Exception as e:
            if i == 3: raise
            time.sleep(3 * (i + 1))

def yahoo_max(sembol):
    r = get("https://query1.finance.yahoo.com/v8/finance/chart/%s?range=max&interval=1d&events=div%%7Csplit" % sembol)["chart"]["result"][0]
    off = r["meta"].get("gmtoffset", 0); q = r["indicators"]["quote"][0]; out = {}
    for i, t in enumerate(r.get("timestamp") or []):
        c = q["close"][i]
        if c: out[datetime.datetime.utcfromtimestamp(t + off).strftime("%Y-%m-%d")] = float(c)
    ev = r.get("events", {})
    return out, sorted(ev.get("splits", {}).keys()), r["meta"].get("firstTradeDate")

def ozet(seri):
    g = sorted(seri); 
    if not g: return {"gun": 0}
    sic = []
    for a, b in zip(g, g[1:]):
        r = seri[b] / seri[a] - 1
        if abs(r) > 0.25: sic.append([b, round(r * 100, 1)])
    return {"ilk": g[0], "son": g[-1], "gun": len(g), "gunluk_%25_ustu_sicrama": sic[:12], "sicrama_sayisi": len(sic)}

try:
    A = json.load(open("analiz.json", encoding="utf-8"))["stocks"]
except Exception as e:
    A = {}; OUT["notlar"].append("analiz.json: %r" % e)

def karsilastir(seri, d10):
    # panelin temiz 10 yillik verisiyle ayni gunlerdeki kapanis orani
    oran = [seri[x[0]] / x[4] for x in d10 if x[0] in seri and x[4]]
    if not oran: return None
    oran.sort()
    return {"ortak_gun": len(oran), "oran_medyan": round(oran[len(oran) // 2], 4), "oran_min": round(oran[0], 4), "oran_max": round(oran[-1], 4)}

for k in list(A.keys()):
    r = {}
    try:
        s, spl, ft = yahoo_max(k + ".IS")
        r["yahoo"] = ozet(s); r["yahoo"]["bolunme"] = spl[:20]; r["yahoo"]["karsilastirma_10y"] = karsilastir(s, A[k]["d"])
    except Exception as e:
        r["yahoo"] = "hata %r" % e
    try:
        import borsapy as bp
        df = bp.Ticker(k).history(period="max")
        s = {str(i)[:10]: float(row["Close"]) for i, row in df.iterrows() if row.get("Close")}
        r["borsapy"] = ozet(s); r["borsapy"]["karsilastirma_10y"] = karsilastir(s, A[k]["d"])
    except Exception as e:
        r["borsapy"] = "hata %r" % e
    OUT["kaynaklar"][k] = r
    time.sleep(1)

for ad, sem in (("ons_altin_vadeli", "GC=F"), ("ons_gumus_vadeli", "SI=F"), ("ons_altin_spot", "XAUUSD=X"), ("ons_gumus_spot", "XAGUSD=X"), ("usdtry", "TRY=X")):
    try:
        s, spl, ft = yahoo_max(sem); OUT["kaynaklar"][ad] = ozet(s)
    except Exception as e:
        OUT["kaynaklar"][ad] = "hata %r" % e
json.dump(OUT, open("uzun-gecmis-test.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("bitti")
