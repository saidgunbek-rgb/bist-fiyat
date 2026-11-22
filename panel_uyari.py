#!/usr/bin/env python3
"""Panel haberleri telefon uyarisi.
analiz.json (hisseler) ve altin.json (altin, gumus) gunluk mumlarindan, analiz.html'deki Panel haberleri ile ayni kurallarla
yeni olaylari bulur; her olay icin tek bildirim gonderilir (panel-uyari-durum.json'da tutulur).
Olaylar: yukselise gecenler (EMA 50 ustune cikis, Supertrend yukselise donus, RSI 30 altindan cikis, WaveTrend dipte yukari kesisim),
dibe yeni girenler, sert dusenler, sert yukselenler. Gunde en cok bir ozet (GitHub issue). Al-sat onerisi degildir.
Cikti: bildirim.json (gonderilecekse) ve panel-uyari-durum.json."""
import json, os, sys, datetime

PENCERE = 5          # son 5 islem gunu
def ema(a, n):
    o = [None] * len(a); k = 2.0 / (n + 1); s = 0.0; c = 0; p = None
    for i, v in enumerate(a):
        if v is None: continue
        if p is None:
            s += v; c += 1
            if c == n: p = s / n; o[i] = p
        else:
            p = v * k + p * (1 - k); o[i] = p
    return o
def sma(a, n):
    o = [None] * len(a)
    for i in range(n - 1, len(a)):
        w = a[i - n + 1:i + 1]
        if all(x is not None for x in w): o[i] = sum(w) / n
    return o
def rma(a, n):
    o = [None] * len(a); s = 0.0; c = 0; p = None
    for i, v in enumerate(a):
        if v is None: continue
        if p is None:
            s += v; c += 1
            if c == n: p = s / n; o[i] = p
        else:
            p = (p * (n - 1) + v) / n; o[i] = p
    return o

def hesapla(d):
    h = [x[2] for x in d]; l = [x[3] for x in d]; c = [x[4] for x in d]; N = len(d)
    tr = [(h[i] - l[i]) if i == 0 else max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(N)]
    R = {"ema50": ema(c, 50)}
    at = rma(tr, 10); st = [None] * N; yon = [None] * N; ub = None; lb = None; dr = 1
    for i in range(N):
        if at[i] is None: continue
        m = (h[i] + l[i]) / 2; u = m + 3 * at[i]; b = m - 3 * at[i]
        if lb is not None and not (b > lb or c[i - 1] < lb): b = lb
        if ub is not None and not (u < ub or c[i - 1] > ub): u = ub
        if st[i - 1] is None: dr = 1
        elif st[i - 1] == ub: dr = 1 if c[i] > u else -1
        else: dr = -1 if c[i] < b else 1
        st[i] = b if dr == 1 else u; yon[i] = dr; ub = u; lb = b
    R["yon"] = yon
    ap = [(x[2] + x[3] + x[4]) / 3 for x in d]; esa = ema(ap, 10)
    dd = ema([None if esa[i] is None else abs(ap[i] - esa[i]) for i in range(N)], 10)
    ci = [None if (esa[i] is None or dd[i] is None or dd[i] == 0) else (ap[i] - esa[i]) / (0.015 * dd[i]) for i in range(N)]
    wt1 = ema(ci, 21); wt2 = sma(wt1, 4); R["wt1"] = wt1
    kes = [0] * N
    for i in range(1, N):
        a1, a2, b1, b2 = wt1[i - 1], wt2[i - 1], wt1[i], wt2[i]
        if None in (a1, a2, b1, b2): continue
        if a1 <= a2 and b1 > b2: kes[i] = 1
        elif a1 >= a2 and b1 < b2: kes[i] = -1
    R["kes"] = kes
    ka = [None] + [max(0, c[i] - c[i - 1]) for i in range(1, N)]; ky = [None] + [max(0, c[i - 1] - c[i]) for i in range(1, N)]
    ga = rma(ka, 14); gy = rma(ky, 14)
    R["rsi"] = [None if (ga[i] is None or gy[i] is None) else (100 if gy[i] == 0 else 100 - 100 / (1 + ga[i] / gy[i])) for i in range(N)]
    return R

def pos_dizi(d):
    """Her gun icin son 252 gunun (bugun dahil) en dusuk/en yuksegine gore konum."""
    out = [None] * len(d)
    for i in range(len(d)):
        a = max(0, i - 251); lo = min(x[3] for x in d[a:i + 1]); hi = max(x[2] for x in d[a:i + 1])
        out[i] = (d[i][4] - lo) / (hi - lo) if hi > lo else None
    return out

def olaylar(kod, ad, d, altin):
    """[(anahtar, grup, metin, tarih)] son PENCERE islem gunundeki olaylar."""
    N = len(d); n = N - 1; E = []
    if N < 80: return E
    R = hesapla(d); c = [x[4] for x in d]; P = pos_dizi(d)
    for i in range(n, n - PENCERE, -1):
        if i < 2: break
        t = d[i][0]
        e = R["ema50"]
        if e[i] is not None and e[i - 1] is not None and c[i] > e[i] and c[i - 1] <= e[i - 1]:
            E.append((f"{kod}|emu|{t}", "yuk", f"{ad}: fiyat EMA 50'nin üstüne çıktı", t))
        if R["yon"][i] is not None and R["yon"][i - 1] is not None and R["yon"][i] != R["yon"][i - 1] and R["yon"][i] == 1:
            E.append((f"{kod}|stu|{t}", "yuk", f"{ad}: Supertrend yükselişe döndü", t))
        if R["rsi"][i] is not None and R["rsi"][i - 1] is not None and R["rsi"][i] >= 30 and R["rsi"][i - 1] < 30:
            E.append((f"{kod}|rup|{t}", "yuk", f"{ad}: RSI 30'un altından çıktı", t))
        if R["kes"][i] == 1 and R["wt1"][i] is not None and R["wt1"][i] < -30:
            E.append((f"{kod}|wup|{t}", "yuk", f"{ad}: WaveTrend dipte yukarı kesişim yaptı", t))
        if P[i] is not None and P[i - 1] is not None and P[i] <= 0.214 and P[i - 1] > 0.214:
            E.append((f"{kod}|dip|{t}", "dip", f"{ad}: son 1 yılın en alt bölgesine girdi", t))
    th = 3 if altin else 5
    for i in range(n, n - 3, -1):
        if i < 1: break
        r = (c[i] / c[i - 1] - 1) * 100; t = d[i][0]
        if r <= -th: E.append((f"{kod}|gdn|{t}", "dus", f"{ad} −%{abs(r):.1f}".replace(".", ","), t))
        elif r >= th: E.append((f"{kod}|gup|{t}", "yuk2", f"{ad} +%{r:.1f}".replace(".", ","), t))
    return E

def tumu(analiz, altin):
    E = []
    for j, alt in ((analiz, False), (altin, True)):
        for k, s in (j.get("stocks") or {}).items():
            d = s.get("d") or []
            if alt: d = [[r[0], r[1], r[2], r[3], r[4], 1] for r in d]
            E += olaylar(k, (s.get("ad") or k) if alt else k, d, alt)
    return E

def trd(s): return s[8:10] + "." + s[5:7] + "." + s[:4]

def main():
    analiz = json.load(open("analiz.json")); altin = json.load(open("altin.json"))
    E = tumu(analiz, altin)
    bugun = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=3)).strftime("%Y-%m-%d")
    try: durum = json.load(open("panel-uyari-durum.json"))
    except Exception: durum = None
    if durum is None:
        durum = {"gonderilen": {e[0]: bugun for e in E}, "son": ""}
        json.dump(durum, open("panel-uyari-durum.json", "w"), ensure_ascii=False, indent=1)
        print("Ilk calisma: %d mevcut olay sessizce kaydedildi, bildirim gonderilmedi." % len(E)); return
    yeni = [e for e in E if e[0] not in durum["gonderilen"]]
    print("Olay: %d, yeni: %d, son gonderim: %s" % (len(E), len(yeni), durum.get("son")))
    if yeni and durum.get("son") != bugun:
        son = max(e[3] for e in yeni)
        G = {"yuk": [], "dip": [], "dus": [], "yuk2": []}
        for e in sorted(yeni, key=lambda x: x[3]): G[e[1]].append(e)
        sat = []
        if G["yuk"]: sat.append("🟢 Yükselişe geçenler:\n" + "\n".join("• " + e[2] + " (" + trd(e[3]) + ")" for e in G["yuk"]))
        if G["dip"]: sat.append("🟡 Dibe yeni girenler:\n" + "\n".join("• " + e[2] + " (" + trd(e[3]) + ")" for e in G["dip"]))
        if G["dus"]: sat.append("🔴 Sert düşenler (son gün):\n" + "\n".join("• " + e[2] + " (" + trd(e[3]) + ")" for e in G["dus"]))
        if G["yuk2"]: sat.append("🟢 Sert yükselenler (son gün):\n" + "\n".join("• " + e[2] + " (" + trd(e[3]) + ")" for e in G["yuk2"]))
        json.dump([{"i": "📣", "t": "Panel haberi · " + trd(son) + " kapanışı", "g": "\n\n".join(sat) + "\n\nÖlçülen durumu yazar; alım-satım önerisi ya da tahmin değildir. Ayrıntı için panelde Araçlar → Panel haberleri."}],
                  open("bildirim.json", "w"), ensure_ascii=False)
        for e in yeni: durum["gonderilen"][e[0]] = bugun
        durum["son"] = bugun
    # eski kayitlari temizle
    lim = (datetime.date.fromisoformat(bugun) - datetime.timedelta(days=40)).isoformat()
    durum["gonderilen"] = {k: v for k, v in durum["gonderilen"].items() if v >= lim or k.split("|")[-1] >= lim}
    json.dump(durum, open("panel-uyari-durum.json", "w"), ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main()
