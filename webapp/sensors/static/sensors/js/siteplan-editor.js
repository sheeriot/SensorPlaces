/**
 * Site Plan Editor System
 * Uses Leaflet to manage site plan layout editing and marker positioning
 */

const sitePlanConfig = {
    debug: false,
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
        markers: new Map(),     // slug -> L.Marker in editor
        imageBounds: null,      // Bounds of the site plan image
        isDirty: false         // Whether there are unsaved changes
    },

    // DOM Element Getters (will be scoped to the modal content)
    get saveButton() { return document.getElementById('save-siteplan-positions'); },
    get resetButton() { return document.getElementById('siteplan-editor-reset'); },

    // The main initialize function is no longer needed as we trigger from the modal handler
    // initialize() { ... } 

    // NEW on-demand initializer for the modal
    initializeEditor(modalBody) {
        this.logDebug('initialization', 'Site plan editor initializing inside modal.');
        
        const container = modalBody.querySelector('#siteplan-editor-map');
        const viewContainer = document.getElementById('siteplan-container'); 
        
        if (!container || !viewContainer) {
            this.logDebug('error', 'Editor or view container not found');
            return;
        }

        const imageUrl = viewContainer.dataset.imageUrl;
        if (!imageUrl) {
            this.logDebug('error', 'Image URL not found on view container');
            return;
        }

        // Setup save/reset buttons inside the modal
        const saveButton = modalBody.querySelector('#save-siteplan-positions');
        if (saveButton) {
            saveButton.addEventListener('click', () => this.saveChanges());
        }

        const resetButton = modalBody.querySelector('#siteplan-editor-reset');
        if (resetButton) {
            resetButton.addEventListener('click', () => this.resetView());
        }

        // Get image dimensions and set up map
        const img = new Image();
        img.onload = () => {
            this.state.imageBounds = [[0, 0], [img.height, img.width]];
            this.initializeEditorMap(container, imageUrl);
        };
        img.src = imageUrl;

        // Add a one-time listener for modal hidden to clean up
        $('#mapplan-modal').one('hidden.bs.modal', () => this.cleanupEditor());
    },

    cleanupEditor() {
        if (this.state.editorMap) {
            // Remove event listeners first
            this.state.editorMap.off();
            this.state.markers.forEach(({marker}) => {
                if (marker) {
                    marker.off();
                    marker.remove();
                }
            });

            // Clear state
            this.state.markers.clear();
            this.state.isDirty = false;

            // Remove map last
            this.state.editorMap.remove();
            this.state.editorMap = null;
            this.state.imageOverlay = null;
            this.state.imageBounds = null;

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
        // --- New Sizing Logic ---
        const siteplanWrapper = container.closest('.siteplan-wrapper');
        if (siteplanWrapper) {
            const imageWidth = this.state.imageBounds[1][1];
            const imageHeight = this.state.imageBounds[1][0];
            const aspectRatio = imageHeight / imageWidth;
            const availableWidth = siteplanWrapper.offsetWidth;
            let calculatedHeight = availableWidth * aspectRatio;
            const maxHeight = window.innerHeight * 0.8; // Use more of the modal height
            const finalHeight = Math.min(calculatedHeight, maxHeight);
            siteplanWrapper.style.height = `${finalHeight}px`;
        }
        // --- End New Sizing Logic ---

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

        // Add image overlay with loading handler
        const bounds = this.state.imageBounds;
        this.state.imageOverlay = L.imageOverlay(imageUrl, bounds)
            .addTo(this.state.editorMap)
            .on('load', () => {
                // Mark as loaded once image is ready
                if (siteplanWrapper) {
                    siteplanWrapper.classList.add('loaded');
                }
                container.dataset.editorReady = 'true';
            });

        // The aspect ratio is now handled by the explicit height calculation above

        // Initial fit
        this.fitMapPerfectly();

        // Create a ResizeObserver for the wrapper
        const resizeObserver = new ResizeObserver(() => {
            requestAnimationFrame(() => this.fitMapPerfectly());
        });

        // Observe both wrapper and container
        if (siteplanWrapper) resizeObserver.observe(siteplanWrapper);
        resizeObserver.observe(container);

        // Also handle window resize
        window.addEventListener('resize', () => {
            requestAnimationFrame(() => this.fitMapPerfectly());
        });

        // Add markers
        this.addEditorMarkers();
        this.logDebug('success', 'Editor map fully initialized and ready');
    },

    addEditorMarkers() {
        try {
            // Instead of reading from the stale dataset, get the most up-to-date
            // locations directly from the sitePlanView's state.
            const locations = Array.from(window.sitePlanEditor.state.locations.values())
                .filter(loc => loc.slug !== 'unassigned-devices');

            if (!locations || locations.length === 0) {
                this.logDebug('warning', 'No locations found in sitePlanView state after filtering.');
                return;
            }

            this.logDebug('markers', `Loading ${locations.length} markers from sitePlanView state.`);

            locations.forEach(location => {
                const coords = this.percentToImageCoords(location.x_pos, location.y_pos);

                // Get the existing icon type from the view
                const viewMarker = window.sitePlanEditor.state.markers.get(location.slug);
                const iconType = viewMarker ? viewMarker.iconType : window.sitePlanEditor.getRandomIcon(location.name);

                const icon = this.createIcon(location.is_active, iconType, location.name);

                const marker = L.marker(coords, {
                    icon: icon,
                    title: location.name,
                    draggable: true
                });

                // Create informative popup
                marker.bindPopup(this.createMarkerPopup(location), {
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
                        this.showToast('Marker must stay within the site plan bounds', 'warning');
                    }
                });

                marker.addTo(this.state.editorMap);

                // Store marker reference with original position in percentages
                this.state.markers.set(location.slug, {
                    marker,
                    iconType,
                    originalPosition: { x_pos: location.x_pos, y_pos: location.y_pos }
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
    percentToImageCoords(x_pos, y_pos) {
        const bounds = this.state.imageBounds;
        const imageX = (x_pos / 100) * bounds[1][1];
        const imageY = (y_pos / 100) * bounds[1][0];
        return [imageY, imageX];
    },

    imageCoordsToPercent(coords) {
        const bounds = this.state.imageBounds;
        return {
            x_pos: Number((coords.lng / bounds[1][1] * 100).toFixed(2)),
            y_pos: Number((coords.lat / bounds[1][0] * 100).toFixed(2))
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
        this.logDebug('saves', 'saveChanges triggered.');
        if (!this.state.isDirty) {
            this.logDebug('saves', 'No changes detected (isDirty is false). Aborting save.');
            return;
        }

        // Get only changed markers
        const changedLocations = Array.from(this.state.markers.entries())
            .map(([slug, {marker, originalPosition}]) => {
                const currentPos = this.imageCoordsToPercent(marker.getLatLng());
                const x_pos = currentPos.x_pos;
                const y_pos = currentPos.y_pos;

                // Compare with original position (both are percentages)
                // Use a small tolerance to avoid floating point issues
                if (Math.abs(x_pos - originalPosition.x_pos) > 0.01 || Math.abs(y_pos - originalPosition.y_pos) > 0.01) {
                    return { slug, x_pos, y_pos };
                }
                return null;
            })
            .filter(loc => loc !== null);

        if (changedLocations.length === 0) {
            this.logDebug('saves', 'No actual location changes detected after diff. Aborting save.');
            return;
        }

        try {
            this.logDebug('saves', 'Saving location updates to backend:', { locations: changedLocations });
            this.showToast('Saving changes...', 'info');

            const response = await window.utils.fetchWithCSRF(
                `/${document.body.dataset.placeSlug}/siteplan/update/`,
                {
                    method: 'POST',
                    body: JSON.stringify({ locations: changedLocations })
                }
            );

            this.logDebug('network', 'Received response from server:', { status: response.status, ok: response.ok });

            if (!response.ok) {
                let errorMessage = `Failed to save changes. Server responded with status ${response.status}.`;
                try {
                    const errorData = await response.json();
                    errorMessage = errorData.message || errorMessage;
                    this.logDebug('error', 'Server error response body:', errorData);
                } catch (e) {
                    this.logDebug('error', 'Could not parse error response body.');
                    errorMessage = `Error ${response.status}: ${response.statusText}`;
                }
                this.showToast(errorMessage, 'danger');
                this.logDebug('error', 'Save failed with non-OK response:', response);
                return;
            }

            const data = await response.json();
            this.logDebug('network', 'Parsed response data:', data);

            if (data.type === 'error' || data.type === 'danger') {
                this.showToast(data.message || 'An unknown error occurred during save.', 'danger');
                this.logDebug('error', 'Save failed with application error:', data);
                return;
            }

            // Success case
            this.state.isDirty = false;

            // Update the view's location data
            if (data.changes && data.changes.locations) {
                // Get the full location data from the view's state and merge
                // with the new position from the server response.
                const updatedLocations = data.changes.locations.reduce((acc, change) => {
                    const slug = change.slug;
                    const existingLocation = window.sitePlanEditor.state.locations.get(slug);
                    if (existingLocation) {
                        acc[slug] = {
                            ...existingLocation,
                            x_pos: parseFloat(change.new_position.x_pos),
                            y_pos: parseFloat(change.new_position.y_pos)
                        };
                    } else {
                        this.logDebug('error', `Could not find existing location for slug: ${slug}`);
                    }
                    return acc;
                }, {});

                this.logDebug('saves', 'Dispatching siteplan-update event with locations:', updatedLocations);

                // Dispatch update event with an object, not an array
                window.dispatchEvent(new CustomEvent('siteplan-update', {
                    detail: { locations: updatedLocations }
                }));
            }

            // Close the modal
            const modal = bootstrap.Modal.getInstance(this.modal);
            if (modal) {
                modal.hide();
            }

            // Show success toast
            this.showToast(data.message || 'Changes saved successfully', data.type || 'warning');

            this.logDebug('success', 'Changes saved successfully:', data);

        } catch (error) {
            this.logDebug('error', 'Save failed due to network or unexpected error:', error);
            this.showToast('A network error occurred while saving. Please check your connection.', 'danger');
        }
    },

    // Function to ensure map fits perfectly
    fitMapPerfectly() {
        if (!this.state.editorMap || !this.state.imageBounds) return;

        // Only update if container is visible
        const container = this.editorContainer;
        if (!container || container.offsetWidth === 0) return;

        this.state.editorMap.invalidateSize();
        this.state.editorMap.fitBounds(this.state.imageBounds, {
            animate: false,
            padding: [0, 0]
        });

        this.logDebug('operation', 'Map fit updated', {
            containerSize: `${container.offsetWidth}x${container.offsetHeight}`
        });
    },

    // Function to show toast using event system
    showToast(message, type = 'info') {
        document.dispatchEvent(new CustomEvent(ToastEvents.SHOW, {
            detail: { message, type }
        }));
    },

    // Utility Methods
    logDebug(type, message, data = null) {
        if (!sitePlanConfig.debug) return;
        const icon = sitePlanConfig.logFormat[type] || sitePlanConfig.logFormat.operation;
        const timestamp = new Date().toISOString().split('T')[1].slice(0, -1);
        console.log(`${timestamp} ${icon} ${message}`, data || '');
    }
};

// Remove the DOMContentLoaded listener, initialization is now on-demand
// document.addEventListener('DOMContentLoaded', () => sitePlanSystem.initialize());

// Export for use in other modules
window.sitePlanSystem = sitePlanSystem;
