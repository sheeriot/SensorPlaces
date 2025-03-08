/**
 * Site Plan Editor System
 * 
 * Manages the site plan layout editor, including:
 * - Marker dragging
 * - Zoom and pan controls
 * - Position saving
 */

// Debug Configuration
const sitePlanConfig = {
    debug: false,            // Master switch for debug mode
    logMarkerDrag: true,    // Log marker drag events and positions
    logTransforms: true,    // Log container transform updates
    logSaveOperations: true // Log position saving operations
};

const sitePlanSystem = {
    // Constants
    ZOOM_FACTOR: 1.1,      // Zoom in/out scale factor
    PAN_DISTANCE: 10,      // Pixels to move per pan action
    
    // State management
    state: {
        scale: 1,
        x: 0,
        y: 0,
        isDragging: false,
        dragTarget: null,
        originalX: 0,
        originalY: 0,
        aspectRatio: 1.333
    },

    // Add aspect ratio constants
    ASPECT_RATIOS: {
        '4:3': 1.333,
        '16:9': 1.778,
        '1:1': 1.0,
        'custom': null
    },

    // DOM element getters
    get mainContainer() {
        return document.getElementById('site-plan-layout');
    },

    get editorContainer() {
        return document.getElementById('siteMapEditorContainer');
    },

    get editorClone() {
        return document.getElementById('site-plan-layout-clone');
    },

    get modal() {
        return document.getElementById('sitePlanModal');
    },

    // Logging helpers
    logDebug(message, data = null) {
        if (!sitePlanConfig.debug) return;
        if (data) {
            console.log(message, data);
        } else {
            console.log(message);
        }
    },

    logWarning(message, data = null) {
        if (!sitePlanConfig.debug) return;
        if (data) {
            console.warn(message, data);
        } else {
            console.warn(message);
        }
    },

    initialize() {
        if (sitePlanConfig.debug) console.group('Site Plan Editor Initialization');

        // Initialize edit button handler
        const editButton = document.getElementById('editSitePlan');
        if (!editButton) {
            if (sitePlanConfig.debug) {
                this.logDebug('Editor button not found - editor not needed on this page');
                console.groupEnd();
            }
            return;
        }

        editButton.addEventListener('click', () => this.openEditor());
        this.logDebug('Edit button handler initialized');

        // Initialize the site map container
        if (this.mainContainer) {
            this.loadContainerState();
            this.updateContainerTransform();
        } else {
            this.logWarning('Site map container not found');
        }

        // Initialize drag handlers for location markers
        const markers = document.querySelectorAll('.location-marker');
        this.logDebug(`Initializing drag handlers for ${markers.length} markers`);
        markers.forEach(marker => this.initializeMarkerDrag(marker));

        if (sitePlanConfig.debug) console.groupEnd();
    },

    loadContainerState() {
        const container = this.mainContainer;
        this.state.scale = parseFloat(container.dataset.scale) || 1;
        this.state.x = parseFloat(container.dataset.x) || 0;
        this.state.y = parseFloat(container.dataset.y) || 0;
        
        this.logDebug('Container initialized with state:', {
            scale: this.state.scale,
            x: this.state.x,
            y: this.state.y
        });
    },

    initializeMarkerDrag(marker) {
        marker.addEventListener('mousedown', e => {
            if (!this.modal.classList.contains('show')) return;
            
            this.startDrag(marker, e);
            
            const handleMouseMove = e => this.handleDragMove(e);
            const handleMouseUp = () => this.endDrag(handleMouseMove, handleMouseUp);
            
            document.addEventListener('mousemove', handleMouseMove);
            document.addEventListener('mouseup', handleMouseUp);
        });
    },

    startDrag(marker, event) {
        this.state.isDragging = true;
        this.state.dragTarget = marker;
        this.state.originalX = event.clientX;
        this.state.originalY = event.clientY;
        
        marker.classList.add('dragging');
        
        if (sitePlanConfig.logMarkerDrag) {
            this.logDebug('Started dragging marker:', {
                id: marker.dataset.locationId,
                initialX: parseFloat(marker.style.left),
                initialY: parseFloat(marker.style.top)
            });
        }
    },

    handleDragMove(event) {
        if (!this.state.isDragging) return;
        
        const marker = this.state.dragTarget;
        const container = marker.closest('#siteMapEditorContainer');
        const rect = container.getBoundingClientRect();
        
        const deltaX = event.clientX - this.state.originalX;
        const deltaY = event.clientY - this.state.originalY;
        
        const percentX = (deltaX / rect.width) * 100;
        const percentY = (deltaY / rect.height) * 100;
        
        // Get the initial position when drag started
        const initialX = parseFloat(marker.style.left) || 0;
        const initialY = parseFloat(marker.style.top) || 0;
        
        const newX = Math.max(0, Math.min(100, initialX + percentX));
        const newY = Math.max(0, Math.min(100, initialY + percentY));
        
        marker.style.left = `${newX}%`;
        marker.style.top = `${newY}%`;

        if (sitePlanConfig.logMarkerDrag) {
            this.logDebug('Marker position:', { newX, newY });
        }

        // Reset the original position for the next move
        this.state.originalX = event.clientX;
        this.state.originalY = event.clientY;
    },

    endDrag(moveHandler, upHandler) {
        const marker = this.state.dragTarget;
        
        if (sitePlanConfig.logMarkerDrag) {
            this.logDebug('Finished dragging marker:', {
                id: marker.dataset.locationId,
                finalX: parseFloat(marker.style.left),
                finalY: parseFloat(marker.style.top)
            });
        }
        
        marker.classList.remove('dragging');
        this.state.isDragging = false;
        this.state.dragTarget = null;
        
        document.removeEventListener('mousemove', moveHandler);
        document.removeEventListener('mouseup', upHandler);
    },

    openEditor() {
        if (sitePlanConfig.debug) console.group('Opening Site Plan Editor');

        new bootstrap.Modal(this.modal).show();
        
        // Clone and prepare editor container
        this.prepareEditorContainer();
        
        // Initialize controls and drag handlers
        this.initializeEditorControls();
        this.initializeEditorMarkers();

        if (sitePlanConfig.debug) console.groupEnd();
    },

    prepareEditorContainer() {
        if (sitePlanConfig.debug) console.group('Preparing Editor Container');

        const editorContainer = this.editorContainer;
        editorContainer.innerHTML = '';
        
        const clone = this.mainContainer.cloneNode(true);
        clone.id = 'site-plan-layout-clone';
        
        // Process all location markers in the editor
        const markers = clone.querySelectorAll('.location-marker');
        markers.forEach(marker => {
            // Remove any display:none that might be set
            marker.classList.remove('d-none');
            
            // Style based on active state
            const isActive = marker.dataset.locationActive === 'true';
            if (!isActive) {
                marker.classList.add('opacity-50');
                marker.style.opacity = '0.5';
                
                if (sitePlanConfig.debug) {
                    this.logDebug('Styling inactive marker:', {
                        id: marker.dataset.locationId,
                        name: marker.title || 'Unnamed'
                    });
                }
            }

            // Add visual feedback for draggable state
            marker.classList.add('cursor-move');
            marker.title = `${marker.title || 'Location'} (Drag to reposition)`;
        });
        
        if (sitePlanConfig.debug) {
            this.logDebug(`Processed ${markers.length} markers:`, {
                total: markers.length,
                active: Array.from(markers).filter(m => m.dataset.locationActive === 'true').length,
                inactive: Array.from(markers).filter(m => m.dataset.locationActive === 'false').length
            });
        }
        
        editorContainer.appendChild(clone);
        
        if (sitePlanConfig.debug) console.groupEnd();
    },

    initializeEditorMarkers() {
        const markers = this.editorContainer.querySelectorAll('.location-marker');
        this.logDebug(`Re-initializing drag handlers for ${markers.length} cloned markers`);
        markers.forEach(marker => this.initializeMarkerDrag(marker));
    },

    initializeEditorControls() {
        const container = this.editorClone;
        
        // Zoom controls
        document.getElementById('zoomIn').onclick = () => {
            this.state.scale *= this.ZOOM_FACTOR;
            this.updateContainerTransform(container);
        };
        
        document.getElementById('zoomOut').onclick = () => {
            this.state.scale /= this.ZOOM_FACTOR;
            this.updateContainerTransform(container);
        };
        
        // Movement controls
        document.getElementById('moveLeft').onclick = () => {
            this.state.x -= this.PAN_DISTANCE;
            this.updateContainerTransform(container);
        };
        
        document.getElementById('moveRight').onclick = () => {
            this.state.x += this.PAN_DISTANCE;
            this.updateContainerTransform(container);
        };
        
        document.getElementById('moveUp').onclick = () => {
            this.state.y -= this.PAN_DISTANCE;
            this.updateContainerTransform(container);
        };
        
        document.getElementById('moveDown').onclick = () => {
            this.state.y += this.PAN_DISTANCE;
            this.updateContainerTransform(container);
        };
        
        // Reset view
        document.getElementById('resetView').onclick = () => {
            this.state.scale = 1;
            this.state.x = 0;
            this.state.y = 0;
            this.updateContainerTransform(container);
        };
        
        // Save changes
        document.getElementById('savePositions').onclick = () => this.saveChanges();

        // Add aspect ratio controls
        document.getElementById('aspectRatioSelect').onchange = (e) => {
            const ratio = e.target.value;
            if (ratio === 'custom') {
                document.getElementById('customAspectRatio').style.display = 'block';
            } else {
                document.getElementById('customAspectRatio').style.display = 'none';
                this.updateAspectRatio(this.ASPECT_RATIOS[ratio]);
            }
        };

        document.getElementById('customAspectRatioForm').onsubmit = (e) => {
            e.preventDefault();
            const width = parseFloat(document.getElementById('aspectWidth').value);
            const height = parseFloat(document.getElementById('aspectHeight').value);
            if (width && height) {
                this.updateAspectRatio(width / height);
            }
        };
    },

    updateContainerTransform(container = null) {
        container = container || this.mainContainer;
        if (!container) return;
        
        const transform = `scale(${this.state.scale}) translate(${this.state.x}px, ${this.state.y}px)`;
        container.style.transform = transform;

        if (sitePlanConfig.logTransforms) {
            this.logDebug('Container transform updated:', {
                scale: this.state.scale,
                x: this.state.x,
                y: this.state.y,
                transform
            });
        }
    },

    updateAspectRatio(ratio) {
        if (!ratio || ratio <= 0) return;

        const container = this.editorClone || this.mainContainer;
        if (!container) return;

        const img = container.querySelector('img');
        if (!img) return;

        // Store the new ratio
        this.state.aspectRatio = ratio;

        // Calculate new dimensions
        const containerWidth = container.offsetWidth;
        const containerHeight = containerWidth / ratio;

        // Update container style
        container.style.height = `${containerHeight}px`;

        if (sitePlanConfig.logTransforms) {
            this.logDebug('Aspect ratio updated:', {
                ratio,
                containerWidth,
                containerHeight
            });
        }

        // Update transform to maintain position
        this.updateContainerTransform(container);
    },

    async saveChanges() {
        if (sitePlanConfig.debug && sitePlanConfig.logSaveOperations) {
            console.group('Saving Site Plan Changes');
        }

        const container = document.getElementById('site-plan-layout-clone');
        const mainContainer = document.getElementById('site-plan-layout');
        const markers = container.querySelectorAll('.location-marker');
        
        // Check for site plan transform changes
        const sitePlanUpdates = {};
        const originalScale = parseFloat(mainContainer.dataset.scale) || 1.0;
        const originalX = parseFloat(mainContainer.dataset.x) || 0;
        const originalY = parseFloat(mainContainer.dataset.y) || 0;

        if (this.state.scale !== originalScale) {
            sitePlanUpdates.site_plan_scale = this.state.scale;
        }
        if (this.state.x !== originalX) {
            sitePlanUpdates.site_plan_x = this.state.x;
        }
        if (this.state.y !== originalY) {
            sitePlanUpdates.site_plan_y = this.state.y;
        }

        if (sitePlanConfig.debug && sitePlanConfig.logSaveOperations) {
            console.log('Site Plan Transform Changes:', {
                original: { 
                    site_plan_scale: originalScale,
                    site_plan_x: originalX,
                    site_plan_y: originalY
                },
                current: {
                    site_plan_scale: this.state.scale,
                    site_plan_x: this.state.x,
                    site_plan_y: this.state.y
                },
                updates: sitePlanUpdates
            });
        }
        
        // Get location position updates
        const locationUpdates = Array.from(markers).reduce((moved, marker) => {
            const id = marker.dataset.locationId;
            const newX = parseFloat(marker.style.left) || 0;
            const newY = parseFloat(marker.style.top) || 0;
            
            if (sitePlanConfig.debug && (isNaN(newX) || isNaN(newY))) {
                this.logWarning('Invalid marker position:', {
                    id,
                    left: marker.style.left,
                    top: marker.style.top,
                    parsedX: newX,
                    parsedY: newY
                });
            }
            
            const originalMarker = mainContainer.querySelector(`[data-location-id="${id}"]`);
            if (originalMarker) {
                const originalX = parseFloat(originalMarker.style.left) || 0;
                const originalY = parseFloat(originalMarker.style.top) || 0;
                
                if (originalX !== newX || originalY !== newY) {
                    moved.push({ id, x: newX, y: newY });
                    if (sitePlanConfig.debug && sitePlanConfig.logSaveOperations) {
                        console.log('Location position changed:', {
                            id,
                            name: marker.title || id,
                            from: { x: originalX, y: originalY },
                            to: { x: newX, y: newY }
                        });
                    }
                }
            }
            return moved;
        }, []);

        // Only send request if there are actual changes
        if (locationUpdates.length === 0 && Object.keys(sitePlanUpdates).length === 0) {
            if (sitePlanConfig.debug) {
                console.log('No changes detected, skipping save');
                console.groupEnd();
            }
            bootstrap.Modal.getInstance(document.getElementById('sitePlanModal')).hide();
            return;
        }

        try {
            const payload = {
                ...sitePlanUpdates,
                site_plan_aspect_ratio: this.state.aspectRatio,
                locations: locationUpdates
            };
            
            if (sitePlanConfig.debug) {
                console.log('Sending request:', {
                    url: `/api/${window.currentPlaceSlug}/update_site_plan_layout/`,
                    payload
                });
            }

            const response = await utils.fetchWithCSRF(
                `/api/${window.currentPlaceSlug}/update_site_plan_layout/`,
                {
                    method: 'POST',
                    body: JSON.stringify(payload)
                }
            );
            
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`Server returned ${response.status}: ${errorText}`);
            }
            
            const data = await response.json();
            
            // Update the main container with new positions
            locationUpdates.forEach(update => {
                const marker = mainContainer.querySelector(`[data-location-id="${update.id}"]`);
                if (marker) {
                    marker.style.left = `${update.x}%`;
                    marker.style.top = `${update.y}%`;
                }
            });
            
            // Update main container transform
            if (Object.keys(sitePlanUpdates).length > 0) {
                mainContainer.dataset.scale = this.state.scale;
                mainContainer.dataset.x = this.state.x;
                mainContainer.dataset.y = this.state.y;
                this.updateContainerTransform(mainContainer);
            }
            
            // Close modal
            bootstrap.Modal.getInstance(document.getElementById('sitePlanModal')).hide();
            
            // Show detailed success message from server
            toastSystem.show({
                message: data.message,
                type: data.type || 'warning'
            });

            if (sitePlanConfig.debug && sitePlanConfig.logSaveOperations) {
                console.log('Successfully saved changes:', data.changes);
            }
            
        } catch (error) {
            console.error('Failed to save changes:', {
                error,
                message: error.message,
                response: error.response,
                stack: error.stack
            });
            const errorMessage = error.response?.data?.error || error.message || 'Failed to save changes';
            toastSystem.show({
                message: errorMessage,
                type: 'danger'
            });
        }

        if (sitePlanConfig.debug && sitePlanConfig.logSaveOperations) {
            console.groupEnd();
        }
    }
};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    sitePlanSystem.logDebug('=== Site Plan Editor Starting Up ===');
    sitePlanSystem.initialize();
});

// Export for use in other modules
window.sitePlanSystem = sitePlanSystem; 