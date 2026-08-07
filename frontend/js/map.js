/**
 * Smart Community Platform - Leaflet Map Logic
 * Custom circle markers, location picker, reverse geocoding, auto-refresh.
 */

const MapManager = {
  map: null,
  markers: {},
  markerLayer: null,
  selectedLocation: null,
  userLocationMarker: null,
  _pickerActive: false,
  _pickerMarker: null,
  _refreshTimer: null,
  _geocodeTimeout: null,

  init(containerId, options) {
    options = options || {};
    const el = document.getElementById(containerId);
    if (!el) return null;
    this.map = L.map(containerId, {
      center: [options.lat || CONFIG.MAP_DEFAULT_LAT, options.lng || CONFIG.MAP_DEFAULT_LNG],
      zoom: options.zoom || CONFIG.MAP_DEFAULT_ZOOM,
      zoomControl: false,
      attributionControl: true
    });

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    }).addTo(this.map);

    L.control.zoom({ position: "bottomright" }).addTo(this.map);
    L.control.scale({ position: "bottomleft", imperial: false }).addTo(this.map);

    this.markerLayer = L.layerGroup().addTo(this.map);
    return this.map;
  },

  setView(lat, lng, zoom) {
    if (!this.map) return;
    this.map.flyTo([lat, lng], zoom || 15, { duration: 1 });
  },

  getUserLocation() {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) { reject(new Error("Geolocation is not supported by your browser.")); return; }
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const lat = pos.coords.latitude;
          const lng = pos.coords.longitude;
          if (this.map) {
            this.map.flyTo([lat, lng], 15, { duration: 1.2 });
            if (this.userLocationMarker) this.map.removeLayer(this.userLocationMarker);
            this.userLocationMarker = L.circleMarker([lat, lng], {
              radius: 8, fillColor: "#3B82F6", fillOpacity: 1, color: "#fff", weight: 3, className: "user-location-pulse"
            }).addTo(this.map).bindPopup("You are here");
          }
          resolve({ lat, lng });
        },
        (err) => {
          const msgs = { 1: "Location access denied. Please enable location in your browser settings.", 2: "Unable to determine your location.", 3: "Location request timed out." };
          reject(new Error(msgs[err.code] || "Unable to get your location."));
        },
        { enableHighAccuracy: true, timeout: 10000 }
      );
    });
  },

  /* ---------- Marker Management ---------- */
  createCustomMarker(issue) {
    const color = CONFIG.STATUS_COLORS[issue.status] || "#6B7280";
    const isCritical = issue.priority === "critical";
    const radius = isCritical ? 12 : 9;
    const marker = L.circleMarker([issue.location_lat, issue.location_lng], {
      radius: radius,
      fillColor: color,
      fillOpacity: 0.9,
      color: "#fff",
      weight: 3,
      className: isCritical ? "marker-critical-pulse" : ""
    });
    marker._issueData = issue;

    marker.on("mouseover", function () { this.setRadius(radius + 4); });
    marker.on("mouseout", function () { this.setRadius(radius); });
    marker.bindPopup(() => MapManager.createMarkerPopup(issue), { maxWidth: 280, className: "issue-popup" });

    return marker;
  },

  async loadMarkers(filters) {
    filters = filters || {};
    try {
      const data = await IssuesAPI.getMapMarkers(filters);
      this.markerLayer.clearLayers();
      this.markers = {};
      const list = Array.isArray(data) ? data : (data.markers || []);
      list.forEach((issue) => {
        if (!issue.location_lat || !issue.location_lng) return;
        const marker = this.createCustomMarker(issue);
        marker.addTo(this.markerLayer);
        this.markers[issue.uuid] = marker;
      });
    } catch (_) { /* silent fail for map markers */ }
  },

  createMarkerPopup(issue) {
    const status = renderStatusBadge(issue.status);
    const priority = renderPriorityBadge(issue.priority);
    return (
      '<div class="map-popup">' +
      '<div class="map-popup-header">' + status + ' ' + priority + '</div>' +
      '<h6 class="map-popup-title">' + escapeHtml(issue.title) + '</h6>' +
      '<div class="map-popup-meta">' +
      '<span><i class="bi bi-hand-thumbs-up"></i> ' + (issue.vote_count || 0) + '</span>' +
      '<span><i class="bi bi-clock"></i> ' + renderTimeAgo(issue.created_at) + '</span>' +
      '</div>' +
      '<a href="issue.html?uuid=' + issue.uuid + '" class="btn btn-sm btn-primary w-100 mt-2">View Details <i class="bi bi-arrow-right"></i></a>' +
      '</div>'
    );
  },

  highlightMarker(uuid) {
    const m = this.markers[uuid];
    if (!m) return;
    m.bringToFront();
    const origRadius = m.getRadius();
    m.setRadius(origRadius + 6);
    m.openPopup();
    setTimeout(() => m.setRadius(origRadius), 2000);
  },

  startAutoRefresh(filters) {
    this.stopAutoRefresh();
    this._refreshTimer = setInterval(() => this.loadMarkers(filters), CONFIG.MAP_REFRESH_INTERVAL_MS);
  },

  stopAutoRefresh() {
    if (this._refreshTimer) { clearInterval(this._refreshTimer); this._refreshTimer = null; }
  },

  /* ---------- Location Picker ---------- */
  enableLocationPicker() {
    if (!this.map) return;
    this._pickerActive = true;
    this.map.getContainer().style.cursor = "crosshair";

    const tip = document.getElementById("map-picker-tip");
    if (tip) tip.style.display = "block";

    this.map.on("click", this._onPickerClick, this);
  },

  disableLocationPicker() {
    if (!this.map) return;
    this._pickerActive = false;
    this.map.getContainer().style.cursor = "";
    this.map.off("click", this._onPickerClick, this);

    const tip = document.getElementById("map-picker-tip");
    if (tip) tip.style.display = "none";

    if (this._pickerMarker) { this.map.removeLayer(this._pickerMarker); this._pickerMarker = null; }
    this.selectedLocation = null;
  },

  _onPickerClick(e) {
    const { lat, lng } = e.latlng;
    this.selectedLocation = { lat, lng, address: "" };

    if (this._pickerMarker) {
      this._pickerMarker.setLatLng([lat, lng]);
    } else {
      this._pickerMarker = L.marker([lat, lng], {
        draggable: true,
        icon: L.divIcon({ className: "picker-marker-icon", html: '<i class="bi bi-geo-alt-fill"></i>', iconSize: [30, 40], iconAnchor: [15, 40] })
      }).addTo(this.map);
      this._pickerMarker.on("dragend", () => {
        const pos = this._pickerMarker.getLatLng();
        this.selectedLocation = { lat: pos.lat, lng: pos.lng, address: "" };
        this._updatePickerDisplay(pos.lat, pos.lng);
        this._reverseGeocodePicker(pos.lat, pos.lng);
      });
    }

    this._updatePickerDisplay(lat, lng);
    this._reverseGeocodePicker(lat, lng);
  },

  _updatePickerDisplay(lat, lng) {
    const coordsEl = document.getElementById("selected-coords");
    if (coordsEl) coordsEl.textContent = lat.toFixed(6) + ", " + lng.toFixed(6);
    const latEl = document.getElementById("issue-lat");
    const lngEl = document.getElementById("issue-lng");
    if (latEl) latEl.value = lat;
    if (lngEl) lngEl.value = lng;
  },

  _reverseGeocodePicker(lat, lng) {
    clearTimeout(this._geocodeTimeout);
    this._geocodeTimeout = setTimeout(() => {
      this.reverseGeocode(lat, lng).then((addr) => {
        if (this.selectedLocation) this.selectedLocation.address = addr;
        const addrEl = document.getElementById("issue-address");
        if (addrEl && addr) addrEl.value = addr;
      });
    }, 500);
  },

  async reverseGeocode(lat, lng) {
    try {
      const resp = await fetch(
        "https://nominatim.openstreetmap.org/reverse?lat=" + lat + "&lon=" + lng + "&format=json&addressdetails=1",
        { headers: { "Accept-Language": "en" } }
      );
      const data = await resp.json();
      return data.display_name || "Location selected";
    } catch (_) {
      return "Location selected";
    }
  },

  getSelectedLocation() {
    return this.selectedLocation;
  },

  /* ---------- Filter helpers ---------- */
  filterMarkersByStatus(status) {
    Object.values(this.markers).forEach((m) => {
      if (!status || m._issueData.status === status) {
        if (!this.markerLayer.hasLayer(m)) this.markerLayer.addLayer(m);
      } else {
        this.markerLayer.removeLayer(m);
      }
    });
  },

  filterMarkersByCategory(category) {
    Object.values(this.markers).forEach((m) => {
      if (!category || m._issueData.category === category) {
        if (!this.markerLayer.hasLayer(m)) this.markerLayer.addLayer(m);
      } else {
        this.markerLayer.removeLayer(m);
      }
    });
  },

  showAllMarkers() {
    Object.values(this.markers).forEach((m) => {
      if (!this.markerLayer.hasLayer(m)) this.markerLayer.addLayer(m);
    });
  }
};
