(function () {
  "use strict";

  var LAGUNA_CENTER = [14.2691, 121.4119];

  function initMap(containerId, points) {
    var el = document.getElementById(containerId);
    if (!el || typeof L === "undefined") return null;

    var map = L.map(el).setView(LAGUNA_CENTER, 10);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
      maxZoom: 18,
    }).addTo(map);

    if (!points || !points.length) {
      L.marker(LAGUNA_CENTER).addTo(map).bindPopup("Laguna, Philippines");
      return map;
    }

    var latlngs = [];
    points.forEach(function (p, i) {
      if (p.lat == null || p.lng == null) return;
      var ll = [p.lat, p.lng];
      latlngs.push(ll);
      L.marker(ll)
        .addTo(map)
        .bindPopup("<strong>" + (i + 1) + ". " + (p.name || "Stop") + "</strong>");
    });

    if (latlngs.length > 1) {
      L.polyline(latlngs, { color: "#9b2c2c", weight: 3, opacity: 0.75 }).addTo(map);
      map.fitBounds(latlngs, { padding: [32, 32] });
    } else if (latlngs.length === 1) {
      map.setView(latlngs[0], 13);
    }

    return map;
  }

  function updateDurationHint() {
    var start = document.getElementById("start_date");
    var end = document.getElementById("end_date");
    var hint = document.getElementById("trip-duration-hint");
    if (!start || !end || !hint) return;
    if (!start.value || !end.value) return;
    var s = new Date(start.value);
    var e = new Date(end.value);
    if (isNaN(s) || isNaN(e)) return;
    var days = Math.max(1, Math.round((e - s) / 86400000) + 1);
    hint.textContent = "Trip duration: " + days + " day" + (days !== 1 ? "s" : "") + " (auto-calculated).";
  }

  function updateSelectedSummary() {
    var summary = document.getElementById("selected-spots-summary");
    if (!summary) return;
    var boxes = document.querySelectorAll(".spot-checkbox:checked");
    if (!boxes.length) {
      summary.innerHTML = '<span class="text-muted small">No spots selected yet.</span>';
      return;
    }
    var names = [];
    boxes.forEach(function (cb) {
      names.push(cb.getAttribute("data-name") || "Spot");
    });
    summary.innerHTML =
      "<strong>" +
      boxes.length +
      " selected:</strong> <span class=\"small\">" +
      names.join(" · ") +
      "</span>";
  }

  document.addEventListener("DOMContentLoaded", function () {
    var points = window.LTCATO_PLANNER_MAP || [];
    initMap("planner-route-map", points);
    initMap("planner-route-map-tab", points);

    ["start_date", "end_date"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.addEventListener("change", updateDurationHint);
    });
    updateDurationHint();

    document.querySelectorAll(".spot-checkbox").forEach(function (cb) {
      cb.addEventListener("change", updateSelectedSummary);
    });
    updateSelectedSummary();

    document.querySelectorAll('[data-bs-toggle="pill"]').forEach(function (tab) {
      tab.addEventListener("shown.bs.tab", function () {
        var mapEl = document.getElementById("planner-route-map");
        if (mapEl && mapEl._leaflet_id) {
          setTimeout(function () {
            window.dispatchEvent(new Event("resize"));
          }, 100);
        }
      });
    });
  });
})();
