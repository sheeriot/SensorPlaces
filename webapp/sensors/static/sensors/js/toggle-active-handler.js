/**
 * Toggle Active Handler
 * 
 * Manages active/inactive state toggling for locations, devices, and sensors
 * 
 * Configuration:
 * -------------
 * To enable debugging, set debug: true in toggleActiveConfig below
 * Debug mode will:
 * - Show toggle lifecycle events
 * - Log state changes
 * - Display API interactions
 */

// System Configuration
const toggleActiveConfig = {
    debug: false,            // Set to true to enable debug mode
    logMarkerChanges: true, // Log marker additions and changes
    logMapEvents: true,     // Log map initialization and updates
    logStatusChanges: true  // Log status label changes
};

// Card structure validator
function validateCardStructure(card, index) {
    const issues = [];
    
    // Check for required class and ID
    if (!card.classList.contains('card')) {
        issues.push('Missing required class="card"');
    }
    if (!card.id) {
        issues.push('Missing required unique ID');
    }

    // Check direct children
    const children = Array.from(card.children);
    const header = children.find(child => child.classList.contains('card-header'));
    const body = children.find(child => child.classList.contains('card-body'));
    const footer = children.find(child => child.classList.contains('card-footer'));
    const unexpectedChildren = children.filter(child => 
        !child.classList.contains('card-header') && 
        !child.classList.contains('card-body') && 
        !child.classList.contains('card-footer')
    );

    if (!header) {
        issues.push('Missing required .card-header');
    }
    if (!body) {
        issues.push('Missing required .card-body');
    }
    if (unexpectedChildren.length > 0) {
        issues.push(`Found ${unexpectedChildren.length} unexpected direct children (only .card-header, .card-body, and .card-footer allowed)`);
    }

    // Check card title location
    if (header) {
        const cardTitles = header.querySelectorAll('.card-title');
        if (cardTitles.length === 0) {
            issues.push('Missing .card-title in .card-header');
        } else if (cardTitles.length > 1) {
            issues.push(`Found ${cardTitles.length} .card-title elements (should be exactly 1)`);
        }
        
        // Check for old ID-based card titles
        const idBasedTitles = header.querySelectorAll('#card-title');
        if (idBasedTitles.length > 0) {
            issues.push('Found #card-title (should use class="card-title" instead)');
        }
    }

    if (issues.length > 0) {
        console.warn(`Card ${index + 1} (${card.id || 'no-id'}) structure issues:`, issues);
        console.debug('Problematic card HTML:', card.outerHTML);
    }

    return {
        header,
        body,
        footer,
        issues
    };
}

// Card status reporter
function reportCardStatus() {
    if (!toggleActiveConfig.debug) return;
    
    document.querySelectorAll('.card-body').forEach((cardBody, index) => {
        const card = cardBody.closest('.card');
        if (!card) {
            console.error(`Card body ${index + 1} is not within a .card element`);
            return;
        }

        // Start card report group first
        console.group(`Card ${index + 1}: ${card.querySelector('.card-title, #card-title')?.textContent?.trim() || 'Untitled'} (${card.id || 'no-id'})`);
        
        // Validate card structure (now inside the group)
        const { header: cardHeader, issues } = validateCardStructure(card, index);
        const cardTitle = cardHeader?.querySelector('.card-title, #card-title')?.textContent?.trim();
        
        // 1. Card Structure Info
        console.debug('Card Structure:', {
            id: card.id || 'UnnamedCard',
            title: cardTitle || 'No Title',
            structureIssues: issues.length > 0 ? issues : 'None'
        });

        // Log validation issues inside the card group
        if (issues.length > 0) {
            console.warn(`Structure issues:`, issues);
            console.debug('Card HTML:', card.outerHTML);
        }

        // 2. Header Toggles Report
        if (cardHeader) {
            console.group('Header Toggles');
            const headerToggles = ['location', 'device', 'sensor'].map(type => ({
                type,
                elements: Array.from(cardHeader.querySelectorAll(`.toggle-${type}-active`))
            })).filter(t => t.elements.length > 0);

            if (headerToggles.length > 0) {
                headerToggles.forEach(({ type, elements }) => {
                    console.table(elements.map(toggle => ({
                        type,
                        id: toggle.dataset[`${type}Id`] || 'no-id',
                        element: toggle.tagName.toLowerCase(),
                        active: toggle.checked || false
                    })));
                });
            } else {
                console.debug('No toggles found in header');
            }
            console.groupEnd(); // End Header Toggles group
        }

        // 3. Body Toggles Report
        console.group('Body Toggles');
        const bodyToggles = ['location', 'device', 'sensor'].map(type => ({
            type,
            elements: Array.from(cardBody.querySelectorAll(`.toggle-${type}-active`))
        })).filter(t => t.elements.length > 0);

        if (bodyToggles.length > 0) {
            bodyToggles.forEach(({ type, elements }) => {
                console.table(elements.map(toggle => ({
                    type,
                    id: toggle.dataset[`${type}Id`] || 'no-id',
                    element: toggle.tagName.toLowerCase(),
                    active: toggle.checked || false,
                    location: toggle.closest('tr') ? 'table-row' : 'other'
                })));
            });
        } else {
            console.debug('No toggles found in body');
        }
        console.groupEnd(); // End Body Toggles group

        console.groupEnd(); // End Card group
    });
}

// Status Management System
const toggleActiveManager = {
    async toggleStatus(type, id, placeSlug, intendedState) {
        if (toggleActiveConfig.debug) {
            console.group('Toggle Status Request');
            console.debug('Parameters:', { type, id, placeSlug, intendedState });
        }

        try {
            const data = await utils.fetchWithCSRF(
                `/api/${placeSlug}/toggle_active/${type}/${id}/`,
                {
                    method: 'POST',
                    body: JSON.stringify({ is_active: intendedState })
                }
            );
            
            if (toggleActiveConfig.debug) {
                console.debug('Server Response:', data);
            }
            
            if (data.status === 'success') {
                // Find all rows that match this model type and ID
                const rows = document.querySelectorAll(`[data-${type}-id="${id}"]`);
                
                // Find the hideInactive state for this model type
                const hideInactiveState = window.hideInactiveManager?.getSwitchStateByModel(type) ?? false;
                
                if (toggleActiveConfig.debug) {
                    console.debug('Updating UI elements:', {
                        rowsFound: rows.length,
                        hideInactiveState,
                        type
                    });
                }
                
                rows.forEach(row => {
                    // Update row attributes to match server state
                    row.setAttribute(`data-${type}-active`, data.is_active.toString());
                    
                    // Update classes based on active state
                    if (data.is_active) {
                        row.classList.remove('opacity-50', 'text-muted', 'd-none');
                    } else {
                        row.classList.add('opacity-50', 'text-muted');
                        // If hideInactive is enabled for this type, also hide the row
                        if (hideInactiveState) {
                            row.classList.add('d-none');
                        }
                    }

                    // Update toggle text - FIXED SELECTOR
                    const statusLabel = row.tagName.toLowerCase() === 'input' 
                        ? row.parentElement.querySelector('.status-label')  // If row is the input, look for sibling label
                        : row.querySelector('.status-label');              // Otherwise look within the row
                        
                    if (statusLabel) {
                        if (toggleActiveConfig.debug) {
                            console.group('Status Label Update');
                            console.debug('Found status label:', statusLabel);
                        }

                        statusLabel.textContent = data.is_active ? 'Active' : 'inactive';
                        statusLabel.classList.toggle('text-success', data.is_active);
                        statusLabel.classList.toggle('text-danger', !data.is_active);

                        if (toggleActiveConfig.debug) {
                            console.debug('Updated to:', {
                                text: statusLabel.textContent,
                                classes: Array.from(statusLabel.classList)
                            });
                            console.groupEnd();
                        }
                    } else if (toggleActiveConfig.debug) {
                        console.warn('Status label not found for:', {
                            type,
                            id,
                            row,
                            parentElement: row.parentElement
                        });
                    }

                    // Handle device detail card if it exists
                    if (type === 'device') {
                        const deviceCard = document.getElementById(`deviceCard_${id}`);
                        if (deviceCard) {
                            if (toggleActiveConfig.debug) {
                                console.group('Device Card Update');
                                console.debug('Found device card:', deviceCard);
                            }

                            // Find badge within the device card
                            const isactiveBadge = deviceCard.querySelector('.isactive-badge span.badge');
                            if (isactiveBadge) {
                                if (toggleActiveConfig.debug) {
                                    console.debug('Found badge:', {
                                        before: {
                                            classes: Array.from(isactiveBadge.classList),
                                            hidden: isactiveBadge.classList.contains('d-none'),
                                            text: isactiveBadge.textContent
                                        }
                                    });
                                }

                                if (data.is_active) {
                                    isactiveBadge.classList.add('d-none');
                                } else {
                                    isactiveBadge.classList.remove('d-none');
                                }

                                if (toggleActiveConfig.debug) {
                                    console.debug('After badge update:', {
                                        after: {
                                            classes: Array.from(isactiveBadge.classList),
                                            hidden: isactiveBadge.classList.contains('d-none'),
                                            text: isactiveBadge.textContent
                                        }
                                    });
                                }
                            } else if (toggleActiveConfig.debug) {
                                console.warn('Badge not found in device card:', {
                                    deviceCard,
                                    selector: '.isactive-badge span.badge'
                                });
                            }

                            if (toggleActiveConfig.debug) {
                                console.groupEnd();
                            }

                            // Update card opacity
                            if (data.is_active) {
                                deviceCard.classList.remove('opacity-75');
                            } else {
                                deviceCard.classList.add('opacity-75');
                            }
                        }
                    }

                    // Handle child toggles based on parent type
                    if (type === 'location') {
                        // Find all device toggles within this location
                        const deviceToggles = document.querySelectorAll(`.toggle-device-active[data-location-id="${id}"]`);
                        deviceToggles.forEach(toggle => {
                            const toggleContainer = toggle.closest('.form-check');
                            if (toggleContainer) {
                                if (data.is_active) {
                                    toggleContainer.classList.remove('d-none');
                                    toggle.disabled = false;
                                } else {
                                    toggleContainer.classList.add('d-none');
                                    toggle.disabled = true;
                                }
                            }
                        });

                        // Update status badges visibility
                        const statusBadges = document.querySelectorAll(`[data-location-id="${id}"] .isactive-badge .badge`);
                        statusBadges.forEach(badge => {
                            if (data.is_active) {
                                badge.classList.add('d-none');
                            } else {
                                badge.classList.remove('d-none');
                            }
                        });
                    } else if (type === 'device') {
                        // Find all sensor toggles within this device
                        const sensorToggles = document.querySelectorAll(`.toggle-sensor-active[data-device-id="${id}"]`);
                        sensorToggles.forEach(toggle => {
                            const toggleContainer = toggle.closest('.form-check');
                            if (toggleContainer) {
                                if (data.is_active) {
                                    toggleContainer.classList.remove('d-none');
                                    toggle.disabled = false;
                                } else {
                                    toggleContainer.classList.add('d-none');
                                    toggle.disabled = true;
                                }
                            }
                        });

                        // Update status badges visibility
                        const sensorStatusBadges = document.querySelectorAll(`[data-device-id="${id}"] .isactive-badge .badge`);
                        sensorStatusBadges.forEach(badge => {
                            if (data.is_active) {
                                badge.classList.add('d-none');
                            } else {
                                badge.classList.remove('d-none');
                            }
                        });
                    }

                    // Handle map markers if this is a place toggle
                    if (type === 'place') {
                        this.updateMapMarkers(id, data.is_active, hideInactiveState);
                    }
                });

                // Find and update all toggle switches for this type/id
                const toggles = document.querySelectorAll(`.toggle-${type}-active[data-${type}-id="${id}"]`);
                toggles.forEach(toggle => {
                    if (toggle.tagName.toLowerCase() === 'input') {
                        toggle.checked = data.is_active;
                    }
                });

                return data;
            } else if (data.status === 'warning') {
                // Handle warning status without throwing an error
                if (toggleActiveConfig.debug) {
                    console.warn('Toggle Status Warning:', data.message);
                }
                return data;
            } else {
                throw new Error(data.message || `Failed to update ${type} status`);
            }
        } catch (error) {
            if (toggleActiveConfig.debug) {
                console.error('Toggle Status Error:', error);
            }
            this.showToast({
                message: error.message,
                type: 'danger',
                addToHistory: true
            });
            return null;
        } finally {
            if (toggleActiveConfig.debug) {
                console.groupEnd();
            }
        }
    },

    updateMapMarkers(placeId, isActive, hideInactive) {
        if (toggleActiveConfig.debug) {
            console.group('Updating Map Markers');
            console.debug('Parameters:', { placeId, isActive, hideInactive });
        }

        try {
            // Update Folium markers
            const foliumMarkers = document.querySelectorAll(`.place-marker[data-place-id="${placeId}"]`);
            if (toggleActiveConfig.debug) {
                console.debug('Found Folium markers:', foliumMarkers.length);
            }

            foliumMarkers.forEach(marker => {
                marker.dataset.placeActive = isActive.toString();
                if (isActive) {
                    marker.classList.remove('opacity-50', 'text-muted', 'd-none');
                } else {
                    marker.classList.add('opacity-50', 'text-muted');
                    if (hideInactive) {
                        marker.classList.add('d-none');
                    }
                }
            });

            // Update Leaflet markers
            const leafletMaps = document.querySelectorAll('.leaflet-map-pane');
            leafletMaps.forEach(mapPane => {
                const markerPane = mapPane.querySelector('.leaflet-marker-pane');
                if (!markerPane) return;

                const leafletMarkers = markerPane.querySelectorAll(`.leaflet-marker-icon[data-place-id="${placeId}"]`);
                if (toggleActiveConfig.debug) {
                    console.debug('Found Leaflet markers:', leafletMarkers.length);
                }

                leafletMarkers.forEach(marker => {
                    marker.dataset.placeActive = isActive.toString();
                    if (isActive) {
                        marker.style.display = '';
                        marker.style.opacity = '1';
                    } else {
                        if (hideInactive) {
                            marker.style.display = 'none';
                        }
                        marker.style.opacity = '0.5';
                    }
                });
            });

        } catch (error) {
            console.error('Error updating map markers:', error);
        }

        if (toggleActiveConfig.debug) {
            console.groupEnd();
        }
    },

    async updateDeviceStatus(deviceId, isActive, placeSlug) {
        if (toggleActiveConfig.debug) {
            console.debug('Action:', { type: 'device', action: 'update', deviceId, isActive });
        }

        try {
            const response = await utils.fetchWithCSRF(
                `/api/${placeSlug}/device/${deviceId}/toggle_active/`,
                {
                    method: 'POST',
                    body: JSON.stringify({ is_active: isActive })
                }
            );
            
            if (!response.ok) throw new Error('Network response was not ok');
            const data = await response.json();
            
            if (data.status === 'success') {
                const device = data.device;
                const row = document.querySelector(`tr[data-device-id="${device.id}"]`);
                
                // Update row styling
                if (!device.is_active) {
                    row.classList.add('text-muted', 'opacity-50');
                } else {
                    row.classList.remove('text-muted', 'opacity-50', 'd-none');
                }

                // Update toggle switch and status label
                const toggle = row.querySelector('.toggle-device-active');
                if (toggle) {
                    toggle.checked = device.is_active;
                    toggle.dataset.currentStatus = device.is_active.toString();
                }

                const statusLabel = row.querySelector('.status-label');
                if (statusLabel) {
                    statusLabel.textContent = device.is_active ? 'Active' : 'Inactive';
                    statusLabel.classList.toggle('text-success', device.is_active);
                    statusLabel.classList.toggle('text-danger', !device.is_active);
                }

                // Show toast with affected sensors if any
                let message = data.message;
                if (device.affected_sensors && device.affected_sensors.length > 0) {
                    message += '<br><br>Affected sensors:<ul class="mb-0">';
                    device.affected_sensors.forEach(sensor => {
                        message += `<li>${sensor}</li>`;
                    });
                    message += '</ul>';
                }
                
                this.showToast(message, 'success', true);
                return data;
            } else {
                throw new Error(data.message || 'Failed to update device status');
            }
        } catch (error) {
            if (toggleActiveConfig.debug) {
                console.debug('Error:', { type: 'device', error: error.message });
            }
            this.showToast(error.message, 'danger', true);
            return null;
        }
    },

    createToggleModal(type) {
        const modalId = `${type}ToggleModal`;
        if (!document.getElementById(modalId)) {
            const modalHTML = `
                <div class="modal fade" id="${modalId}" tabindex="-1" aria-labelledby="${modalId}Label" aria-hidden="true" data-bs-backdrop="static">
                    <div class="modal-dialog">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title" id="${modalId}Label">Confirm Status Change</h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                            </div>
                            <div class="modal-body">
                                <p id="${type}ToggleMessage"></p>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                                <button type="button" class="btn btn-primary" id="confirm${type.charAt(0).toUpperCase() + type.slice(1)}Toggle">
                                    <span class="spinner-border spinner-border-sm d-none" role="status" aria-hidden="true"></span>
                                    Confirm
                                </button>
                            </div>
                        </div>
                    </div>
                </div>`;
            document.body.insertAdjacentHTML('beforeend', modalHTML);
        }

        const modalElement = document.getElementById(modalId);
        let modal = bootstrap.Modal.getInstance(modalElement);
        if (!modal) {
            modal = new bootstrap.Modal(modalElement, {
                backdrop: 'static',
                keyboard: false
            });
        }

        return {
            modal: modal,
            element: modalElement,
            messageEl: document.getElementById(`${type}ToggleMessage`),
            confirmBtn: document.getElementById(`confirm${type.charAt(0).toUpperCase() + type.slice(1)}Toggle`),
            spinner: document.getElementById(`confirm${type.charAt(0).toUpperCase() + type.slice(1)}Toggle`).querySelector('.spinner-border')
        };
    },

    initializeLocationToggles() {
        const modalComponents = this.createToggleModal('location');
        
        document.querySelectorAll('.toggle-location-active').forEach(toggle => {
            if (toggle.tagName.toLowerCase() === 'button') return; // Skip buttons, they're handled separately
            
            const oldHandler = toggle._changeHandler;
            if (oldHandler) toggle.removeEventListener('change', oldHandler);

            const changeHandler = async function(e) {
                e.preventDefault();
                
                const locationId = this.dataset.locationId;
                const placeSlug = this.dataset.placeSlug;
                const newStatus = this.checked;
                const toggleElement = this;

                // Find the parent row to get the names
                const row = document.querySelector(`tr[data-location-id="${locationId}"]`);
                const locationName = row.dataset.locationName;
                const placeName = row.dataset.placeName;

                this.checked = !newStatus;
                
                modalComponents.messageEl.innerHTML = newStatus ? 
                    `Are you sure you want to Activate <i class='bi bi-geo-alt'></i> ${locationName} at <i class='bi bi-house-gear'></i> ${placeName}?` : 
                    `Are you sure you want to Deactivate <i class='bi bi-geo-alt'></i> ${locationName} at <i class='bi bi-house-gear'></i> ${placeName}?`;

                modalComponents.confirmBtn.disabled = false;
                modalComponents.spinner.classList.add('d-none');
                
                modalComponents.modal.show();

                const handleConfirm = async () => {
                    modalComponents.confirmBtn.disabled = true;
                    modalComponents.spinner.classList.remove('d-none');

                    try {
                        const result = await toggleActiveManager.toggleStatus('location', locationId, placeSlug, newStatus);
                        if (result) {
                            toggleElement.checked = result.is_active;
                            modalComponents.modal.hide();
                        }
                    } finally {
                        modalComponents.confirmBtn.disabled = false;
                        modalComponents.spinner.classList.add('d-none');
                    }
                };

                modalComponents.confirmBtn.removeEventListener('click', handleConfirm);
                modalComponents.confirmBtn.addEventListener('click', handleConfirm, { once: true });
            };

            toggle._changeHandler = changeHandler;
            toggle.addEventListener('change', changeHandler);
        });
    },

    initializeDeviceToggles() {
        const modalComponents = this.createToggleModal('device');
        
        document.querySelectorAll('.toggle-device-active').forEach(toggle => {
            if (toggle.tagName.toLowerCase() === 'button') return; // Skip buttons, they're handled separately
            
            const oldHandler = toggle._changeHandler;
            if (oldHandler) toggle.removeEventListener('change', oldHandler);

            const changeHandler = async function(e) {
                e.preventDefault();
                
                const deviceId = this.dataset.deviceId;
                const placeSlug = this.dataset.placeSlug;
                const newStatus = this.checked;
                const toggleElement = this;

                this.checked = !newStatus;
                
                modalComponents.messageEl.textContent = newStatus ? 
                    'Are you sure you want to activate this device? This will allow its sensors to be activated.' : 
                    'Are you sure you want to deactivate this device? This will disable all its sensors.';

                modalComponents.confirmBtn.disabled = false;
                modalComponents.spinner.classList.add('d-none');
                
                modalComponents.modal.show();

                const handleConfirm = async () => {
                    modalComponents.confirmBtn.disabled = true;
                    modalComponents.spinner.classList.remove('d-none');

                    try {
                        const result = await toggleActiveManager.toggleStatus('device', deviceId, placeSlug, newStatus);
                        if (result) {
                            toggleElement.checked = result.is_active;
                            modalComponents.modal.hide();
                        }
                    } finally {
                        modalComponents.confirmBtn.disabled = false;
                        modalComponents.spinner.classList.add('d-none');
                    }
                };

                modalComponents.confirmBtn.removeEventListener('click', handleConfirm);
                modalComponents.confirmBtn.addEventListener('click', handleConfirm, { once: true });
            };

            toggle._changeHandler = changeHandler;
            toggle.addEventListener('change', changeHandler);
        });
    },

    initializeSensorToggles() {
        const modalComponents = this.createToggleModal('sensor');
        
        document.querySelectorAll('.toggle-sensor-active').forEach(toggle => {
            if (toggle.tagName.toLowerCase() === 'button') return; // Skip buttons, they're handled separately
            
            const oldHandler = toggle._changeHandler;
            if (oldHandler) toggle.removeEventListener('change', oldHandler);

            const changeHandler = async function(e) {
                e.preventDefault();
                
                const sensorId = this.dataset.sensorId;
                const placeSlug = this.dataset.placeSlug;
                const newStatus = this.checked;
                const toggleElement = this;

                this.checked = !newStatus;
                
                modalComponents.messageEl.textContent = newStatus ? 
                    'Are you sure you want to activate this sensor?' : 
                    'Are you sure you want to deactivate this sensor?';

                modalComponents.confirmBtn.disabled = false;
                modalComponents.spinner.classList.add('d-none');
                
                modalComponents.modal.show();

                const handleConfirm = async () => {
                    modalComponents.confirmBtn.disabled = true;
                    modalComponents.spinner.classList.remove('d-none');

                    try {
                        const result = await toggleActiveManager.toggleStatus('sensor', sensorId, placeSlug, newStatus);
                        if (result) {
                            toggleElement.checked = result.is_active;
                            modalComponents.modal.hide();
                        }
                    } finally {
                        modalComponents.confirmBtn.disabled = false;
                        modalComponents.spinner.classList.add('d-none');
                    }
                };

                modalComponents.confirmBtn.removeEventListener('click', handleConfirm);
                modalComponents.confirmBtn.addEventListener('click', handleConfirm, { once: true });
            };

            toggle._changeHandler = changeHandler;
            toggle.addEventListener('change', changeHandler);
        });
    },

    initializeDeviceStatusButtons() {
        document.querySelectorAll('.toggle-device-active').forEach(button => {
            if (button.tagName.toLowerCase() !== 'button') return; // Only handle buttons
            
            button.addEventListener('click', async (e) => {
                e.preventDefault();
                const deviceId = button.dataset.deviceId;
                const placeSlug = button.dataset.placeSlug;
                const currentStatus = button.dataset.currentStatus === 'true';
                const newStatus = !currentStatus;
                
                const modalComponents = this.createToggleModal('device');
                modalComponents.messageEl.textContent = newStatus ? 
                    'Are you sure you want to activate this device? This will allow its sensors to be activated.' : 
                    'Are you sure you want to deactivate this device? This will disable all its sensors.';
                
                const handleConfirm = async () => {
                    modalComponents.confirmBtn.disabled = true;
                    modalComponents.spinner.classList.remove('d-none');
                    
                    try {
                        await this.updateDeviceStatus(deviceId, newStatus, placeSlug);
                        modalComponents.modal.hide();
                    } finally {
                        modalComponents.confirmBtn.disabled = false;
                        modalComponents.spinner.classList.add('d-none');
                    }
                };

                modalComponents.confirmBtn.removeEventListener('click', handleConfirm);
                modalComponents.confirmBtn.addEventListener('click', handleConfirm, { once: true });
                
                modalComponents.modal.show();
            });
        });
    },

    // Update showToast to handle both object and parameter formats
    showToast(messageOrObject, type = 'info', addToHistory = true) {
        let toastData;
        
        if (typeof messageOrObject === 'object') {
            toastData = messageOrObject;
        } else {
            toastData = {
                message: messageOrObject,
                type: type,
                addToHistory: addToHistory
            };
        }

        // Use the toast system if available, otherwise fallback to event dispatch
        if (window.toastSystem) {
            window.toastSystem.show(toastData);
        } else {
            document.dispatchEvent(new CustomEvent(ToastEvents.SHOW, {
                detail: toastData
            }));
        }
    }
};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    toggleActiveManager.initializeLocationToggles();
    toggleActiveManager.initializeDeviceToggles();
    toggleActiveManager.initializeSensorToggles();
    
    // Report initial card status
    reportCardStatus();
});

// Export for use in other modules
window.toggleActiveManager = toggleActiveManager; 