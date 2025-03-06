/**
 * Toggle Active Handler
 * 
 * Manages active/inactive state toggling for locations, devices, and sensors
 * 
 * Configuration:
 * -------------
 * To enable debugging, set debug: true in toggleConfig below
 * Debug mode will:
 * - Show toggle lifecycle events
 * - Log state changes
 * - Display API interactions
 */

// System Configuration
const toggleConfig = {
    debug: false           // Set to true to enable debug mode
};

// Debug logging helper
function debugLog(group, message, data = null) {
    if (!toggleConfig.debug) return;
    console.group(`Toggle System - ${group}`);
    console.log(message);
    if (data) console.log(data);
    console.groupEnd();
}

// Status Management System
const toggleActiveManager = {
    async toggleStatus(type, id, placeSlug, intendedState) {
        debugLog('Toggle', `Toggling ${type} status`, {
            type,
            id,
            placeSlug,
            intendedState
        });

        try {
            const response = await utils.fetchWithCSRF(
                `/api/${placeSlug}/${type}/${id}/toggle_active/`,
                {
                    method: 'POST',
                    body: JSON.stringify({ is_active: intendedState })
                }
            );
            
            if (!response.ok) throw new Error('Network response was not ok');
            const data = await response.json();
            
            if (data.status === 'success') {
                debugLog('API Response', `${type} status updated successfully`, data);

                // Find the row and update its visibility based on type
                const row = document.querySelector(`[data-${type}-id="${id}"]`);
                const hideInactiveSwitch = document.getElementById(`hideInactive${type.charAt(0).toUpperCase() + type.slice(1)}sSwitch`);
                
                if (row && hideInactiveSwitch) {
                    debugLog('UI Update', `Updating ${type} row visibility`, {
                        rowId: row.id,
                        isActive: data.is_active,
                        hideInactive: hideInactiveSwitch.checked
                    });

                    row.setAttribute(`data-${type}-active`, data.is_active.toString());
                    row.classList.toggle('opacity-50', !data.is_active);
                    row.classList.toggle('text-muted', !data.is_active);
                    
                    // Only hide if switch is checked and item is now inactive
                    if (hideInactiveSwitch.checked && !data.is_active) {
                        row.classList.add('d-none');
                    } else {
                        row.classList.remove('d-none');
                    }
                }

                // Special handling for locations affecting devices
                if (type === 'location') {
                    debugLog('Cascade', 'Updating affected devices', {
                        locationId: id,
                        isActive: data.is_active
                    });

                    const deviceToggles = document.querySelectorAll(`[data-location-id="${id}"] .device-status-toggle`);
                    deviceToggles.forEach(toggle => {
                        toggle.disabled = !data.is_active;
                        if (!data.is_active) {
                            const deviceRow = toggle.closest('tr');
                            if (deviceRow) {
                                deviceRow.classList.add('opacity-50', 'text-muted');
                            }
                        }
                    });
                }

                // Special handling for devices affecting sensors
                if (type === 'device') {
                    debugLog('Cascade', 'Updating affected sensors', {
                        deviceId: id,
                        isActive: data.is_active
                    });

                    const sensorToggles = document.querySelectorAll(`[data-device-id="${id}"] .sensor-status-toggle`);
                    sensorToggles.forEach(toggle => {
                        toggle.disabled = !data.is_active;
                        if (!data.is_active) {
                            const sensorRow = toggle.closest('tr');
                            if (sensorRow) {
                                sensorRow.classList.add('opacity-50', 'text-muted');
                            }
                        }
                    });
                }

                document.dispatchEvent(new CustomEvent(`${type}StatusChanged`, {
                    detail: { 
                        id, 
                        type,
                        isActive: data.is_active 
                    }
                }));
                
                // Use toastSystem consistently with server-provided type
                toastSystem.show(data.message, data.type || 'warning', true);
                return data;
            } else {
                throw new Error(data.message || `Failed to update ${type} status`);
            }
        } catch (error) {
            debugLog('Error', `Failed to toggle ${type} status`, error);
            console.error(`Error updating ${type} status:`, error);
            toastSystem.show(error.message, 'danger', true);
            return null;
        }
    },

    async updateDeviceStatus(deviceId, isActive, placeSlug) {
        debugLog('Device', 'Updating device status', {
            deviceId,
            isActive,
            placeSlug
        });

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
                debugLog('API Response', 'Device status updated successfully', data);

                const device = data.device;
                const row = document.querySelector(`tr[data-device-id="${device.id}"]`);
                const toggle = row.querySelector('.device-status-toggle');
                
                // Update toggle state
                debugLog('UI Update', 'Updating device toggle state', {
                    deviceId: device.id,
                    isActive: device.is_active
                });

                toggle.checked = device.is_active;
                const label = document.getElementById(`deviceStatusLabel_${device.id}`);
                if (label) {
                    label.textContent = device.is_active ? 'Active' : 'inactive';
                    label.classList.toggle('text-success', device.is_active);
                    label.classList.toggle('text-danger', !device.is_active);
                }
                
                // Update row styling
                if (!device.is_active) {
                    row.classList.add('text-muted', 'opacity-50');
                    if (document.getElementById('hideInactiveDevices')?.checked) {
                        row.classList.add('d-none');
                    }
                } else {
                    row.classList.remove('text-muted', 'opacity-50', 'd-none');
                }

                // Show toast with affected sensors if any
                let message = data.message;
                if (device.affected_sensors && device.affected_sensors.length > 0) {
                    debugLog('Cascade', 'Processing affected sensors', {
                        count: device.affected_sensors.length,
                        sensors: device.affected_sensors
                    });

                    message += '<br><br>Affected sensors:<ul class="mb-0">';
                    device.affected_sensors.forEach(sensor => {
                        message += `<li>${sensor}</li>`;
                    });
                    message += '</ul>';
                }
                
                // Use toastSystem consistently
                toastSystem.show(message, 'success');
                return data;
            } else {
                throw new Error(data.message || 'Failed to update device status');
            }
        } catch (error) {
            debugLog('Error', 'Failed to update device status', error);
            console.error('Error updating device status:', error);
            toastSystem.show(error.message, 'danger');
            return null;
        }
    },

    createToggleModal(type) {
        debugLog('Modal', `Creating toggle modal for ${type}`);

        const modalId = `${type}ToggleModal`;
        if (!document.getElementById(modalId)) {
            const modalHTML = `
                <div class="modal fade" id="${modalId}" tabindex="-1" aria-labelledby="${modalId}Label" aria-hidden="true">
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
            debugLog('Modal', `Created new modal: ${modalId}`);
        }
        return {
            modal: new bootstrap.Modal(document.getElementById(modalId)),
            element: document.getElementById(modalId),
            messageEl: document.getElementById(`${type}ToggleMessage`),
            confirmBtn: document.getElementById(`confirm${type.charAt(0).toUpperCase() + type.slice(1)}Toggle`),
            spinner: document.getElementById(`confirm${type.charAt(0).toUpperCase() + type.slice(1)}Toggle`).querySelector('.spinner-border')
        };
    },

    initializeLocationToggles() {
        debugLog('Initialize', 'Setting up location toggle handlers');

        const modalComponents = this.createToggleModal('location');
        
        document.querySelectorAll('.location-status-toggle').forEach(toggle => {
            const oldHandler = toggle._changeHandler;
            if (oldHandler) toggle.removeEventListener('change', oldHandler);

            const changeHandler = async function(e) {
                e.preventDefault();
                
                const locationId = this.dataset.locationId;
                const placeSlug = this.dataset.placeSlug;
                const newStatus = this.checked;
                const toggleElement = this;
                
                debugLog('Location', 'Location toggle clicked', {
                    locationId,
                    placeSlug,
                    newStatus
                });

                this.checked = !newStatus;
                
                modalComponents.messageEl.textContent = newStatus ? 
                    'Are you sure you want to activate this location? This will allow its devices to be activated.' : 
                    'Are you sure you want to deactivate this location? This will disable all its devices.';

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
        debugLog('Initialize', 'Setting up device toggle handlers');

        const modalComponents = this.createToggleModal('device');
        
        document.querySelectorAll('.device-status-toggle').forEach(toggle => {
            const oldHandler = toggle._changeHandler;
            if (oldHandler) toggle.removeEventListener('change', oldHandler);

            const changeHandler = async function(e) {
                e.preventDefault();
                
                const deviceId = this.dataset.deviceId;
                const placeSlug = this.dataset.placeSlug;
                const newStatus = this.checked;
                const toggleElement = this;
                
                debugLog('Device', 'Device toggle clicked', {
                    deviceId,
                    placeSlug,
                    newStatus
                });

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
        debugLog('Initialize', 'Setting up sensor toggle handlers');

        const modalComponents = this.createToggleModal('sensor');
        
        document.querySelectorAll('.sensor-status-toggle').forEach(toggle => {
            const oldHandler = toggle._changeHandler;
            if (oldHandler) toggle.removeEventListener('change', oldHandler);

            const changeHandler = async function(e) {
                e.preventDefault();
                
                const sensorId = this.dataset.sensorId;
                const placeSlug = this.dataset.placeSlug;
                const newStatus = this.checked;
                const toggleElement = this;
                
                debugLog('Sensor', 'Sensor toggle clicked', {
                    sensorId,
                    placeSlug,
                    newStatus
                });

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
        document.querySelectorAll('.toggle-device-status').forEach(button => {
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
    }
};

// Visibility Toggle System
const visibilityToggleManager = {
    initializeLocationNav() {
        debugLog('Initialize', 'Setting up location navigation visibility');

        const hideInactiveSwitch = document.getElementById('hideInactiveLocations');
        if (!hideInactiveSwitch) return;

        const locationRows = document.querySelectorAll('[data-location-active]');
        const locationMarkers = document.querySelectorAll('[data-location-active]');

        const filterLocations = () => {
            const hideInactive = hideInactiveSwitch.checked;
            debugLog('Visibility', 'Filtering locations', {
                hideInactive,
                locationCount: locationRows.length + locationMarkers.length
            });
            
            // Filter all elements with data-location-active attribute
            [...locationRows, ...locationMarkers].forEach(el => {
                const isActive = el.getAttribute('data-location-active') === 'true';
                el.classList.toggle('d-none', hideInactive && !isActive);
            });
        };

        // Initial filter
        filterLocations();
        // Filter on toggle change
        hideInactiveSwitch.addEventListener('change', filterLocations);
    },

    initializePlacesList() {
        // This will be provided by common.js
        if (typeof placesVisibilitySystem !== 'undefined' && placesVisibilitySystem.initialize) {
            placesVisibilitySystem.initialize();
        }
    },

    initializeDeviceList() {
        debugLog('Initialize', 'Setting up device list visibility');

        const hideInactiveSwitch = document.getElementById('hideInactiveDevices');
        if (!hideInactiveSwitch) return;

        const deviceCard = hideInactiveSwitch.closest('.card');
        const deviceElements = deviceCard.querySelectorAll('[data-device-active]');

        const filterDevices = () => {
            const hideInactive = hideInactiveSwitch.checked;
            debugLog('Visibility', 'Filtering devices', {
                hideInactive,
                deviceCount: deviceElements.length
            });

            deviceElements.forEach(el => {
                const isActive = el.getAttribute('data-device-active') === 'true';
                el.classList.toggle('d-none', hideInactive && !isActive);
            });
        };

        // Initial filter
        filterDevices();
        // Filter on toggle change
        hideInactiveSwitch.addEventListener('change', filterDevices);
    },

    initializeSensorList() {
        debugLog('Initialize', 'Setting up sensor list visibility');

        const hideInactiveSwitch = document.getElementById('hideInactiveSensors');
        if (!hideInactiveSwitch) return;

        const sensorCard = hideInactiveSwitch.closest('.card');
        const sensorElements = sensorCard.querySelectorAll('[data-sensor-active]');

        const filterSensors = () => {
            const hideInactive = hideInactiveSwitch.checked;
            debugLog('Visibility', 'Filtering sensors', {
                hideInactive,
                sensorCount: sensorElements.length
            });

            sensorElements.forEach(el => {
                const isActive = el.getAttribute('data-sensor-active') === 'true';
                el.classList.toggle('d-none', hideInactive && !isActive);
            });
        };

        // Initial filter
        filterSensors();
        // Filter on toggle change
        hideInactiveSwitch.addEventListener('change', filterSensors);
    }
};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    debugLog('Initialize', 'Toggle Active Handler - Initializing');

    // Initialize active state toggle functionality
    toggleActiveManager.initializeLocationToggles();
    toggleActiveManager.initializeDeviceToggles();
    toggleActiveManager.initializeSensorToggles();
    
    // Initialize visibility switch functionality
    visibilityToggleManager.initializeLocationNav();
    visibilityToggleManager.initializePlacesList();
    visibilityToggleManager.initializeDeviceList();
    visibilityToggleManager.initializeSensorList();

    debugLog('Initialize', 'Toggle Active Handler - Initialized');
});

// Export for use in other modules
window.toggleActiveManager = toggleActiveManager;
window.visibilityToggleManager = visibilityToggleManager; 