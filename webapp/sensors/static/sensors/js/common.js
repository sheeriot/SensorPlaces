// Helper function to get CSRF token
function getCookie(name) {
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
}

// Show toast message
function showToast(message, type = 'success') {
    console.log('Showing toast:', message, type);
    const toast = document.getElementById('statusToast');
    const toastMessage = document.getElementById('toastMessage');
    
    if (toast && toastMessage) {
        console.log('Toast elements found');
        toastMessage.textContent = message;
        toastMessage.className = `toast-body text-${type}`;
        
        // Make sure Bootstrap is loaded
        if (typeof bootstrap === 'undefined') {
            console.error('Bootstrap is not loaded!');
            return;
        }

        // Create new Toast instance
        try {
            const bsToast = bootstrap.Toast.getOrCreateInstance(toast);
            // Set options
            toast.dataset.bsDelay = '8000';  // 8 seconds
            // Show the toast
            bsToast.show();
            console.log('Toast shown successfully');
        } catch (error) {
            console.error('Error showing toast:', error);
        }
    } else {
        console.error('Toast elements not found:', {toast, toastMessage});
    }
}

// Update device status in UI
function updateDeviceStatus(toggle, data, statusLabel, deviceRow, hideInactiveSwitch) {
    // Update the toggle state and appearance
    toggle.checked = data.is_active;
    toggle.style.opacity = data.is_active ? '1' : '0.5';
    
    // Update the status label
    if (statusLabel) {
        statusLabel.textContent = data.is_active ? 'Active' : 'inactive';
        statusLabel.className = `form-check-label status-label ${data.is_active ? 'text-success' : 'text-danger'}`;
    }

    // Update row's active state and visibility
    if (deviceRow) {
        deviceRow.setAttribute('data-device-active', data.is_active.toString());
        if (hideInactiveSwitch && hideInactiveSwitch.checked && !data.is_active) {
            deviceRow.classList.add('hidden');
        } else {
            deviceRow.classList.remove('hidden');
        }
    }

    // Dispatch a custom event to notify other components
    const event = new CustomEvent('deviceStatusChanged', {
        detail: {
            isActive: data.is_active,
            deviceId: toggle.dataset.deviceId
        }
    });
    document.dispatchEvent(event);
}

// Update device counts in UI
function updateDeviceCounts(locationId, data) {
    const activeCountEl = document.getElementById(`location-${locationId}-active`);
    const inactiveCountEl = document.getElementById(`location-${locationId}-inactive`);
    if (activeCountEl) activeCountEl.textContent = data.active_devices_count;
    if (inactiveCountEl) inactiveCountEl.textContent = data.inactive_devices_count;
}

// Revert device status in UI
function revertDeviceStatus(toggle, status, statusLabel, deviceRow, hideInactiveSwitch) {
    toggle.checked = status;
    if (statusLabel) {
        statusLabel.textContent = status ? 'Active' : 'inactive';
        statusLabel.className = `form-check-label status-label ${status ? 'text-success' : 'text-danger'}`;
    }
    if (deviceRow) {
        deviceRow.setAttribute('data-device-active', status.toString());
        if (hideInactiveSwitch && hideInactiveSwitch.checked) {
            deviceRow.classList.toggle('hidden', !status);
        }
    }
}

// Time-based color themes
const timeThemes = {
    morning: { color: '#FF8C00' },     // 5-11
    afternoon: { color: '#000000' },   // 11-17
    evening: { color: '#4B0082' },     // 17-21
    night: { color: '#1E4B9C' }       // 21-5
};

// Update local time display
function updateLocalTime() {
    const now = new Date();
    const offset = -now.getTimezoneOffset();
    const offsetHours = Math.floor(Math.abs(offset) / 60);
    const offsetMinutes = Math.abs(offset) % 60;
    const offsetSign = offset >= 0 ? '+' : '-';
    const offsetString = offsetSign + 
        String(offsetHours).padStart(2, '0') + 
        String(offsetMinutes).padStart(2, '0');

    const hour = now.getHours();
    const timeSpan = document.getElementById('localTime');
    if (!timeSpan) return;

    // Set color based on time of day
    if (hour >= 5 && hour < 11) {
        timeSpan.style.color = timeThemes.morning.color;
    } else if (hour >= 11 && hour < 17) {
        timeSpan.style.color = timeThemes.afternoon.color;
    } else if (hour >= 17 && hour < 21) {
        timeSpan.style.color = timeThemes.evening.color;
    } else {
        timeSpan.style.color = timeThemes.night.color;
    }

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
    
    // Update tooltip with alternative formats
    const isoTime = now.toISOString();
    const unixTime = Math.floor(now.getTime() / 1000);
    timeSpan.setAttribute('data-bs-title', 
        `ISO: ${isoTime}\nUNIX: ${unixTime}\nClick to copy current timestamp`);
}

// Convert Django messages to Toasts
function convertMessagesToToasts() {
    console.log('Converting messages to toasts...');
    const messages = document.querySelectorAll('.alert:not(.processed)');
    console.log('Found unprocessed messages:', messages.length);
    
    messages.forEach(message => {
        // Get text content without the close button text
        const messageText = message.childNodes[0] ? 
            message.childNodes[0].textContent.trim() : 
            message.textContent.trim();

        // Skip empty messages
        if (!messageText) {
            message.remove();
            return;
        }

        console.log('Processing message:', messageText);
        
        const type = message.classList.contains('alert-success') ? 'success' :
                    message.classList.contains('alert-warning') ? 'warning' :
                    message.classList.contains('alert-danger') ? 'danger' : 'info';
        
        // Mark message as processed and remove it before showing toast
        message.classList.add('processed');
        message.remove();
        
        // Show the toast
        showToast(messageText, type);
    });
}

// Initialize time display and tooltips
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM Content Loaded');
    
    // Convert messages immediately
    convertMessagesToToasts();

    // Initialize tooltips
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    const tooltipList = [...tooltipTriggerList].map(el => new bootstrap.Tooltip(el));

    // Initialize time display
    updateLocalTime();
    setInterval(updateLocalTime, 1000);

    // Add click handler to copy timestamp
    const timeSpan = document.getElementById('localTime');
    if (timeSpan) {
        timeSpan.addEventListener('click', function() {
            const now = new Date();
            navigator.clipboard.writeText(now.toISOString()).then(() => {
                const tooltip = bootstrap.Tooltip.getInstance(this);
                const originalTitle = this.getAttribute('data-bs-title');
                
                // Show "Copied!" message
                tooltip.setContent({ '.tooltip-inner': 'Copied!' });
                
                // Reset tooltip after 1 second
                setTimeout(() => {
                    tooltip.setContent({ '.tooltip-inner': originalTitle });
                }, 1000);
            });
        });
    }
});

// Device list functionality
function initializeDeviceList() {
    const hideInactiveSwitch = document.getElementById('hideInactiveDevices');
    const deviceRows = document.querySelectorAll('.device-row');

    function updateDeviceVisibility() {
        deviceRows.forEach(row => {
            if (hideInactiveSwitch.checked && row.classList.contains('inactive')) {
                row.classList.add('d-none');
            } else {
                row.classList.remove('d-none');
            }
        });
    }

    if (hideInactiveSwitch) {
        hideInactiveSwitch.addEventListener('change', updateDeviceVisibility);
        updateDeviceVisibility();
    }
}

// Initialize sensor list functionality
function initializeSensorList() {
    const hideInactiveSwitch = document.getElementById('hideSensorInactiveSwitch');
    const sensorRows = document.querySelectorAll('.sensor-row');

    function updateSensorVisibility() {
        sensorRows.forEach(row => {
            if (row.dataset.sensorActive === 'false') {
                if (hideInactiveSwitch.checked) {
                    row.classList.add('d-none');
                } else {
                    row.classList.remove('d-none');
                }
            }
        });
    }

    if (hideInactiveSwitch) {
        hideInactiveSwitch.addEventListener('change', updateSensorVisibility);
        // Initial state
        updateSensorVisibility();
    }

    // Initialize sensor status toggles with mousedown event instead of click
    document.querySelectorAll('.sensor-status-toggle').forEach(toggle => {
        toggle.addEventListener('mousedown', function(event) {
            // Prevent any default actions
            event.preventDefault();
            
            const sensorId = this.dataset.sensorId;
            const deviceId = this.dataset.deviceId;
            const placeSlug = this.dataset.placeSlug;
            
            // Get the current state - this is guaranteed to be the actual current state
            const currentState = this.checked;
            // The intended state is the opposite of what it currently is
            const intendedState = !currentState;
            
            handleSensorStatusToggle(this, sensorId, placeSlug, intendedState);
        });
        
        // Prevent the click event from changing the state
        toggle.addEventListener('click', function(event) {
            event.preventDefault();
        });
        
        // Prevent the change event from firing
        toggle.addEventListener('change', function(event) {
            event.preventDefault();
        });
    });
}

// Initialize device list functionality when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeDeviceList();
    initializeSensorList();
});

// Update device UI elements after status change
function updateDeviceUI(toggle, deviceId, data) {
    const statusLabel = document.getElementById(`deviceStatusLabel_${deviceId}`);
    const deviceCard = document.getElementById(`deviceCard_${deviceId}`);
    const deviceRow = toggle.closest('tr');  // Get the device's row
    const hideInactiveSwitch = document.getElementById('hideInactiveDevices');
    
    // Update toggle
    toggle.checked = data.is_active;
    toggle.style.opacity = data.is_active ? '1' : '0.5';
    
    // Update status label
    if (statusLabel) {
        statusLabel.textContent = data.is_active ? 'Active' : 'inactive';
        statusLabel.className = `form-check-label status-label ${data.is_active ? 'text-success' : 'text-danger'}`;
    }
    
    // Update device card
    if (deviceCard) {
        if (data.is_active) {
            deviceCard.classList.remove('opacity-75');
        } else {
            deviceCard.classList.add('opacity-75');
        }
        deviceCard.querySelectorAll('dd').forEach(dd => {
            if (!dd.querySelector('.form-check')) {
                dd.style.color = data.is_active ? '#212529' : '#6c757d';
            }
        });
    }

    // Update device row
    if (deviceRow) {
        if (data.is_active) {
            deviceRow.classList.remove('text-muted', 'opacity-50', 'inactive', 'd-none');
            deviceRow.classList.add('active');
        } else {
            deviceRow.classList.remove('active');
            deviceRow.classList.add('text-muted', 'opacity-50', 'inactive');
            // Hide the row if the hide inactive switch is checked
            if (hideInactiveSwitch && hideInactiveSwitch.checked) {
                deviceRow.classList.add('d-none');
            }
        }
        deviceRow.setAttribute('data-device-active', data.is_active.toString());
    }
}

// Update device navigation item
function updateDeviceNavItem(deviceId, isActive) {
    const deviceNavItem = document.querySelector(`.list-group-item[data-device-id="${deviceId}"]`);
    if (!deviceNavItem) return;

    deviceNavItem.setAttribute('data-active', isActive.toString());
    const statusBadge = deviceNavItem.querySelector('.badge.bg-danger');
    
    if (isActive) {
        if (statusBadge) statusBadge.remove();
    } else {
        if (!statusBadge) {
            const badge = document.createElement('span');
            badge.className = 'badge bg-danger ms-2';
            badge.textContent = 'inactive';
            deviceNavItem.querySelector('div:first-child').appendChild(badge);
        }
    }
    
    // Update visibility based on hide inactive switch
    const hideInactiveDevices = document.getElementById('hideInactiveDevicesNav');
    if (hideInactiveDevices && hideInactiveDevices.checked && !isActive) {
        deviceNavItem.classList.add('hidden');
    } else {
        deviceNavItem.classList.remove('hidden');
    }
}

// Update location device counts
function updateLocationDeviceCounts(locationId, isActive, previousState) {
    if (locationId) {
        const activeCountEl = document.getElementById(`location-${locationId}-active`);
        const inactiveCountEl = document.getElementById(`location-${locationId}-inactive`);
        
        if (activeCountEl && inactiveCountEl) {
            let activeCount = parseInt(activeCountEl.textContent);
            let inactiveCount = parseInt(inactiveCountEl.textContent);
            
            // Only update if the state has actually changed
            if (isActive !== previousState) {
                if (isActive) {
                    activeCount++;
                    inactiveCount--;
                } else {
                    activeCount--;
                    inactiveCount++;
                }
                
                activeCountEl.textContent = activeCount;
                inactiveCountEl.textContent = inactiveCount;
            }
        }
    }
}

// Update sensors card UI
function updateSensorsCard(isActive) {
    const sensorsCard = document.querySelector('.sensors-card');
    if (!sensorsCard) return;

    // Update card opacity
    sensorsCard.className = `card sensors-card ${!isActive ? 'opacity-75' : ''}`;
    
    // Update all sensor toggles and rows
    const sensorToggles = sensorsCard.querySelectorAll('.sensor-status-toggle');
    const sensorRows = sensorsCard.querySelectorAll('tbody tr:not(.readings-results)');
    
    sensorToggles.forEach(toggle => {
        toggle.disabled = !isActive;
    });

    sensorRows.forEach(row => {
        if (!isActive) {
            row.classList.add('text-muted', 'opacity-50');
        } else {
            const toggle = row.querySelector('.sensor-status-toggle');
            if (toggle && toggle.checked) {
                row.classList.remove('text-muted', 'opacity-50');
            }
        }
    });

    // Update all buttons in the sensors card
    const buttons = sensorsCard.querySelectorAll('button:not(.sensor-status-toggle), a.btn');
    buttons.forEach(button => {
        if (!button.classList.contains('sensor-status-toggle')) {
            button.disabled = !isActive;
        }
    });

    // Update the Add Sensor button
    const addSensorBtn = sensorsCard.querySelector('.card-header a.btn-primary');
    if (addSensorBtn) {
        addSensorBtn.disabled = !isActive;
    }
}

// Initialize device status toggle functionality
function initializeDeviceStatusToggle() {
    document.querySelectorAll('.device-status-toggle').forEach(toggle => {
        const deviceId = toggle.dataset.deviceId;
        const locationId = toggle.dataset.locationId;
        const placeSlug = toggle.dataset.placeSlug;
        
        if (!deviceId || !placeSlug) {
            console.error('Toggle element missing required data attributes:', toggle);
            toggle.disabled = true;
            return;
        }

        toggle.addEventListener('change', async function(e) {
            const newStatus = this.checked;
            
            // Only show confirmation when deactivating
            if (!newStatus) {
                // First, fetch the list of active sensors that will be affected
                try {
                    const response = await fetch(`/api/${placeSlug}/device/${deviceId}/active_sensors/`);
                    if (!response.ok) throw new Error('Failed to fetch sensor information');
                    const data = await response.json();
                    
                    let confirmMessage = 'Are you sure you want to deactivate this device?\n\n';
                    if (data.sensors && data.sensors.length > 0) {
                        confirmMessage += 'The following sensors will be deactivated:\n';
                        data.sensors.forEach(sensor => {
                            confirmMessage += `- ${sensor.name} (${sensor.type})\n`;
                        });
                    } else {
                        confirmMessage += 'No active sensors will be affected.';
                    }

                    if (!confirm(confirmMessage)) {
                        // Revert the toggle state since user cancelled
                        this.checked = true;
                        return;
                    }
                } catch (error) {
                    console.error('Error fetching sensor information:', error);
                    // Revert the toggle state and show error
                    this.checked = true;
                    showToast('Failed to fetch sensor information', 'danger');
                    return;
                }
            } else if (!confirm('Are you sure you want to activate this device?')) {
                // Revert the toggle state since user cancelled activation
                this.checked = false;
                return;
            }

            try {
                const response = await fetch(`/api/${placeSlug}/device/${deviceId}/toggle_active/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                    body: JSON.stringify({ is_active: newStatus })
                });

                if (!response.ok) throw new Error('Network response was not ok');
                const data = await response.json();

                if (data.status === 'success') {
                    updateDeviceUI(this, deviceId, data);
                    updateDeviceNavItem(deviceId, data.is_active);
                    updateSensorsCard(data.is_active);
                    updateLocationDeviceCounts(locationId, data.is_active, !newStatus);
                    
                    document.dispatchEvent(new CustomEvent('deviceStatusChanged', {
                        detail: { isActive: data.is_active, deviceId, locationId }
                    }));

                    showToast('Device status updated successfully', 'success');
                } else {
                    throw new Error(data.message || 'Failed to update device status');
                }
            } catch (error) {
                console.error('Error:', error);
                // Revert the toggle state since update failed
                this.checked = !newStatus;
                showToast(error.message || 'Failed to update device status', 'danger');
            }
        });
    });
}

// Initialize device status toggle when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeDeviceStatusToggle();
});

// Location filtering functionality
function initializeLocationFiltering() {
    const hideInactiveSwitch = document.getElementById('hideInactiveSwitch');
    const locationRows = document.querySelectorAll('tr[data-active]');
    const locationMarkers = document.querySelectorAll('.location-marker');

    function filterLocations() {
        if (!hideInactiveSwitch) return;
        const hideInactive = hideInactiveSwitch.checked;
        
        // Filter table rows
        locationRows.forEach(row => {
            const isActive = row.dataset.active === 'true';
            row.style.display = (hideInactive && !isActive) ? 'none' : '';
        });

        // Filter map markers
        locationMarkers.forEach(marker => {
            const isActive = marker.dataset.active === 'true';
            marker.style.display = (hideInactive && !isActive) ? 'none' : '';
        });
    }

    if (hideInactiveSwitch) {
        // Initial filter
        hideInactiveSwitch.checked = true;  // Start with inactive locations hidden
        filterLocations();

        // Filter on toggle change
        hideInactiveSwitch.addEventListener('change', filterLocations);
    }
}

// Update place statistics
function initializePlaceStatistics(placeSlug) {
    function updateStatistics() {
        fetch(`/api/${placeSlug}/stats/`)
            .then(response => response.json())
            .then(data => {
                // Update device counts
                const devicesActive = document.getElementById('devices-active');
                const devicesInactive = document.getElementById('devices-inactive');
                if (devicesActive) devicesActive.textContent = data.devices_active;
                if (devicesInactive) devicesInactive.textContent = data.devices_inactive;
                
                // Update sensor counts
                const sensorsActive = document.getElementById('sensors-active');
                const sensorsInactive = document.getElementById('sensors-inactive');
                if (sensorsActive) sensorsActive.textContent = data.sensors_active;
                if (sensorsInactive) sensorsInactive.textContent = data.sensors_inactive;
            });
    }

    // Update statistics every 30 seconds if we're on a place page
    if (placeSlug) {
        setInterval(updateStatistics, 30000);
    }
}

// Initialize location filtering and statistics when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeLocationFiltering();
    
    // Initialize statistics if we have a place slug
    if (window.currentPlaceSlug) {
        initializePlaceStatistics(window.currentPlaceSlug);
    }
});

// Sensor Card Functionality
document.addEventListener('DOMContentLoaded', function() {
    // Listen for device status changes
    document.addEventListener('deviceStatusChanged', function(event) {
        const isDeviceActive = event.detail.isActive;
        const deviceId = event.detail.deviceId;
        const sensorsCard = document.querySelector('.sensors-card');
        
        if (sensorsCard) {
            // Update card opacity
            sensorsCard.className = `card sensors-card ${!isDeviceActive ? 'opacity-75' : ''}`;
            
            // Update all sensor toggles and rows
            const sensorToggles = sensorsCard.querySelectorAll('.sensor-status-toggle');
            const sensorRows = sensorsCard.querySelectorAll('tbody tr:not(.readings-results)');
            
            sensorToggles.forEach(toggle => {
                // Only update toggles for this device
                if (toggle.dataset.deviceId === deviceId) {
                    toggle.disabled = !isDeviceActive;
                }
            });

            sensorRows.forEach(row => {
                const toggle = row.querySelector('.sensor-status-toggle');
                if (toggle && toggle.dataset.deviceId === deviceId) {
                    if (!isDeviceActive) {
                        row.classList.add('text-muted', 'opacity-50');
                    } else {
                        // Only remove opacity if the sensor itself is active
                        if (toggle.checked) {
                            row.classList.remove('text-muted', 'opacity-50');
                        }
                    }
                }
            });

            // Update all action buttons
            const buttons = sensorsCard.querySelectorAll('button:not(.sensor-status-toggle), a.btn');
            buttons.forEach(button => {
                button.disabled = !isDeviceActive;
            });

            // Update the Add Sensor button
            const addSensorBtn = sensorsCard.querySelector('.card-header a.btn-primary');
            if (addSensorBtn) {
                addSensorBtn.disabled = !isDeviceActive;
            }
        }
    });

    // Add click handlers for all test buttons
    document.querySelectorAll('.test-readings-btn').forEach(button => {
        button.addEventListener('click', function() {
            const sensorId = this.dataset.sensorId;
            const url = this.dataset.url;
            const resultsRow = document.getElementById(`readings-results-${sensorId}`);
            const alertDiv = resultsRow.querySelector('.alert');
            const summaryDiv = resultsRow.querySelector('.readings-summary');
            const recentDiv = resultsRow.querySelector('.recent-readings');
            
            // Show the results row and loading state
            resultsRow.classList.remove('d-none');
            alertDiv.classList.remove('d-none', 'alert-success', 'alert-warning', 'alert-danger');
            alertDiv.classList.add('alert-info');
            alertDiv.textContent = 'Testing connection and fetching readings...';
            summaryDiv.classList.add('d-none');
            recentDiv.classList.add('d-none');
            
            // Make the AJAX call
            fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                },
            })
            .then(response => response.json())
            .then(data => {
                handleSensorTestResponse(data, alertDiv, summaryDiv, recentDiv);
            })
            .catch(error => {
                handleSensorTestError(alertDiv, summaryDiv, recentDiv);
            });
        });
    });

    // Add change handlers for sensor status toggles
    document.querySelectorAll('.sensor-status-toggle').forEach(toggle => {
        toggle.addEventListener('change', function() {
            const sensorId = this.dataset.sensorId;
            const deviceId = this.dataset.deviceId;
            const placeSlug = this.dataset.placeSlug;
            const newStatus = this.checked;
            const row = this.closest('tr');

            handleSensorStatusToggle(this, sensorId, placeSlug, newStatus, row);
        });
    });
});

// Helper Functions
function handleSensorTestResponse(data, alertDiv, summaryDiv, recentDiv) {
    // Clear previous alert classes
    alertDiv.classList.remove('alert-info', 'alert-success', 'alert-warning', 'alert-danger');
    
    if (data.status === 'success') {
        // Show success message
        alertDiv.classList.add('alert-success');
        alertDiv.textContent = data.message;
        
        // Update summary table
        updateSensorSummary(data, summaryDiv);
        
        // Update recent readings table
        updateRecentReadings(data, recentDiv);
    } else if (data.status === 'warning') {
        alertDiv.classList.add('alert-warning');
        alertDiv.textContent = data.message;
        summaryDiv.classList.add('d-none');
        recentDiv.classList.add('d-none');
    } else {
        alertDiv.classList.add('alert-danger');
        alertDiv.textContent = data.message;
        summaryDiv.classList.add('d-none');
        recentDiv.classList.add('d-none');
    }
}

function updateSensorSummary(data, summaryDiv) {
    summaryDiv.classList.remove('d-none');
    summaryDiv.querySelector('.count').textContent = data.summary.count;
    summaryDiv.querySelector('.min').textContent = `${data.summary.min} ${data.summary.unit}`;
    summaryDiv.querySelector('.max').textContent = `${data.summary.max} ${data.summary.unit}`;
    summaryDiv.querySelector('.avg').textContent = `${data.summary.avg.toFixed(2)} ${data.summary.unit}`;
    summaryDiv.querySelector('.timerange').textContent = 
        `${new Date(data.summary.first_timestamp).toLocaleString()} - ${new Date(data.summary.last_timestamp).toLocaleString()}`;
}

function updateRecentReadings(data, recentDiv) {
    if (data.readings && data.readings.length > 0) {
        recentDiv.classList.remove('d-none');
        const tbody = recentDiv.querySelector('tbody');
        tbody.innerHTML = '';
        data.readings.forEach(reading => {
            const row = tbody.insertRow();
            row.insertCell(0).textContent = new Date(reading.timestamp).toLocaleString();
            row.insertCell(1).textContent = `${reading.value} ${data.summary.unit}`;
        });
    }
}

function handleSensorTestError(alertDiv, summaryDiv, recentDiv) {
    alertDiv.classList.remove('alert-info');
    alertDiv.classList.add('alert-danger');
    alertDiv.textContent = 'An error occurred while testing the sensor readings.';
    summaryDiv.classList.add('d-none');
    recentDiv.classList.add('d-none');
}

function handleSensorStatusToggle(toggle, sensorId, placeSlug, intendedState) {
    // The confirmation message should be based on what we're trying to do
    const confirmMessage = intendedState ? 
        'Are you sure you want to activate this sensor?' : 
        'Are you sure you want to deactivate this sensor?';
    
    // Get the modal elements
    const modal = document.getElementById('sensorStatusModal');
    const modalBody = document.getElementById('sensorStatusModalBody');
    const confirmButton = document.getElementById('sensorStatusConfirm');
    
    // Set the confirmation message
    modalBody.textContent = confirmMessage;
    
    // Get or create Bootstrap modal instance
    let bsModal = bootstrap.Modal.getInstance(modal) || new bootstrap.Modal(modal);
    
    // Handle confirmation
    const handleConfirm = () => {
        // Hide modal
        bsModal.hide();
        
        // Proceed with the status change - toggle will only change on success
        fetch(`/api/${placeSlug}/sensor/${sensorId}/toggle_active/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
            },
            body: JSON.stringify({
                is_active: intendedState
            })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            if (data.status === 'success') {
                // Only update UI elements after successful response
                updateSensorUI(toggle, sensorId, data);

                // Show success message
                showToast(`Sensor ${data.is_active ? 'activated' : 'deactivated'} successfully`, 'success');

                // Dispatch event to notify other components
                document.dispatchEvent(new CustomEvent('sensorStatusChanged', {
                    detail: {
                        isActive: data.is_active,
                        sensorId: sensorId
                    }
                }));
            } else {
                throw new Error(data.message || 'Failed to update sensor status');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showToast(error.message || 'Failed to update sensor status', 'danger');
        });
    };

    // Handle modal hidden event (triggered by both X button and Cancel button)
    const handleHidden = () => {
        confirmButton.clicked = false;
    };

    // Remove any existing event listeners
    modal.removeEventListener('hidden.bs.modal', handleHidden);
    confirmButton.removeEventListener('click', handleConfirm);
    
    // Add new event listeners
    modal.addEventListener('hidden.bs.modal', handleHidden);
    confirmButton.addEventListener('click', () => {
        confirmButton.clicked = true;
        handleConfirm();
    });
    
    // Show the modal
    bsModal.show();
}

// Update sensor UI elements after status change
function updateSensorUI(toggle, sensorId, data) {
    const statusLabel = document.getElementById(`sensorStatusLabel_${sensorId}`);
    const sensorRow = toggle.closest('tr');
    const hideInactiveSwitch = document.getElementById('hideSensorInactiveSwitch');
    
    // Update toggle state to match backend state
    toggle.checked = data.is_active;
    
    // Update row data attribute and classes
    if (sensorRow) {
        sensorRow.setAttribute('data-sensor-active', data.is_active.toString());
        
        // Update inactive class
        if (!data.is_active) {
            sensorRow.classList.add('inactive');
            // Hide row if the hide inactive switch is checked
            if (hideInactiveSwitch && hideInactiveSwitch.checked) {
                sensorRow.classList.add('d-none');
            }
        } else {
            // Remove both inactive and d-none classes when activating
            sensorRow.classList.remove('inactive');
            sensorRow.classList.remove('d-none');
        }
    }

    // Update status label
    if (statusLabel) {
        statusLabel.textContent = data.is_active ? 'Active' : 'inactive';
        statusLabel.className = `form-check-label status-label ${data.is_active ? 'text-success' : 'text-danger'}`;
    }
}