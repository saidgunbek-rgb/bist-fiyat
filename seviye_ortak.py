# Ortak seviye hesabi: Analiz sayfasindaki (analiz.html) hesabin Python karsiligi.
# Karne, Kutuphane, "Bugun dikkat" ve telefon bildirimleri bu dosyayi kullanir; boylece panelin her yerinde
# alim bolgesi, risk ve hedef ayni rakamdir. analiz.html'deki hesap degisirse burasi da ayni sekilde degismeli
# (dogrulama: dogrula_seviye.js ile iki hesap birebir karsilastirilir).
import json, datetime, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}


def _ema(a, n, alfa):
    o, s, c, p = [None] * len(a), 0.0, 0, None
    for i, v in enumerate(a):
        if v is None:
            continue
        if p is None:
            s += v; c += 1
            if c == n:
                p = s / n; o[i] = p
        else:
            p = alfa * v + (1 - alfa) * p; o[i] = p
    return o


def ema(a, n):
    return _ema(a, n, 2.0 / (n + 1))


def rma(a, n):
    return _ema(a, n, 1.0 / n)


def hesapla(d):
    """d: [[tarih, acilis, yuksek, dusuk, kapanis, hacim], ...] -> gostergeler (analiz.html hesapla ile ayni)."""
    h = [x[2] for x in d]; l = [x[3] for x in d]; c = [x[4] for x in d]
    tr = [h[0] - l[0]] + [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(1, len(d))]
    R = {"ema": {n: ema(c, n) for n in (20, 50, 200)}, "atr14": rma(tr, 14)}
    at = rma(tr, 10)
    st, yon = [None] * len(d), [None] * len(d)
    ub = lb = None
    for i in range(len(d)):
        if at[i] is None:
            continue
        m = (h[i] + l[i]) / 2
        u, b = m + 3 * at[i], m - 3 * at[i]
        if lb is not None and not (b > lb or c[i - 1] < lb):
            b = lb
        if ub is not None and not (u < ub or c[i - 1] > ub):
            u = ub
        if st[i - 1] is None:
            dr = 1
        elif st[i - 1] == ub:
            dr = 1 if c[i] > u else -1
        else:
            dr = -1 if c[i] < b else 1
        st[i] = b if dr == 1 else u
        yon[i] = dr
        ub, lb = u, b
    R["st"], R["styon"] = st, yon
    return R


def hacim_profili(d, a, b, adet=40):
    lo = min(x[3] for x in d[a:b + 1]); hi = max(x[2] for x in d[a:b + 1])
    stp = (hi - lo) / adet or 1
    v = [0.0] * adet; top = 0
    for r in d[a:b + 1]:
        vol = r[5] or 0
        if not vol:
            continue
        k1 = max(0, min(adet - 1, int((r[3] - lo) // stp)))
        k2 = max(0, min(adet - 1, int((r[2] - lo) // stp)))
        for k in range(k1, k2 + 1):
            v[k] += vol / (k2 - k1 + 1)
        top += vol
    if not top:
        return None
    pk = max(range(adet), key=lambda k: (v[k], -k))
    al = ust = pk; t2 = v[pk]
    while t2 < top * 0.7 and (al > 0 or ust < adet - 1):
        va = v[al - 1] if al > 0 else -1
        vu = v[ust + 1] if ust < adet - 1 else -1
        if vu >= va:
            ust += 1; t2 += vu
        else:
            al -= 1; t2 += va
    return {"poc": lo + (pk + 0.5) * stp, "val": lo + al * stp, "vah": lo + (ust + 1) * stp}


def r2(x):
    return None if x is None else round(x + 0.0, 2)


def seviyeler(d):
    """analiz.html seviyeler() ile ayni kurallar + Karne'nin kullandigi alanlar."""
    if len(d) < 260:
        return None
    I = hesapla(d); n = len(d) - 1; c = d[n][4]; E = I["ema"]
    a = max(0, n - 249)
    hi = max(x[2] for x in d[a:]); lo = min(x[3] for x in d[a:])
    F = lambda r: hi - (hi - lo) * r
    atr = I["atr14"][n] or 0
    if c > F(0.5):
        alim, alim2 = [F(0.618), F(0.5)], [F(0.786), F(0.618)]
    elif c > F(0.618):
        alim, alim2 = [F(0.786), F(0.618)], [F(1), F(0.786)]
    elif c > F(0.786):
        alim, alim2 = [F(1), F(0.786)], None
    else:
        alim, alim2 = None, None
    if I["styon"][n] == 1:
        risk, riskn = I["st"][n], "Supertrend"
    elif E[200][n] is not None and E[200][n] < c:
        risk, riskn = E[200][n], "200 günlük ortalama"
    else:
        risk, riskn = lo, "1 yıllık dip"
    if risk >= c:
        risk, riskn = c - 2 * atr, "2 ATR altı"
    stopA = alim[0] - atr if alim else None
    if c < F(0) * 0.99:
        h1, h1n, h2, h2n = F(0), "son 1 yılın zirvesi", hi + (hi - lo) * 0.272, "Fibonacci 1,272 uzantısı"
    else:
        h1, h1n, h2, h2n = hi + (hi - lo) * 0.272, "Fibonacci 1,272 uzantısı", hi + (hi - lo) * 0.618, "Fibonacci 1,618 uzantısı"
    VP = hacim_profili(d, a, n, 40); kes = None
    if VP and alim:
        if alim[0] <= VP["poc"] <= alim[1]:
            kes = [max(alim[0], VP["poc"] - atr * 0.5), min(alim[1], VP["poc"] + atr * 0.5)]
        else:
            k1, k2 = max(alim[0], VP["val"]), min(alim[1], VP["vah"])
            if k2 - k1 > 0.002 * c:
                kes = [k1, k2]
    # Yukseliste ekleme: son 10 gun haric 1 yilin gun ici zirvesi; ust uste 2 kapanis ustunde ise kirilim teyitli
    z0 = max(x[2] for x in d[max(0, n - 259):n - 9])
    cc = [x[4] for x in d]
    if cc[-1] > z0 and cc[-2] > z0:
        kd = "teyit"
    elif cc[-1] > z0:
        kd = "ilk"
    elif any(x > z0 for x in cc[-10:]):
        kd = "geri"
    else:
        kd = "bekleniyor"
    kir = {"sev": r2(z0), "durum": kd, "gt_alt": r2(z0 * 0.97), "gt_ust": r2(z0)}
    e2, e5 = E[200][n], E[50][n]
    if e2 is None or e5 is None:
        trend = "yatay"
    elif c >= e2:
        trend = "yukari" if e5 >= e2 else "toparlanma"
    else:
        trend = "zayiflama" if e5 >= e2 else "asagi"
    if c < risk:
        durum = "risk"
    elif c >= h1 * 0.99:
        durum = "kar_al"
    elif alim and alim[0] <= c <= alim[1]:
        durum = "alim"
    elif alim2 and alim2[0] <= c <= alim2[1]:
        durum = "alim2"
    elif c <= F(0.786):
        durum = "dikkat"
    else:
        durum = "bekle"
    e2o = E[200][n - 20] if n >= 20 else None
    return {"yontem": "analiz", "son": r2(c), "tarih": d[n][0], "gun": len(d),
            "ma50": r2(e5), "ma200": r2(e2), "ma200_once": r2(e2o), "ort_tur": "EMA",
            "dip": r2(lo), "zirve": r2(hi), "f236": r2(F(0.236)), "f382": r2(F(0.382)), "f50": r2(F(0.5)),
            "f618": r2(F(0.618)), "f786": r2(F(0.786)),
            "alim": [r2(x) for x in alim] if alim else None, "alim2": [r2(x) for x in alim2] if alim2 else None,
            "kes": [r2(x) for x in kes] if kes else None, "stopA": r2(stopA), "atr": r2(atr),
            "poc": r2(VP["poc"]) if VP else None,
            "bolge": "alim" if durum == "alim" else ("alim2" if durum == "alim2" else None),
            "h1": r2(h1), "h1n": h1n, "h2": r2(h2), "h2n": h2n, "risk": r2(risk), "riskn": riskn,
            "kir": kir, "durum": durum, "trend": trend}


def _yahoo_son(kod):
    u = "https://query1.finance.yahoo.com/v8/finance/chart/%s.IS?range=1mo&interval=1d" % kod
    r = json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30))["chart"]["result"][0]
    off = r["meta"].get("gmtoffset", 10800); q = r["indicators"]["quote"][0]; o = {}
    for i, t in enumerate(r.get("timestamp") or []):
        if q["close"][i] and q["high"][i] and q["low"][i] and q["open"][i]:
            dd = datetime.datetime.utcfromtimestamp(t + off).strftime("%Y-%m-%d")
            o[dd] = [dd, q["open"][i], q["high"][i], q["low"][i], q["close"][i], (q.get("volume") or [0] * (i + 1))[i] or 0]
    return o


def _borsapy_son(kod):
    import borsapy as bp
    df = bp.Ticker(kod).history(period="1mo"); o = {}
    for idx, row in df.iterrows():
        dd = str(idx)[:10]
        try:
            o[dd] = [dd, float(row["Open"]), float(row["High"]), float(row["Low"]), float(row["Close"]), float(row.get("Volume") or 0)]
        except Exception:
            pass
    return o


def mum_serisi(kod, ser, analiz_yolu="analiz.json"):
    """Dogrulanmis kapanislar (ser: {tarih: kapanis}) ile analiz.json'daki dogrulanmis mumlari birlestirir.
    analiz.json'dan sonraki gunlerin mumu Yahoo (yoksa borsapy) mumundan, kapanisi ser ile tutuyorsa alinir.
    Donus: (mumlar, not) ya da (None, sebep)."""
    try:
        A = json.load(open(analiz_yolu, encoding="utf-8"))["stocks"].get(kod)
    except Exception as e:
        return None, "analiz.json okunamadi: %s" % e
    if not A or len(A.get("d") or []) < 300:
        return None, "analiz.json'da bu hissenin mum verisi yok"
    d = [list(x) for x in A["d"]]
    son = d[-1][0]
    eksik = sorted(t for t in ser if t > son)
    if eksik:
        kaynaklar = []
        for fn in (_yahoo_son, _borsapy_son):
            try:
                kaynaklar.append(fn(kod))
            except Exception:
                kaynaklar.append({})
        for t in eksik:
            m = None
            for K in kaynaklar:
                x = K.get(t)
                if x and abs(x[4] - ser[t]) <= max(0.011, 0.002 * ser[t]):
                    m = x
                    break
            if not m:
                return None, "%s gunu icin dogrulanmis mum bulunamadi" % t
            c = ser[t]
            d.append([t, round(m[1], 2), round(max(m[2], m[1], c), 2), round(min(m[3], m[1], c), 2), c, int(m[5] or 0)])
    # analiz.json'daki son gunler karnenin dogruladigi kapanisla celisiyorsa karnenin kapanisi esas alinir
    for r in d[-30:]:
        if r[0] in ser and abs(r[4] - ser[r[0]]) > max(0.011, 0.002 * ser[r[0]]):
            return None, "%s gunu analiz.json ile karne kapanisi tutmuyor" % r[0]
    return d, "ok (%d mum, son %s)" % (len(d), d[-1][0])


def tek_hesapla(kod, ser):
    """Karne icin: Analiz yontemiyle seviyeler. Mum verisi yoksa None (cagiran eski yonteme duser)."""
    d, notu = mum_serisi(kod, ser)
    if not d:
        print("Ortak seviye hesaplanamadi", kod, notu)
        return None
    t = seviyeler(d)
    if t:
        ds = sorted(ser)
        t["seri"] = [[x, r2(ser[x])] for x in ds[-260:]]
        t["mum_notu"] = notu
    return t
