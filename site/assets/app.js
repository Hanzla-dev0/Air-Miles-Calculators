(function () {
  "use strict";

  var BASE = "";
  try {
    var cs = document.currentScript;
    if (cs && cs.src) BASE = cs.src.replace(/assets\/app\.js.*$/, "");
  } catch (e) {}

  var R_MILES = 3958.8;
  var KM_PER_MILE = 1.609344;
  var NM_PER_MILE = 0.868976;

  var airports = window.AMC_AIRPORTS || [];
  var routeSet = window.AMC_ROUTES || {};
  var byCode = {};
  airports.forEach(function (a) { byCode[a[0]] = a; });

  function toRad(d) { return (d * Math.PI) / 180; }

  function haversineMiles(a, b) {
    var dLat = toRad(b[4] - a[4]);
    var dLon = toRad(b[5] - a[5]);
    var h = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(toRad(a[4])) * Math.cos(toRad(b[4])) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
    return 2 * R_MILES * Math.asin(Math.min(1, Math.sqrt(h)));
  }

  function fmt(n) { return Math.round(n).toLocaleString("en-US"); }

  function flightTime(miles) {
    var hours = miles / 500 + 0.5;
    var h = Math.floor(hours);
    var m = Math.round((hours - h) * 60);
    if (m === 60) { h += 1; m = 0; }
    return h + " h " + (m < 10 ? "0" : "") + m + " min";
  }

  function norm(s) {
    return s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  }

  function search(q) {
    q = norm(q.trim());
    if (!q) return [];
    var exact = [], starts = [], contains = [];
    airports.forEach(function (a) {
      var code = a[0].toLowerCase();
      var city = norm(a[2]);
      var name = norm(a[1]);
      var country = norm(a[3]);
      if (code === q) exact.push(a);
      else if (code.indexOf(q) === 0 || city.indexOf(q) === 0) starts.push(a);
      else if (name.indexOf(q) !== -1 || city.indexOf(q) !== -1 || country.indexOf(q) !== -1) contains.push(a);
    });
    return exact.concat(starts, contains).slice(0, 8);
  }

  function label(a) { return a[2] + " (" + a[0] + ") – " + a[1]; }

  function Picker(input, list) {
    var self = this;
    this.input = input;
    this.list = list;
    this.value = null;
    this.items = [];
    this.active = -1;

    input.addEventListener("input", function () {
      self.value = null;
      self.items = search(input.value);
      self.active = -1;
      self.render();
    });
    input.addEventListener("focus", function () {
      if (input.value && !self.value) {
        self.items = search(input.value);
        self.render();
      }
    });
    input.addEventListener("keydown", function (e) {
      if (!self.items.length) return;
      if (e.key === "ArrowDown") { e.preventDefault(); self.active = (self.active + 1) % self.items.length; self.render(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); self.active = (self.active - 1 + self.items.length) % self.items.length; self.render(); }
      else if (e.key === "Enter" && self.active >= 0) { e.preventDefault(); self.choose(self.items[self.active]); }
      else if (e.key === "Escape") { self.items = []; self.render(); }
    });
    document.addEventListener("click", function (e) {
      if (!input.parentNode.contains(e.target)) { self.items = []; self.render(); }
    });
  }

  Picker.prototype.render = function () {
    var self = this;
    this.list.innerHTML = "";
    this.input.setAttribute("aria-expanded", this.items.length ? "true" : "false");
    if (!this.items.length) { this.list.hidden = true; return; }
    this.list.hidden = false;
    this.items.forEach(function (a, i) {
      var li = document.createElement("li");
      li.setAttribute("role", "option");
      li.className = i === self.active ? "active" : "";
      var code = document.createElement("strong");
      code.textContent = a[0];
      var txt = document.createElement("span");
      txt.textContent = " " + a[2] + ", " + a[3] + " – " + a[1];
      li.appendChild(code);
      li.appendChild(txt);
      li.addEventListener("mousedown", function (e) { e.preventDefault(); self.choose(a); });
      self.list.appendChild(li);
    });
  };

  Picker.prototype.choose = function (a) {
    this.value = a;
    this.input.value = label(a);
    this.items = [];
    this.render();
    this.input.dispatchEvent(new Event("chosen"));
  };

  Picker.prototype.set = function (code) {
    var a = byCode[code];
    if (a) this.choose(a);
  };

  function init() {
    var form = document.getElementById("calc-form");
    if (!form) return;
    var from = new Picker(document.getElementById("from"), document.getElementById("from-list"));
    var to = new Picker(document.getElementById("to"), document.getElementById("to-list"));
    var out = document.getElementById("result");
    var err = document.getElementById("calc-error");

    var preset = form.getAttribute("data-from");
    var presetTo = form.getAttribute("data-to");
    if (preset) from.set(preset);
    if (presetTo) to.set(presetTo);

    document.getElementById("swap").addEventListener("click", function () {
      var a = from.value, b = to.value;
      if (b) from.choose(b); else { from.input.value = ""; from.value = null; }
      if (a) to.choose(a); else { to.input.value = ""; to.value = null; }
    });

    function show(a, b) {
      var mi = haversineMiles(a, b);
      var km = mi * KM_PER_MILE;
      var nm = mi * NM_PER_MILE;
      var key = (a[0] + "-" + b[0]).toLowerCase();
      var link = routeSet[key] ? '<p class="more"><a href="' + BASE + 'distance/' + routeSet[key] + '/">Full ' + a[2] + ' to ' + b[2] + ' route details →</a></p>' : "";
      out.innerHTML =
        '<h2 class="res-title">' + a[2] + " (" + a[0] + ") to " + b[2] + " (" + b[0] + ")</h2>" +
        '<div class="res-grid">' +
        '<div class="stat"><span class="num">' + fmt(mi) + '</span><span class="unit">air miles</span></div>' +
        '<div class="stat"><span class="num">' + fmt(km) + '</span><span class="unit">kilometres</span></div>' +
        '<div class="stat"><span class="num">' + fmt(nm) + '</span><span class="unit">nautical miles</span></div>' +
        '<div class="stat"><span class="num">' + flightTime(mi) + '</span><span class="unit">est. flight time</span></div>' +
        "</div>" + link +
        '<p class="note">Great-circle (shortest path) distance between the two airports. Flight time assumes an average cruise speed of about 500 mph plus 30 minutes for take-off and landing.</p>';
      out.hidden = false;
    }

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      err.textContent = "";
      var a = from.value, b = to.value;
      if (!a || !b) {
        err.textContent = "Please pick both airports from the suggestions.";
        out.hidden = true;
        return;
      }
      if (a[0] === b[0]) {
        err.textContent = "Choose two different airports.";
        out.hidden = true;
        return;
      }
      show(a, b);
      out.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });

    if (preset && presetTo && from.value && to.value) show(from.value, to.value);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
