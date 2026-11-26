# Banka gram altin/gumus alis-satis kaynagi testi (doviz.com). Sonuc: banka-test.json
import json, re, urllib.request, datetime
BANKALAR = ["Kapalıçarşı", "Akbank", "Garanti BBVA", "Enpara"]
URLLER = {
    "altin": ["https://altin.doviz.com/alternatif-bank/gram-altin/bilgi",
              "https://altin.doviz.com/akbank/gram-altin/bilgi",
              "https://altin.doviz.com/gram-altin"],
    "gumus": ["https://altin.doviz.com/alternatif-bank/gram-gumus/bilgi",
              "https://altin.doviz.com/akbank/gram-gumus/bilgi",
              "https://altin.doviz.com/gram-gumus"],
}
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
      "Accept-Language": "tr-TR,tr;q=0.9", "Accept": "text/html"}
def sayi(t):
    try: return float(t.replace(".", "").replace(",", "."))
    except Exception: return None
def sade(h):
    h = re.sub(r"(?is)<(script|style).*?</\1>", " ", h)
    h = re.sub(r"(?s)<[^>]+>", " ", h)
    h = h.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", h)
def ayikla(metin):
    out = {}
    for b in BANKALAR:
        for m in re.finditer(re.escape(b), metin):
            sn = metin[m.end():m.end() + 80]
            n = re.findall(r"\d{1,3}(?:\.\d{3})*,\d{2}", sn)
            if len(n) >= 2:
                a, s = sayi(n[0]), sayi(n[1])
                if a and s and s >= a:
                    out[b] = {"alis": a, "satis": s}; break
    return out
sonuc = {"tarih": datetime.datetime.utcnow().isoformat() + "Z", "kaynak": {}}
for ad, liste in URLLER.items():
    for u in liste:
        k = {"url": u}
        try:
            r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40)
            h = r.read().decode("utf-8", "replace"); k["durum"] = r.status; k["boyut"] = len(h)
            m = sade(h); k["bulunan"] = ayikla(m)
            i = m.find("Akbank"); k["ornek"] = m[max(0, i - 200):i + 300] if i >= 0 else m[:300]
        except Exception as e:
            k["hata"] = str(e)[:200]
        sonuc["kaynak"].setdefault(ad, []).append(k)
        if len(k.get("bulunan", {})) == len(BANKALAR): break
json.dump(sonuc, open("banka-test.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({a: [{"url": x["url"], "durum": x.get("durum"), "bulunan": x.get("bulunan"), "hata": x.get("hata")} for x in l] for a, l in sonuc["kaynak"].items()}, ensure_ascii=False, indent=1))
