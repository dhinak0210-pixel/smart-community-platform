/**
 * Leaflet Map Integration Module
 */

let map = null;
let markersGroup = null;

const MapManager = {
  initMap(containerId = 'map') {
    if (!document.getElementById(containerId)) return;

    map = L.map(containerId).setView(CONFIG.DEFAULT_MAP_CENTER, CONFIG.DEFAULT_MAP_ZOOM);

    // OpenStreetMap dark layer tiles
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; OpenStreetMap &copy; CARTO',
      maxZoom: 19,
    }).addTo(map);

    markersGroup = L.layerGroup().addTo(map);

    // Map click fills lat/lng in report issue form
    map.on('click', (e) => {
      const latInput = document.getElementById('issueLat');
      const lngInput = document.getElementById('issueLng');
      if (latInput && lngInput) {
        latInput.value = e.latlng.lat.toFixed(6);
        lngInput.value = e.latlng.lng.toFixed(6);
      }
    });
  },

  renderIssueMarkers(issues) {
    if (!markersGroup) return;
    markersGroup.clearLayers();

    issues.forEach(issue => {
      if (issue.latitude && issue.longitude) {
        const marker = L.marker([issue.latitude, issue.longitude]);
        const popupContent = `
          <div style="color:#0f172a; max-width:200px;">
            <h6 style="margin:0 0 5px; font-weight:700;">${issue.title}</h6>
            <p style="margin:0 0 5px; font-size:0.8rem; color:#475569;">${issue.description.substring(0, 75)}...</p>
            <span class="badge badge-${issue.status}">${issue.status.replace('_', ' ')}</span>
          </div>
        `;
        marker.bindPopup(popupContent);
        markersGroup.addLayer(marker);
      }
    });
  }
};
