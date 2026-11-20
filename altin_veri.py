# Analiz sayfasi icin altin ve gumus (ons, gram) gunluk mum verisi: altin.json
# Kaynaklar: Yahoo (ana) + bagimsiz yedek: altin icin PAXG (Kraken, Coinbase), gumus icin SLV ETF (Yahoo), dolar/TL icin Avrupa Merkez Bankasi kuru (Frankfurter).
# Iki kaynak kapanista tutmazsa o gun "uyusmadi" diye kayda gecer. Anlik spot (gold-api) son gunle karsilastirilir. Yahoo hic gelmezse onceki veri korunur, yeni gunler yedekten eklenir.
# Gram altin / gram gumus = ons fiyati (USD) x dolar/TL / 31,1035 (1 ons = 31,1035 gram). Kuyumcu fiyati degil, piyasa (spot) fiyatidir.
# Diger dosyalara dokunmaz. Bir kaynak hic gelmezse onceki dogrulanmis veri korunur, dosya bos kalmaz.
import json, sys, time, datetime, urllib.request, urllib.error, csv, io

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
SIMDI = datetime.datetime.utcnow()
BAS_S = (SIMDI - datetime.timedelta(days=3660)).strftime("%Y-%m-%d")
GRAM = 31.1034768

# kod: (ad, grup, birim, yahoo sembolleri (ilk calisan), yedek kaynak adi)
LISTE = {
    "ONS":   ("Ons altın", "altin", "$", ["XAUUSD=X", "GC=F"], "paxg"),
    "XAG":   ("Ons gümüş", "altin", "$", ["XAGUSD=X", "SI=F"], "slv"),
}
KUR = (["TRY=X", "USDTRY=X"], "ecb")
SPOT = {"ONS": "XAU", "XAG": "XAG"}
TOL = {"ONS": 0.01, "XAG": 0.015, "USDTRY": 0.01}  # gunluk aralik disinda kalma payi: altinda %1, gumusde %1,5, kurda %1


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


def mum(d, o, h, l, c):
    c, o, h, l = sayi(c), sayi(o), sayi(h), sayi(l)
    return [d, o or c, h or c, l or c, c] if c else None


def paxg():
    # 1 ons altina bagli token: Kraken (~2 yil gunluk), olmazsa Coinbase (~300 gun). Seviye olarak ons altinla kiyaslanir.
    out = {}
    try:
        r = oku("https://api.kraken.com/0/public/OHLC?pair=PAXGUSD&interval=1440", deneme=2)["result"]
        for row in r[[k for k in r if k != "last"][0]]:
            d = datetime.datetime.utcfromtimestamp(row[0]).strftime("%Y-%m-%d")
            m = mum(d, row[1], row[2], row[3], row[4])
            if m:
                out[d] = m[1:] + [0]
    except Exception:
        out = {}
    if len(out) < 100:
        r = oku("https://api.exchange.coinbase.com/products/PAXG-USD/candles?granularity=86400", deneme=2)
        for row in r:  # [zaman, dusuk, yuksek, acilis, kapanis, hacim]
            d = datetime.datetime.utcfromtimestamp(row[0]).strftime("%Y-%m-%d")
            m = mum(d, row[3], row[2], row[1], row[4])
            if m:
                out[d] = m[1:] + [0]
    return out


def slv(ana):
    # Gumus ETF'i: seviyesi ons gumusten farkli oldugu icin son 90 ortak gunun ortanca orani ile olceklenir.
    E = yahoo("SLV")
    ort = sorted(ana[d][3] / E[d][3] for d in sorted(set(ana) & set(E))[-90:])
    if len(ort) < 30:
        raise Exception("SLV ile ortak gun az")
    k = ort[len(ort) // 2]
    return {d: [round(x * k, 4) for x in E[d][:4]] + [0] for d in E}


def ecb():
    # Avrupa Merkez Bankasi referans kuru (Frankfurter): gunde tek deger.
    for u in ("https://api.frankfurter.dev/v1/%s..?base=USD&symbols=TRY", "https://api.frankfurter.app/%s..?from=USD&to=TRY"):
        try:
            r = oku(u % BAS_S, deneme=2)["rates"]
            return {d: [v["TRY"]] * 4 + [0] for d, v in r.items() if v.get("TRY")}
        except Exception:
            continue
    raise Exception("frankfurter ulasilamadi")


def spot(kod):
    # Anlik altin/gumus fiyati (gold-api); yalniz son gunun makul olup olmadigina bakmak icin.
    return sayi(oku("https://api.gold-api.com/price/%s" % kod, deneme=2).get("price"))


def al(yahoolar, yedek, log):
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
        S = {"paxg": paxg, "ecb": ecb}[yedek]() if yedek in ("paxg", "ecb") else slv(Y)
    except Exception as e:
        S = {}
        log["hatalar"].append("yedek %s: %s" % (yedek, e))
    log["kaynak"] = {"yahoo": yk, "yahoo_gun": len(Y), "yedek": yedek, "yedek_gun": len(S)}
    return Y, S


def birlestir(Y, S, log, tol):
    # Ana seri Yahoo; yedek kaynakla son 1 yilda kapanis karsilastirilir (tutmayan gunler kayda gecer, veriyi degistirmez). Yahoo hic yoksa yedek kullanilir.
    ana, yedek = (Y, S) if Y else (S, {})
    seri, ayni, fark, yok = [], 0, [], 0
    sinir = (SIMDI - datetime.timedelta(days=370)).strftime("%Y-%m-%d")
    for d in sorted(ana):
        r = ana[d]
        if yedek and d >= sinir:
            if d in yedek:
                # Iki kaynagin kapanis saati farkli (vadeli ~19:30 TR, token gunu 03:00 TR'de kapanir, ETF 18:00 TR'de):
                # Yahoo kapanisi, yedegin O GUNKU dusuk-yuksek araliginin (tolerans payiyla) icinde mi diye bakilir.
                alt, ust = min(yedek[d][:4]), max(yedek[d][:4])
                if alt * (1 - tol) <= r[3] <= ust * (1 + tol):
                    ayni += 1
                else:
                    fark.append([d, round(r[3], 4), round(alt, 4), round(ust, 4)])
            else:
                yok += 1
        seri.append([d] + [round(x, 4) for x in r[:4]] + [int(r[4] or 0)])
    log["dogrulama"] = {"son1yil_tutan": ayni, "tutmayan": len(fark), "yedekte_olmayan": yok, "ornek_tutmayan": fark[-10:]}
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
        if not Y and kod in onceki and S:
            # Yahoo yok: onceki dogrulanmis seri korunur, yalniz ondan yeni gunler yedekten eklenir
            seri = list(onceki[kod]["d"])
            son = seri[-1][0]
            yeni_g = [[d] + [round(x, 4) for x in S[d][:4]] + [0] for d in sorted(S) if d > son]
            seri += yeni_g
            log["hatalar"].append("yahoo yok: onceki veri korundu, %d yeni gun yedekten eklendi" % len(yeni_g))
        else:
            seri = birlestir(Y, S, log, TOL[kod])
        # anlik spot ile son gunun uyumu
        try:
            sp = spot(SPOT[kod])
            if sp and seri:
                log["anlik_spot"] = {"spot": round(sp, 3), "son_kapanis": seri[-1][4], "fark_yuzde": round((seri[-1][4] / sp - 1) * 100, 2)}
                if abs(seri[-1][4] / sp - 1) > 0.03:
                    log["hatalar"].append("son gun anlik spot ile %%3'ten fazla ayrisiyor: %s" % log["anlik_spot"])
        except Exception as e:
            log["hatalar"].append("anlik spot alinamadi: %s" % e)
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
    kur = birlestir(KY, KS, log, TOL["USDTRY"])
    kontrol["USDTRY"] = log
    K = {r[0]: r for r in kur} if len(kur) > 250 else {}
    for ons, gk, gad in (("ONS", "GRAM", "Gram altın"), ("XAG", "GGUM", "Gram gümüş")):
        if ons in stocks and K:
            g = []
            for r in stocks[ons]["d"]:
                k = K.get(r[0])
                if not k:
                    continue  # o gun kur yoksa gram uydurulmaz
                o_, h_, l_, c_ = [r[i] * k[i] / GRAM for i in (1, 2, 3, 4)]
                # ons ve kur mumlari ayni anda tepe/dip yapmaz; carpimdan cikan yuksek/dusuk, acilis ve kapanisin disina tasmasin
                h_, l_ = max(o_, h_, l_, c_), min(o_, h_, l_, c_)
                g.append([r[0]] + [round(x, 3 if ons == "XAG" else 2) for x in (o_, h_, l_, c_)] + [0])
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
