# Valor (alis/satis) verisinin hangi kaynaktan, hangi alan adiyla geldigini bulan TEST dosyasi.
# Panele hicbir sey yazmaz; yalnizca valor-test.json uretir.
import json, re, urllib.request, urllib.error, traceback
OUT = {"borsapy": {}, "tefas_sayfa": {}, "notlar": []}
try:
    import borsapy as bp
    OUT["borsapy"]["surum"] = getattr(bp, "__version__", "?")
except Exception as e:
    bp = None; OUT["notlar"].append("borsapy import: %r" % e)

def kodlar(dosya, n):
    try:
        L = json.load(open(dosya, encoding="utf-8"))["fonlar"]
        return [x["k"] for x in L[:n]]
    except Exception as e:
        OUT["notlar"].append("%s okunamadi: %r" % (dosya, e)); return []

ORNEK = kodlar("fonlar.json", 3) + kodlar("borclanma.json", 3) + kodlar("yabanci.json", 2)
if bp:
    try:
        r = bp.search_funds("para piyasası", limit=15)
        OUT["borsapy"]["para_piyasasi_arama"] = [{"k": x.get("fund_code"), "ad": x.get("name")} for x in r][:15]
        ORNEK += [x.get("fund_code") for x in r[:3] if x.get("fund_code")]
    except Exception as e:
        OUT["notlar"].append("para piyasasi arama: %r" % e)
    for k in ORNEK:
        d = {}
        try:
            f = bp.Fund(k)
            info = dict(f.info)
            d["info_anahtarlar"] = sorted(info.keys())
            d["valor_alanlari"] = {a: str(b) for a, b in info.items() if re.search(r"val[oö]r|settle|valu|t\+", a, re.I)}
            d["nitelikler"] = [a for a in dir(f) if not a.startswith("_")]
            for a in d["nitelikler"]:
                if re.search(r"val[oö]r|settle|detail|trading|rule|order", a, re.I):
                    try:
                        v = getattr(f, a)
                        v = v() if callable(v) else v
                        d.setdefault("ek", {})[a] = str(v)[:500]
                    except Exception as e:
                        d.setdefault("ek", {})[a] = "hata %r" % e
        except Exception as e:
            d["hata"] = repr(e)
        OUT["borsapy"][k] = d

def getir(url, basliklar=None):
    rq = urllib.request.Request(url, headers=basliklar or {"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(rq, timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return 0, repr(e)

for k in ORNEK[:4]:
    for adres in ("https://www.tefas.gov.tr/en/fund-detailed-analysis/%s" % k,
                  "https://www.tefas.gov.tr/FonAnaliz.aspx?FonKod=%s" % k):
        st, gv = getir(adres)
        m = re.findall(r".{0,80}[Vv]al[oö]r.{0,120}", gv)[:6]
        js = sorted(set(re.findall(r'["\'](/api/[^"\']+)["\']', gv)))[:30]
        OUT["tefas_sayfa"][adres] = {"durum": st, "uzunluk": len(gv), "valor_parcalari": m, "api_adresleri": js}
json.dump(OUT, open("valor-test.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=str)
print("bitti")
