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

    marker.bindPopup('Drag me or click anywhere to set location!');
    marker.openPopup();

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

// Place Map Modal System
const placeMapModal = {
    map: null,
    marker: null,

    initialize() {
        const modal = document.getElementById('placeMapModal');
        if (!modal) return;

        modal.addEventListener('show.bs.modal', (event) => {
            const button = event.relatedTarget;
            const lat = parseFloat(button.getAttribute('data-place-lat'));
            const lon = parseFloat(button.getAttribute('data-place-lon'));
            const name = button.getAttribute('data-place-name');
            const container = modal.querySelector('#placeMapContainer');
            
            if (container && lat && lon) {
                // Ensure Leaflet is available
                if (typeof L === 'undefined') {
                    console.error('Leaflet is not loaded');
                    return;
                }

                // Clear previous map instance if it exists
                if (this.map) {
                    this.map.remove();
                    this.map = null;
                    this.marker = null;
                }

                // Initialize new map
                this.map = L.map(container).setView([lat, lon], 15);
                L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                    attribution: '© OpenStreetMap contributors'
                }).addTo(this.map);

                // Add marker
                this.marker = L.marker([lat, lon], {
                    title: name
                }).addTo(this.map);

                if (name) {
                    this.marker.bindPopup(name, {
                        offset: L.point(0, 25),  // Move popup below marker
                        autoPan: false,          // Prevent map from panning
                        closeButton: false,      // Remove close button
                        className: 'place-popup', // Custom class for styling
                        autoPanPadding: [50, 50],
                        keepInView: true         // Keep popup in view
                    }).openPopup();
                }

                // Force map to redraw after modal animation
                modal.addEventListener('shown.bs.modal', () => {
                    if (this.map) {
                        this.map.invalidateSize();
                    }
                }, { once: true });
            }
        });

        // Clean up map when modal is hidden
        modal.addEventListener('hide.bs.modal', () => {
            if (this.map) {
                this.map.remove();
                this.map = null;
                this.marker = null;
            }
        });
    }
};

// Time Display System
const timeDisplay = {
    themes: {
        morning: { color: '#FF8C00' },     // 5-11
        afternoon: { color: '#000000' },   // 11-17
        evening: { color: '#4B0082' },     // 17-21
        night: { color: '#1E4B9C' }       // 21-5
    },

    update() {
        const timeSpan = document.getElementById('localTime');
        if (!timeSpan) return;

        const now = new Date();
        const hour = now.getHours();
        
        // Set color based on time of day
        timeSpan.style.color = 
            hour >= 5 && hour < 11 ? this.themes.morning.color :
            hour >= 11 && hour < 17 ? this.themes.afternoon.color :
            hour >= 17 && hour < 21 ? this.themes.evening.color :
            this.themes.night.color;

        // Format date in YYYY/MM/DD format
        const year = now.getFullYear();
        const month = String(now.getMonth() + 1).padStart(2, '0');
        const day = String(now.getDate()).padStart(2, '0');
        const dateStr = `${year}/${month}/${day}`;
        
        const timeStr = now.toLocaleString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
        });

        // Get timezone info
        const shortTZ = new Intl.DateTimeFormat('en', { timeZoneName: 'short' })
            .formatToParts(now)
            .find(part => part.type === 'timeZoneName')?.value || '';

        // Get offset in compact format
        const offset = -now.getTimezoneOffset();
        const offsetHours = Math.floor(Math.abs(offset) / 60);
        const offsetMinutes = Math.abs(offset) % 60;
        const offsetString = `${offset >= 0 ? '+' : '-'}${String(offsetHours).padStart(2, '0')}${String(offsetMinutes).padStart(2, '0')}`;
        
        // Update display with compact format
        timeSpan.innerHTML = `<small>${dateStr} ${timeStr} ${offsetString} (${shortTZ})</small>`;
        
        // Update tooltip with full details
        const isoTime = now.toISOString();
        const unixTime = Math.floor(now.getTime() / 1000);
        const fullTimeString = now.toLocaleString('en-US', {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false,
            timeZoneName: 'long'
        });
        
        timeSpan.setAttribute('data-bs-title', 
            `${fullTimeString}\nISO: ${isoTime}\nUNIX: ${unixTime}\nClick to copy current timestamp`);
    },

    initializeTimestampCopy() {
        const timeSpan = document.getElementById('localTime');
        if (!timeSpan) return;

        timeSpan.addEventListener('click', function() {
            const now = new Date();
            navigator.clipboard.writeText(now.toISOString()).then(() => {
                const tooltip = bootstrap.Tooltip.getInstance(this);
                const originalTitle = this.getAttribute('data-bs-title');
                
                tooltip.setContent({ '.tooltip-inner': 'Copied!' });
                setTimeout(() => {
                    tooltip.setContent({ '.tooltip-inner': originalTitle });
                }, 1000);
            });
        });
    }
};

// Site Plan Management System
const sitePlanManager = {
    editorMode: false,
    currentScale: 1.0,
    currentX: 0,
    currentY: 0,
    modal: null,
    
    initialize() {
        const container = document.getElementById('siteMapContainer');
        if (!container) return;

        // Initialize from data attributes
        this.currentScale = parseFloat(container.dataset.scale) || 1.0;
        this.currentX = parseFloat(container.dataset.x) || 0;
        this.currentY = parseFloat(container.dataset.y) || 0;

        // Apply initial transform
        this.updateTransform(container);

        // Set up edit button
        const editButton = document.getElementById('editSitePlan');
        if (editButton) {
            editButton.addEventListener('click', () => this.openEditor());
        }

        // Initialize controls
        this.initializeControls();
    },

    updateTransform(target) {
        // Constrain scale
        this.currentScale = Math.max(0.5, Math.min(3.0, this.currentScale));
        
        // Only transform the background
        const background = target.querySelector('.site-plan-background');
        if (background) {
            background.style.transform = `scale(${this.currentScale}) translate(${this.currentX}px, ${this.currentY}px)`;
        }
    },

    initializeControls() {
        // Zoom controls
        document.getElementById('zoomIn')?.addEventListener('click', () => {
            this.currentScale = Math.min(this.currentScale * 1.2, 3.0);
            this.updateTransform(this.editorMode ? document.getElementById('siteMapEditorContainer') : document.getElementById('siteMapContainer'));
        });

        document.getElementById('zoomOut')?.addEventListener('click', () => {
            this.currentScale = Math.max(this.currentScale / 1.2, 0.5);
            this.updateTransform(this.editorMode ? document.getElementById('siteMapEditorContainer') : document.getElementById('siteMapContainer'));
        });

        // Movement controls
        const MOVE_STEP = 20;
        document.getElementById('moveLeft')?.addEventListener('click', () => {
            this.currentX -= MOVE_STEP / this.currentScale;
            this.updateTransform(this.editorMode ? document.getElementById('siteMapEditorContainer') : document.getElementById('siteMapContainer'));
        });

        document.getElementById('moveRight')?.addEventListener('click', () => {
            this.currentX += MOVE_STEP / this.currentScale;
            this.updateTransform(this.editorMode ? document.getElementById('siteMapEditorContainer') : document.getElementById('siteMapContainer'));
        });

        document.getElementById('moveUp')?.addEventListener('click', () => {
            this.currentY -= MOVE_STEP / this.currentScale;
            this.updateTransform(this.editorMode ? document.getElementById('siteMapEditorContainer') : document.getElementById('siteMapContainer'));
        });

        document.getElementById('moveDown')?.addEventListener('click', () => {
            this.currentY += MOVE_STEP / this.currentScale;
            this.updateTransform(this.editorMode ? document.getElementById('siteMapEditorContainer') : document.getElementById('siteMapContainer'));
        });

        // Reset view
        document.getElementById('resetView')?.addEventListener('click', () => {
            this.currentScale = 1.0;
            this.currentX = 0;
            this.currentY = 0;
            this.updateTransform(this.editorMode ? document.getElementById('siteMapEditorContainer') : document.getElementById('siteMapContainer'));
        });

        // Save button
        document.getElementById('savePositions')?.addEventListener('click', () => this.saveChanges());
    },

    initializeDraggable(marker) {
        // Remove any existing listeners first
        if (marker._dragListeners) {
            this.cleanupDraggable(marker);
        }

        let isDragging = false;
        let containerRect;
        let markerRect;

        const onMouseDown = (e) => {
            e.preventDefault();
            e.stopPropagation();
            
            isDragging = true;
            containerRect = marker.closest('#siteMapEditorContainer').getBoundingClientRect();
            markerRect = marker.getBoundingClientRect();
            
            // Calculate click position relative to marker
            const clickOffsetX = e.clientX - markerRect.left;
            const clickOffsetY = e.clientY - markerRect.top;
            
            // Store these as percentages of marker size
            marker._dragData = {
                offsetX: clickOffsetX / markerRect.width,
                offsetY: clickOffsetY / markerRect.height
            };
            
            marker.classList.add('dragging');
        };

        const onMouseMove = (e) => {
            if (!isDragging) return;
            e.preventDefault();

            // Get the stored offset percentages
            const { offsetX, offsetY } = marker._dragData;
            
            // Calculate marker dimensions as percentages of container
            const markerWidthPercent = (markerRect.width / containerRect.width) * 100;
            const markerHeightPercent = (markerRect.height / containerRect.height) * 100;
            
            // Calculate new position considering the click offset
            const rawX = ((e.clientX - containerRect.left) / containerRect.width) * 100;
            const rawY = ((e.clientY - containerRect.top) / containerRect.height) * 100;
            
            // Adjust position by the offset
            const adjustedX = rawX - (offsetX * markerWidthPercent);
            const adjustedY = rawY - (offsetY * markerHeightPercent);
            
            // Constrain to container bounds
            const xPercent = Math.max(0, Math.min(100 - markerWidthPercent, adjustedX));
            const yPercent = Math.max(0, Math.min(100 - markerHeightPercent, adjustedY));
            
            // Update position
            marker.style.left = `${xPercent}%`;
            marker.style.top = `${yPercent}%`;
            marker.dataset.x = xPercent.toFixed(2);
            marker.dataset.y = yPercent.toFixed(2);
        };

        const onMouseUp = (e) => {
            if (!isDragging) return;
            
            e.preventDefault();
            isDragging = false;
            delete marker._dragData;
            marker.classList.remove('dragging');
        };

        // Add new event listeners
        marker.addEventListener('mousedown', onMouseDown);
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);

        // Store listeners for cleanup
        marker._dragListeners = { onMouseDown, onMouseMove, onMouseUp };
    },

    cleanupDraggable(marker) {
        if (marker._dragListeners) {
            const { onMouseDown, onMouseMove, onMouseUp } = marker._dragListeners;
            marker.removeEventListener('mousedown', onMouseDown);
            document.removeEventListener('mousemove', onMouseMove);
            marker.removeEventListener('mouseup', onMouseUp);
            delete marker._dragListeners;
        }
    },

    openEditor() {
        this.editorMode = true;
        const container = document.getElementById('siteMapContainer');
        const editorContainer = document.getElementById('siteMapEditorContainer');
        const modalElement = document.getElementById('sitePlanModal');
        
        // Clone the site map content
        editorContainer.innerHTML = container.innerHTML;
        this.updateTransform(editorContainer);
        
        // Initialize draggable markers
        const markers = editorContainer.querySelectorAll('.location-marker');
        markers.forEach(marker => this.initializeDraggable(marker));
        
        // Initialize and store modal instance
        this.modal = new bootstrap.Modal(modalElement);
        
        // Set up modal cleanup
        modalElement.addEventListener('hidden.bs.modal', () => {
            this.editorMode = false;
            // Cleanup draggable markers
            markers.forEach(marker => this.cleanupDraggable(marker));
            // Ensure modal backdrop is removed
            document.body.classList.remove('modal-open');
            const backdrop = document.querySelector('.modal-backdrop');
            if (backdrop) backdrop.remove();
        }, { once: true });

        this.modal.show();
    },

    async saveChanges() {
        const editorContainer = document.getElementById('siteMapEditorContainer');
        const mainContainer = document.getElementById('siteMapContainer');
        const markers = editorContainer.querySelectorAll('.location-marker');
        const placeSlug = window.currentPlaceSlug;

        // Store original state for potential rollback and change comparison
        const originalState = {
            html: mainContainer.innerHTML,
            scale: parseFloat(mainContainer.dataset.scale) || 1.0,
            x: parseFloat(mainContainer.dataset.x) || 0,
            y: parseFloat(mainContainer.dataset.y) || 0
        };

        try {
            if (!placeSlug) {
                throw new Error('Place slug not found. Please refresh the page and try again.');
            }

            // Prepare marker position updates
            const markerPromises = Array.from(markers).map(marker => {
                const locationId = marker.dataset.locationId;
                const x = marker.dataset.x;
                const y = marker.dataset.y;
                
                return utils.fetchWithCSRF(`/api/${placeSlug}/locations/${locationId}/position/`, {
                    method: 'POST',
                    body: JSON.stringify({ x_coord: x, y_coord: y })
                });
            });

            // Prepare layout settings update
            const layoutData = {
                site_plan_scale: this.currentScale,
                site_plan_x: this.currentX,
                site_plan_y: this.currentY
            };

            // Combine all promises into a single Promise.all call
            const responses = await Promise.all([
                // Layout settings update
                utils.fetchWithCSRF(`/api/${placeSlug}/update_site_plan_layout/`, {
                    method: 'POST',
                    body: JSON.stringify(layoutData)
                }),
                // Marker position updates
                ...markerPromises
            ]);
            
            // Check if any response was not ok
            for (const response of responses) {
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.error || 'Failed to save changes');
                }
            }
            
            // Update the main container
            mainContainer.innerHTML = editorContainer.innerHTML;
            this.updateTransform(mainContainer);
            
            // Close modal properly
            if (this.modal) {
                this.modal.hide();
            }
            
            // Build success message with changes
            let successParts = ['Layout saved successfully!'];
            
            // Only add scale if it changed
            if (Math.abs(this.currentScale - originalState.scale) > 0.01) {
                successParts.push(`• Scale: ${this.currentScale.toFixed(2)}x`);
            }
            
            // Only add position if it changed
            if (Math.abs(this.currentX - originalState.x) > 1 || Math.abs(this.currentY - originalState.y) > 1) {
                successParts.push(`• Position: (${this.currentX.toFixed(0)}, ${this.currentY.toFixed(0)})`);
            }
            
            // Add marker count if any were updated
            if (markers.length > 0) {
                successParts.push(`• Updated ${markers.length} location marker${markers.length !== 1 ? 's' : ''}`);
            }
            
            toastSystem.show(successParts.join('\n'), 'success');
        } catch (error) {
            console.error('Error in saveChanges:', error);
            
            // Restore original state
            mainContainer.innerHTML = originalState.html;
            this.currentScale = originalState.scale;
            this.currentX = originalState.x;
            this.currentY = originalState.y;
            this.updateTransform(mainContainer);
            
            // Show error toast
            toastSystem.show(error.message || 'Error saving layout', 'danger');
            
            // Close modal
            if (this.modal) {
                this.modal.hide();
            }
        }
    }
};

// Live Stats System
const liveStats = {
    async fetchAndUpdateStats() {
        if (!window.currentPlaceSlug) return;
        
        try {
            const response = await utils.fetchWithCSRF(`/api/${window.currentPlaceSlug}/stats/`);
            if (!response.ok) throw new Error('Failed to fetch stats');
            
            const data = await response.json();
            
            // Update device counts
            const devicesActive = document.getElementById('devices-active');
            const devicesInactive = document.getElementById('devices-inactive');
            if (devicesActive) devicesActive.textContent = data.devices_active;
            if (devicesInactive) devicesInactive.textContent = data.devices_inactive;
            
            // Update sensor counts
            const sensorsActive = document.getElementById('sensors-active');
            const sensorsInactive = document.getElementById('sensors-inactive');
            if (sensorsActive) sensorsActive.textContent = data.sensors_active;
            if (sensorsInactive) sensorsInactive.textContent = data.sensors_inactive;
            
            // Update location counts
            const activeLocations = data.locations.filter(loc => loc.is_active).length;
            const inactiveLocations = data.locations.filter(loc => !loc.is_active).length;
            
            const locationsActive = document.querySelector('.locations-active');
            const locationsInactive = document.querySelector('.locations-inactive');
            if (locationsActive) locationsActive.textContent = activeLocations;
            if (locationsInactive) locationsInactive.textContent = inactiveLocations;
            
        } catch (error) {
            console.error('Error fetching stats:', error);
        }
    },

    startPolling(interval = 30000) { // Default to 30 seconds
        this.fetchAndUpdateStats(); // Initial fetch
        setInterval(() => this.fetchAndUpdateStats(), interval);
    }
};

// Initialize everything when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    [...document.querySelectorAll('[data-bs-toggle="tooltip"]')]
        .forEach(el => new bootstrap.Tooltip(el));
    
    // Initialize time display
    timeDisplay.update();
    setInterval(() => timeDisplay.update(), 1000);
    timeDisplay.initializeTimestampCopy();
    
    // Initialize site plan manager
    sitePlanManager.initialize();
    
    // Initialize place map modal
    placeMapModal.initialize();
    
    // Initialize live stats
    liveStats.startPolling();
});