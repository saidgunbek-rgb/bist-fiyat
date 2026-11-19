# Analiz sayfasi icin gunluk mum verisi (analiz.yml calistirir). Ciktisi: analiz.json
# Kural: bir gunun KAPANISI en az iki kaynakta (Yahoo, borsapy, Is Yatirim) ayni degilse o gun seriye alinmaz.
# Mumun acilis/en yuksek/en dusuk/hacim degerleri, kapanisi dogrulanan kaynaktan alinir; en yuksek/en dusuk ikinci
# kaynakla da karsilastirilir ve tutarsiz mum kaydedilir (kontrol icin), uydurma deger yazilmaz.
import json, os, re, sys, time, datetime, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
SIMDI = datetime.datetime.now(datetime.timezone.utc)
BUGUN = (SIMDI + datetime.timedelta(hours=3)).date()
BAS = BUGUN - datetime.timedelta(days=1830)  # 5 yil
BAS_S = BAS.isoformat()
EN_AZ_GUN = 120
_TR = SIMDI + datetime.timedelta(hours=3)
# Seans acikken (ya da kapanis kesinlesmeden) bugunun yarim mumu alinmaz
SON_GUN = BUGUN.isoformat() if (_TR.hour, _TR.minute) >= (18, 15) or _TR.weekday() >= 5 else (BUGUN - datetime.timedelta(days=1)).isoformat()


def hisse_listesi():
    """fiyat.yml HISSELER (portfoy) + kutuphane.yml KUTUPHANE. Ad bilgisi kutuphaneden."""
    kodlar, adlar = [], {}
    try:
        m = re.search(r'HISSELER:\s*"([^"]*)"', open(".github/workflows/fiyat.yml", encoding="utf-8").read())
        for k in (m.group(1) if m else "").split(","):
            k = k.strip().upper()
            if k and k not in kodlar:
                kodlar.append(k)
    except Exception as e:
        print("fiyat.yml okunamadi:", e)
    try:
        m = re.search(r'KUTUPHANE:\s*"([^"]*)"', open(".github/workflows/kutuphane.yml", encoding="utf-8").read())
        for oge in (m.group(1) if m else "").split(","):
            p = [x.strip() for x in oge.split("=")]
            if p and p[0]:
                k = p[0].upper()
                if len(p) > 1:
                    adlar[k] = p[1]
                if k not in kodlar:
                    kodlar.append(k)
    except Exception as e:
        print("kutuphane.yml okunamadi:", e)
    return kodlar, adlar


def sayi(x):
    try:
        x = float(x)
    except Exception:
        return None
    return x if x == x and x > 0 else None


def get(url):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40))


def yahoo(kod):
    u = "https://query1.finance.yahoo.com/v8/finance/chart/%s.IS?range=5y&interval=1d" % kod
    r = get(u)["chart"]["result"][0]
    off = r["meta"].get("gmtoffset", 10800)
    q = r["indicators"]["quote"][0]
    out = {}
    for i, t in enumerate(r.get("timestamp") or []):
        c = sayi(q["close"][i])
        if not c:
            continue
        d = datetime.datetime.utcfromtimestamp(t + off).strftime("%Y-%m-%d")
        if BAS_S <= d <= SON_GUN:
            out[d] = {"o": sayi(q["open"][i]), "h": sayi(q["high"][i]), "l": sayi(q["low"][i]), "c": round(c, 2),
                      "v": (q.get("volume") or [None] * (i + 1))[i]}
    return out


def borsapy_gecmis(kod):
    import borsapy as bp
    df = bp.Ticker(kod).history(period="5y")
    out = {}
    for idx, row in df.iterrows():
        c = sayi(row.get("Close"))
        d = str(idx)[:10]
        if c and BAS_S <= d <= SON_GUN:
            out[d] = {"o": sayi(row.get("Open")), "h": sayi(row.get("High")), "l": sayi(row.get("Low")), "c": round(c, 2),
                      "v": sayi(row.get("Volume"))}
    return out


def isyatirim(kod):
    out, d = {}, BAS
    while d <= BUGUN:
        e = min(d + datetime.timedelta(days=90), BUGUN)
        u = ("https://www.isyatirim.com.tr/_layouts/15/IsYatirim.Website/Common/Data.aspx/HisseTekil"
             "?hisse=%s&startdate=%s&enddate=%s") % (kod, d.strftime("%d-%m-%Y"), e.strftime("%d-%m-%Y"))
        for x in (get(u).get("value") or []):
            try:
                t = datetime.datetime.strptime(x["HGDG_TARIH"], "%d-%m-%Y").strftime("%Y-%m-%d")
            except Exception:
                continue
            c = sayi(x.get("HGDG_KAPANIS"))
            if c:
                out[t] = {"c": round(c, 2), "h": sayi(x.get("HGDG_MAX")), "l": sayi(x.get("HGDG_MIN"))}
        d = e + datetime.timedelta(days=1)
        time.sleep(1)
    return out


def esit(a, b, tol=0.002):
    return a is not None and b is not None and abs(a - b) <= max(0.011, tol * max(a, b))


def mum_tamam(m):
    return m and all(m.get(k) for k in ("o", "h", "l", "c")) and m["l"] <= min(m["o"], m["c"]) + 0.011 \
        and m["h"] >= max(m["o"], m["c"]) - 0.011


def birlestir(K):
    """K: {kaynak: {tarih: mum}} -> (seri, sayac, kayitlar). Seri: [[tarih, a, y, d, k, hacim], ...]

    1. adim: kapanisi en az iki kaynakta ayni olan gunler dogrudan alinir.
    2. adim (cozumleme): kaynaklarin tutmadigi gunlerde dogru deger analizle bulunur.
       Is Yatirim fiyatlari temettu/bedelsiz icin duzeltilmistir; duzeltme carpani iki duzeltme arasinda sabittir.
       Carpan, o gunun cevresindeki dogrulanmis gunlerden (Is Yatirim / dogrulanmis kapanis) hesaplanir ve Is Yatirim
       kapanisi bu carpanla gercek (duzeltilmemis) fiyata cevrilir. Yahoo ya da borsapy'den hangisi bu degerle
       %0,4 icinde tutuyorsa o gunun mumu ondan alinir. Boylece gun atlanmaz, uydurma deger de yazilmaz.
       Sadece tek kaynakta gorunen gun (ornegin borsanin kapali oldugu gun: 8 Subat 2023) islem gormemis sayilir."""
    kayit = []
    say = {"iki_kaynak": 0, "cozulen": 0, "islem_yok": 0, "atlanan": 0, "hl_farkli": 0}
    tarihler = sorted(set(K.get("yahoo", {})) | set(K.get("borsapy", {})) | set(K.get("isyatirim", {})))
    # 5 yillik pencere, kaynaklarin hepsinin veri verdigi ilk gunden baslar (pencere basinda tek kaynakli gun kalmasin)
    ilkler = [min(K[s]) for s in ("yahoo", "borsapy") if K.get(s)]
    if len(ilkler) == 2:
        tarihler = [d for d in tarihler if d >= max(ilkler)]
    kabul, bekleyen = {}, []

    def mum_al(d, m, kaynaklar):
        for s in ("yahoo", "borsapy"):
            if s in kaynaklar and mum_tamam(m.get(s)):
                x = dict(m[s]); x["kaynak"] = s
                return x
        return None

    def kaydet(d, mum, kap, destek):
        for s in destek:
            if s == mum["kaynak"]:
                continue
            o = m_[d][s]
            if o.get("h") and o.get("l") and not (esit(o["h"], mum["h"], 0.005) and esit(o["l"], mum["l"], 0.005)):
                say["hl_farkli"] += 1
                kayit.append({"tarih": d, "neden": "en yuksek/en dusuk %s ile farkli" % s,
                              mum["kaynak"]: [mum["h"], mum["l"]], s: [o["h"], o["l"]]})
            break
        c = mum["c"]
        v = mum.get("v")
        kabul[d] = [d, round(mum["o"], 2), round(max(mum["h"], mum["o"], c), 2), round(min(mum["l"], mum["o"], c), 2),
                    c, int(v) if v else 0]

    m_ = {}
    for d in tarihler:
        m = {s: K[s][d] for s in K if d in K[s]}
        m_[d] = m
        kap = {s: v["c"] for s, v in m.items()}
        destek = []
        for s, v in kap.items():
            uyan = [x for x, w in kap.items() if esit(v, w)]
            if len(uyan) > len(destek):
                destek = uyan
        mum = mum_al(d, m, destek) if len(destek) >= 2 else None
        if mum:
            kaydet(d, mum, kap, destek)
            say["iki_kaynak"] += 1
        else:
            bekleyen.append(d)

    # 2. adim: cozumleme
    sira = {d: i for i, d in enumerate(tarihler)}
    oran = [(sira[d], K["isyatirim"][d]["c"] / kabul[d][4]) for d in kabul if d in K.get("isyatirim", {})]
    for d in bekleyen:
        m = m_[d]
        kap = {s: v["c"] for s, v in m.items()}
        hamlar = [s for s in ("yahoo", "borsapy") if s in m]
        if len(m) == 1:
            say["islem_yok"] += 1
            kayit.append({"tarih": d, "kapanislar": kap, "neden": "sadece tek kaynakta var; o gun islem gormemis sayildi"})
            continue
        cozum = None
        isy = (m.get("isyatirim") or {}).get("c")
        if isy and hamlar:
            i0 = sira[d]
            yakin = sorted(oran, key=lambda x: abs(x[0] - i0))[:10]
            # carpan bir temettu gunu araya girdiyse degisir: sadece ayni taraftaki en yakin gunlerin carpanina guven
            once = [r for i, r in yakin if i < i0][:5]
            sonra = [r for i, r in yakin if i > i0][:5]
            adaylar_f = []
            for grup in (once, sonra):
                if grup:
                    g = sorted(grup)
                    adaylar_f.append(g[len(g) // 2])
            en_iyi = None
            for f in adaylar_f:
                hedef = isy / f
                for s in hamlar:
                    fark = abs(m[s]["c"] - hedef) / hedef
                    if fark <= 0.004 and mum_tamam(m[s]) and (en_iyi is None or fark < en_iyi[0]):
                        en_iyi = (fark, s, round(hedef, 2))
            if en_iyi:
                cozum = en_iyi
        if cozum:
            mum = dict(m[cozum[1]]); mum["kaynak"] = cozum[1]
            kaydet(d, mum, kap, [cozum[1]])
            say["cozulen"] += 1
            kayit.append({"tarih": d, "kapanislar": kap, "secilen": cozum[1], "is_yatirim_gercek_karsiligi": cozum[2],
                          "neden": "kaynaklar tutmadi; Is Yatirim duzeltme carpaniyla dogru deger bulundu"})
        else:
            say["atlanan"] += 1
            kayit.append({"tarih": d, "kapanislar": kap, "neden": "dogru deger kesinlestirilemedi, alinmadi"})
    seri = [kabul[d] for d in sorted(kabul)]
    return seri, say, kayit


def main():
    kodlar, adlar = hisse_listesi()
    print("Hisseler:", kodlar)
    try:
        onceki = json.load(open("analiz.json", encoding="utf-8"))
    except Exception:
        onceki = {}
    eski = onceki.get("stocks") or {}
    try:
        import borsapy  # noqa: F401
        bp_var = True
    except Exception as e:
        print("borsapy yok:", e)
        bp_var = False

    stocks, log, korunan = {}, {}, []
    for kod in kodlar:
        K, hatalar = {}, []
        kaynaklar = [("yahoo", yahoo)] + ([("borsapy", borsapy_gecmis)] if bp_var else [])
        for ad, fn in kaynaklar:
            try:
                K[ad] = fn(kod)
            except Exception as e:
                K[ad] = {}
                hatalar.append("%s: %s" % (ad, e))
                print("HATA", kod, ad, e)
        # Is Yatirim sadece iki kaynak bazi gunlerde tutmadiginda ya da biri hic gelmediginde sorulur
        # Is Yatirim her zaman sorulur: ucuncu kaynak olarak tutmayan gunlerin dogru degerini bulmaya yarar
        if True:
            try:
                K["isyatirim"] = isyatirim(kod)
            except Exception as e:
                hatalar.append("isyatirim: %s" % e)
                print("HATA", kod, "isyatirim", e)
        seri, say, kayit = birlestir(K)
        if len(seri) >= EN_AZ_GUN:
            stocks[kod] = {"ad": adlar.get(kod, ""), "d": seri, "son": seri[-1][0]}
        elif (eski.get(kod) or {}).get("d"):
            stocks[kod] = eski[kod]  # bugun dogrulanamadi: son dogrulanmis veri kalir
            korunan.append(kod)
        log[kod] = {"ozet": say, "kaynak_gun": {s: len(v) for s, v in K.items()}, "hatalar": hatalar, "kayit": kayit[-40:]}
        print(kod, say, "gun:", len(seri), hatalar)

    if not stocks:
        print("Hic veri alinamadi; dosya degistirilmedi")
        sys.exit(1)
    son = max(s["son"] for s in stocks.values())
    veri = {"updated": son, "updatedAt": SIMDI.strftime("%Y-%m-%dT%H:%M:%SZ"), "korunan": korunan,
            "stocks": stocks, "kontrol": log}
    json.dump(veri, open("analiz.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("Tamam. Korunan:", korunan)


if __name__ == "__main__":
    main()
