// Global state
if (typeof window.currentPlaceSlug === 'undefined') {
    window.currentPlaceSlug = null;
}

// Utility Functions
const utils = {
    getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
    },

    async fetchWithCSRF(url, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCookie('csrftoken'),
            }
        };
        // Ensure URL doesn't start with double slashes
        url = url.replace(/^\/+/, '/');
        return fetch(url, { ...defaultOptions, ...options });
    }
};

// Toast System
const toastSystem = {
    history: [],
    MAX_HISTORY: 50,

    async loadHistory() {
        try {
            const response = await utils.fetchWithCSRF('/api/toast-history/');
            const data = await response.json();
            if (data.history) {
                this.history = data.history.map(item => ({
                    ...item,
                    timestamp: new Date(item.timestamp)
                }));
                this.updateHistoryBadge();
            }
        } catch (error) {
            console.error('Error loading toast history:', error);
        }
    },

    async saveHistory() {
        try {
            await utils.fetchWithCSRF('/api/toast-history/', {
        method: 'POST',
                body: JSON.stringify({ history: this.history })
            });
        } catch (error) {
            console.error('Error saving toast history:', error);
        }
    },

    show(message, type = 'success', addToHistory = true) {
        // Create toast data with consistent structure
        const toastData = {
            id: `toast_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
            message: typeof message === 'object' ? message.message : message,
            type: typeof message === 'object' ? message.type : type,
            timestamp: new Date().toISOString(),
            addToHistory: typeof message === 'object' ? message.addToHistory : addToHistory
        };

        // Only add to history if addToHistory is true
        if (toastData.addToHistory) {
            // Add to history
            this.history.unshift({
                ...toastData,
                timestamp: new Date(toastData.timestamp)
            });
            
            // Keep history within limit
            if (this.history.length > this.MAX_HISTORY) {
                this.history = this.history.slice(0, this.MAX_HISTORY);
            }
            
            // Save to server and update badge
            this.saveHistory();
            this.updateHistoryBadge();
        }
        
        // Create toast container if it doesn't exist
        let toastContainer = document.querySelector('.toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
            document.body.appendChild(toastContainer);
        }

        // Create and show toast
        const toastHtml = `
            <div class="toast fade show text-${toastData.type}" id="${toastData.id}">
                <div class="d-flex align-items-center">
                    <div class="toast-body d-flex align-items-center flex-grow-1" style="font-family: 'monospace';">
                        <i class="bi bi-${
                            toastData.type === 'success' ? 'check-circle' : 
                            toastData.type === 'danger' ? 'exclamation-circle' :
                            toastData.type === 'warning' ? 'exclamation-triangle' : 
                            'info-circle'
                        } me-2"></i>
                        <span>${toastData.message}</span>
                    </div>
                    <button type="button" class="btn-close me-2" data-bs-dismiss="toast"></button>
                </div>
            </div>
        `;

        toastContainer.insertAdjacentHTML('afterbegin', toastHtml);
        const toastEl = document.getElementById(toastData.id);
        
        const toast = new bootstrap.Toast(toastEl, {
            delay: 5000,
            autohide: true
        });
        
        toast.show();
        
        toastEl.addEventListener('hidden.bs.toast', () => {
            toastEl.remove();
            // Remove toast container if it's empty
            if (!toastContainer.children.length) {
                toastContainer.remove();
            }
        });
    },

    updateHistoryBadge() {
        const badge = document.getElementById('toastHistoryBadge');
        if (badge) {
            const count = this.history.length;
            badge.textContent = count || '';
            badge.classList.toggle('d-none', count === 0);
            // Also update the aria-label for accessibility
            const btn = document.getElementById('toastHistoryBtn');
            if (btn) {
                btn.setAttribute('aria-label', `Notification History (${count} notifications)`);
            }
        }
    },

    showHistory() {
    const modalHtml = `
            <div class="modal fade" id="toastHistoryModal" tabindex="-1">
            <div class="modal-dialog modal-xl">
                <div class="modal-content">
                    <div class="modal-header">
                            <h5 class="modal-title">Notification History</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="toast-history-list">
                                ${this.history.map(toast => {
                                    const timestamp = new Date(toast.timestamp);
                                    const dateStr = timestamp.toLocaleString('en-US', {
                                        year: 'numeric',
                                        month: '2-digit',
                                        day: '2-digit'
                                    });
                                    const timeStr = timestamp.toLocaleString('en-US', {
                                        hour: '2-digit',
                                        minute: '2-digit',
                                        second: '2-digit',
                                        hour12: false
                                    });
                                    const shortTZ = new Intl.DateTimeFormat('en', { timeZoneName: 'short' })
                                        .formatToParts(timestamp)
                                        .find(part => part.type === 'timeZoneName')?.value || '';
                                    const offset = -timestamp.getTimezoneOffset();
                                    const offsetHours = Math.floor(Math.abs(offset) / 60);
                                    const offsetMinutes = Math.abs(offset) % 60;
                                    const offsetString = `${offset >= 0 ? '+' : '-'}${String(offsetHours).padStart(2, '0')}${String(offsetMinutes).padStart(2, '0')}`;
                                    
                                    return `
                                        <div class="toast-history-item mb-3">
                                            <div class="toast-history-time font-monospace text-muted" style="font-size: 0.75em;">
                                                ${dateStr} ${timeStr} ${shortTZ} UTC${offsetString}
                                            </div>
                                            <div class="text-${toast.type} font-monospace">
                                                ${toast.message}
                                            </div>
                                        </div>
                                    `;
                                }).join('')}
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                            <button type="button" class="btn btn-danger" onclick="toastSystem.clearHistory()">Clear History</button>
                    </div>
                </div>
            </div>
        </div>
    `;

        document.getElementById('toastHistoryModal')?.remove();
    document.body.insertAdjacentHTML('beforeend', modalHtml);
        new bootstrap.Modal(document.getElementById('toastHistoryModal')).show();
    },

    async clearHistory() {
        try {
            await utils.fetchWithCSRF('/api/toast-history/', { method: 'DELETE' });
            this.history = [];
            this.updateHistoryBadge();
            bootstrap.Modal.getInstance(document.getElementById('toastHistoryModal'))?.hide();
        } catch (error) {
            console.error('Error clearing toast history:', error);
        }
    }
};

// Status Management System
const toggleActiveManager = {
    async toggleStatus(type, id, placeSlug, intendedState) {
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
                // Find the row and update its visibility if it's a sensor
                if (type === 'sensor') {
                    const sensorRow = document.querySelector(`[data-sensor-id="${id}"]`);
                    const hideInactiveSwitch = document.getElementById('hideSensorInactiveSwitch');
                    
                    if (sensorRow && hideInactiveSwitch) {
                        sensorRow.setAttribute('data-sensor-active', data.is_active.toString());
                        // Only hide if switch is checked and sensor is now inactive
                        if (hideInactiveSwitch.checked && !data.is_active) {
                            sensorRow.classList.add('d-none');
                        } else {
                            sensorRow.classList.remove('d-none');
                        }
                    }
                }

                document.dispatchEvent(new CustomEvent(`${type}StatusChanged`, {
                    detail: { 
                        id, 
                        type,
                        isActive: data.is_active 
                    }
                }));
                toastSystem.show(data.message, data.type);
                return data;
            } else {
                throw new Error(data.message || `Failed to update ${type} status`);
            }
        } catch (error) {
            console.error(`Error updating ${type} status:`, error);
            toastSystem.show(error.message, 'danger');
            return null;
        }
    },

    updateUI(element, isActive, type) {
        // Common UI updates
        element.classList.toggle('opacity-50', !isActive);
        element.classList.toggle('text-muted', !isActive);
        
        // Update status indicators
        const statusIndicator = element.querySelector('.status-indicator');
        if (statusIndicator) {
            statusIndicator.classList.toggle('bg-success', isActive);
            statusIndicator.classList.toggle('bg-danger', !isActive);
        }
        
        // Update monospace elements if sensor
        if (type === 'sensor') {
            element.querySelectorAll('.sensor-value, .sensor-timestamp')
                .forEach(el => el.classList.toggle('opacity-50', !isActive));
        }

        // Add or remove the d-none class based on isActive
        if (!isActive) {
            element.classList.add('d-none'); // Add d-none class if not active
        } else {
            element.classList.remove('d-none'); // Remove d-none class if active
        }
    },

    initializeDeviceToggles() {
        // Create the confirmation modal if it doesn't exist
        if (!document.getElementById('deviceToggleConfirmModal')) {
            const modalHtml = `
                <div class="modal fade" id="deviceToggleConfirmModal" tabindex="-1">
                    <div class="modal-dialog">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title">Confirm Status Change</h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                            </div>
                            <div class="modal-body" style="font-family: 'Courier New', monospace;">
                                <p class="confirmation-message"></p>
                                <div class="affected-sensors-list d-none">
                                    <p class="text-warning">
                                        <i class="bi bi-exclamation-triangle"></i>
                                        The following sensors will be deactivated:
                                    </p>
                                    <ul class="list-unstyled mb-0">
                                    </ul>
                                </div>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                                <button type="button" class="btn btn-primary" id="deviceToggleConfirm">Confirm</button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            document.body.insertAdjacentHTML('beforeend', modalHtml);
        }

        const deviceToggles = document.querySelectorAll('.device-status-toggle');

        deviceToggles.forEach(toggle => {
            // Remove any existing event listeners
            toggle.removeEventListener('change', this.handleDeviceToggle);
            
            // Add new event listener
            toggle.addEventListener('change', async function(e) {
                e.preventDefault();
                
                const deviceId = this.dataset.deviceId;
                const placeSlug = this.dataset.placeSlug;
                const newStatus = this.checked;
                const statusLabel = document.getElementById(`deviceStatusLabel_${deviceId}`);
                const deviceCard = document.getElementById(`deviceCard_${deviceId}`);
                const deviceRow = this.closest('tr') || this.closest('.device-row');
                const sensorsCard = document.querySelector('#sensors-card');
                
                // Revert the checkbox state until confirmed
                this.checked = !newStatus;
                
                // Get the modal and update its content
                const modal = document.getElementById('deviceToggleConfirmModal');
                const modalInstance = new bootstrap.Modal(modal);
                
                // If deactivating, first get the list of active sensors
                if (!newStatus) {
                    try {
                        const response = await fetch(`/api/${placeSlug}/device/${deviceId}/active_sensors/`);
                        const data = await response.json();

                        if (data.status === 'success' && data.sensors.length > 0) {
                            // Show warning about sensors that will be deactivated
                            modal.querySelector('.confirmation-message').textContent = 'Are you sure you want to deactivate this device? This will also deactivate all associated sensors:';
                            
                            // Update the affected sensors list
                            const sensorsList = modal.querySelector('.affected-sensors-list ul');
                            sensorsList.innerHTML = data.sensors.map(sensor => 
                                `<li><i class="bi bi-thermometer"></i> ${sensor.name} (${sensor.type})</li>`
                            ).join('');
                            
                            modal.querySelector('.affected-sensors-list').classList.remove('d-none');
                        } else {
                            // No active sensors to warn about
                            modal.querySelector('.confirmation-message').textContent = 'Are you sure you want to deactivate this device?';
                            modal.querySelector('.affected-sensors-list').classList.add('d-none');
                        }
                    } catch (error) {
                        modal.querySelector('.confirmation-message').textContent = 'Are you sure you want to deactivate this device?';
                        modal.querySelector('.affected-sensors-list').classList.add('d-none');
                    }
                } else {
                    // Activating device
                    modal.querySelector('.confirmation-message').textContent = 'Are you sure you want to activate this device?';
                    modal.querySelector('.affected-sensors-list').classList.add('d-none');
                }

                // Set up the confirmation action
                const confirmButton = modal.querySelector('#deviceToggleConfirm');
                const handleConfirm = async () => {
                    modalInstance.hide();
                    confirmButton.removeEventListener('click', handleConfirm);

                    const result = await toggleActiveManager.toggleStatus('device', deviceId, placeSlug, newStatus);
                    
                    if (!result) {
                        this.checked = !newStatus;
                        return;
                    }

                    // Update the toggle state and appearance
                    this.checked = result.is_active;
                    this.style.opacity = result.is_active ? '1' : '0.5';
                    
                    // Update the status label if it exists
                    if (statusLabel) {
                        statusLabel.textContent = result.is_active ? 'Active' : 'inactive';
                        statusLabel.className = `form-check-label status-label ${result.is_active ? 'text-success' : 'text-danger'}`;
                    }
    
                    // Update the device card styling if it exists
                    if (deviceCard) {
                        deviceCard.className = `card rounded-3 shadow-sm border-0 mb-4 ${!result.is_active ? 'opacity-50' : ''}`;
                        
                        // Update all value text colors in device card
                        deviceCard.querySelectorAll('dd').forEach(dd => {
                            if (!dd.querySelector('.form-check')) {
                                dd.classList.toggle('text-muted', !result.is_active);
                            }
                        });
                    }

                    // Update device row if it exists
                    if (deviceRow) {
                        deviceRow.classList.toggle('opacity-50', !result.is_active);
                        deviceRow.classList.toggle('text-muted', !result.is_active);
                        deviceRow.setAttribute('data-device-active', result.is_active.toString());
                        
                        // Update badge if it exists
                        const badge = deviceRow.querySelector('.badge');
                        if (badge) {
                            badge.style.display = result.is_active ? 'none' : 'inline-block';
                        }

                        // Check if we need to hide the row based on the hide inactive switch
                        const hideInactiveSwitch = document.getElementById('hideInactiveDevices');
                        if (hideInactiveSwitch && hideInactiveSwitch.checked && !result.is_active) {
                            deviceRow.classList.add('d-none');
                        }
                    }

                    // Update sensors card if it exists
                    if (sensorsCard) {
                        // Try different selectors
                        const selectorAttempts = [
                            `tr[data-device-id="${deviceId}"]`,
                            `tr[data-deviceid="${deviceId}"]`,
                            `tr[data-device="${deviceId}"]`,
                            `.sensor-row[data-device-id="${deviceId}"]`,
                            `.sensor-row[data-deviceid="${deviceId}"]`
                        ];
                        
                        let allSensorRows;
                        for (const selector of selectorAttempts) {
                            const rows = document.querySelectorAll(selector);
                            if (rows.length > 0) {
                                allSensorRows = rows;
                                break;
                            }
                        }
                        
                        if (allSensorRows && allSensorRows.length > 0) {
                            allSensorRows.forEach(row => {
                                if (!result.is_active) {
                                    // Update sensor row UI for inactive state
                                    row.setAttribute('data-sensor-active', 'false');
                                    row.classList.add('text-muted', 'opacity-50');
                                    
                                    // Update status label and toggle
                                    const statusLabel = row.querySelector('.status-label');
                                    const toggle = row.querySelector('.sensor-status-toggle');
                                    
                                    if (statusLabel) {
                                        statusLabel.textContent = 'inactive';
                                        statusLabel.className = 'form-check-label status-label text-danger';
                                    }
                                    
                                    if (toggle) {
                                        toggle.checked = false;
                                        toggle.disabled = true;
                                    }
                                    
                                    // Force update the Bootstrap switch if it exists
                                    const switchLabel = row.querySelector('.form-switch');
                                    if (switchLabel) {
                                        const input = switchLabel.querySelector('input[type="checkbox"]');
                                        if (input) {
                                            input.checked = false;
                                            input.disabled = true;
                                        }
                                    }
                                    
                                    // Disable test readings button
                                    const testButton = row.querySelector('.test-readings-btn');
                                    if (testButton) {
                                        testButton.disabled = true;
                                    }
                                    
                                    // Update any sensor values or timestamps
                                    row.querySelectorAll('.sensor-value, .sensor-timestamp').forEach(el => {
                                        el.classList.add('opacity-50');
                                    });

                                    // Check if we need to hide the row based on the hide inactive switch
                                    const hideInactiveSwitch = document.getElementById('hideSensorInactiveSwitch');
                                    if (hideInactiveSwitch && hideInactiveSwitch.checked) {
                                        row.classList.add('d-none');
                                    }
                                } else {
                                    // When device is activated, only enable controls but maintain visual state based on sensor's active state
                                    const sensorActive = row.getAttribute('data-sensor-active') === 'true';
                                    
                                    // Keep opacity and text-muted if sensor itself is inactive
                                    if (sensorActive) {
                                        row.classList.remove('text-muted', 'opacity-50');
                                    }
                                    
                                    const toggle = row.querySelector('.sensor-status-toggle');
                                    if (toggle) {
                                        toggle.disabled = false;
                                    }
                                    
                                    // Enable test readings button but keep it disabled if sensor is inactive
                                    const testButton = row.querySelector('.test-readings-btn');
                                    if (testButton) {
                                        testButton.disabled = !sensorActive;
                                    }
                                    
                                    // Enable action buttons but keep them disabled if sensor is inactive
                                    row.querySelectorAll('.btn-group .btn').forEach(btn => {
                                        btn.disabled = !sensorActive;
                                    });
                                }
                            });
                        }

                        // Update all buttons in the sensors card
                        const buttons = sensorsCard.querySelectorAll('button:not(.sensor-status-toggle), a.btn');
                        buttons.forEach(button => {
                            button.disabled = !result.is_active;
                        });

                        // Update the Add Sensor button
                        const addSensorBtn = sensorsCard.querySelector('.card-header a.btn-primary');
                        if (addSensorBtn) {
                            addSensorBtn.disabled = !result.is_active;
                        }
                    }

                    // Update location stats if available
                    if (result.active_devices_count !== undefined && result.location_id) {
                        const activeCountEl = document.getElementById(`location-${result.location_id}-active`);
                        const inactiveCountEl = document.getElementById(`location-${result.location_id}-inactive`);
                        if (activeCountEl) activeCountEl.textContent = result.active_devices_count;
                        if (inactiveCountEl) inactiveCountEl.textContent = result.inactive_devices_count || '0';
                    }
                };

                // Set up the confirmation button click handler
                confirmButton.addEventListener('click', handleConfirm);

                // Show the modal
                modalInstance.show();

                // Clean up the event listener when the modal is hidden
                modal.addEventListener('hidden.bs.modal', () => {
                    confirmButton.removeEventListener('click', handleConfirm);
                }, { once: true });
            });
        });
    },

    updateSensorUI(sensorRow, result, hideInactiveSwitch) {
        if (!sensorRow) return;

        // Update basic UI classes
        sensorRow.classList.toggle('opacity-50', !result.is_active);
        sensorRow.classList.toggle('text-muted', !result.is_active);
        sensorRow.setAttribute('data-sensor-active', result.is_active.toString());

        // Handle visibility based on active status and hide inactive switch
        if (hideInactiveSwitch?.checked && !result.is_active) {
            sensorRow.classList.add('d-none');
        } else {
            sensorRow.classList.remove('d-none');
        }

        // Update status label if it exists
        const statusLabel = sensorRow.querySelector('.status-label');
        if (statusLabel) {
            statusLabel.textContent = result.is_active ? 'Active' : 'inactive';
            statusLabel.className = `form-check-label status-label ${result.is_active ? 'text-success' : 'text-danger'}`;
        }

        // Update test readings button
        const testButton = sensorRow.querySelector('.test-readings-btn');
        if (testButton) {
            testButton.disabled = !result.is_active;
        }

        // Update sensor values and timestamps
        sensorRow.querySelectorAll('.sensor-value, .sensor-timestamp').forEach(el => {
            el.classList.toggle('opacity-50', !result.is_active);
        });
    },

    initializeSensorToggles() {
        // Create the confirmation modal if it doesn't exist
        if (!document.getElementById('sensorToggleConfirmModal')) {
            const modalHtml = `
                <div class="modal fade" id="sensorToggleConfirmModal" tabindex="-1">
                    <div class="modal-dialog">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title">Confirm Status Change</h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                            </div>
                            <div class="modal-body" style="font-family: 'Courier New', monospace;">
                                <!-- Message will be set dynamically -->
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                                <button type="button" class="btn btn-primary" id="sensorToggleConfirm">Confirm</button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            document.body.insertAdjacentHTML('beforeend', modalHtml);
        }

        document.querySelectorAll('.sensor-status-toggle').forEach(toggle => {
            toggle.addEventListener('change', async function(e) {
                e.preventDefault();
                
                const sensorId = this.dataset.sensorId;
                const placeSlug = this.dataset.placeSlug;
                const newStatus = this.checked;
                const sensorRow = this.closest('tr');
                
                // Revert the checkbox state until confirmed
                this.checked = !newStatus;
                
                const confirmMessage = newStatus ? 
                    'Are you sure you want to activate this sensor?' : 
                    'Are you sure you want to deactivate this sensor?';

                // Get the modal and update its content
                const modal = document.getElementById('sensorToggleConfirmModal');
                const modalInstance = new bootstrap.Modal(modal);
                modal.querySelector('.modal-body').textContent = confirmMessage;

                // Set up the confirmation action
                const confirmButton = modal.querySelector('#sensorToggleConfirm');
                const handleConfirm = async () => {
                    modalInstance.hide();
                    confirmButton.removeEventListener('click', handleConfirm);

                    const result = await toggleActiveManager.toggleStatus('sensor', sensorId, placeSlug, newStatus);
                    
                    if (!result) {
                        this.checked = !newStatus;
                        return;
                    }

                    // Update the toggle state
                    this.checked = result.is_active;
                    
                    // Update all UI elements
                    const hideInactiveSwitch = document.getElementById('hideSensorInactiveSwitch');
                    toggleActiveManager.updateSensorUI(sensorRow, result, hideInactiveSwitch);
                };

                // Set up the confirmation button click handler
                confirmButton.addEventListener('click', handleConfirm);

                // Show the modal
                modalInstance.show();

                // Clean up the event listener when the modal is hidden
                modal.addEventListener('hidden.bs.modal', () => {
                    confirmButton.removeEventListener('click', handleConfirm);
                }, { once: true });
            });
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

        // Get timezone offset
        const offset = -now.getTimezoneOffset();
        const offsetHours = Math.floor(Math.abs(offset) / 60);
        const offsetMinutes = Math.abs(offset) % 60;
        const offsetString = `${offset >= 0 ? '+' : '-'}${String(offsetHours).padStart(2, '0')}${String(offsetMinutes).padStart(2, '0')}`;

        // Get short timezone code
        const shortTZ = new Intl.DateTimeFormat('en', { timeZoneName: 'short' })
            .formatToParts(now)
            .find(part => part.type === 'timeZoneName')?.value || '';
        
        // Format date and time
        const dateString = now.toLocaleString('en-US', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
        });
        
        const timeString = now.toLocaleString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
        });

        timeSpan.textContent = `${dateString} ${timeString} ${shortTZ} UTC${offsetString}`;
        
        const isoTime = now.toISOString();
        const unixTime = Math.floor(now.getTime() / 1000);
        const fullTimeString = now.toLocaleString('en-US', {
            weekday: 'long',
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false,
            timeZoneName: 'long'
        });
        timeSpan.setAttribute('data-bs-title', 
            `${fullTimeString}\nISO: ${isoTime}\nUNIX: ${unixTime}\nClick to copy current timestamp`);
    },

    initializeClickToCopy() {
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

// Navigation System
const navigationSystem = {
    initializeLocationNav() {
        const hideInactiveSwitch = document.getElementById('hideInactiveLocations');
        if (!hideInactiveSwitch) return;

        const locationCard = hideInactiveSwitch.closest('.card');
        const locationItems = locationCard.querySelectorAll('.list-group-item[data-active]');
        const siteMapMarkers = document.querySelectorAll('.location-marker[data-active]');

        const filterLocations = () => {
        const hideInactive = hideInactiveSwitch.checked;
        
            // Filter list items
            locationItems.forEach(item => {
                item.classList.toggle('d-none', hideInactive && item.getAttribute('data-active') === 'false');
        });

        // Filter map markers
            siteMapMarkers.forEach(marker => {
                marker.style.display = (hideInactive && marker.getAttribute('data-active') === 'false') ? 'none' : 'block';
        });
        };

        // Initial filter
        filterLocations();

        // Filter on toggle change
        hideInactiveSwitch.addEventListener('change', filterLocations);

        // Update location stats every 30 seconds if we're on a place page
        const placeSlug = document.body.dataset.placeSlug;
        if (placeSlug) {
            const updateLocationStats = async () => {
                try {
                    const response = await utils.fetchWithCSRF(`/api/${placeSlug}/stats/`);
                    if (!response.ok) throw new Error('Network response was not ok');
                    
                    const data = await response.json();
                    data.locations.forEach(loc => {
                        const activeCountEl = document.getElementById(`location-${loc.id}-active`);
                        const inactiveCountEl = document.getElementById(`location-${loc.id}-inactive`);
                        if (activeCountEl) activeCountEl.textContent = loc.active_devices_count;
                        if (inactiveCountEl) inactiveCountEl.textContent = loc.inactive_devices_count || '0';
                    });
                } catch (error) {
                    console.error('Error updating location stats:', error);
                }
            };

            // Initial stats update
            updateLocationStats();

            // Set up interval for updates
            setInterval(updateLocationStats, 30000);
        }
    },

    initializeDeviceNav() {
        const hideInactiveSwitch = document.getElementById('hideInactiveDevicesNav');
        if (!hideInactiveSwitch) return;

        const deviceCard = hideInactiveSwitch.closest('.card');
        const deviceItems = deviceCard.querySelectorAll('.list-group-item[data-active]');

        const filterDevices = () => {
            const hideInactive = hideInactiveSwitch.checked;
            deviceItems.forEach(item => {
                item.classList.toggle('d-none', hideInactive && item.getAttribute('data-active') === 'false');
            });
        };

        // Initial filter
        filterDevices();

        // Filter on toggle change
        hideInactiveSwitch.addEventListener('change', filterDevices);
    },

    initializeDeviceList() {
        const hideInactiveSwitch = document.getElementById('hideInactiveDevices');
        if (!hideInactiveSwitch) return;

        const deviceCard = hideInactiveSwitch.closest('.card');
        const deviceItems = deviceCard.querySelectorAll('[data-device-active]');

        const filterDevices = () => {
            const hideInactive = hideInactiveSwitch.checked;
            deviceItems.forEach(item => {
                const isActive = item.getAttribute('data-device-active') === 'true';
                item.classList.toggle('d-none', hideInactive && !isActive);
            });
        };

        // Initial filter
        filterDevices();

        // Filter on toggle change
        hideInactiveSwitch.addEventListener('change', filterDevices);
    },

    initializeSensorList() {
        const hideInactiveSwitch = document.getElementById('hideSensorInactiveSwitch');
        if (!hideInactiveSwitch) return;

        const sensorCard = hideInactiveSwitch.closest('.card');
        const sensorRows = sensorCard.querySelectorAll('[data-sensor-active]');

        const filterSensors = () => {
            const hideInactive = hideInactiveSwitch.checked;
            sensorRows.forEach(row => {
                const isActive = row.getAttribute('data-sensor-active') === 'true';
                row.classList.toggle('d-none', hideInactive && !isActive);
            });
        };

        filterSensors();
        hideInactiveSwitch.addEventListener('change', filterSensors);
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

        console.log('Starting saveChanges operation...');

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

            console.log('Preparing marker position updates...');
            // Prepare marker position updates
            const markerPromises = Array.from(markers).map(marker => {
                const locationId = marker.dataset.locationId;
                const x = marker.dataset.x;
                const y = marker.dataset.y;
                
                console.log(`Updating marker position for location ${locationId}: x=${x}, y=${y}`);
                return utils.fetchWithCSRF(`/api/${placeSlug}/locations/${locationId}/position/`, {
                    method: 'POST',
                    body: JSON.stringify({ x_coord: x, y_coord: y })
                });
            });

            console.log('Preparing layout settings update...');
            // Prepare layout settings update
            const layoutData = {
                site_plan_scale: this.currentScale,
                site_plan_x: this.currentX,
                site_plan_y: this.currentY
            };
            console.log('Layout update data:', layoutData);

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
            
            console.log('All updates completed, checking responses...');
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
            
            console.log('Save operation completed successfully');
            
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

// Initialize everything when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize toast system
    toastSystem.loadHistory();
    
    // Set up toast history button click handler
    const toastHistoryBtn = document.getElementById('toastHistoryBtn');
    if (toastHistoryBtn) {
        toastHistoryBtn.addEventListener('click', () => toastSystem.showHistory());
    }
    
    // Initialize tooltips
    [...document.querySelectorAll('[data-bs-toggle="tooltip"]')]
        .forEach(el => new bootstrap.Tooltip(el));
    
    // Initialize time display
    timeDisplay.update();
    setInterval(() => timeDisplay.update(), 1000);
    timeDisplay.initializeClickToCopy();
    
    // Initialize device toggles
    toggleActiveManager.initializeDeviceToggles();
    
    // Initialize sensor toggles
    toggleActiveManager.initializeSensorToggles();
    
    // Initialize status toggles
    document.querySelectorAll('[data-toggle-type]').forEach(toggle => {
        // Skip device toggles as they're handled by initializeDeviceToggles
        if (toggle.classList.contains('device-status-toggle')) {
            return;
        }
        
        toggle.addEventListener('change', async function() {
            const type = this.dataset.toggleType;
            const id = this.dataset.id;
            const placeSlug = this.dataset.placeSlug;
            const currentState = this.checked;
            
            const result = await toggleActiveManager.toggleStatus(type, id, placeSlug, currentState);
            if (!result) {
                this.checked = !currentState; // Revert on failure
            }
        });
    });
    
    // Convert any Django messages to toasts
    document.querySelectorAll('.alert:not(.processed)').forEach(message => {
        const type = message.classList.contains('alert-success') ? 'success' :
                    message.classList.contains('alert-warning') ? 'warning' :
                    message.classList.contains('alert-danger') ? 'danger' : 'info';
        
        const messageText = message.childNodes[0]?.textContent.trim() || 
                          message.textContent.trim();
        
        if (messageText) {
            // Mark the message as processed
            message.classList.add('processed');
            
            // Remove the alert from DOM
            message.remove();
            
            // Show toast and automatically store in history
            toastSystem.show(messageText, type);
        }
    });

    // Set up a MutationObserver to watch for new Django messages
    const messagesContainer = document.getElementById('django-messages');
    if (messagesContainer) {
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                mutation.addedNodes.forEach((node) => {
                    if (node.classList && node.classList.contains('alert') && !node.classList.contains('processed')) {
                        const type = node.classList.contains('alert-success') ? 'success' :
                                   node.classList.contains('alert-warning') ? 'warning' :
                                   node.classList.contains('alert-danger') ? 'danger' : 'info';
                        
                        const messageText = node.childNodes[0]?.textContent.trim() || 
                                          node.textContent.trim();
                        
                        if (messageText) {
                            // Mark the message as processed
                            node.classList.add('processed');
                            
                            // Remove the alert from DOM
                            node.remove();
                            
                            // Show toast and automatically store in history
                            toastSystem.show(messageText, type);
                        }
                    }
                });
        });
    });

        observer.observe(messagesContainer, {
            childList: true,
            subtree: true
        });
    }

    // Initialize navigation
    navigationSystem.initializeLocationNav();
    navigationSystem.initializeDeviceNav();
    navigationSystem.initializeDeviceList();
    navigationSystem.initializeSensorList();

    // Initialize site plan manager
    sitePlanManager.initialize();
});

function showToast(message, type = 'info') {
    toastSystem.show({
        message: message,
        type: type,
        addToHistory: true  // Ensure all toasts are added to history
    });
}