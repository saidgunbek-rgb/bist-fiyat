/* Cevrimdisi destek: internet varken sayfalari ve verileri telefona kaydeder.
   Her zaman once internetten en guncel hali alinir; internet yoksa (ya da 8 sn icinde cevap gelmezse)
   en son kaydedilen hali gosterilir ve sayfaya "x-onbellek" basligiyla kayit zamani bildirilir. */
var KAP = "bist-panel-v1";
var SAYFALAR = ["./", "index.html", "karne.html", "fon.html", "yabanci.html"];
self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(KAP).then(function (c) { return Promise.all(SAYFALAR.map(function (u) { return c.add(u).catch(function () {}); })); }));
  self.skipWaiting();
});
self.addEventListener("activate", function (e) { e.waitUntil(self.clients.claim()); });
function bizim(u) {
  return (u.origin === self.location.origin && u.pathname.indexOf(new URL("./", self.location).pathname) === 0) ||
         (u.host === "raw.githubusercontent.com" && u.pathname.indexOf("/saidgunbek-rgb/bist-fiyat/") === 0);
}
function anahtar(u) { return u.origin + u.pathname; }   // ?t=... gibi ekler atilir
self.addEventListener("fetch", function (e) {
  var r = e.request; if (r.method !== "GET") return;
  var u = new URL(r.url); if (!bizim(u)) return;
  var key = anahtar(u);
  e.respondWith(new Promise(function (coz) {
    var bitti = false;
    function kayittan() {
      if (bitti) return; 
      caches.open(KAP).then(function (c) { return c.match(key); }).then(function (m) {
        if (bitti) return;
        if (!m) return;                       // kayit yoksa internet cevabini beklemeye devam
        bitti = true;
        var h = new Headers(m.headers); h.set("x-onbellek", m.headers.get("x-kayit") || "1");
        m.blob().then(function (b) { coz(new Response(b, { status: 200, headers: h })); });
      });
    }
    var sure = setTimeout(kayittan, 8000);
    fetch(r).then(function (res) {
      if (res && res.ok && (res.type === "basic" || res.type === "cors")) {
        var kopya = res.clone();
        kopya.blob().then(function (b) {
          var h = new Headers(); var ct = kopya.headers.get("content-type"); if (ct) h.set("content-type", ct);
          h.set("x-kayit", new Date().toISOString());
          return caches.open(KAP).then(function (c) { return c.put(key, new Response(b, { status: 200, headers: h })); });
        }).catch(function () {});
      }
      if (!bitti) { bitti = true; clearTimeout(sure); coz(res); }
    }).catch(function () {
      clearTimeout(sure);
      caches.open(KAP).then(function (c) { return c.match(key); }).then(function (m) {
        if (bitti) return; bitti = true;
        if (!m) return coz(Response.error());
        var h = new Headers(m.headers); h.set("x-onbellek", m.headers.get("x-kayit") || "1");
        m.blob().then(function (b) { coz(new Response(b, { status: 200, headers: h })); });
      });
    });
  }));
});
