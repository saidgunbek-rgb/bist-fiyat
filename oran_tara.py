# Altin/Gumus orani icin saatlik ve 15 dakikalik veri (Yahoo: GC=F altin vadeli, SI=F gumus vadeli). Sonuc: oran.json
import json, urllib.request, datetime, sys
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
def yahoo(sym, interval, rng):
    u = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval={interval}&range={rng}"
    r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60)
    res = json.loads(r.read().decode())["chart"]["result"][0]
    q = res["indicators"]["quote"][0]; out = {}
    for i, t in enumerate(res["timestamp"]):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if None in (o, h, l, c) or min(o, h, l, c) <= 0: continue
        out[t] = (o, h, l, c)
    return out
def oran(interval, rng):
    G, S = yahoo("GC=F", interval, rng), yahoo("SI=F", interval, rng)
    bars = []
    for t in sorted(set(G) & set(S)):
        go, gh, gl, gc = G[t]; so, sh, sl, sc = S[t]
        o, c = go / so, gc / sc
        # Fitil: iki enstrumanin ayni baradaki en uc degerlerinden oranin MUMKUN en genis araligi degil, sadece
        # acilis-kapanis arasi kullanilir; fitil ust-donem birlestirmesinde (saatlik/4 saatlik/gunluk) olusur.
        bars.append([t, round(o, 3), round(max(o, c), 3), round(min(o, c), 3), round(c, 3)])
    return bars
sonuc = {"kaynak": "Yahoo Finance GC=F / SI=F (vadeli islem, spot'a cok yakin)", "guncelleme": datetime.datetime.utcnow().isoformat() + "Z"}
for ad, iv, rg in (("g15", "15m", "60d"), ("g60", "60m", "730d")):
    try:
        sonuc[ad] = oran(iv, rg)
    except Exception as e:
        print("HATA", ad, e); sonuc[ad] = None
if not sonuc.get("g15") and not sonuc.get("g60"):
    sys.exit("veri alinamadi")
json.dump(sonuc, open("oran.json", "w"), separators=(",", ":"))
print({k: (len(v) if isinstance(v, list) else v) for k, v in sonuc.items()})
