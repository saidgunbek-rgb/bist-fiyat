# Enpara gram altin / gram gumus alis-satis (doviz.com). Yazar: enpara.json
# Aksam calismasinda (>=18:20 TR) prices.json icine GRAMALTIN / GRAMGUMUS degerleme fiyati (Enpara ALIS) da yazilir.
# Dogrulanamayan deger yazilmaz: eski deger korunur, panel "—" gosterir.
import json, re, urllib.request, datetime
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
      "Accept-Language": "tr-TR,tr;q=0.9", "Accept": "text/html"}
SAYI = r"\d{1,3}(?:\.\d{3})*,\d{2}"
def sayi(t):
    try: return float(t.replace(".", "").replace(",", "."))
    except Exception: return None
def sade(h):
    h = re.sub(r"(?is)<(script|style).*?</\1>", " ", h)
    h = re.sub(r"(?s)<[^>]+>", " ", h)
    h = h.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", h)
def sayfa(u):
    r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40)
    return sade(r.read().decode("utf-8", "replace"))
def cek(m):
    mm = re.search(r"Alış\s*/\s*Satış\s*(%s)\s*/\s*(%s)" % (SAYI, SAYI), m)
    if not mm: return None
    a, s = sayi(mm.group(1)), sayi(mm.group(2))
    if not (a and s and s >= a): return None
    sa = re.search(r"Son\s*\(\s*(\d{2}:\d{2})\s*\)", m)
    return {"alis": a, "satis": s, "saat": sa.group(1) if sa else None}
def altin_yedek():
    m = sayfa("https://altin.doviz.com/alternatif-bank/gram-altin/bilgi")
    for x in re.finditer("Enpara", m):
        n = re.findall(SAYI, m[x.end():x.end() + 80])
        if len(n) >= 2 and sayi(n[1]) >= sayi(n[0]):
            return {"alis": sayi(n[0]), "satis": sayi(n[1]), "saat": None}
    return None
def yahoo_canli(sym):
    son = None
    for host in ("query1", "query2"):
        try:
            r = json.load(urllib.request.urlopen(urllib.request.Request("https://%s.finance.yahoo.com/v8/finance/chart/%s?interval=1d&range=5d" % (host, sym), headers=UA), timeout=30))["chart"]["result"][0]["meta"]
            v = float(r["regularMarketPrice"])
            if v > 0: return v
        except Exception as e:
            son = e
            print("HATA yahoo", host, sym, str(e)[:100])
    raise son or Exception("fiyat yok")
ist_ = datetime.datetime.utcnow() + datetime.timedelta(hours=3)
REF, REFK = {}, {}
try:
    usd = yahoo_canli("USDTRY=X")
    REF["GRAMALTIN"] = yahoo_canli("GC=F") * usd / 31.1035; REFK["GRAMALTIN"] = "yahoo canli"
    REF["GRAMGUMUS"] = yahoo_canli("SI=F") * usd / 31.1035; REFK["GRAMGUMUS"] = "yahoo canli"
except Exception as e:
    print("HATA referans (yahoo)", str(e)[:120])
# yedek referans: altin.json (ons x USDTRY / 31,1035, kendi botu) son satir; 2 gunden eskiyse kullanilmaz
try:
    aj = json.load(open("altin.json", encoding="utf-8"))
    for ad, k in (("GRAMALTIN", "GRAM"), ("GRAMGUMUS", "GGUM")):
        if ad in REF: continue
        satir = aj["stocks"][k]; satir = satir["d"] if isinstance(satir, dict) else satir
        t = datetime.datetime.strptime(satir[-1][0], "%Y-%m-%d")
        if (ist_ - t).days <= 2 and satir[-1][4] > 0:
            REF[ad] = float(satir[-1][4]); REFK[ad] = "altin.json " + satir[-1][0]
except Exception as e:
    print("HATA referans (yedek)", str(e)[:120])
print("referans:", {k: (round(v, 2), REFK[k]) for k, v in REF.items()})
ist_ = datetime.datetime.utcnow() + datetime.timedelta(hours=3)
KAYNAK = {"GRAMALTIN": ["https://altin.doviz.com/enpara/gram-altin", "https://altin.doviz.com/enpara/gram-altin/bilgi"],
          "GRAMGUMUS": ["https://altin.doviz.com/enpara/gumus", "https://altin.doviz.com/enpara/gumus/bilgi"]}
try: eski = json.load(open("enpara.json", encoding="utf-8"))
except Exception: eski = {}
now = datetime.datetime.utcnow(); ist = now + datetime.timedelta(hours=3)
out = {"updatedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "kaynak": "doviz.com (Enpara)"}
for ad, urller in KAYNAK.items():
    q = None
    for u in urller:
        try:
            q = cek(sayfa(u))
        except Exception as e:
            print("HATA", ad, u, str(e)[:120])
        if q: break
    if not q and ad == "GRAMALTIN":
        try: q = altin_yedek()
        except Exception as e: print("HATA yedek", str(e)[:120])
    if q:
        q["makas"] = round((q["satis"] / q["alis"] - 1) * 100, 2)
        q["tamam"] = q["makas"] <= (8.0 if ad == "GRAMGUMUS" else 6.0)   # makas cok genisse satis dogrulanamadi sayilir
        q["zaman"] = out["updatedAt"]
        r = REF.get(ad)
        # capraz kontrol: Enpara alisi, ons x dolar referansindan %10'dan fazla asagi ya da %3'ten fazla yukari sapmissa gecersiz
        q["ref"] = round(r, 2) if r else None
        q["ref_kaynak"] = REFK.get(ad)
        q["gecerli"] = bool(r) and (0.90 * r <= q["alis"] <= 1.03 * r)
        out[ad] = q
        print(ad, q)
    else:
        out[ad] = eski.get(ad)
        print(ad, "alinamadi, eski deger korundu")
json.dump(out, open("enpara.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
# aksam degerleme fiyati (Enpara alis) -> prices.json
if (ist.weekday() < 5) and (ist.hour, ist.minute) >= (18, 20):
    try:
        v = json.load(open("prices.json"))
        g = v.setdefault("days", {}).setdefault(ist.strftime("%Y-%m-%d"), {"p": {}})
        g.setdefault("p", {})
        for ad in KAYNAK:
            q = out.get(ad)
            if q and q.get("alis") and q.get("gecerli") and q.get("zaman") == out["updatedAt"]:
                g["p"][ad] = q["alis"]
        json.dump(v, open("prices.json", "w"), indent=1, sort_keys=True)
    except Exception as e:
        print("prices.json yazilamadi", str(e)[:120])
