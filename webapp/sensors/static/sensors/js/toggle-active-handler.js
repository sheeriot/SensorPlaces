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
    debug: false,
    logMarkerChanges: true,
    logMapEvents: true,
    logStatusChanges: true
};

// console.log('toggleActiveConfig:', toggleActiveConfig);

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
    // Add getHideInactiveState before toggleStatus
    getHideInactiveState(type) {
        const switchEl = document.querySelector(`.hide-inactive-${type}-switch`);
        if (toggleActiveConfig.debug) {
            console.debug('Hide Inactive Switch:', {
                type,
                switchFound: !!switchEl,
                switchClass: `hide-inactive-${type}-switch`,
                state: switchEl?.checked
            });
        }
        return switchEl?.checked || false;
    },

    async toggleStatus(modelType, id, placeSlug) {
        if (toggleActiveConfig.debug) {
            console.group('Toggle Status Request');
            console.debug('Parameters:', { modelType, id, placeSlug });
        }

        try {
            const response = await window.utils.fetchWithCSRF(
                `/api/${placeSlug}/toggle-active/`,
                {
                    method: 'POST',
                    body: JSON.stringify({
                        model_type: modelType,
                        id: id
                    })
                }
            );
            
            if (toggleActiveConfig.debug) {
                console.debug('Server Response:', response);
            }
            
            if (response.success || response.status === 'success') {
                // Find all elements that match this model type and ID
                const wrappers = document.querySelectorAll(`.toggle-button-wrapper[data-${modelType}-id="${id}"]`);
                const rows = document.querySelectorAll(`[data-${modelType}-id="${id}"]`);
                
                // Find the hideInactive state for this model type
                const hideInactiveState = this.getHideInactiveState(modelType);
                
                // Update all toggle buttons
                const toggleButtons = document.querySelectorAll(`.toggle-${modelType}-active[data-${modelType}-id="${id}"]`);
                toggleButtons.forEach(button => {
                    // Update button state
                    button.setAttribute('data-current-status', response.is_active.toString());
                    button.setAttribute('aria-pressed', response.is_active.toString());
                    if (response.is_active) {
                        button.classList.add('active');
                    } else {
                        button.classList.remove('active');
                    }
                    
                    // Update status label
                    const statusLabel = button.querySelector('.status-label');
                    if (statusLabel) {
                        statusLabel.textContent = response.is_active ? 'Active' : 'Inactive';
                        statusLabel.classList.toggle('text-success', response.is_active);
                        statusLabel.classList.toggle('text-danger', !response.is_active);
                    }
                });
                
                // Update wrapper attributes
                wrappers.forEach(wrapper => {
                    wrapper.setAttribute(`data-${modelType}-active`, response.is_active.toString());
                });
                
                // Update other elements with the same data attribute
                rows.forEach(row => {
                    if (toggleActiveConfig.debug) {
                        console.group('Updating row');
                        console.debug('Row before update:', {
                            row,
                            classes: Array.from(row.classList),
                            active: row.getAttribute(`data-${modelType}-active`),
                            hideInactiveState
                        });
                    }

                    // Update row attributes to match server state
                    row.setAttribute(`data-${modelType}-active`, response.is_active.toString());
                    
                    // Update classes based on active state
                    if (response.is_active) {
                        row.classList.remove('opacity-50', 'text-muted', 'd-none');
                    } else {
                        row.classList.add('opacity-50', 'text-muted');
                        
                        // Check if hideInactive is enabled for this type
                        if (hideInactiveState) {
                            if (toggleActiveConfig.debug) {
                                console.debug('Hiding inactive row:', {
                                    hideInactiveState,
                                    rowType: modelType,
                                    rowId: id
                                });
                            }
                            row.classList.add('d-none');
                        }
                    }

                    // Update any other status labels inside the row
                    const statusLabels = row.querySelectorAll('.status-label');
                    statusLabels.forEach(label => {
                        if (!label.closest('.toggle-active-button')) { // Skip labels inside toggle buttons
                            label.textContent = response.is_active ? 'Active' : 'Inactive';
                            label.classList.toggle('text-success', response.is_active);
                            label.classList.toggle('text-danger', !response.is_active);
                        }
                    });

                    // Handle device detail card if it exists
                    if (modelType === 'device') {
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

                                if (response.is_active) {
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
                            }

                            if (toggleActiveConfig.debug) {
                                console.groupEnd();
                            }

                            // Update card opacity
                            if (response.is_active) {
                                deviceCard.classList.remove('opacity-75');
                            } else {
                                deviceCard.classList.add('opacity-75');
                            }
                        }
                    }

                    if (toggleActiveConfig.debug) {
                        console.debug('Row after update:', {
                            classes: Array.from(row.classList),
                            active: row.getAttribute(`data-${modelType}-active`),
                            hidden: row.classList.contains('d-none')
                        });
                        console.groupEnd();
                    }
                });

                // Handle child toggles based on parent type
                if (modelType === 'location') {
                    this.updateChildTogglesForLocation(id, response.is_active);
                } else if (modelType === 'device') {
                    this.updateChildTogglesForDevice(id, response.is_active);
                }

                // Handle map markers if this is a place toggle
                if (modelType === 'place') {
                    this.updateMapMarkers(id, response.is_active, hideInactiveState);
                }

                return response;
            } else if (response.status === 'warning') {
                // Handle warning status
                if (toggleActiveConfig.debug) {
                    console.warn('Toggle Status Warning:', response.message);
                }
                
                this.showToast({
                    message: response.message,
                    type: 'warning',
                    addToHistory: true
                });
                
                return response;
            } else {
                throw new Error(response.message || `Failed to update ${modelType} status`);
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
            // Clean up any old handlers
            toggle.removeEventListener('click', toggle._clickHandler);
            
            // Create new click handler
            const clickHandler = async function(e) {
                e.preventDefault();
                
                const locationId = this.dataset.locationId;
                const placeSlug = this.dataset.placeSlug;
                const currentStatus = this.getAttribute('aria-pressed') === 'true' || 
                                     this.dataset.currentStatus === 'true';
                const newStatus = !currentStatus;
                
                // Find the location name
                const wrapper = this.closest('.toggle-button-wrapper');
                let locationName = 'this location';
                
                // Try to find location name in parent row or from label
                const row = this.closest('tr, [data-location-name]');
                if (row && row.dataset.locationName) {
                    locationName = row.dataset.locationName;
                } else {
                    // Try to find from a nearby element with location-name class
                    const nameEl = document.querySelector(`.location-name[data-location-id="${locationId}"]`);
                    if (nameEl) {
                        locationName = nameEl.textContent.trim();
                    }
                }
                
                let message = newStatus ? 
                    `Are you sure you want to Activate <i class='bi bi-geo-alt'></i> ${locationName}?` : 
                    `Are you sure you want to Deactivate <i class='bi bi-geo-alt'></i> ${locationName}?`;

                // For deactivation, add info about active devices that will be deactivated
                if (!newStatus) {
                    // Find all active devices for this location
                    const activeDevices = Array.from(document.querySelectorAll(`.toggle-device-active[data-location-id="${locationId}"]`))
                        .filter(deviceToggle => {
                            return deviceToggle.classList.contains('active') || 
                                   deviceToggle.getAttribute('aria-pressed') === 'true' ||
                                   deviceToggle.dataset.currentStatus === 'true';
                        })
                        .map(deviceToggle => {
                            // Try to find device name
                            const deviceRow = deviceToggle.closest('tr, [data-device-name]');
                            if (deviceRow && deviceRow.dataset.deviceName) {
                                return deviceRow.dataset.deviceName;
                            }
                            
                            const deviceNameEl = deviceToggle.querySelector('.device-name') || 
                                                document.querySelector(`.device-name[data-device-id="${deviceToggle.dataset.deviceId}"]`);
                            return deviceNameEl ? deviceNameEl.textContent.trim() : null;
                        })
                        .filter(name => name); // Remove any null/undefined entries

                    if (activeDevices.length > 0) {
                        message += '<br><br>The following active devices will be deactivated:<ul class="mb-0">';
                        activeDevices.forEach(deviceName => {
                            message += `<li>${deviceName}</li>`;
                        });
                        message += '</ul>';
                        message += '<br><small class="text-muted">All sensors in these devices will also be deactivated.</small>';
                    }
                }
                
                modalComponents.messageEl.innerHTML = message;
                modalComponents.confirmBtn.disabled = false;
                modalComponents.spinner.classList.add('d-none');
                
                modalComponents.modal.show();

                const handleConfirm = async () => {
                    modalComponents.confirmBtn.disabled = true;
                    modalComponents.spinner.classList.remove('d-none');

                    try {
                        const result = await toggleActiveManager.toggleStatus('location', locationId, placeSlug);
                        if (result) {
                            modalComponents.modal.hide();
                            // Use the handleToggleResponse to process the response
                            toggleActiveManager.handleToggleResponse(result);
                        }
                    } finally {
                        modalComponents.confirmBtn.disabled = false;
                        modalComponents.spinner.classList.add('d-none');
                    }
                };

                modalComponents.confirmBtn.removeEventListener('click', handleConfirm);
                modalComponents.confirmBtn.addEventListener('click', handleConfirm, { once: true });
            };

            toggle._clickHandler = clickHandler;
            toggle.addEventListener('click', clickHandler);
        });
    },

    initializeDeviceToggles() {
        const modalComponents = this.createToggleModal('device');
        
        document.querySelectorAll('.toggle-device-active').forEach(toggle => {
            // Clean up any old handlers
            toggle.removeEventListener('click', toggle._clickHandler);
            
            // Create new click handler
            const clickHandler = async function(e) {
                e.preventDefault();
                
                const deviceId = this.dataset.deviceId;
                const placeSlug = this.dataset.placeSlug;
                const currentStatus = this.getAttribute('aria-pressed') === 'true' || 
                                     this.dataset.currentStatus === 'true';
                const newStatus = !currentStatus;
                
                // Find the device name
                let deviceName = 'this device';
                
                // Try to find device name in parent row or from label
                const row = this.closest('tr, [data-device-name]');
                if (row && row.dataset.deviceName) {
                    deviceName = row.dataset.deviceName;
                } else {
                    // Try to find from a nearby element with device-name class
                    const nameEl = this.querySelector('.device-name') || 
                                  document.querySelector(`.device-name[data-device-id="${deviceId}"]`);
                    if (nameEl) {
                        deviceName = nameEl.textContent.trim();
                    }
                }
                
                let message = '';
                if (newStatus) {
                    message = `Are you sure you want to activate <i class='bi bi-hdd-rack'></i> ${deviceName}?<br><small class="text-muted">This will allow its sensors to be activated.</small>`;
                } else {
                    // Find all active sensors for this device
                    const activeSensors = Array.from(document.querySelectorAll(`.toggle-sensor-active[data-device-id="${deviceId}"]`))
                        .filter(sensorToggle => {
                            return sensorToggle.classList.contains('active') || 
                                   sensorToggle.getAttribute('aria-pressed') === 'true' ||
                                   sensorToggle.dataset.currentStatus === 'true';
                        })
                        .map(sensorToggle => {
                            // Try to find sensor name
                            const sensorRow = sensorToggle.closest('tr, [data-sensor-name]');
                            if (sensorRow && sensorRow.dataset.sensorName) {
                                return sensorRow.dataset.sensorName;
                            }
                            
                            const sensorNameEl = sensorToggle.querySelector('.sensor-name') || 
                                               document.querySelector(`.sensor-name[data-sensor-id="${sensorToggle.dataset.sensorId}"]`);
                            return sensorNameEl ? sensorNameEl.textContent.trim() : null;
                        })
                        .filter(name => name); // Remove any null/undefined entries

                    message = `Are you sure you want to deactivate <i class='bi bi-hdd-rack'></i> ${deviceName}?`;
                    
                    if (activeSensors.length > 0) {
                        message += '<br><br>The following active sensors will be deactivated:<ul class="mb-0">';
                        activeSensors.forEach(sensorName => {
                            message += `<li>${sensorName}</li>`;
                        });
                        message += '</ul>';
                    }
                }
                
                modalComponents.messageEl.innerHTML = message;
                modalComponents.confirmBtn.disabled = false;
                modalComponents.spinner.classList.add('d-none');
                modalComponents.modal.show();

                const handleConfirm = async () => {
                    modalComponents.confirmBtn.disabled = true;
                    modalComponents.spinner.classList.remove('d-none');

                    try {
                        const result = await toggleActiveManager.toggleStatus('device', deviceId, placeSlug);
                        if (result) {
                            modalComponents.modal.hide();
                            // Use the handleToggleResponse to process the response
                            toggleActiveManager.handleToggleResponse(result);
                        }
                    } finally {
                        modalComponents.confirmBtn.disabled = false;
                        modalComponents.spinner.classList.add('d-none');
                    }
                };

                modalComponents.confirmBtn.removeEventListener('click', handleConfirm);
                modalComponents.confirmBtn.addEventListener('click', handleConfirm, { once: true });
            };

            toggle._clickHandler = clickHandler;
            toggle.addEventListener('click', clickHandler);
        });
    },

    initializeSensorToggles() {
        const modalComponents = this.createToggleModal('sensor');
        
        document.querySelectorAll('.toggle-sensor-active').forEach(toggle => {
            // Clean up any old handlers
            toggle.removeEventListener('click', toggle._clickHandler);
            
            // Create new click handler
            const clickHandler = async function(e) {
                e.preventDefault();
                
                const sensorId = this.dataset.sensorId;
                const placeSlug = this.dataset.placeSlug;
                const currentStatus = this.getAttribute('aria-pressed') === 'true' || 
                                     this.dataset.currentStatus === 'true';
                const newStatus = !currentStatus;
                
                // Find the sensor name
                let sensorName = 'this sensor';
                
                // Try to find sensor name in parent row or from label
                const row = this.closest('tr, [data-sensor-name]');
                if (row && row.dataset.sensorName) {
                    sensorName = row.dataset.sensorName;
                } else {
                    // Try to find from a nearby element with sensor-name class
                    const nameEl = this.querySelector('.sensor-name') || 
                                  document.querySelector(`.sensor-name[data-sensor-id="${sensorId}"]`);
                    if (nameEl) {
                        sensorName = nameEl.textContent.trim();
                    }
                }
                
                modalComponents.messageEl.innerHTML = newStatus ? 
                    `Are you sure you want to activate <i class='bi bi-thermometer'></i> ${sensorName}?` : 
                    `Are you sure you want to deactivate <i class='bi bi-thermometer'></i> ${sensorName}?`;

                modalComponents.confirmBtn.disabled = false;
                modalComponents.spinner.classList.add('d-none');
                
                modalComponents.modal.show();

                const handleConfirm = async () => {
                    modalComponents.confirmBtn.disabled = true;
                    modalComponents.spinner.classList.remove('d-none');

                    try {
                        const result = await toggleActiveManager.toggleStatus('sensor', sensorId, placeSlug);
                        if (result) {
                            modalComponents.modal.hide();
                            // Use the handleToggleResponse to process the response
                            toggleActiveManager.handleToggleResponse(result);
                        }
                    } finally {
                        modalComponents.confirmBtn.disabled = false;
                        modalComponents.spinner.classList.add('d-none');
                    }
                };

                modalComponents.confirmBtn.removeEventListener('click', handleConfirm);
                modalComponents.confirmBtn.addEventListener('click', handleConfirm, { once: true });
            };

            toggle._clickHandler = clickHandler;
            toggle.addEventListener('click', clickHandler);
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

    // Update showToast method to ensure proper handling
    showToast(messageOrObject, type = 'info', addToHistory = true) {
        if (toggleActiveConfig.debug) {
            console.log('showToast called with:', { messageOrObject, type, addToHistory });
        }

        const toastData = typeof messageOrObject === 'object' 
            ? messageOrObject 
            : { message: messageOrObject, type, addToHistory };

        if (window.toastSystem) {
            if (toggleActiveConfig.debug) {
                console.log('Delegating to toast system:', toastData);
            }
            window.toastSystem.show(toastData);
        } else {
            // Fallback to event dispatch
            if (toggleActiveConfig.debug) {
                console.log('Toast system not available, dispatching event');
            }
            document.dispatchEvent(new CustomEvent(ToastEvents.SHOW, {
                detail: toastData
            }));
        }
    },

    handleToggleResponse(response) {
        if (toggleActiveConfig.debug) {
            console.group('Handling Toggle Response');
            console.debug('Response:', response);
        }
        
        if (!response) {
            if (toggleActiveConfig.debug) {
                console.debug('No response to handle');
                console.groupEnd();
            }
            return;
        }

        try {
            // Handle toast message from response
            if (response.toast) {
                if (toggleActiveConfig.debug) {
                    console.debug('Showing toast from response:', response.toast);
                }
                // Use the toast system to display the message
                window.toastSystem.showToast(response.toast.message, response.toast.type);
            }
            
            // Handle any dependencies that were affected
            if (response.dependencies && response.dependencies.length > 0) {
                // We might want to update UI for the affected dependencies
                if (toggleActiveConfig.debug) {
                    console.debug('Dependencies affected:', response.dependencies);
                }
                
                // Update UI for each dependency
                response.dependencies.forEach(dep => {
                    // Find any toggles for this dependency
                    const depToggles = document.querySelectorAll(
                        `.toggle-${dep.type}-active[data-${dep.type}-id="${dep.id}"]`
                    );
                    
                    // Update each toggle to match the new state (always false for dependencies)
                    depToggles.forEach(toggle => {
                        if (toggle.tagName.toLowerCase() === 'input') {
                            toggle.checked = false;
                        }
                    });
                    
                    // Find related rows and update their classes
                    const depRows = document.querySelectorAll(`[data-${dep.type}-id="${dep.id}"]`);
                    depRows.forEach(row => {
                        row.setAttribute(`data-${dep.type}-active`, "false");
                        row.classList.add('opacity-50', 'text-muted');
                        
                        // If we're hiding inactive items, hide this row
                        const hideInactive = this.getHideInactiveState(dep.type);
                        if (hideInactive) {
                            row.classList.add('d-none');
                        }
                    });
                });
            }
        } catch (error) {
            console.error('Error handling toggle response:', error);
        } finally {
            if (toggleActiveConfig.debug) {
                console.groupEnd();
            }
        }
    },

    // Add helper methods to update child toggles
    updateChildTogglesForLocation(locationId, isActive) {
        // Find all device toggles within this location
        const deviceToggles = document.querySelectorAll(`.toggle-device-active[data-location-id="${locationId}"]`);
        deviceToggles.forEach(toggle => {
            const toggleWrapper = toggle.closest('.toggle-button-wrapper');
            if (toggleWrapper) {
                if (isActive) {
                    toggleWrapper.classList.remove('d-none');
                    toggle.disabled = false;
                } else {
                    toggleWrapper.classList.add('d-none');
                    toggle.disabled = true;
                }
            }
        });

        // Update status badges visibility
        const statusBadges = document.querySelectorAll(`[data-location-id="${locationId}"] .isactive-badge .badge`);
        statusBadges.forEach(badge => {
            if (isActive) {
                badge.classList.add('d-none');
            } else {
                badge.classList.remove('d-none');
            }
        });
    },

    updateChildTogglesForDevice(deviceId, isActive) {
        // Find all sensor toggles within this device
        const sensorToggles = document.querySelectorAll(`.toggle-sensor-active[data-device-id="${deviceId}"]`);
        sensorToggles.forEach(toggle => {
            const toggleWrapper = toggle.closest('.toggle-button-wrapper');
            if (toggleWrapper) {
                if (isActive) {
                    toggleWrapper.classList.remove('d-none');
                    toggle.disabled = false;
                } else {
                    toggleWrapper.classList.add('d-none');
                    toggle.disabled = true;
                }
            }
        });

        // Update status badges visibility
        const sensorStatusBadges = document.querySelectorAll(`[data-device-id="${deviceId}"] .isactive-badge .badge`);
        sensorStatusBadges.forEach(badge => {
            if (isActive) {
                badge.classList.add('d-none');
            } else {
                badge.classList.remove('d-none');
            }
        });
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