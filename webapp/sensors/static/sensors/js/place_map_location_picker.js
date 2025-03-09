/**
 * Place Map Location Picker
 * Handles the interactive map for selecting place locations
 */

const PlaceMapLocationPicker = {
    initialize(options = {}) {
        const {
            mapContainerId = 'place-form-map',
            latInputId = 'id_latitude',
            lngInputId = 'id_longitude',
            defaultLat = 30.26715,
            defaultLng = -97.74306,
            zoom = 13,
            debug = false
        } = options;

        if (debug) {
            console.group('Place Map Location Picker');
            console.log('Initializing with options:', options);
        }

        const mapContainer = document.getElementById(mapContainerId);
        const latInput = document.getElementById(latInputId);
        const lngInput = document.getElementById(lngInputId);

        if (!mapContainer || !latInput || !lngInput) {
            if (debug) {
                console.error('Required elements not found:', { mapContainer, latInput, lngInput });
                this.showToast('Map initialization failed: Required elements not found', 'danger');
                console.groupEnd();
            }
            return null;
        }

        // Get initial coordinates
        const initialLat = parseFloat(latInput.value) || defaultLat;
        const initialLng = parseFloat(lngInput.value) || defaultLng;

        if (debug) {
            console.log('Initial coordinates:', { initialLat, initialLng });
        }

        // Initialize map
        const map = L.map(mapContainerId).setView([initialLat, initialLng], zoom);
        
        // Add tile layer
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '© OpenStreetMap contributors'
        }).addTo(map);

        // Add marker
        let marker = L.marker([initialLat, initialLng], {
            draggable: true,
            title: 'Drag me or click anywhere on the map!'
        }).addTo(map);

        // Update coordinates when marker is dragged
        marker.on('dragend', (e) => {
            const position = e.target.getLatLng();
            this.updateCoordinates(position.lat, position.lng, latInput, lngInput);
            if (debug) console.log('Marker dragged to:', position);
        });

        // Update marker when coordinates are manually entered
        const updateMarker = () => {
            const lat = parseFloat(latInput.value);
            const lng = parseFloat(lngInput.value);
            if (!isNaN(lat) && !isNaN(lng)) {
                marker.setLatLng([lat, lng]);
                map.setView([lat, lng]);
                if (debug) console.log('Marker updated from inputs:', { lat, lng });
            }
        };

        // Add input event listeners
        ['change', 'input'].forEach(event => {
            latInput.addEventListener(event, updateMarker);
            lngInput.addEventListener(event, updateMarker);
        });

        // Allow clicking on map to set marker
        map.on('click', (e) => {
            marker.setLatLng(e.latlng);
            this.updateCoordinates(e.latlng.lat, e.latlng.lng, latInput, lngInput);
            if (debug) console.log('Map clicked at:', e.latlng);
        });

        // Add map instructions if not present
        this.addMapInstructions(mapContainer);

        if (debug) {
            console.log('Map initialization complete');
            console.groupEnd();
        }

        return { map, marker };
    },

    updateCoordinates(lat, lng, latInput, lngInput) {
        latInput.value = lat.toFixed(5);
        lngInput.value = lng.toFixed(5);
        
        // Trigger change event on inputs
        [latInput, lngInput].forEach(input => {
            input.dispatchEvent(new Event('change', { bubbles: true }));
        });
    },

    addMapInstructions(mapContainer) {
        // Only add instructions if they don't already exist
        if (!mapContainer.previousElementSibling?.classList.contains('map-instructions')) {
            const instructions = document.createElement('div');
            instructions.className = 'map-instructions text-muted mb-2';
            instructions.innerHTML = `
                <small class="d-block mb-1">
                    <i class="fas fa-mouse-pointer me-1"></i>Click anywhere on the map to set location
                </small>
                <small class="d-block">
                    <i class="fas fa-arrows-alt me-1"></i>Drag the marker to fine-tune position
                </small>
            `;
            mapContainer.parentNode.insertBefore(instructions, mapContainer);
        }
    },

    showToast(message, type = 'info') {
        document.dispatchEvent(new CustomEvent(ToastEvents.SHOW, {
            detail: { message, type }
        }));
    }
};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    PlaceMapLocationPicker.initialize({
        debug: false  // Set to true to enable debug logging
    });
}); 