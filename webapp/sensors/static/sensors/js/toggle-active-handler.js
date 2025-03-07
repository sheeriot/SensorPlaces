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
    debug: false        // Set to true to enable debug mode
};

// Card status reporter
function reportCardStatus() {
    if (!toggleActiveConfig.debug) return;
    
    document.querySelectorAll('.card-body').forEach((card, index) => {
        const cardInfo = {
            index: index + 1,
            id: card.id || 'UnnamedCard',
            classes: Array.from(card.classList).join(' ')
        };
        console.debug('Card:', cardInfo);

        // Check all toggle types at once
        const toggleCounts = {};
        ['location', 'device', 'sensor'].forEach(type => {
            const toggles = card.querySelectorAll(`.toggle-${type}-active`);
            if (toggles.length > 0) {
                toggleCounts[type] = toggles.length;
                const statusData = Array.from(toggles).map(toggle => {
                    const row = toggle.closest('tr');
                    const isButton = toggle.tagName.toLowerCase() === 'button';
                    return {
                        id: toggle.dataset[`${type}Id`],
                        type: isButton ? 'button' : 'switch',
                        active: isButton ? toggle.dataset.currentStatus === 'true' : toggle.checked,
                        rowClasses: row ? Array.from(row.classList).join(' ') : 'N/A'
                    };
                });

                console.group(`Card ${card.id || 'unnamed'} - ${type}s:`);
                console.table(statusData);
                console.groupEnd();
            }
        });

        // Single summary message for cards with no toggles
        if (Object.keys(toggleCounts).length === 0) {
            console.debug(`Card ${cardInfo.id} has no toggles`);
        }
    });
}

// Status Management System
const toggleActiveManager = {
    async toggleStatus(type, id, placeSlug, intendedState) {
        if (toggleActiveConfig.debug) {
            console.debug('Action:', { type, action: 'toggle', id, intendedState });
        }

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
                // Find all rows that match this model type and ID
                const rows = document.querySelectorAll(`[data-${type}-id="${id}"]`);
                
                // Find the hideInactive switch for this model type
                const hideInactiveSwitch = document.querySelector(`.hideInactive-${type}-switch`);
                const shouldHide = hideInactiveSwitch?.checked ?? false;
                
                if (toggleActiveConfig.debug) {
                    console.debug('Response:', data);
                }
                
                rows.forEach(row => {
                    // Update row attributes to match server state
                    row.setAttribute(`data-${type}-active`, data.is_active.toString());
                    
                    // Update classes based on active state
                    if (data.is_active) {
                        row.classList.remove('opacity-50', 'text-muted', 'd-none');
                    } else {
                        row.classList.add('opacity-50', 'text-muted');
                        // If hideInactive switch is checked, also hide the row
                        if (shouldHide) {
                            row.classList.add('d-none');
                        }
                    }

                    // Update toggle text
                    const statusLabel = row.querySelector('.status-label');
                    if (statusLabel) {
                        statusLabel.textContent = data.is_active ? 'Active' : 'inactive';
                        statusLabel.classList.toggle('text-success', data.is_active);
                        statusLabel.classList.toggle('text-danger', !data.is_active);
                    }
                });

                // Find and update all toggle switches for this type/id
                const toggles = document.querySelectorAll(`.toggle-${type}-active[data-${type}-id="${id}"]`);
                toggles.forEach(toggle => {
                    if (toggle.tagName.toLowerCase() === 'input') {
                        toggle.checked = data.is_active;
                    }
                });

                // Show toast notification with HTML content
                let message = data.message;
                if (data.affected_sensors?.length > 0) {
                    message += '<br><br>Affected sensors:<ul class="mb-0">';
                    data.affected_sensors.forEach(sensor => {
                        message += `<li>${sensor}</li>`;
                    });
                    message += '</ul>';
                }

                toastSystem.show({
                    message: message,
                    type: data.type || 'warning',
                    addToHistory: true
                });
                return data;
            } else {
                throw new Error(data.message || `Failed to update ${type} status`);
            }
        } catch (error) {
            if (toggleActiveConfig.debug) {
                console.debug('Error:', { type, error: error.message });
            }
            toastSystem.show({
                message: error.message,
                type: 'danger',
                addToHistory: true
            });
            return null;
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

                // Show toast with affected sensors if any
                let message = data.message;
                if (device.affected_sensors && device.affected_sensors.length > 0) {
                    message += '<br><br>Affected sensors:<ul class="mb-0">';
                    device.affected_sensors.forEach(sensor => {
                        message += `<li>${sensor}</li>`;
                    });
                    message += '</ul>';
                }
                
                toastSystem.show({
                    message: message,
                    type: 'success',
                    addToHistory: true
                });
                return data;
            } else {
                throw new Error(data.message || 'Failed to update device status');
            }
        } catch (error) {
            if (toggleActiveConfig.debug) {
                console.debug('Error:', { type: 'device', error: error.message });
            }
            toastSystem.show({
                message: error.message,
                type: 'danger',
                addToHistory: true
            });
            return null;
        }
    },

    createToggleModal(type) {
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