/**
 * Common JavaScript functionality for the sensors application
 * 
 * Configuration:
 * -------------
 * To enable debugging, set debug: true in commonConfig below
 * Debug mode will:
 * - Show initialization logs for map systems
 * - Log marker processing details
 * - Show detailed state changes
 */

// System Configuration
const commonConfig = {
    debug: false,            // Set to true to enable debug mode
    logMarkerChanges: true, // Log marker additions and changes
    logMapEvents: true      // Log map initialization and updates
};

// Global state
if (typeof window.currentPlaceSlug === 'undefined') {
    window.currentPlaceSlug = null;
}

// Map Initialization
function initializeLocationMap(options = {}) {
    const {
        mapId = 'preview-map',
        latInputId,
        lonInputId,
        initialLat = 30.26715,
        initialLon = -97.74306,
        zoom = 13
    } = options;

    const map = L.map(mapId).setView([initialLat, initialLon], zoom);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    let marker = L.marker([initialLat, initialLon], {
        draggable: true,
        title: 'Drag me or click anywhere on the map!'
    }).addTo(map);

    if (latInputId && lonInputId) {
        const latInput = document.getElementById(latInputId);
        const lonInput = document.getElementById(lonInputId);

        function updateMarker() {
            const lat = parseFloat(latInput.value) || initialLat;
            const lon = parseFloat(lonInput.value) || initialLon;
            marker.setLatLng([lat, lon]);
            map.setView([lat, lon], zoom);
        }

        if (latInput && lonInput) {
            if (latInput.value && lonInput.value) {
                updateMarker();
            }

            latInput.addEventListener('input', updateMarker);
            lonInput.addEventListener('input', updateMarker);

            map.on('click', function(e) {
                const lat = e.latlng.lat.toFixed(5);
                const lng = e.latlng.lng.toFixed(5);
                latInput.value = lat;
                lonInput.value = lng;
                updateMarker();
            });

            marker.on('dragend', function(e) {
                const position = e.target.getLatLng();
                const lat = position.lat.toFixed(5);
                const lng = position.lng.toFixed(5);
                latInput.value = lat;
                lonInput.value = lng;
            });
        }
    }

    return { map, marker };
}

// Folium Map Marker System
const foliumMarkerSystem = {
    initialize() {
        if (!commonConfig.debug) return this.initializeQuiet();
        
        console.group('Folium Marker System');
        
        // Find the map container using attribute selector
        const mapContainer = document.querySelector('div[id^="places_overview_map_"]');
        if (!mapContainer) {
            console.log('No Folium map found on this page');
            console.groupEnd();
            return;
        }

        if (!mapContainer._leaflet_id) {
            console.log('Leaflet not initialized on map');
            console.groupEnd();
            return;
        }

        // Start observing the marker pane
        const markerPane = document.querySelector('.leaflet-marker-pane');
        if (!markerPane) {
            console.log('No marker pane found');
            console.groupEnd();
            return;
        }

        console.log('Setting up marker observer');
        this.setupMarkerObserver(markerPane);
        console.groupEnd();
    },

    // Silent initialization when debug is off
    initializeQuiet() {
        const mapContainer = document.querySelector('div[id^="places_overview_map_"]');
        if (!mapContainer || !mapContainer._leaflet_id) return;
        
        const markerPane = document.querySelector('.leaflet-marker-pane');
        if (!markerPane) return;
        
        this.setupMarkerObserver(markerPane);
    },

    setupMarkerObserver(markerPane) {
        // Process marker function
        function processMarker(node) {
            if (!node.classList) return;
            
            // Match any class containing 'marker'
            const classes = Array.from(node.classList);
            const isMarker = classes.some(cls => 
                cls.includes('marker') || 
                cls.includes('Marker')
            );
            
            if (isMarker) {
                // Add our custom class if not already present
                if (!node.classList.contains('place-marker')) {
                    node.classList.add('place-marker');
                }
                
                // Add Bootstrap utility classes for inactive places
                if (node.dataset.placeActive === 'false') {
                    node.classList.add('opacity-50', 'text-dim', 'd-none');
                }
            }
        }

        // Use MutationObserver to watch for marker additions
        const observer = new MutationObserver(mutations => {
            mutations.forEach(mutation => {
                if (mutation.addedNodes) {
                    mutation.addedNodes.forEach(processMarker);
                }
            });
        });

        observer.observe(markerPane, {
            childList: true,
            subtree: true
        });
        
        // Process any existing markers
        const existingMarkers = markerPane.querySelectorAll('*');
        if (commonConfig.debug) {
            console.log(`Processing ${existingMarkers.length} existing markers`);
        }
        existingMarkers.forEach(processMarker);
    }
};

// Place Form Map System
const placeFormMapSystem = {
    initialize(options = {}) {
        const mapDiv = document.getElementById('preview-map');
        if (!mapDiv) return;

        const {
            latInputId,
            lonInputId,
            defaultLat = 30.2672,
            defaultLon = -97.7431,
            zoom = 13
        } = options;

        // Add instructions above map
        const instructions = document.createElement('div');
        instructions.className = 'map-instructions';
        instructions.innerHTML = '<i class="bi bi-info-circle me-2"></i>Click anywhere on the map or drag the marker to set the location coordinates';
        mapDiv.parentNode.insertBefore(instructions, mapDiv);
        
        const latInput = document.getElementById(latInputId);
        const lonInput = document.getElementById(lonInputId);
        if (!latInput || !lonInput) return;

        let map = L.map(mapDiv);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(map);

        // Initialize marker
        let lat = latInput.value || defaultLat;
        let lon = lonInput.value || defaultLon;
        let marker = L.marker([lat, lon], {
            draggable: true
        }).addTo(map);

        // Set initial view
        map.setView([lat, lon], zoom);

        // Update marker and inputs on map click
        map.on('click', (e) => {
            marker.setLatLng(e.latlng);
            this.updateInputs(e.latlng, latInput, lonInput);
        });

        // Update inputs on marker drag
        marker.on('dragend', (e) => {
            this.updateInputs(marker.getLatLng(), latInput, lonInput);
        });

        // Update marker when inputs change
        latInput.addEventListener('change', () => this.updateMarkerFromInputs(latInput, lonInput, marker, map));
        lonInput.addEventListener('change', () => this.updateMarkerFromInputs(latInput, lonInput, marker, map));

        // Initialize modal map if it exists
        this.initializeModalMap(latInput, lonInput);

        return { map, marker };
    },

    updateInputs(latlng, latInput, lonInput) {
        latInput.value = latlng.lat.toFixed(5);
        lonInput.value = latlng.lng.toFixed(5);
    },

    updateMarkerFromInputs(latInput, lonInput, marker, map) {
        let lat = parseFloat(latInput.value);
        let lon = parseFloat(lonInput.value);
        if (!isNaN(lat) && !isNaN(lon)) {
            marker.setLatLng([lat, lon]);
            map.setView([lat, lon]);
        }
    },

    initializeModalMap(latInput, lonInput) {
        const placeMapModal = document.getElementById('placeMapModal');
        if (!placeMapModal) return;

        const placeMapContainer = document.getElementById('placeMapContainer');
        let modalMap = null;
        
        placeMapModal.addEventListener('shown.bs.modal', function () {
            if (!modalMap) {
                modalMap = L.map(placeMapContainer);
                L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                    attribution: '© OpenStreetMap contributors'
                }).addTo(modalMap);
                
                const modalLat = parseFloat(latInput.value);
                const modalLon = parseFloat(lonInput.value);
                
                if (!isNaN(modalLat) && !isNaN(modalLon)) {
                    L.marker([modalLat, modalLon]).addTo(modalMap);
                    modalMap.setView([modalLat, modalLon], 13);
                }
            }
            modalMap.invalidateSize();
        });
    }
};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    if (commonConfig.debug) {
        console.group('=== Map System Startup ===');
    }
    
    // Initialize core systems
    foliumMarkerSystem.initialize();
    
    // Initialize preview map if it exists
    const previewMap = document.getElementById('preview-map');
    if (previewMap && commonConfig.debug) {
        console.log('Initializing preview map');
        initializeLocationMap({
            latInputId: 'id_latitude',
            lonInputId: 'id_longitude'
        });
    }
    
    if (commonConfig.debug) {
        console.groupEnd();
    }
});