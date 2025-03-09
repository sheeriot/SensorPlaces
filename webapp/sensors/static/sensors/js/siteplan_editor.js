/**
 * Site Plan Editor System
 * Uses Leaflet to manage site plan layout editing and marker positioning
 */

const sitePlanConfig = {
    debug: true,
    logGroups: {
        initialization: true,
        markers: true,
        saves: true,
        network: true
    },
    logFormat: {
        operation: '🔷',
        warning: '⚠️',
        error: '🔴',
        success: '✅'
    }
};

const sitePlanSystem = {
    // Constants
    DEFAULT_ZOOM: 2,
    MIN_ZOOM: 0,
    MAX_ZOOM: 4,
    
    // State
    state: {
        editorMap: null,        // Editor Leaflet map instance
        imageOverlay: null,     // Current image overlay in editor
        markers: new Map(),     // id -> L.Marker in editor
        imageBounds: null,      // Bounds of the site plan image
        isDirty: false         // Whether there are unsaved changes
    },

    // DOM Element Getters
    get viewContainer() { return document.getElementById('siteplan-container'); },
    get editorContainer() { return document.getElementById('siteplan-editor-map'); },
    get modal() { return document.getElementById('siteplan-editor'); },
    get editButton() { return document.getElementById('siteplan-edit'); },
    get saveButton() { return document.getElementById('siteplan-save'); },
    get resetButton() { return document.getElementById('siteplan-editor-reset'); },

    // Initialization Methods
    initialize() {
        if (!this.viewContainer || !this.editorContainer) {
            this.logDebug('error', 'Required containers not found');
            return;
        }
        
        // Initialize the Bootstrap modal
        const modal = this.modal;
        if (!modal) {
            this.logDebug('error', 'Modal element not found');
            return;
        }

        // Initialize edit button click handler
        const editButton = this.editButton;
        if (editButton) {
            editButton.addEventListener('click', () => {
                const bsModal = new bootstrap.Modal(modal);
                bsModal.show();
            });
            this.logDebug('initialization', 'Edit button handler initialized');
        }

        // Set up modal event listeners
        modal.addEventListener('show.bs.modal', () => this.setupEditor());
        modal.addEventListener('shown.bs.modal', () => {
            // Force a resize after modal is fully shown
            if (this.state.editorMap) {
                this.state.editorMap.invalidateSize();
                this.fitMapPerfectly();
            }
        });
        modal.addEventListener('hidden.bs.modal', () => this.cleanupEditor());

        // Initialize save button click handler
        const saveButton = document.getElementById('siteplan-save');
        if (saveButton) {
            saveButton.addEventListener('click', () => {
                this.logDebug('saves', 'Save button clicked');
                this.saveChanges();
            });
            this.logDebug('initialization', 'Save button handler initialized');
        } else {
            this.logDebug('error', 'Save button not found with ID: siteplan-save');
        }

        if (this.resetButton) {
            this.resetButton.addEventListener('click', () => this.resetView());
        }

        this.logDebug('initialization', 'Site plan editor initialized');
    },

    cleanupEditor() {
        if (this.state.editorMap) {
            this.state.editorMap.remove();
            this.state.editorMap = null;
            this.state.imageOverlay = null;
            this.state.markers.clear();
            this.state.imageBounds = null;
            this.state.isDirty = false;
            this.logDebug('initialization', 'Editor cleaned up');
        }
    },

    setupEditor() {
        const container = this.editorContainer;
        const imageUrl = this.viewContainer.dataset.imageUrl;
        
        if (!container || !imageUrl) return;

        container.dataset.editorReady = 'false';

        // Log initial container dimensions
        this.logDebug('initialization', 'Initial container dimensions:', {
            width: container.offsetWidth,
            height: container.offsetHeight,
            style: container.style.cssText
        });

        // Get image dimensions
        const img = new Image();
        img.onload = () => {
            // Set container aspect ratio to match image
            const aspectRatio = (img.height / img.width) * 100;
            container.style.paddingBottom = `${aspectRatio}%`;
            
            // Store bounds and initialize
            this.state.imageBounds = [[0, 0], [img.height, img.width]];
            
            // Wait for modal transition to complete
            setTimeout(() => {
                this.logDebug('initialization', 'Container dimensions after modal transition:', {
                    width: container.offsetWidth,
                    height: container.offsetHeight,
                    style: container.style.cssText
                });
                
                this.initializeEditorMap(container, imageUrl);
            }, 300); // Wait for Bootstrap's default transition duration
        };
        img.src = imageUrl;
    },

    initializeEditorMap(container, imageUrl) {
        // Initialize map with same settings as view, but enable dragging
        this.state.editorMap = L.map(container, {
            crs: L.CRS.Simple,
            zoomControl: false,
            dragging: true,      // Enable for marker dragging
            touchZoom: false,    // Disable zoom
            scrollWheelZoom: false, // Disable zoom
            doubleClickZoom: false,
            boxZoom: false,
            keyboard: false,
            attributionControl: false,
            zoomSnap: 0,
            zoomDelta: 0,
            minZoom: -2,         // Allow some zoom flexibility for better fitting
            maxZoom: 2
        });

        // Add image overlay
        const bounds = this.state.imageBounds;
        this.state.imageOverlay = L.imageOverlay(imageUrl, bounds).addTo(this.state.editorMap);

        // Set container aspect ratio based on image
        const wrapper = container.closest('.siteplan-wrapper');
        if (wrapper) {
            const aspectRatio = (this.state.imageBounds[1][0] / this.state.imageBounds[1][1]) * 100;
            wrapper.style.paddingBottom = `${aspectRatio}%`;
            
            // Clear any existing styles that might interfere
            wrapper.style.height = '';
            wrapper.style.minHeight = '';
            wrapper.style.maxHeight = '';
            container.style.position = 'absolute';
        }

        // Initial fit
        this.fitMapPerfectly();

        // Create a ResizeObserver for the wrapper
        const resizeObserver = new ResizeObserver(() => {
            requestAnimationFrame(() => this.fitMapPerfectly());
        });

        // Observe both wrapper and container
        if (wrapper) resizeObserver.observe(wrapper);
        resizeObserver.observe(container);

        // Also handle window resize
        window.addEventListener('resize', () => {
            requestAnimationFrame(() => this.fitMapPerfectly());
        });

        // Add markers
        this.addEditorMarkers();
        container.dataset.editorReady = 'true';
        this.logDebug('success', 'Editor map fully initialized and ready');
    },

    addEditorMarkers() {
        try {
            // Parse locations data
            const rawData = this.viewContainer.dataset.locations || '[]';
            const unescapedData = rawData.replace(/\\u(\w{4})/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)));
            const locations = JSON.parse(unescapedData);

            locations.forEach(location => {
                const coords = this.percentToImageCoords(location.x, location.y);
                
                // Create marker with label
                const iconType = window.sitePlanView.getRandomIcon(location.name);
                const icon = L.divIcon({
                    className: `location-marker bg-primary border border-2 border-white rounded-3 shadow-sm p-2`,
                    iconSize: null,  // Let it size to content
                    iconAnchor: null, // Will be set after creation
                    html: `
                        <div class="d-flex flex-column align-items-center">
                            <i class="bi bi-${iconType}-fill text-white fs-5"></i>
                            <div class="marker-label text-white small mt-1">
                                ${location.name}
                            </div>
                        </div>
                    `
                });
                
                const marker = L.marker(coords, {
                    icon: icon,
                    title: location.name,
                    draggable: true
                });

                // Create informative popup
                const popupContent = `
                    <div class="p-2">
                        <h6 class="mb-1">${location.name}</h6>
                        ${location.description ? `<p class="mb-1 small text-muted">${location.description}</p>` : ''}
                        ${location.active_devices_count ? `
                            <div class="text-success small">
                                <i class="bi bi-circle-fill me-1"></i>
                                ${location.active_devices_count} active device${location.active_devices_count !== 1 ? 's' : ''}
                            </div>
                        ` : ''}
                    </div>
                `;
                
                marker.bindPopup(popupContent, {
                    offset: [0, -10],
                    closeButton: false,
                    className: 'location-popup',
                    autoPan: false,
                    autoPanPadding: [50, 50],
                    keepInView: true
                });

                // Show popup on hover
                marker.on('mouseover', function() {
                    this.openPopup();
                });
                
                marker.on('mouseout', function() {
                    this.closePopup();
                });

                // Dragging behavior
                let isDragging = false;
                let originalPosition = null;

                marker.on('mousedown', function(e) {
                    isDragging = false;
                    originalPosition = marker.getLatLng();
                    marker.getElement().classList.add('dragging');
                });

                marker.on('dragstart', function(e) {
                    isDragging = true;
                    this.closePopup();
                    sitePlanSystem.state.isDirty = true;
                });

                marker.on('drag', function(e) {
                    if (isDragging) {
                        // Optional: Add visual feedback during drag
                        this.getElement().style.opacity = '0.8';
                    }
                });

                marker.on('dragend', function(e) {
                    isDragging = false;
                    this.getElement().classList.remove('dragging');
                    this.getElement().style.opacity = '1';
                    
                    // Validate new position is within bounds
                    const newPos = this.getLatLng();
                    const bounds = sitePlanSystem.state.imageBounds;
                    
                    if (!bounds) return;
                    
                    // If outside bounds, return to original position
                    if (newPos.lat < bounds[0][0] || newPos.lat > bounds[1][0] ||
                        newPos.lng < bounds[0][1] || newPos.lng > bounds[1][1]) {
                        this.setLatLng(originalPosition);
                        toastSystem.show({
                            message: 'Marker must stay within the site plan bounds',
                            type: 'warning',
                            duration: 3000
                        });
                    }
                });

                marker.addTo(this.state.editorMap);
                
                // Store marker reference
                this.state.markers.set(location.id, {
                    marker,
                    iconType,
                    originalPosition: coords
                });
            });

            this.logDebug('success', `Successfully added ${locations.length} markers to editor`);
        } catch (error) {
            this.logDebug('error', 'Failed to parse locations data:', error);
            if (this.editorContainer) {
                this.editorContainer.dataset.editorReady = 'error';
            }
        }
    },

    // Helper Methods
    percentToImageCoords(xPercent, yPercent) {
        const bounds = this.state.imageBounds;
        const imageX = (xPercent / 100) * bounds[1][1];
        const imageY = (yPercent / 100) * bounds[1][0];
        return [imageY, imageX];
    },

    imageCoordsToPercent(coords) {
        const bounds = this.state.imageBounds;
        return {
            x: (coords.lng / bounds[1][1]) * 100,
            y: (coords.lat / bounds[1][0]) * 100
        };
    },

    createMarkerPopup(location) {
        return `
            <div class="p-2">
                <h6 class="mb-1">${location.name}</h6>
            </div>
        `;
    },

    resetView() {
        if (!this.state.editorMap || !this.state.imageBounds) return;
        this.state.editorMap.fitBounds(this.state.imageBounds);
        this.logDebug('operation', 'Reset editor view to bounds');
    },

    // Save changes
    async saveChanges() {
        if (!this.state.isDirty) return;

        const updates = {
            locations: Array.from(this.state.markers.entries()).map(([id, {marker}]) => {
                const percent = this.imageCoordsToPercent(marker.getLatLng());
                return {
                    id,
                    x: percent.x,
                    y: percent.y
                };
            })
        };

        try {
            this.logDebug('saves', 'Saving location updates:', updates);
            const response = await fetch(
                `/api/${document.body.dataset.placeSlug}/siteplan_update/`,
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                    },
                    body: JSON.stringify(updates)
                }
            );
            
            const data = await response.json();
            
            if (!response.ok) {
                // Show the specific error from the backend
                toastSystem.show({
                    message: data.message || 'Failed to save changes',
                    type: data.type || 'danger',
                    tags: data.tags || 'error layout-update',
                    addToHistory: true
                });
                this.logDebug('error', 'Save failed:', data);
                return;
            }

            // Success case
            this.state.isDirty = false;
            toastSystem.show({
                message: data.message || 'Changes saved successfully',
                type: data.type || 'success',
                tags: data.tags || 'layout-update',
                addToHistory: true
            });
            
            // Reload the page to refresh the view
            window.location.reload();
            
        } catch (error) {
            this.logDebug('error', 'Save failed:', error);
            toastSystem.show({
                message: 'Network error while saving changes',
                type: 'danger',
                tags: 'error layout-update network',
                addToHistory: true
            });
        }
    },

    // Function to ensure map fits perfectly
    fitMapPerfectly() {
        if (!this.state.editorMap || !this.state.imageBounds) return;
        
        // Force a size update
        this.state.editorMap.invalidateSize();
        
        // Get current container size
        const container = this.editorContainer;
        const containerWidth = container.offsetWidth;
        const containerHeight = container.offsetHeight;
        
        // Calculate zoom to fit perfectly
        const imageWidth = this.state.imageBounds[1][1];
        const imageHeight = this.state.imageBounds[1][0];
        const widthRatio = containerWidth / imageWidth;
        const heightRatio = containerHeight / imageHeight;
        const zoom = Math.min(widthRatio, heightRatio);
        
        // Center and zoom
        this.state.editorMap.setView([imageHeight/2, imageWidth/2], Math.log2(zoom));
        this.state.editorMap.fitBounds(this.state.imageBounds, {
            animate: false,
            padding: [0, 0]
        });
        
        this.logDebug('operation', 'Map fit perfectly', {
            containerSize: `${containerWidth}x${containerHeight}`,
            imageSize: `${imageWidth}x${imageHeight}`,
            zoom: zoom
        });
    },

    // Utility Methods
    logDebug(type, message, data = null) {
        if (!sitePlanConfig.debug) return;
        const icon = sitePlanConfig.logFormat[type] || sitePlanConfig.logFormat.operation;
        const timestamp = new Date().toISOString().split('T')[1].slice(0, -1);
        console.log(`${timestamp} ${icon} ${message}`, data || '');
    }
};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => sitePlanSystem.initialize());

// Export for use in other modules
window.sitePlanSystem = sitePlanSystem; 