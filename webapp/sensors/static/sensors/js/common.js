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
    const toast = document.getElementById('statusToast');
    const toastMessage = document.getElementById('toastMessage');
    
    if (toast && toastMessage) {
        toastMessage.textContent = message;
        toastMessage.className = `toast-body text-${type}`;
        const bsToast = new bootstrap.Toast(toast);
        bsToast.show();
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

// Initialize time display and tooltips
document.addEventListener('DOMContentLoaded', function() {
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

    // Device status toggle handling
    document.querySelectorAll('.device-status-toggle').forEach(toggle => {
        toggle.addEventListener('change', async function(e) {
            const deviceRow = this.closest('.device-row');
            const deviceId = deviceRow.dataset.deviceId;
            const newStatus = !this.checked;
            
            if (!confirm(`Are you sure you want to ${newStatus ? 'deactivate' : 'activate'} this device?`)) {
                e.preventDefault();
                this.checked = !newStatus;
                return;
            }

            try {
                if (!window.currentPlaceSlug) {
                    throw new Error('Place slug not available');
                }

                const response = await fetch(`/api/${window.currentPlaceSlug}/device/${deviceId}/toggle_active/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken')
                    },
                    body: JSON.stringify({ is_active: !newStatus })
                });

                if (!response.ok) throw new Error('Network response was not ok');
                
                const data = await response.json();
                
                // Update UI elements
                const statusLabel = deviceRow.querySelector('.status-label');
                deviceRow.dataset.active = (!newStatus).toString();
                statusLabel.textContent = newStatus ? 'inactive' : 'active';
                
                if (newStatus) {
                    deviceRow.classList.add('inactive');
                    if (hideInactiveSwitch && hideInactiveSwitch.checked) {
                        deviceRow.classList.add('d-none');
                    }
                } else {
                    deviceRow.classList.remove('inactive');
                    deviceRow.classList.remove('d-none');
                }

                // Update place nav card counts if they exist
                const activeCountElement = document.getElementById('active-device-count');
                const inactiveCountElement = document.getElementById('inactive-device-count');
                if (activeCountElement && data.active_count !== undefined) {
                    activeCountElement.textContent = data.active_count;
                }
                if (inactiveCountElement && data.inactive_count !== undefined) {
                    inactiveCountElement.textContent = `(${data.inactive_count})`;
                }

                // Dispatch event for other components
                document.dispatchEvent(new CustomEvent('deviceStatusChanged', {
                    detail: { deviceId, isActive: !newStatus }
                }));

            } catch (error) {
                console.error('Error:', error);
                this.checked = !newStatus;
                alert('Failed to update device status. Please try again.');
            }
        });
    });
}

// Initialize device list functionality when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeDeviceList();
});

// Initialize device status toggle functionality
function initializeDeviceStatusToggle() {
    document.querySelectorAll('.device-status-toggle').forEach(toggle => {
        toggle.addEventListener('change', function(e) {
            e.preventDefault();
            
            const deviceId = this.dataset.deviceId;
            const locationId = this.dataset.locationId;
            const placeSlug = this.dataset.placeSlug;
            const newStatus = this.checked;
            const statusLabel = document.getElementById(`deviceStatusLabel_${deviceId}`);
            const deviceCard = document.getElementById(`deviceCard_${deviceId}`);
            const sensorsCard = document.querySelector('.sensors-card');
            
            const confirmMessage = newStatus ? 
                'Are you sure you want to activate this device?' : 
                'Are you sure you want to deactivate this device? This will also deactivate all associated sensors.';
            
            if (confirm(confirmMessage)) {
                fetch(`/api/${placeSlug}/device/${deviceId}/toggle_active/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                    body: JSON.stringify({
                        is_active: newStatus
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
                        // Update the toggle state and appearance
                        this.checked = data.is_active;
                        this.style.opacity = data.is_active ? '1' : '0.5';
                        
                        // Update the status label
                        if (statusLabel) {
                            statusLabel.textContent = data.is_active ? 'Active' : 'inactive';
                            statusLabel.className = `form-check-label status-label ${data.is_active ? 'text-success' : 'text-danger'}`;
                        }
                        
                        // Update the device card styling
                        if (deviceCard) {
                            deviceCard.className = `card rounded-3 shadow-sm border-0 mb-4 ${!data.is_active ? 'opacity-75' : ''}`;
                        }
                        
                        // Update device nav card item
                        const deviceNavItem = document.querySelector(`.list-group-item[data-device-id="${deviceId}"]`);
                        if (deviceNavItem) {
                            deviceNavItem.setAttribute('data-active', data.is_active.toString());
                            const statusBadge = deviceNavItem.querySelector('.badge.bg-danger');
                            if (data.is_active) {
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
                            if (hideInactiveDevices && hideInactiveDevices.checked && !data.is_active) {
                                deviceNavItem.classList.add('hidden');
                            } else {
                                deviceNavItem.classList.remove('hidden');
                            }
                        }
                        
                        // Update all value text colors in device card
                        if (deviceCard) {
                            deviceCard.querySelectorAll('dd').forEach(dd => {
                                if (!dd.querySelector('.form-check')) {
                                    dd.style.color = data.is_active ? '#212529' : '#6c757d';
                                }
                            });
                        }

                        // Update sensors card if it exists
                        if (sensorsCard) {
                            // Update card opacity
                            sensorsCard.className = `card sensors-card ${!data.is_active ? 'opacity-75' : ''}`;
                            
                            // Update all sensor toggles and rows
                            const sensorToggles = sensorsCard.querySelectorAll('.sensor-status-toggle');
                            const sensorRows = sensorsCard.querySelectorAll('tbody tr:not(.readings-results)');
                            
                            sensorToggles.forEach(toggle => {
                                toggle.disabled = !data.is_active;
                            });

                            sensorRows.forEach(row => {
                                if (!data.is_active) {
                                    row.classList.add('text-muted', 'opacity-50');
                                } else {
                                    // Only remove opacity if the sensor itself is active
                                    const toggle = row.querySelector('.sensor-status-toggle');
                                    if (toggle && toggle.checked) {
                                        row.classList.remove('text-muted', 'opacity-50');
                                    }
                                }
                            });

                            // Update all buttons in the sensors card
                            const buttons = sensorsCard.querySelectorAll('button, a.btn');
                            buttons.forEach(button => {
                                if (!button.classList.contains('sensor-status-toggle')) {
                                    button.disabled = !data.is_active;
                                }
                            });

                            // Update the Add Sensor button
                            const addSensorBtn = sensorsCard.querySelector('.card-header a.btn-primary');
                            if (addSensorBtn) {
                                addSensorBtn.disabled = !data.is_active;
                            }

                            // Dispatch a custom event to notify the sensor card
                            const event = new CustomEvent('deviceStatusChanged', {
                                detail: {
                                    isActive: data.is_active,
                                    deviceId: deviceId
                                }
                            });
                            document.dispatchEvent(event);
                        }

                        showToast('Device status updated successfully', 'success');
                    } else {
                        throw new Error(data.message || 'Failed to update device status');
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    this.checked = !newStatus;
                    showToast(error.message || 'Failed to update device status', 'danger');
                });
            } else {
                this.checked = !newStatus;
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

function handleSensorStatusToggle(toggle, sensorId, placeSlug, newStatus, row) {
    const confirmMessage = newStatus ? 
        'Are you sure you want to activate this sensor?' : 
        'Are you sure you want to deactivate this sensor?';

    if (confirm(confirmMessage)) {
        fetch(`/api/${placeSlug}/sensors/${sensorId}/toggle_active/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
            },
            body: JSON.stringify({
                is_active: newStatus
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
                // Update the toggle state
                toggle.checked = data.is_active;
                
                // Update row styling
                if (!data.is_active) {
                    row.classList.add('text-muted', 'opacity-50');
                } else {
                    row.classList.remove('text-muted', 'opacity-50');
                }
            } else {
                throw new Error(data.message || 'Failed to update sensor status');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            toggle.checked = !newStatus;
            alert('Failed to update sensor status');
        });
    } else {
        toggle.checked = !newStatus;
    }
}

// Handle form submissions
document.addEventListener('DOMContentLoaded', function() {
    // Handle delete forms
    document.querySelectorAll('form[data-delete-form]').forEach(form => {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            
            if (!confirm('Are you sure you want to delete this item?')) {
                return;
            }
            
            fetch(this.action, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(response => response.json())
            .then(data => {
                showToast(data.message, data.status);
                if (data.redirect_url) {
                    window.location.href = data.redirect_url;
                }
            })
            .catch(error => {
                showToast('An error occurred while processing your request.', 'danger');
                console.error('Error:', error);
            });
        });
    });

    // Handle create/update forms
    document.querySelectorAll('form:not([data-delete-form])').forEach(form => {
        form.addEventListener('submit', function(e) {
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
            }
            
            // Let the form submit normally, but show any Django messages as toasts
            const messages = document.querySelectorAll('.alert');
            messages.forEach(message => {
                const type = message.classList.contains('alert-success') ? 'success' :
                            message.classList.contains('alert-warning') ? 'warning' :
                            message.classList.contains('alert-danger') ? 'danger' : 'info';
                showToast(message.textContent, type);
                message.remove();
            });
        });
    });
}); 