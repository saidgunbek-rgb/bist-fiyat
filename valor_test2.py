# Valoru bos gelen fonlari inceler: ham TEFAS degeri, kaynak kodu ve alternatif adresler. Panele yazmaz.
import json, re, os, inspect, urllib.request, urllib.error
OUT = {"bos_fonlar": {}, "dolu_ornek": {}, "borsapy_kaynak": {}, "dogrudan": {}, "notlar": []}
import borsapy as bp
OUT["surum"] = getattr(bp, "__version__", "?")

def liste(dosya):
    try:
        j = json.load(open(dosya, encoding="utf-8"))
        return [x["k"] for x in j["fonlar"] if x.get("vb") is None], [x["k"] for x in j["fonlar"] if x.get("vb") is not None]
    except Exception as e:
        OUT["notlar"].append("%s: %r" % (dosya, e)); return [], []

bos, dolu = [], []
for d in ("fonlar.json", "borclanma.json", "para.json"):
    b, o = liste(d); bos += b[:6]; dolu += o[:2]

def ham(k):
    r = {}
    try:
        f = bp.Fund(k)
        info = dict(f.info)
        r["valor_ve_durum"] = {a: repr(info.get(a)) for a in ("buy_valor", "sell_valor", "tefas_status", "first_trading_time", "last_trading_time", "min_purchase", "min_redemption", "max_purchase", "max_redemption", "fund_class", "category", "date")}
        r["tum_info"] = {a: repr(b)[:80] for a, b in info.items()}
    except Exception as e:
        r["hata"] = repr(e)
    return r

for k in bos: OUT["bos_fonlar"][k] = ham(k)
for k in dolu[:4]: OUT["dolu_ornek"][k] = ham(k)

# borsapy kaynak kodunda valor nereden geliyor
try:
    kok = os.path.dirname(bp.__file__)
    for dp, _, fs in os.walk(kok):
        for fn in fs:
            if not fn.endswith(".py"): continue
            p = os.path.join(dp, fn)
            try: t = open(p, encoding="utf-8").read()
            except Exception: continue
            if re.search(r"valor|valör", t, re.I):
                satir = [l.strip()[:200] for l in t.splitlines() if re.search(r"valor|valör|https?://[^\s'\"]*tefas", l, re.I)]
                OUT["borsapy_kaynak"][os.path.relpath(p, kok)] = satir[:40]
except Exception as e:
    OUT["notlar"].append("kaynak: %r" % e)

# dogrudan TEFAS adresleri (borsapy kaynagindaki adresler denenir)
adresler = set()
for v in OUT["borsapy_kaynak"].values():
    for l in v:
        adresler.update(re.findall(r"https?://[^\s'\"\)]+", l))
for a in sorted(adresler)[:12]:
    try:
        rq = urllib.request.Request(a, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(rq, timeout=20) as r:
            OUT["dogrudan"][a] = {"durum": r.status, "ilk": r.read(300).decode("utf-8", "replace")}
    except Exception as e:
        OUT["dogrudan"][a] = repr(e)[:150]
json.dump(OUT, open("valor-test2.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=str)
print("bitti")
