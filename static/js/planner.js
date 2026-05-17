(function () {
  "use strict";

  var LAGUNA_CENTER = [121.4119, 14.2691]; // Mapbox uses [lng, lat]
  var map;
  var markers = [];

  function getPanelOffset() {
    var offset = 0;
    if (window.innerWidth <= 768) return [0, 0];
    
    var formOpen = !document.getElementById('planner-form-panel').classList.contains('is-closed');
    var resultsPanel = document.getElementById('planner-results-panel');
    var resultsOpen = window.HAS_PLAN && resultsPanel && !resultsPanel.classList.contains('is-closed');
    
    // Panel width is 380px for form, 400px for results
    var totalWidth = 0;
    if (formOpen) totalWidth += 380;
    if (resultsOpen) totalWidth += 400;
    
    // Mapbox panning takes half the offset
    return [- (totalWidth / 2), 0];
  }

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

    var geolocate = new mapboxgl.GeolocateControl({
      positionOptions: { enableHighAccuracy: true },
      trackUserLocation: true,
      showUserHeading: true
    });
    map.addControl(geolocate, 'top-right');

    var pathCoords = [];
    var bounds = new mapboxgl.LngLatBounds();

    var startLat = document.getElementById("starting_lat");
    var startLng = document.getElementById("starting_lng");
    var hasStartingPoint = startLat && startLng && startLat.value && startLng.value;

    if (hasStartingPoint) {
        var startLngLat = [parseFloat(startLng.value), parseFloat(startLat.value)];
        pathCoords.push(startLngLat);
        bounds.extend(startLngLat);
        
        // Green marker for start
        var startEl = document.createElement('div');
        startEl.className = 'marker';
        startEl.style.backgroundColor = '#28a745';
        startEl.style.color = 'white';
        startEl.style.width = '24px';
        startEl.style.height = '24px';
        startEl.style.borderRadius = '50%';
        startEl.style.textAlign = 'center';
        startEl.style.lineHeight = '24px';
        startEl.style.fontSize = '12px';
        startEl.style.fontWeight = 'bold';
        startEl.style.boxShadow = '0 2px 4px rgba(0,0,0,0.3)';
        startEl.innerHTML = '<i class="ph ph-flag"></i>';

        new mapboxgl.Marker(startEl)
            .setLngLat(startLngLat)
            .setPopup(new mapboxgl.Popup({ offset: 25 }).setHTML("<strong>Starting Point</strong>"))
            .addTo(map);
    }

    if (points && points.length) {
      points.forEach(function (p, i) {
        if (p.lat == null || p.lng == null) return;
        var ll = [parseFloat(p.lng), parseFloat(p.lat)];
        pathCoords.push(ll);
        bounds.extend(ll);

        var popup = new mapboxgl.Popup({ offset: 25 })
            .setHTML("<strong>" + (i + 1) + ". " + (p.name || "Stop") + "</strong>");

        var mEl = document.createElement('div');
        mEl.className = 'marker';
        mEl.style.backgroundColor = '#0056b3';
        mEl.style.color = 'white';
        mEl.style.width = '24px';
        mEl.style.height = '24px';
        mEl.style.borderRadius = '50%';
        mEl.style.textAlign = 'center';
        mEl.style.lineHeight = '24px';
        mEl.style.fontSize = '12px';
        mEl.style.fontWeight = 'bold';
        mEl.style.boxShadow = '0 2px 4px rgba(0,0,0,0.3)';
        mEl.textContent = i + 1;

        var marker = new mapboxgl.Marker(mEl)
          .setLngLat(ll)
          .setPopup(popup)
          .addTo(map);
        markers.push(marker);
      });
    } else if (!hasStartingPoint) {
      // Just Laguna Center if nothing is selected
      new mapboxgl.Marker().setLngLat(LAGUNA_CENTER).addTo(map);
    }

    map.on('load', function() {
        var offset = getPanelOffset();
        
        if (pathCoords.length > 1) {
            // Fetch Directions from Mapbox
            // Limit 25 coords. For very long itineraries, we slice it.
            var reqCoords = pathCoords.slice(0, 25).map(c => c.join(',')).join(';');
            var url = 'https://api.mapbox.com/directions/v5/mapbox/driving/' + reqCoords + '?geometries=geojson&access_token=' + mapboxgl.accessToken;
            
            fetch(url)
              .then(res => res.json())
              .then(data => {
                  if (data.routes && data.routes.length) {
                      var route = data.routes[0].geometry;
                      map.addSource('route', {
                          'type': 'geojson',
                          'data': {
                              'type': 'Feature',
                              'properties': {},
                              'geometry': route
                          }
                      });
                      map.addLayer({
                          'id': 'route',
                          'type': 'line',
                          'source': 'route',
                          'layout': {
                              'line-join': 'round',
                              'line-cap': 'round'
                          },
                          'paint': {
                              'line-color': '#0056b3',
                              'line-width': 5,
                              'line-opacity': 0.8
                          }
                      });
                      
                      // Fit to the actual route geometry bounds
                      var routeBounds = new mapboxgl.LngLatBounds();
                      route.coordinates.forEach(function(coord) {
                          routeBounds.extend(coord);
                      });
                      map.fitBounds(routeBounds, { padding: 50 });
                      map.panBy(offset);
                  } else {
                      // Fallback to fitting point bounds if routing fails
                      map.fitBounds(bounds, { padding: 50 });
                      map.panBy(offset);
                  }
              })
              .catch(err => {
                  console.error("Directions API error:", err);
                  map.fitBounds(bounds, { padding: 50 });
                  map.panBy(offset);
              });
        } else if (pathCoords.length === 1) {
            map.setCenter(pathCoords[0]);
            map.setZoom(13);
            map.panBy(offset);
        } else {
            map.panBy(offset);
        }
        
        // Draw unselected spots as small gray markers
        if (window.LTCATO_ALL_SPOTS && window.LTCATO_ALL_SPOTS.length) {
          window.LTCATO_ALL_SPOTS.forEach(function(s) {
              var isSelected = false;
              var cb = document.querySelector(".spot-checkbox[value='" + s.id + "']");
              if (cb) {
                  isSelected = cb.checked;
              }
              
              if (!isSelected) {
                  var el = document.createElement('div');
                  el.className = 'all-spots-marker';
                  el.style.width = '14px';
                  el.style.height = '14px';
                  el.style.borderRadius = '50%';
                  el.style.backgroundColor = '#6c757d'; // gray
                  el.style.border = '2px solid white';
                  el.style.boxShadow = '0 1px 3px rgba(0,0,0,0.3)';
                  el.style.cursor = 'pointer';
                  el.title = s.name;
                  
                  var popupHTML = "<strong>" + s.name + "</strong><br>" + 
                    "<small>" + s.category_name + "</small><br>" +
                    "<button class='btn btn-sm btn-primary mt-2 w-100 btn-add-spot-map' data-id='" + s.id + "'>" + 
                    "Add to Plan" + 
                    "</button>";

                  var popup = new mapboxgl.Popup({ offset: 10 }).setHTML(popupHTML);
                  
                  new mapboxgl.Marker(el)
                      .setLngLat([s.lng, s.lat])
                      .setPopup(popup)
                      .addTo(map);
                  
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
                              el.style.backgroundColor = '#0056b3'; // turn blue to indicate selected
                           }
                        });
                     }
                  });
              }
          });
        }
    });

    return map;
  }

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
        
        if (map && window.innerWidth > 768) {
          // If closing everything, pan map back to center
          var currentOffset = getPanelOffset()[0]; 
          map.panBy([-currentOffset, 0], { duration: 300 }); 
        }
      });

      btnOpen.addEventListener("click", function() {
        formPanel.classList.remove("is-closed");
        if (window.HAS_PLAN && resultsPanel) resultsPanel.classList.remove("is-closed");
        btnOpen.classList.add("is-hidden");
        
        if (map && window.innerWidth > 768) {
          map.panBy(getPanelOffset(), { duration: 300 });
        }
      });
    }
    
    if (btnCloseResults && resultsPanel) {
      btnCloseResults.addEventListener("click", function() {
        resultsPanel.classList.add("is-closed");
        window.HAS_PLAN = false; // State changed
        if (map && window.innerWidth > 768) {
           // We just removed the 400px panel, shift map 200px right
           map.panBy([200, 0], { duration: 300 });
        }
      });
    }
    
    if (btnReopen && resultsPanel) {
      btnReopen.addEventListener("click", function() {
        resultsPanel.classList.remove("is-closed");
        window.HAS_PLAN = true; // State changed
        if (map && window.innerWidth > 768) {
           // We just added the 400px panel, shift map 200px left
           map.panBy([-200, 0], { duration: 300 });
        }
      });
    }
  }

  function setupGpsButton() {
    var btn = document.getElementById("btn-use-gps");
    var inputPoint = document.getElementById("starting_point");
    var inputLat = document.getElementById("starting_lat");
    var inputLng = document.getElementById("starting_lng");

    if (btn) {
      btn.addEventListener("click", function() {
        if (!navigator.geolocation) {
          alert("Geolocation is not supported by your browser");
          return;
        }
        btn.innerHTML = '<i class="ph ph-spinner ph-spin"></i>';
        btn.disabled = true;

        navigator.geolocation.getCurrentPosition(function(position) {
          inputLat.value = position.coords.latitude;
          inputLng.value = position.coords.longitude;
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
      updateNearbySuggestions();
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
    
    updateNearbySuggestions();
  }

  // Haversine formula
  function getDistanceFromLatLonInKm(lat1, lon1, lat2, lon2) {
    var R = 6371;
    var dLat = (lat2 - lat1) * (Math.PI / 180);
    var dLon = (lon2 - lon1) * (Math.PI / 180);
    var a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(lat1 * (Math.PI / 180)) * Math.cos(lat2 * (Math.PI / 180)) *
      Math.sin(dLon / 2) * Math.sin(dLon / 2);
    var c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
  }

  function updateNearbySuggestions() {
    var container = document.getElementById("nearby-suggestions-container");
    var list = document.getElementById("nearby-suggestions-list");
    if (!container || !list || !window.LTCATO_PLANNER_MAP) return;

    var selectedBoxes = document.querySelectorAll(".spot-checkbox:checked");
    if (selectedBoxes.length === 0) {
      container.classList.add("d-none");
      return;
    }

    var selectedCoords = [];
    var selectedIds = new Set();
    selectedBoxes.forEach(function(cb) {
      selectedIds.add(cb.value);
      var lat = parseFloat(cb.getAttribute("data-lat"));
      var lng = parseFloat(cb.getAttribute("data-lng"));
      if (!isNaN(lat) && !isNaN(lng)) {
        selectedCoords.push({ lat: lat, lng: lng });
      }
    });

    var suggestions = [];
    if (window.LTCATO_ALL_SPOTS) {
        window.LTCATO_ALL_SPOTS.forEach(function(spot) {
          if (selectedIds.has(spot.id.toString()) || spot.lat == null || spot.lng == null) return;
          
          var minDistance = Infinity;
          selectedCoords.forEach(function(coord) {
            var d = getDistanceFromLatLonInKm(coord.lat, coord.lng, parseFloat(spot.lat), parseFloat(spot.lng));
            if (d < minDistance) minDistance = d;
          });

          if (minDistance <= 5.0) { // Within 5km
            suggestions.push({ spot: spot, dist: minDistance });
          }
        });
    }

    if (suggestions.length === 0) {
      container.classList.add("d-none");
      return;
    }

    suggestions.sort(function(a, b) { return a.dist - b.dist; });
    suggestions = suggestions.slice(0, 5); // Top 5 closest

    list.innerHTML = "";
    suggestions.forEach(function(s) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn btn-sm btn-outline-primary rounded-pill";
      btn.innerHTML = '<i class="ph ph-plus"></i> ' + s.spot.name + " <small>(" + s.dist.toFixed(1) + "km)</small>";
      btn.onclick = function() {
        var cb = document.querySelector(".spot-checkbox[value='" + s.spot.id + "']");
        if (cb) {
          cb.checked = true;
          // Trigger change event to update summary
          var evt = document.createEvent("HTMLEvents");
          evt.initEvent("change", false, true);
          cb.dispatchEvent(evt);
          
          // Flash effect
          cb.closest('.planner-spot-option').scrollIntoView({ behavior: 'smooth', block: 'center' });
          var card = cb.nextElementSibling;
          var originalBg = card.style.backgroundColor;
          card.style.backgroundColor = '#e6f7ff';
          setTimeout(function() { card.style.backgroundColor = originalBg; }, 1000);
        }
      };
      list.appendChild(btn);
    });
    container.classList.remove("d-none");
  }

  function setupItineraryInteractions() {
    // 1. Get Directions Buttons
    document.querySelectorAll('.get-directions-btn').forEach(function(btn) {
      btn.addEventListener('click', function() {
        var startLat = this.getAttribute('data-start-lat');
        var startLng = this.getAttribute('data-start-lng');
        var endLat = this.getAttribute('data-end-lat');
        var endLng = this.getAttribute('data-end-lng');
        var container = this.nextElementSibling;
        
        if (!startLat || !startLng || !endLat || !endLng) return;
        
        if (!container.classList.contains('d-none') && container.innerHTML.trim() !== '') {
          container.classList.add('d-none'); // Toggle off
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
          .then(res => res.json())
          .then(data => {
            self.innerHTML = '<i class="ph ph-car"></i> Hide Directions';
            self.disabled = false;
            
            if (data.routes && data.routes.length > 0) {
              var route = data.routes[0];
              var steps = route.legs[0].steps;
              var html = '<strong class="text-dark">' + (route.distance / 1000).toFixed(1) + ' km</strong> (' + Math.round(route.duration / 60) + ' min)<br><ol class="ps-3 mt-2 mb-0">';
              
              steps.forEach(function(step) {
                if (step.maneuver && step.maneuver.instruction) {
                  var distStr = step.distance < 1000 ? Math.round(step.distance) + 'm' : (step.distance/1000).toFixed(1) + 'km';
                  html += '<li class="mb-1 pb-1 border-bottom">' + step.maneuver.instruction + ' <small class="text-muted">(' + distStr + ')</small></li>';
                }
              });
              html += '</ol>';
              container.innerHTML = html;
              container.classList.remove('d-none');
              
              if (map) {
                  if (map.getSource('route-highlight')) {
                      map.getSource('route-highlight').setData(route.geometry);
                  } else {
                      map.addSource('route-highlight', {
                          'type': 'geojson',
                          'data': route.geometry
                      });
                      map.addLayer({
                          'id': 'route-highlight',
                          'type': 'line',
                          'source': 'route-highlight',
                          'layout': { 'line-join': 'round', 'line-cap': 'round' },
                          'paint': { 'line-color': '#e11d48', 'line-width': 6, 'line-opacity': 0.9 }
                      });
                  }
                  
                  var bounds = new mapboxgl.LngLatBounds();
                  route.geometry.coordinates.forEach(c => bounds.extend(c));
                  map.fitBounds(bounds, { padding: 50 });
                  if (window.innerWidth > 768) setTimeout(() => map.panBy(getPanelOffset()), 300);
              }
            } else {
              container.innerHTML = 'No route found.';
              container.classList.remove('d-none');
            }
          })
          .catch(err => {
            self.innerHTML = '<i class="ph ph-warning"></i> Error';
            self.disabled = false;
            console.error("Directions Error", err);
          });
      });
    });

    // 2. Load Suggestions Buttons
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
        var url = 'https://api.mapbox.com/geocoding/v5/mapbox.places/' + query + '.json?proximity=' + lng + ',' + lat + '&limit=3&access_token=' + window.MAPBOX_TOKEN;

        fetch(url)
          .then(res => res.json())
          .then(data => {
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
                  var mEl = document.createElement('div');
                  mEl.className = 'marker';
                  mEl.style.backgroundColor = type === 'dining' ? '#ffc107' : '#0dcaf0';
                  mEl.style.color = '#000';
                  mEl.style.width = '24px';
                  mEl.style.height = '24px';
                  mEl.style.borderRadius = '50%';
                  mEl.style.textAlign = 'center';
                  mEl.style.lineHeight = '24px';
                  mEl.style.fontSize = '12px';
                  mEl.style.boxShadow = '0 2px 4px rgba(0,0,0,0.3)';
                  mEl.innerHTML = type === 'dining' ? '<i class="ph ph-fork-knife"></i>' : '<i class="ph ph-bed"></i>';

                  var popup = new mapboxgl.Popup({ offset: 25 }).setHTML("<strong>" + name + "</strong><br><small>" + address + "</small>");
                  new mapboxgl.Marker(mEl).setLngLat(f.geometry.coordinates).setPopup(popup).addTo(map);
                }
              });
              container.innerHTML = html;
              container.classList.remove('d-none');
              
              if (map) {
                  map.flyTo({ center: [parseFloat(lng), parseFloat(lat)], zoom: 14 });
                  if (window.innerWidth > 768) setTimeout(() => map.panBy(getPanelOffset()), 500);
              }
            } else {
              container.innerHTML = '<span class="small text-muted">No places found nearby on Mapbox.</span>';
              container.classList.remove('d-none');
            }
          })
          .catch(err => {
            self.innerHTML = '<i class="ph ph-warning"></i> Error searching';
            self.disabled = false;
            console.error("Geocoding Error", err);
          });
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var points = window.LTCATO_PLANNER_MAP || [];
    initMap("planner-route-map", points);
    setupGpsButton();
    setupPanelToggle();
    setupItineraryInteractions();

    ["start_date", "end_date"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.addEventListener("change", updateDurationHint);
    });
    updateDurationHint();

    document.querySelectorAll(".spot-checkbox").forEach(function (cb) {
      cb.addEventListener("change", updateSelectedSummary);
    });
    updateSelectedSummary();
  });
})();
