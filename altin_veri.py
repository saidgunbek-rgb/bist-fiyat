# Analiz sayfasi icin altin ve gumus (ons, gram) gunluk mum verisi: altin.json
# Kaynaklar: Yahoo (ana) + Stooq (dogrulama). Iki kaynak kapanista tutmazsa o gun "uyusmadi" diye kayda gecer.
# Gram altin / gram gumus = ons fiyati (USD) x dolar/TL / 31,1035 (1 ons = 31,1035 gram). Kuyumcu fiyati degil, piyasa (spot) fiyatidir.
# Diger dosyalara dokunmaz. Bir kaynak hic gelmezse onceki dogrulanmis veri korunur, dosya bos kalmaz.
import json, sys, time, datetime, urllib.request, urllib.error, csv, io

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
SIMDI = datetime.datetime.utcnow()
BAS_S = (SIMDI - datetime.timedelta(days=3660)).strftime("%Y-%m-%d")
GRAM = 31.1034768

# kod: (ad, grup, birim, yahoo sembolleri (ilk calisan), stooq sembolu)
LISTE = {
    "ONS":   ("Ons altın", "altin", "$", ["XAUUSD=X", "GC=F"], "xauusd"),
    "XAG":   ("Ons gümüş", "altin", "$", ["XAGUSD=X", "SI=F"], "xagusd"),
}
KUR = (["TRY=X", "USDTRY=X"], "usdtry")


def sayi(x):
    try:
        x = float(x)
    except Exception:
        return None
    return x if x == x and x > 0 else None


def oku(url, js=True, deneme=3):
    # Hizli vazgecer: 404 gibi kalici hatada tekrar denemez; baglanti sorununda en fazla 3 kez, 15 sn zaman asimiyla dener.
    for i in range(deneme):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=15).read()
            return json.loads(r) if js else r.decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (400, 401, 403, 404) or i == deneme - 1:
                raise
            time.sleep(3)
        except Exception:
            if i == deneme - 1:
                raise
            time.sleep(3)


def yahoo(sembol):
    r = oku("https://query1.finance.yahoo.com/v8/finance/chart/%s?range=10y&interval=1d" % sembol)["chart"]["result"][0]
    off = r["meta"].get("gmtoffset", 0)
    q = r["indicators"]["quote"][0]
    out = {}
    for i, t in enumerate(r.get("timestamp") or []):
        c = sayi(q["close"][i])
        if not c:
            continue
        d = datetime.datetime.utcfromtimestamp(t + off).strftime("%Y-%m-%d")
        if d >= BAS_S:
            out[d] = [sayi(q["open"][i]) or c, sayi(q["high"][i]) or c, sayi(q["low"][i]) or c, c, (q.get("volume") or [0] * (i + 1))[i] or 0]
    return out


def stooq(sembol):
    t = oku("https://stooq.com/q/d/l/?s=%s&i=d" % sembol, js=False, deneme=1)
    out = {}
    for s in csv.DictReader(io.StringIO(t)):
        d = s.get("Date") or s.get("Data")
        c = sayi(s.get("Close") or s.get("Zamkniecie"))
        if d and c and d >= BAS_S:
            out[d] = [sayi(s.get("Open")) or c, sayi(s.get("High")) or c, sayi(s.get("Low")) or c, c, int(float(s.get("Volume") or 0))]
    return out


def al(yahoolar, stq, log):
    Y, yk = {}, None
    for s in yahoolar:
        try:
            Y = yahoo(s)
            if len(Y) > 200:
                yk = s
                break
        except Exception as e:
            log["hatalar"].append("yahoo %s: %s" % (s, e))
    try:
        S = stooq(stq)
    except Exception as e:
        S = {}
        log["hatalar"].append("stooq %s: %s" % (stq, e))
    log["kaynak"] = {"yahoo": yk, "yahoo_gun": len(Y), "stooq_gun": len(S)}
    return Y, S


def birlestir(Y, S, log, tol):
    # Ana seri Yahoo; Stooq ile son 1 yilda kapanis karsilastirilir. Yahoo hic yoksa Stooq kullanilir.
    ana, yedek = (Y, S) if Y else (S, {})
    seri, ayni, fark, yok = [], 0, [], 0
    sinir = (SIMDI - datetime.timedelta(days=370)).strftime("%Y-%m-%d")
    for d in sorted(ana):
        r = ana[d]
        if yedek and d >= sinir:
            if d in yedek:
                if abs(yedek[d][3] / r[3] - 1) <= tol:
                    ayni += 1
                else:
                    fark.append([d, round(r[3], 4), round(yedek[d][3], 4)])
            else:
                yok += 1
        seri.append([d] + [round(x, 4) for x in r[:4]] + [int(r[4] or 0)])
    log["dogrulama"] = {"son1yil_tutan": ayni, "tutmayan": len(fark), "stooqta_olmayan": yok, "ornek_tutmayan": fark[-10:]}
    return seri


def main():
    try:
        onceki = json.load(open("altin.json", encoding="utf-8")).get("stocks") or {}
    except Exception:
        onceki = {}
    stocks, kontrol = {}, {}
    for kod, (ad, grup, birim, ys, sq) in LISTE.items():
        log = {"hatalar": []}
        Y, S = al(ys, sq, log)
        # spot ile vadeli arasinda fark olabilir: altinda %1, gumuste %1,5
        seri = birlestir(Y, S, log, {"ONS": 0.01, "XAG": 0.015}.get(kod, 0.005))
        kontrol[kod] = log
        if len(seri) >= 250:
            stocks[kod] = {"ad": ad, "grup": grup, "birim": birim, "d": seri, "son": seri[-1][0]}
        elif kod in onceki:
            stocks[kod] = onceki[kod]
            log["hatalar"].append("yeni veri yetersiz, onceki veri korundu")
        print(kod, log)
    # gram altin: ayni gunun ons ve dolar/TL degerleriyle
    log = {"hatalar": []}
    KY, KS = al(KUR[0], KUR[1], log)
    kur = birlestir(KY, KS, log, 0.005)
    kontrol["USDTRY"] = log
    K = {r[0]: r for r in kur} if len(kur) > 250 else {}
    for ons, gk, gad in (("ONS", "GRAM", "Gram altın"), ("XAG", "GGUM", "Gram gümüş")):
        if ons in stocks and K:
            g = []
            for r in stocks[ons]["d"]:
                k = K.get(r[0])
                if not k:
                    continue  # o gun kur yoksa gram uydurulmaz
                g.append([r[0]] + [round(r[i] * k[i] / GRAM, 3 if ons == "XAG" else 2) for i in (1, 2, 3, 4)] + [0])
            if len(g) >= 250:
                stocks[gk] = {"ad": gad, "grup": "altin", "birim": "TL", "d": g, "son": g[-1][0]}
                stocks[ons]["kur_son"] = kur[-1][4]
                continue
        if gk in onceki:
            stocks[gk] = onceki[gk]
    if not stocks:
        print("Hic veri alinamadi; dosya degistirilmedi")
        sys.exit(1)
    sira = ["GRAM", "ONS", "GGUM", "XAG"]
    stocks = {k: stocks[k] for k in sira if k in stocks}
    json.dump({"updated": max(s["son"] for s in stocks.values()), "updatedAt": SIMDI.strftime("%Y-%m-%dT%H:%M:%SZ"),
               "stocks": stocks, "kontrol": kontrol}, open("altin.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("Tamam:", list(stocks))


if __name__ == "__main__":
    main()
