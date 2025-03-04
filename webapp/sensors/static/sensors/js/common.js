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

    show(message, type = 'success') {
        // Add to history
        this.history.unshift({
            message,
            type,
            timestamp: new Date()
        });
        
        // Keep history within limit
        if (this.history.length > this.MAX_HISTORY) {
            this.history = this.history.slice(0, this.MAX_HISTORY);
        }
        
        this.saveHistory();
        this.updateHistoryBadge();
        
        // Create toast container if it doesn't exist
        let toastContainer = document.querySelector('.toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.className = 'toast-container';
            document.body.appendChild(toastContainer);
        }
        
        // Create and show toast
        const toastId = `toast_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        const toastHtml = `
            <div class="toast fade show bg-${type}" role="alert" aria-live="assertive" aria-atomic="true" id="${toastId}">
                <div class="d-flex align-items-center">
                    <div class="toast-body flex-grow-1">
                        ${type === 'success' ? '<i class="bi bi-check-circle"></i>' : ''}
                        ${type === 'danger' ? '<i class="bi bi-exclamation-circle"></i>' : ''}
                        ${type === 'warning' ? '<i class="bi bi-exclamation-triangle"></i>' : ''}
                        ${type === 'info' ? '<i class="bi bi-info-circle"></i>' : ''}
                        <span class="ms-2">${message}</span>
                    </div>
                    <button type="button" class="btn-close me-2" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
            </div>
        `;
        
        toastContainer.insertAdjacentHTML('afterbegin', toastHtml);
        const toastEl = document.getElementById(toastId);
        
        const toast = new bootstrap.Toast(toastEl, {
            delay: 4000,
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
            badge.textContent = this.history.length || '';
            badge.classList.toggle('d-none', !this.history.length);
        }
    },

    showHistory() {
        const modalHtml = `
            <div class="modal fade" id="toastHistoryModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Notification History</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div class="toast-history-list">
                                ${this.history.map(toast => `
                                    <div class="toast-history-item">
                                        <div class="toast-history-time">
                                            ${toast.timestamp.toLocaleTimeString()}
                                        </div>
                                        <div class="text-${toast.type}">
                                            ${toast.message}
                                        </div>
                                    </div>
                                `).join('')}
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
const statusManager = {
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
                document.dispatchEvent(new CustomEvent(`${type}StatusChanged`, {
                    detail: { isActive: data.is_active, id, type }
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
    },

    initializeDeviceToggles() {
        // Create the confirmation modal if it doesn't exist
        if (!document.getElementById('deviceToggleConfirmModal')) {
            const modalHtml = `
                <div class="modal fade" id="deviceToggleConfirmModal" tabindex="-1" aria-labelledby="deviceToggleConfirmModalLabel" aria-hidden="true">
                    <div class="modal-dialog">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title" id="deviceToggleConfirmModalLabel">Confirm Status Change</h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                            </div>
                            <div class="modal-body">
                                <!-- Message will be set dynamically -->
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

        document.querySelectorAll('.device-status-toggle').forEach(toggle => {
            toggle.addEventListener('change', async function(e) {
                e.preventDefault();
                
                const deviceId = this.dataset.deviceId;
                const placeSlug = this.dataset.placeSlug;
                const newStatus = this.checked;
                const statusLabel = document.getElementById(`deviceStatusLabel_${deviceId}`);
                const deviceCard = document.getElementById(`deviceCard_${deviceId}`);
                const deviceRow = this.closest('tr') || this.closest('.device-row');
                const sensorsCard = document.querySelector('.sensors-card');
                
                // Revert the checkbox state until confirmed
                this.checked = !newStatus;
                
                const confirmMessage = newStatus ? 
                    'Are you sure you want to activate this device?' : 
                    'Are you sure you want to deactivate this device? This will also deactivate all associated sensors.';

                // Get the modal and update its content
                const modal = document.getElementById('deviceToggleConfirmModal');
                const modalInstance = new bootstrap.Modal(modal);
                modal.querySelector('.modal-body').textContent = confirmMessage;

                // Set up the confirmation action
                const confirmButton = modal.querySelector('#deviceToggleConfirm');
                const handleConfirm = async () => {
                    modalInstance.hide();
                    confirmButton.removeEventListener('click', handleConfirm);

                    const result = await statusManager.toggleStatus('device', deviceId, placeSlug, newStatus);
                    
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
                            deviceRow.classList.add('hidden');
                        }
                    }

                    // Update sensors card if it exists
                    if (sensorsCard) {
                        // Update card opacity
                        sensorsCard.className = `card sensors-card ${!result.is_active ? 'opacity-50' : ''}`;
                        
                        // Update all sensor toggles and rows
                        const sensorToggles = sensorsCard.querySelectorAll('.sensor-status-toggle');
                        const sensorRows = sensorsCard.querySelectorAll('tbody tr:not(.readings-results)');
                        
                        sensorToggles.forEach(toggle => {
                            if (toggle.dataset.deviceId === deviceId) {
                                toggle.disabled = !result.is_active;
                            }
                        });

                        sensorRows.forEach(row => {
                            const toggle = row.querySelector('.sensor-status-toggle');
                            if (toggle && toggle.dataset.deviceId === deviceId) {
                                if (!result.is_active) {
                                    row.classList.add('text-muted', 'opacity-50');
                                } else {
                                    // Only remove opacity if the sensor itself is active
                                    if (toggle.checked) {
                                        row.classList.remove('text-muted', 'opacity-50');
                                    }
                                }
                            }
                        });

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

    initializeSensorToggles() {
        // Create the confirmation modal if it doesn't exist
        if (!document.getElementById('sensorToggleConfirmModal')) {
            const modalHtml = `
                <div class="modal fade" id="sensorToggleConfirmModal" tabindex="-1" aria-labelledby="sensorToggleConfirmModalLabel" aria-hidden="true">
                    <div class="modal-dialog">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title" id="sensorToggleConfirmModalLabel">Confirm Status Change</h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                            </div>
                            <div class="modal-body">
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
                const statusLabel = document.getElementById(`sensorStatusLabel_${sensorId}`);
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

                    const result = await statusManager.toggleStatus('sensor', sensorId, placeSlug, newStatus);
                    
                    if (!result) {
                        this.checked = !newStatus;
                        return;
                    }

                    // Update the toggle state
                    this.checked = result.is_active;
                    
                    // Update the status label if it exists
                    if (statusLabel) {
                        statusLabel.textContent = result.is_active ? 'Active' : 'inactive';
                        statusLabel.className = `form-check-label status-label ${result.is_active ? 'text-success' : 'text-danger'}`;
                    }

                    // Update sensor row if it exists
                    if (sensorRow) {
                        sensorRow.classList.toggle('opacity-50', !result.is_active);
                        sensorRow.classList.toggle('text-muted', !result.is_active);
                        sensorRow.setAttribute('data-sensor-active', result.is_active.toString());

                        // Check if we need to hide the row based on the hide inactive switch
                        const hideInactiveSwitch = document.getElementById('hideSensorInactiveSwitch');
                        if (hideInactiveSwitch && hideInactiveSwitch.checked && !result.is_active) {
                            sensorRow.classList.add('hidden');
                        }

                        // Update test readings button
                        const testButton = sensorRow.querySelector('.test-readings-btn');
                        if (testButton) {
                            testButton.disabled = !result.is_active;
                        }
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

        const offset = -now.getTimezoneOffset();
        const offsetHours = Math.floor(Math.abs(offset) / 60);
        const offsetMinutes = Math.abs(offset) % 60;
        const offsetString = `${offset >= 0 ? '+' : '-'}${String(offsetHours).padStart(2, '0')}${String(offsetMinutes).padStart(2, '0')}`;

        const weekday = now.toLocaleString('en-US', { weekday: 'long' });
        const timeString = now.toLocaleString('en-US', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
        });

        timeSpan.textContent = `${weekday}, ${timeString} (UTC${offsetString})`;
        
        const isoTime = now.toISOString();
        const unixTime = Math.floor(now.getTime() / 1000);
        timeSpan.setAttribute('data-bs-title', 
            `ISO: ${isoTime}\nUNIX: ${unixTime}\nClick to copy current timestamp`);
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
                item.classList.toggle('hidden', hideInactive && item.getAttribute('data-active') === 'false');
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
                item.classList.toggle('hidden', hideInactive && item.getAttribute('data-active') === 'false');
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
                item.classList.toggle('hidden', hideInactive && !isActive);
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
                row.classList.toggle('hidden', hideInactive && !isActive);
            });
        };

        // Initial filter
        filterSensors();

        // Filter on toggle change
        hideInactiveSwitch.addEventListener('change', filterSensors);
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
    statusManager.initializeDeviceToggles();
    
    // Initialize sensor toggles
    statusManager.initializeSensorToggles();
    
    // Initialize status toggles
    document.querySelectorAll('[data-toggle-type]').forEach(toggle => {
        toggle.addEventListener('change', async function() {
            const type = this.dataset.toggleType;
            const id = this.dataset.id;
            const placeSlug = this.dataset.placeSlug;
            const currentState = this.checked;
            
            const result = await statusManager.toggleStatus(type, id, placeSlug, currentState);
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
});