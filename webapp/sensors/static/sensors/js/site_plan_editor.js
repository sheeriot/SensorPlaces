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
    get viewContainer() { return document.getElementById('site-plan-container'); },
    get editorContainer() { return document.getElementById('site-plan-editor-map'); },
    get modal() { return document.getElementById('sitePlanModal'); },
    get editButton() { return document.getElementById('site-plan-edit'); },
    get saveButton() { return document.getElementById('site-plan-editor-save'); },
    get resetButton() { return document.getElementById('site-plan-editor-reset'); },

    // Initialization Methods
    initialize() {
        if (!this.editButton) return;
        
        // Set up event listeners
        this.editButton.addEventListener('click', () => {
            const modal = new bootstrap.Modal(this.modal);
            modal.show();
            this.setupEditor();
        });

        // Clean up when modal is hidden
        this.modal.addEventListener('hidden.bs.modal', () => {
            this.cleanupEditor();
        });

        if (this.saveButton) {
            this.saveButton.addEventListener('click', () => this.saveChanges());
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
        if (!container) {
            this.logDebug('error', 'Cannot setup editor: missing container');
            return;
        }

        // Clean up any existing editor
        this.cleanupEditor();

        // Get image URL and validate
        const imageUrl = this.viewContainer.dataset.imageUrl;
        if (!imageUrl) {
            this.logDebug('error', 'Cannot setup editor: missing image URL');
            return;
        }

        this.logDebug('initialization', 'Setting up editor with container and image URL');
        container.dataset.editorReady = 'false';

        // Create a temporary image to get dimensions
        const img = new Image();
        img.onload = () => {
            // Store image bounds
            this.state.imageBounds = [[0, 0], [img.height, img.width]];
            this.logDebug('initialization', `Image loaded with dimensions ${img.width}x${img.height}`);
            
            // Initialize the editor map
            this.initializeEditorMap(container, imageUrl);
        };
        img.onerror = () => {
            this.logDebug('error', 'Failed to load site plan image');
            container.dataset.editorReady = 'error';
        };
        img.src = imageUrl;
    },

    initializeEditorMap(container, imageUrl) {
        // Check if map already exists
        if (this.state.editorMap) {
            this.logDebug('warning', 'Editor map already exists, cleaning up first');
            this.cleanupEditor();
        }

        this.logDebug('initialization', 'Creating editor map...');

        // Initialize Leaflet map with better defaults
        this.state.editorMap = L.map(container, {
            crs: L.CRS.Simple,
            minZoom: -2,  // Allow more zoom out for better overview
            maxZoom: 2,   // Limit max zoom to avoid pixelation
            zoomSnap: 0.1,  // Smoother zooming
            zoomDelta: 0.5, // Smaller zoom steps
            wheelPxPerZoomLevel: 120, // More precise wheel zooming
            bounceAtZoomLimits: false // Don't bounce when hitting zoom limits
        });

        // Add image overlay
        const bounds = this.state.imageBounds;
        this.state.imageOverlay = L.imageOverlay(imageUrl, bounds).addTo(this.state.editorMap);
        this.logDebug('initialization', 'Added image overlay to map');

        // Add existing markers
        this.addEditorMarkers();

        // Fit map to bounds with padding
        this.state.editorMap.fitBounds(bounds, {
            padding: [20, 20],
            maxZoom: 0  // Don't zoom in too far when fitting
        });

        // Update ready state
        container.dataset.editorReady = 'true';
        this.logDebug('success', 'Editor map fully initialized and ready');
    },

    addEditorMarkers() {
        try {
            // Get raw data and unescape it first
            const rawData = this.viewContainer.dataset.locations || '[]';
            this.logDebug('markers', 'Processing location data for editor');
            
            // Unescape the JSON string before parsing (same as view)
            const unescapedData = rawData.replace(/\\u(\w{4})/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)));
            
            const locations = JSON.parse(unescapedData);
            this.logDebug('markers', `Found ${locations.length} locations to add to editor`);

            locations.forEach(location => {
                const coords = this.percentToImageCoords(location.x, location.y);
                this.logDebug('markers', `Adding marker for "${location.name}" at [${coords}]`);
                
                const marker = L.marker(coords, {
                    draggable: true,
                    title: location.name
                });
                
                marker.bindPopup(this.createMarkerPopup(location));
                marker.addTo(this.state.editorMap);
                this.state.markers.set(location.id, marker);

                // Handle marker drag
                marker.on('dragstart', () => {
                    this.state.isDirty = true;
                    this.logDebug('markers', `Started dragging marker ${location.id}`);
                });

                marker.on('dragend', () => {
                    const pos = marker.getLatLng();
                    this.logDebug('markers', `Marker ${location.id} moved to:`, pos);
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
                ${location.active_devices_count > 0 ? `
                    <div class="text-muted small">
                        ${location.active_devices_count} active device${location.active_devices_count !== 1 ? 's' : ''}
                    </div>
                ` : ''}
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
        if (!this.state.editorMap || !this.state.imageBounds || !this.state.isDirty) {
            this.logDebug('warning', 'No changes to save');
            return;
        }

        const updates = {
            locations: Array.from(this.state.markers.entries()).map(([id, marker]) => {
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
                `/api/${document.body.dataset.placeSlug}/update_site_plan_layout/`,
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                    },
                    body: JSON.stringify(updates)
                }
            );

            if (!response.ok) throw new Error('Save failed');

            const data = await response.json();
            
            // Reload the page to refresh the view
            window.location.reload();
            
            this.state.isDirty = false;
            toastSystem.show({
                message: data.message || 'Changes saved successfully',
                type: data.type || 'success',
                tags: data.tags || 'layout-update',
                addToHistory: true
            });

        } catch (error) {
            this.logDebug('error', 'Save failed:', error);
            toastSystem.show({
                message: error.message || 'Failed to save changes',
                type: 'danger',
                tags: 'error layout-update',
                addToHistory: true
            });
        }
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
document.addEventListener('DOMContentLoaded', async () => {
    try {
        // Check if site plan view exists and needs initialization
        if (window.sitePlanView) {
            if (!window.sitePlanView.state.initialized) {
                console.log('Waiting for site plan view initialization...');
                await window.sitePlanView.initialize();
            } else {
                console.log('Site plan view already initialized');
            }
        } else {
            console.log('Site plan view not found');
        }
        
        // Initialize the editor system
        sitePlanSystem.initialize();
    } catch (error) {
        console.error('Error during initialization:', error);
    }
});

// Export for use in other modules
window.sitePlanSystem = sitePlanSystem; 