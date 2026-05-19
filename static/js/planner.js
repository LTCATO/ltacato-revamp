(function () {
  "use strict";

  var LAGUNA_CENTER = [121.4119, 14.2691]; // Mapbox uses [lng, lat]
  var map;
  var markers = [];

  // ── Category → pin style mapping ──────────────────────────────────────────
  var CATEGORY_STYLES = {
    "heritage": { color: "#6c757d", icon: "ph-buildings" },
    "cultural heritage": { color: "#6c757d", icon: "ph-buildings" },
    "heritage site": { color: "#6c757d", icon: "ph-buildings" },
    "nature": { color: "#198754", icon: "ph-tree" },
    "nature & eco": { color: "#198754", icon: "ph-tree" },
    "eco-tourism": { color: "#198754", icon: "ph-leaf" },
    "beach": { color: "#0dcaf0", icon: "ph-waves" },
    "lake": { color: "#0dcaf0", icon: "ph-waves" },
    "waterfall": { color: "#0dcaf0", icon: "ph-drop" },
    "adventure": { color: "#fd7e14", icon: "ph-mountains" },
    "adventure & sports": { color: "#fd7e14", icon: "ph-mountains" },
    "religious": { color: "#6f42c1", icon: "ph-church" },
    "religious site": { color: "#6f42c1", icon: "ph-church" },
    "museum": { color: "#795548", icon: "ph-bank" },
    "arts": { color: "#e91e63", icon: "ph-palette" },
    "festival": { color: "#ff5722", icon: "ph-confetti" },
    "resort": { color: "#17a2b8", icon: "ph-umbrella" },
    "park": { color: "#28a745", icon: "ph-park" },
    "farm": { color: "#8bc34a", icon: "ph-plant" },
    "hot spring": { color: "#dc3545", icon: "ph-thermometer-hot" },
    "default": { color: "#0056b3", icon: "ph-map-pin" }
  };

  function getCategoryStyle(categoryName) {
    if (!categoryName) return CATEGORY_STYLES["default"];
    var key = categoryName.toLowerCase().trim();
    if (CATEGORY_STYLES[key]) return CATEGORY_STYLES[key];
    // Partial match
    for (var k in CATEGORY_STYLES) {
      if (k !== "default" && (key.includes(k) || k.includes(key))) {
        return CATEGORY_STYLES[k];
      }
    }
    return CATEGORY_STYLES["default"];
  }

  function getPanelOffset() {
    if (window.innerWidth <= 768) return [0, 0];
    var formOpen = !document.getElementById('planner-form-panel').classList.contains('is-closed');
    var resultsPanel = document.getElementById('planner-results-panel');
    var resultsOpen = window.HAS_PLAN && resultsPanel && !resultsPanel.classList.contains('is-closed');
    var totalWidth = 0;
    if (formOpen) totalWidth += 380;
    if (resultsOpen) totalWidth += 400;
    return [-(totalWidth / 2), 0];
  }

  // ── Build a rich popup card for a plan stop ────────────────────────────────
  function buildStopPopup(p, index) {
    var style = getCategoryStyle(p.category_name);
    var ratingHtml = p.rating ? '<span class="badge" style="background:' + style.color + ';color:#fff">★ ' + p.rating + '</span> ' : '';
    var catHtml = p.category_name ? '<small style="color:' + style.color + '"><i class="' + style.icon + '"></i> ' + p.category_name + '</small><br>' : '';
    var lguHtml = p.lgu_name ? '<small class="text-muted"><i class="ph ph-map-pin"></i> ' + p.lgu_name + '</small><br>' : '';
    var descHtml = p.description ? '<p style="font-size:0.78rem;margin:4px 0 6px;color:#555;line-height:1.3">' + p.description + '</p>' : '';
    var viewBtn = p.tourist_spot_id ? '<a href="/spots/' + p.tourist_spot_id + '" class="btn btn-sm btn-outline-secondary" style="font-size:0.75rem;padding:2px 8px" target="_blank"><i class="ph ph-eye"></i> View</a> ' : '';
    var planBtn = p.tourist_spot_id ? '<a href="/planner?spot_id=' + p.tourist_spot_id + '" class="btn btn-sm" style="font-size:0.75rem;padding:2px 8px;background:' + style.color + ';color:#fff"><i class="ph ph-calendar-plus"></i> Plan</a>' : '';
    return '<div style="min-width:180px;max-width:220px">' +
      '<strong style="font-size:0.9rem">' + (index + 1) + '. ' + (p.name || 'Stop') + '</strong><br>' +
      catHtml + lguHtml + ratingHtml +
      descHtml +
      '<div style="margin-top:4px">' + viewBtn + planBtn + '</div>' +
      '</div>';
  }

  // ── Build a rich popup card for an unselected spot ─────────────────────────
  function buildSpotPopup(s) {
    var style = getCategoryStyle(s.category_name);
    var ratingHtml = s.rating ? '<span class="badge" style="background:' + style.color + ';color:#fff">★ ' + s.rating + '</span> ' : '';
    var catHtml = s.category_name ? '<small style="color:' + style.color + '"><i class="' + style.icon + '"></i> ' + s.category_name + '</small><br>' : '';
    var lguHtml = s.lgu_name ? '<small class="text-muted"><i class="ph ph-map-pin"></i> ' + s.lgu_name + '</small><br>' : '';
    var descHtml = s.description ? '<p style="font-size:0.78rem;margin:4px 0 6px;color:#555;line-height:1.3">' + s.description + '</p>' : '';
    var viewBtn = '<a href="/spots/' + s.id + '" class="btn btn-sm btn-outline-secondary" style="font-size:0.75rem;padding:2px 8px" target="_blank"><i class="ph ph-eye"></i> View</a> ';
    var addBtn = '<button class="btn btn-sm btn-add-spot-map" data-id="' + s.id + '" style="font-size:0.75rem;padding:2px 8px;background:' + style.color + ';color:#fff;border:none"><i class="ph ph-plus"></i> Add to Plan</button>';
    return '<div style="min-width:180px;max-width:220px">' +
      '<strong style="font-size:0.9rem">' + (s.name || 'Spot') + '</strong><br>' +
      catHtml + lguHtml + ratingHtml +
      descHtml +
      '<div style="margin-top:4px">' + viewBtn + addBtn + '</div>' +
      '</div>';
  }

  // ── Create a styled marker element ─────────────────────────────────────────
  function createMarkerEl(opts) {
    // opts: { color, icon, label, size }
    var size = opts.size || 30;
    var el = document.createElement('div');
    el.className = 'planner-map-marker';
    el.style.cssText = [
      'background:' + opts.color,
      'color:#fff',
      'width:' + size + 'px',
      'height:' + size + 'px',
      'border-radius:50% 50% 50% 0',
      'transform:rotate(-45deg)',
      'display:flex',
      'align-items:center',
      'justify-content:center',
      'box-shadow:0 2px 6px rgba(0,0,0,0.35)',
      'border:2px solid rgba(255,255,255,0.8)',
      'cursor:pointer',
      'font-size:' + Math.round(size * 0.45) + 'px',
      'font-weight:700'
    ].join(';');
    var inner = document.createElement('div');
    inner.style.transform = 'rotate(45deg)';
    if (opts.label != null) {
      inner.textContent = opts.label;
    } else if (opts.icon) {
      inner.innerHTML = '<i class="ph ' + opts.icon + '"></i>';
    }
    el.appendChild(inner);
    return el;
  }

  // ── Draw route line via Mapbox Directions ──────────────────────────────────
  function drawRoute(pathCoords, bounds) {
    if (pathCoords.length < 2) return;
    var reqCoords = pathCoords.slice(0, 25).map(function(c) { return c.join(','); }).join(';');
    var url = 'https://api.mapbox.com/directions/v5/mapbox/driving/' + reqCoords +
              '?geometries=geojson&overview=full&access_token=' + mapboxgl.accessToken;

    fetch(url)
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (data.routes && data.routes.length) {
          var route = data.routes[0].geometry;
          if (map.getSource('route')) {
            map.getSource('route').setData({ type: 'Feature', properties: {}, geometry: route });
          } else {
            map.addSource('route', { type: 'geojson', data: { type: 'Feature', properties: {}, geometry: route } });
            map.addLayer({
              id: 'route',
              type: 'line',
              source: 'route',
              layout: { 'line-join': 'round', 'line-cap': 'round' },
              paint: { 'line-color': '#0056b3', 'line-width': 5, 'line-opacity': 0.85 }
            });
          }
          var routeBounds = new mapboxgl.LngLatBounds();
          route.coordinates.forEach(function(coord) { routeBounds.extend(coord); });
          map.fitBounds(routeBounds, { padding: 60 });
          map.panBy(getPanelOffset());
        } else {
          map.fitBounds(bounds, { padding: 60 });
          map.panBy(getPanelOffset());
        }
      })
      .catch(function(err) {
        console.error("Directions API error:", err);
        map.fitBounds(bounds, { padding: 60 });
        map.panBy(getPanelOffset());
      });
  }

  // ── Init map ───────────────────────────────────────────────────────────────
  function initMap(containerId, points) {
    var el = document.getElementById(containerId);
    if (!el || typeof mapboxgl === "undefined") return null;

    mapboxgl.accessToken = window.MAPBOX_TOKEN;

    map = new mapboxgl.Map({
      container: containerId,
      style: 'mapbox://styles/mapbox/streets-v12',
      center: LAGUNA_CENTER,
      zoom: 9,
      attributionControl: false
    });

    map.addControl(new mapboxgl.NavigationControl(), 'top-right');
    map.addControl(new mapboxgl.AttributionControl({ compact: true }), 'bottom-right');
    map.addControl(new mapboxgl.GeolocateControl({
      positionOptions: { enableHighAccuracy: true },
      trackUserLocation: true,
      showUserHeading: true
    }), 'top-right');

    var pathCoords = [];
    var bounds = new mapboxgl.LngLatBounds();

    var startLatEl = document.getElementById("starting_lat");
    var startLngEl = document.getElementById("starting_lng");
    var hasStartingPoint = startLatEl && startLngEl && startLatEl.value && startLngEl.value;

    if (hasStartingPoint) {
      var startLngLat = [parseFloat(startLngEl.value), parseFloat(startLatEl.value)];
      pathCoords.push(startLngLat);
      bounds.extend(startLngLat);
      var startEl = createMarkerEl({ color: '#28a745', icon: 'ph-flag', size: 30 });
      new mapboxgl.Marker(startEl)
        .setLngLat(startLngLat)
        .setPopup(new mapboxgl.Popup({ offset: 25 }).setHTML('<strong>Starting Point</strong>'))
        .addTo(map);
    }

    if (points && points.length) {
      points.forEach(function(p, i) {
        if (p.lat == null || p.lng == null) return;
        var ll = [parseFloat(p.lng), parseFloat(p.lat)];
        pathCoords.push(ll);
        bounds.extend(ll);
        var style = getCategoryStyle(p.category_name);
        var mEl = createMarkerEl({ color: style.color, label: i + 1, size: 30 });
        var popup = new mapboxgl.Popup({ offset: 25, maxWidth: '240px' })
          .setHTML(buildStopPopup(p, i));
        new mapboxgl.Marker(mEl).setLngLat(ll).setPopup(popup).addTo(map);
        markers.push({ marker: mEl, ll: ll });
      });
    } else if (!hasStartingPoint) {
      new mapboxgl.Marker().setLngLat(LAGUNA_CENTER).addTo(map);
    }

    map.on('load', function() {
      if (pathCoords.length > 1) {
        drawRoute(pathCoords, bounds);
      } else if (pathCoords.length === 1) {
        map.setCenter(pathCoords[0]);
        map.setZoom(13);
        map.panBy(getPanelOffset());
      } else {
        map.panBy(getPanelOffset());
      }

      // Draw unselected spots as small category-colored dots
      if (window.LTCATO_ALL_SPOTS && window.LTCATO_ALL_SPOTS.length) {
        window.LTCATO_ALL_SPOTS.forEach(function(s) {
          var cb = document.querySelector(".spot-checkbox[value='" + s.id + "']");
          if (cb && cb.checked) return; // skip selected spots (already drawn above)

          var style = getCategoryStyle(s.category_name);
          var dotEl = document.createElement('div');
          dotEl.className = 'all-spots-marker';
          dotEl.style.cssText = 'width:12px;height:12px;border-radius:50%;background:' + style.color +
            ';border:2px solid white;box-shadow:0 1px 3px rgba(0,0,0,0.3);cursor:pointer;opacity:0.75';
          dotEl.title = s.name;

          var popup = new mapboxgl.Popup({ offset: 10, maxWidth: '240px' }).setHTML(buildSpotPopup(s));
          var m = new mapboxgl.Marker(dotEl).setLngLat([s.lng, s.lat]).setPopup(popup).addTo(map);

          popup.on('open', function() {
            var btn = popup.getElement().querySelector('.btn-add-spot-map');
            if (btn) {
              btn.addEventListener('click', function() {
                var cb2 = document.querySelector(".spot-checkbox[value='" + s.id + "']");
                if (cb2) {
                  cb2.checked = true;
                  var evt = document.createEvent("HTMLEvents");
                  evt.initEvent("change", false, true);
                  cb2.dispatchEvent(evt);
                  cb2.closest('.planner-spot-option').scrollIntoView({ behavior: 'smooth', block: 'center' });
                  popup.remove();
                  dotEl.style.opacity = '1';
                  dotEl.style.width = '16px';
                  dotEl.style.height = '16px';
                }
              });
            }
          });
        });
      }
    });

    return map;
  }

  // ── Panel toggle ───────────────────────────────────────────────────────────
  function setupPanelToggle() {
    var formPanel = document.getElementById("planner-form-panel");
    var resultsPanel = document.getElementById("planner-results-panel");
    var btnOpen = document.getElementById("btn-open-planner");
    var btnCloseForm = document.getElementById("btn-close-planner");
    var btnCloseResults = document.getElementById("btn-close-results");
    var btnReopen = document.getElementById("btn-reopen-results");

    if (btnCloseForm && btnOpen && formPanel) {
      btnCloseForm.addEventListener("click", function() {
        formPanel.classList.add("is-closed");
        if (resultsPanel) resultsPanel.classList.add("is-closed");
        btnOpen.classList.remove("is-hidden");
        if (map && window.innerWidth > 768) map.panBy([-getPanelOffset()[0], 0], { duration: 300 });
      });
      btnOpen.addEventListener("click", function() {
        formPanel.classList.remove("is-closed");
        if (window.HAS_PLAN && resultsPanel) resultsPanel.classList.remove("is-closed");
        btnOpen.classList.add("is-hidden");
        if (map && window.innerWidth > 768) map.panBy(getPanelOffset(), { duration: 300 });
      });
    }
    if (btnCloseResults && resultsPanel) {
      btnCloseResults.addEventListener("click", function() {
        resultsPanel.classList.add("is-closed");
        window.HAS_PLAN = false;
        if (map && window.innerWidth > 768) map.panBy([200, 0], { duration: 300 });
      });
    }
    if (btnReopen && resultsPanel) {
      btnReopen.addEventListener("click", function() {
        resultsPanel.classList.remove("is-closed");
        window.HAS_PLAN = true;
        if (map && window.innerWidth > 768) map.panBy([-200, 0], { duration: 300 });
      });
    }
  }

  // ── GPS button ─────────────────────────────────────────────────────────────
  function setupGpsButton() {
    var btn = document.getElementById("btn-use-gps");
    var inputPoint = document.getElementById("starting_point");
    var inputLat = document.getElementById("starting_lat");
    var inputLng = document.getElementById("starting_lng");
    if (!btn) return;
    btn.addEventListener("click", function() {
      if (!navigator.geolocation) { alert("Geolocation is not supported by your browser"); return; }
      btn.innerHTML = '<i class="ph ph-spinner ph-spin"></i>';
      btn.disabled = true;
      navigator.geolocation.getCurrentPosition(function(pos) {
        inputLat.value = pos.coords.latitude;
        inputLng.value = pos.coords.longitude;
        inputPoint.value = "Current Location";
        btn.innerHTML = '<i class="ph ph-check text-success"></i> GPS';
        btn.disabled = false;
      }, function() {
        alert("Unable to retrieve your location. Please check browser permissions.");
        btn.innerHTML = '<i class="ph ph-crosshair"></i> GPS';
        btn.disabled = false;
      });
    });
  }

  // ── Geocode typed starting point ───────────────────────────────────────────
  function setupStartingPointGeocoder() {
    var inputPoint = document.getElementById("starting_point");
    var inputLat = document.getElementById("starting_lat");
    var inputLng = document.getElementById("starting_lng");
    if (!inputPoint || !inputLat || !inputLng) return;

    var debounceTimer;
    inputPoint.addEventListener("input", function() {
      // Clear coords when user types manually
      inputLat.value = "";
      inputLng.value = "";
      clearTimeout(debounceTimer);
      var val = inputPoint.value.trim();
      if (val.length < 3) return;
      debounceTimer = setTimeout(function() {
        var url = 'https://api.mapbox.com/geocoding/v5/mapbox.places/' +
          encodeURIComponent(val + ' Laguna Philippines') +
          '.json?limit=1&country=PH&access_token=' + window.MAPBOX_TOKEN;
        fetch(url)
          .then(function(r) { return r.json(); })
          .then(function(data) {
            if (data.features && data.features.length) {
              var coords = data.features[0].geometry.coordinates;
              inputLng.value = coords[0];
              inputLat.value = coords[1];
            }
          })
          .catch(function() {});
      }, 600);
    });
  }

  // ── Duration hint ──────────────────────────────────────────────────────────
  function updateDurationHint() {
    var start = document.getElementById("start_date");
    var end = document.getElementById("end_date");
    var hint = document.getElementById("trip-duration-hint");
    if (!start || !end || !hint || !start.value || !end.value) return;
    var s = new Date(start.value), e = new Date(end.value);
    if (isNaN(s) || isNaN(e)) return;
    var days = Math.max(1, Math.round((e - s) / 86400000) + 1);
    hint.textContent = "Trip duration: " + days + " day" + (days !== 1 ? "s" : "") + " (auto-calculated).";
  }

  // ── Selected spots summary ─────────────────────────────────────────────────
  function updateSelectedSummary() {
    var summary = document.getElementById("selected-spots-summary");
    if (!summary) return;
    var boxes = document.querySelectorAll(".spot-checkbox:checked");
    if (!boxes.length) {
      summary.innerHTML = '<span class="text-muted small">No spots selected yet.</span>';
      updateNearbySuggestions();
      return;
    }
    var names = [];
    boxes.forEach(function(cb) { names.push(cb.getAttribute("data-name") || "Spot"); });
    summary.innerHTML = "<strong>" + boxes.length + " selected:</strong> <span class=\"small\">" + names.join(" · ") + "</span>";
    updateNearbySuggestions();
  }

  function getDistanceFromLatLonInKm(lat1, lon1, lat2, lon2) {
    var R = 6371, dLat = (lat2 - lat1) * Math.PI / 180, dLon = (lon2 - lon1) * Math.PI / 180;
    var a = Math.sin(dLat/2)*Math.sin(dLat/2) + Math.cos(lat1*Math.PI/180)*Math.cos(lat2*Math.PI/180)*Math.sin(dLon/2)*Math.sin(dLon/2);
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
  }

  function updateNearbySuggestions() {
    var container = document.getElementById("nearby-suggestions-container");
    var list = document.getElementById("nearby-suggestions-list");
    if (!container || !list) return;
    var selectedBoxes = document.querySelectorAll(".spot-checkbox:checked");
    if (!selectedBoxes.length) { container.classList.add("d-none"); return; }
    var selectedCoords = [], selectedIds = new Set();
    selectedBoxes.forEach(function(cb) {
      selectedIds.add(cb.value);
      var lat = parseFloat(cb.getAttribute("data-lat")), lng = parseFloat(cb.getAttribute("data-lng"));
      if (!isNaN(lat) && !isNaN(lng)) selectedCoords.push({ lat: lat, lng: lng });
    });
    var suggestions = [];
    if (window.LTCATO_ALL_SPOTS) {
      window.LTCATO_ALL_SPOTS.forEach(function(spot) {
        if (selectedIds.has(spot.id.toString()) || spot.lat == null || spot.lng == null) return;
        var minDist = Infinity;
        selectedCoords.forEach(function(c) {
          var d = getDistanceFromLatLonInKm(c.lat, c.lng, parseFloat(spot.lat), parseFloat(spot.lng));
          if (d < minDist) minDist = d;
        });
        if (minDist <= 5.0) suggestions.push({ spot: spot, dist: minDist });
      });
    }
    if (!suggestions.length) { container.classList.add("d-none"); return; }
    suggestions.sort(function(a, b) { return a.dist - b.dist; });
    suggestions = suggestions.slice(0, 5);
    list.innerHTML = "";
    suggestions.forEach(function(s) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn btn-sm btn-outline-primary rounded-pill";
      btn.innerHTML = '<i class="ph ph-plus"></i> ' + s.spot.name + ' <small>(' + s.dist.toFixed(1) + 'km)</small>';
      btn.onclick = function() {
        var cb = document.querySelector(".spot-checkbox[value='" + s.spot.id + "']");
        if (cb) {
          cb.checked = true;
          var evt = document.createEvent("HTMLEvents"); evt.initEvent("change", false, true); cb.dispatchEvent(evt);
          cb.closest('.planner-spot-option').scrollIntoView({ behavior: 'smooth', block: 'center' });
          var card = cb.nextElementSibling;
          var orig = card.style.backgroundColor;
          card.style.backgroundColor = '#e6f7ff';
          setTimeout(function() { card.style.backgroundColor = orig; }, 1000);
        }
      };
      list.appendChild(btn);
    });
    container.classList.remove("d-none");
  }

  // ── AJAX spot search (no page reload) ─────────────────────────────────────
  function setupAjaxSearch() {
    var filterForm = document.querySelector('.spots-filters');
    if (!filterForm) return;

    // Prevent default form submission
    filterForm.addEventListener('submit', function(e) {
      e.preventDefault();
      doAjaxSearch();
    });

    // Auto-submit on select change
    filterForm.querySelectorAll('select').forEach(function(sel) {
      sel.addEventListener('change', function() { doAjaxSearch(); });
    });

    // Debounced search on text input
    var searchInput = filterForm.querySelector('input[name="q"]');
    if (searchInput) {
      var debounce;
      searchInput.addEventListener('input', function() {
        clearTimeout(debounce);
        debounce = setTimeout(doAjaxSearch, 400);
      });
    }
  }

  function doAjaxSearch() {
    var filterForm = document.querySelector('.spots-filters');
    if (!filterForm) return;
    var params = new URLSearchParams(new FormData(filterForm));
    var url = window.location.pathname + '?' + params.toString();

    // Save current form state before fetch
    var savedState = collectFormState();

    fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function(r) { return r.text(); })
      .then(function(html) {
        var parser = new DOMParser();
        var doc = parser.parseFromString(html, 'text/html');
        var newPicker = doc.querySelector('.planner-spot-picker');
        var oldPicker = document.querySelector('.planner-spot-picker');
        if (newPicker && oldPicker) {
          oldPicker.innerHTML = newPicker.innerHTML;
          // Re-attach checkbox listeners
          oldPicker.querySelectorAll('.spot-checkbox').forEach(function(cb) {
            cb.addEventListener('change', updateSelectedSummary);
          });
          // Restore previously checked state
          restoreFormState(savedState);
          updateSelectedSummary();
        }
        // Update the spot count label
        var newTitle = doc.querySelector('.planner-form__title[data-spot-count]');
        var oldTitle = document.querySelector('.planner-form__title[data-spot-count]');
        if (newTitle && oldTitle) oldTitle.innerHTML = newTitle.innerHTML;
      })
      .catch(function(err) { console.error('Search error:', err); });
  }

  function collectFormState() {
    var state = { checked: [], title: '', start_date: '', end_date: '', departure_time: '', return_time: '',
      starting_point: '', starting_lat: '', starting_lng: '', traveler_count: '', total_budget: '',
      trip_purpose: '', pace: '' };
    document.querySelectorAll('.spot-checkbox:checked').forEach(function(cb) { state.checked.push(cb.value); });
    ['title','start_date','end_date','departure_time','return_time','starting_point',
     'starting_lat','starting_lng','traveler_count','total_budget'].forEach(function(id) {
      var el = document.getElementById(id);
      if (el) state[id] = el.value;
    });
    ['trip_purpose','pace'].forEach(function(id) {
      var el = document.getElementById(id);
      if (el) state[id] = el.value;
    });
    return state;
  }

  function restoreFormState(state) {
    if (!state) return;
    // Restore checkboxes
    state.checked.forEach(function(id) {
      var cb = document.querySelector('.spot-checkbox[value="' + id + '"]');
      if (cb) cb.checked = true;
    });
  }

  // ── Itinerary interactions (directions + nearby suggestions) ───────────────
  function setupItineraryInteractions() {
    // Get Directions buttons
    document.querySelectorAll('.get-directions-btn').forEach(function(btn) {
      btn.addEventListener('click', function() {
        var startLat = this.getAttribute('data-start-lat'), startLng = this.getAttribute('data-start-lng');
        var endLat = this.getAttribute('data-end-lat'), endLng = this.getAttribute('data-end-lng');
        var container = this.nextElementSibling;
        if (!startLat || !startLng || !endLat || !endLng) return;
        if (!container.classList.contains('d-none') && container.innerHTML.trim() !== '') {
          container.classList.add('d-none');
          this.innerHTML = '<i class="ph ph-car"></i> Get Directions';
          return;
        }
        this.innerHTML = '<i class="ph ph-spinner ph-spin"></i> Loading...';
        this.disabled = true;
        var self = this;
        var url = 'https://api.mapbox.com/directions/v5/mapbox/driving/' +
          startLng + ',' + startLat + ';' + endLng + ',' + endLat +
          '?steps=true&geometries=geojson&access_token=' + window.MAPBOX_TOKEN;
        fetch(url)
          .then(function(r) { return r.json(); })
          .then(function(data) {
            self.innerHTML = '<i class="ph ph-car"></i> Hide Directions';
            self.disabled = false;
            if (data.routes && data.routes.length > 0) {
              var route = data.routes[0];
              var steps = route.legs[0].steps;
              var html = '<strong class="text-dark">' + (route.distance/1000).toFixed(1) + ' km</strong> (' + Math.round(route.duration/60) + ' min)<br><ol class="ps-3 mt-2 mb-0">';
              steps.forEach(function(step) {
                if (step.maneuver && step.maneuver.instruction) {
                  var d = step.distance < 1000 ? Math.round(step.distance) + 'm' : (step.distance/1000).toFixed(1) + 'km';
                  html += '<li class="mb-1 pb-1 border-bottom">' + step.maneuver.instruction + ' <small class="text-muted">(' + d + ')</small></li>';
                }
              });
              html += '</ol>';
              container.innerHTML = html;
              container.classList.remove('d-none');
              if (map) {
                if (map.getSource('route-highlight')) {
                  map.getSource('route-highlight').setData(route.geometry);
                } else {
                  map.addSource('route-highlight', { type: 'geojson', data: route.geometry });
                  map.addLayer({ id: 'route-highlight', type: 'line', source: 'route-highlight',
                    layout: { 'line-join': 'round', 'line-cap': 'round' },
                    paint: { 'line-color': '#e11d48', 'line-width': 6, 'line-opacity': 0.9 } });
                }
                var b = new mapboxgl.LngLatBounds();
                route.geometry.coordinates.forEach(function(c) { b.extend(c); });
                map.fitBounds(b, { padding: 50 });
                if (window.innerWidth > 768) setTimeout(function() { map.panBy(getPanelOffset()); }, 300);
              }
            } else {
              container.innerHTML = 'No route found.';
              container.classList.remove('d-none');
            }
          })
          .catch(function(err) {
            self.innerHTML = '<i class="ph ph-warning"></i> Error';
            self.disabled = false;
            console.error("Directions Error", err);
          });
      });
    });

    // Load nearby restaurants/hotels buttons
    document.querySelectorAll('.load-suggestion-btn').forEach(function(btn) {
      btn.addEventListener('click', function() {
        var li = this.closest('.planner-stop');
        var lat = li.getAttribute('data-search-lat');
        var lng = li.getAttribute('data-search-lng');
        var type = li.getAttribute('data-suggestion-type');
        var container = this.nextElementSibling;
        if (!lat || !lng) return;
        this.innerHTML = '<i class="ph ph-spinner ph-spin"></i> Searching...';
        this.disabled = true;
        var self = this;
        var query = type === 'dining' ? 'restaurant' : 'hotel';
        var url = 'https://api.mapbox.com/geocoding/v5/mapbox.places/' + query +
          '.json?proximity=' + lng + ',' + lat + '&limit=4&country=PH&access_token=' + window.MAPBOX_TOKEN;
        fetch(url)
          .then(function(r) { return r.json(); })
          .then(function(data) {
            self.style.display = 'none';
            var placeholder = li.querySelector('.placeholder-text');
            if (placeholder) placeholder.style.display = 'none';
            if (data.features && data.features.length > 0) {
              var html = '';
              data.features.forEach(function(f, i) {
                var name = f.text;
                var address = f.place_name.replace(name + ', ', '');
                var dist = getDistanceFromLatLonInKm(parseFloat(lat), parseFloat(lng), f.geometry.coordinates[1], f.geometry.coordinates[0]);
                html += '<div class="p-2 border rounded bg-white shadow-sm">';
                html += '<strong class="text-dark">' + (i+1) + '. ' + name + '</strong> <small class="text-muted">(' + dist.toFixed(1) + 'km away)</small><br>';
                html += '<small class="text-muted"><i class="ph ph-map-pin"></i> ' + address + '</small>';
                html += '</div>';
                if (map) {
                  var color = type === 'dining' ? '#ffc107' : '#0dcaf0';
                  var icon = type === 'dining' ? 'ph-fork-knife' : 'ph-bed';
                  var mEl = createMarkerEl({ color: color, icon: icon, size: 26 });
                  var popup = new mapboxgl.Popup({ offset: 25 }).setHTML('<strong>' + name + '</strong><br><small>' + address + '</small>');
                  new mapboxgl.Marker(mEl).setLngLat(f.geometry.coordinates).setPopup(popup).addTo(map);
                }
              });
              container.innerHTML = html;
              container.classList.remove('d-none');
              if (map) {
                map.flyTo({ center: [parseFloat(lng), parseFloat(lat)], zoom: 14 });
                if (window.innerWidth > 768) setTimeout(function() { map.panBy(getPanelOffset()); }, 500);
              }
            } else {
              container.innerHTML = '<span class="small text-muted">No places found nearby.</span>';
              container.classList.remove('d-none');
            }
          })
          .catch(function(err) {
            self.innerHTML = '<i class="ph ph-warning"></i> Error searching';
            self.disabled = false;
            console.error("Geocoding Error", err);
          });
      });
    });
  }

  // ── Starting point required validation ────────────────────────────────────
  function setupStartingPointValidation() {
    var form = document.getElementById('planner-form');
    var inputPoint = document.getElementById('starting_point');
    var inputLat = document.getElementById('starting_lat');
    var inputLng = document.getElementById('starting_lng');
    if (!form || !inputPoint) return;

    form.addEventListener('submit', function(e) {
      var val = inputPoint.value.trim();
      if (!val) {
        e.preventDefault();
        inputPoint.classList.add('is-invalid');
        var feedback = inputPoint.parentElement.querySelector('.invalid-feedback');
        if (!feedback) {
          feedback = document.createElement('div');
          feedback.className = 'invalid-feedback';
          feedback.textContent = 'Please enter a starting point (e.g. Calamba, SLEX exit).';
          inputPoint.parentElement.appendChild(feedback);
        }
        inputPoint.focus();
        return;
      }
      inputPoint.classList.remove('is-invalid');
      // If user typed something but no coords were geocoded yet, try to geocode synchronously
      // (we already debounce on input, so coords should be set; if not, warn but allow)
    });

    inputPoint.addEventListener('input', function() {
      if (inputPoint.value.trim()) inputPoint.classList.remove('is-invalid');
    });
  }

  // ── DOMContentLoaded ───────────────────────────────────────────────────────
  document.addEventListener("DOMContentLoaded", function() {
    var points = window.LTCATO_PLANNER_MAP || [];
    initMap("planner-route-map", points);
    setupGpsButton();
    setupStartingPointGeocoder();
    setupStartingPointValidation();
    setupPanelToggle();
    setupAjaxSearch();
    setupItineraryInteractions();

    ["start_date", "end_date"].forEach(function(id) {
      var el = document.getElementById(id);
      if (el) el.addEventListener("change", updateDurationHint);
    });
    updateDurationHint();

    document.querySelectorAll(".spot-checkbox").forEach(function(cb) {
      cb.addEventListener("change", updateSelectedSummary);
    });
    updateSelectedSummary();
  });

})();
