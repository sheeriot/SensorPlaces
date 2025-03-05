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
                <div class="modal fade" id="deviceToggleConfirmModal" tabindex="-1" role="dialog" aria-labelledby="deviceToggleModalTitle" data-bs-backdrop="static">
                    <div class="modal-dialog" role="document">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title" id="deviceToggleModalTitle">Confirm Status Change</h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
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

            // Add event listener to handle modal show/hide
            const modal = document.getElementById('deviceToggleConfirmModal');
            
            // Store the element that had focus before the modal was opened
            let previousActiveElement = null;

            modal.addEventListener('show.bs.modal', () => {
                // Store the currently focused element
                previousActiveElement = document.activeElement;
            });

            modal.addEventListener('shown.bs.modal', () => {
                // Focus the confirm button by default
                const confirmButton = modal.querySelector('#deviceToggleConfirm');
                if (confirmButton) {
                    confirmButton.focus();
                }
            });

            modal.addEventListener('hide.bs.modal', () => {
                // Remove focus from any element inside the modal before it's hidden
                if (document.activeElement && modal.contains(document.activeElement)) {
                    document.activeElement.blur();
                }
            });

            modal.addEventListener('hidden.bs.modal', () => {
                // Restore focus to the previous element
                if (previousActiveElement && previousActiveElement.focus) {
                    previousActiveElement.focus();
                }
            });

            // Handle keyboard navigation within modal
            modal.addEventListener('keydown', (e) => {
                if (e.key === 'Tab') {
                    const focusableElements = modal.querySelectorAll(
                        'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
                    );
                    const firstFocusable = focusableElements[0];
                    const lastFocusable = focusableElements[focusableElements.length - 1];

                    // If shift+tab and on first element, move to last
                    if (e.shiftKey && document.activeElement === firstFocusable) {
                        e.preventDefault();
                        lastFocusable.focus();
                    }
                    // If tab and on last element, move to first
                    else if (!e.shiftKey && document.activeElement === lastFocusable) {
                        e.preventDefault();
                        firstFocusable.focus();
                    }
                }
            });
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
                        const response = await utils.fetchWithCSRF(`/api/${placeSlug}/device/${deviceId}/active_sensors/`);
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
                <div class="modal" id="sensorToggleConfirmModal" tabindex="-1" role="dialog" aria-modal="true" data-bs-backdrop="static">
                    <div class="modal-dialog" role="document">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title" id="sensorToggleModalTitle">Confirm Status Change</h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
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

            const modal = document.getElementById('sensorToggleConfirmModal');
            let previousActiveElement = null;
            let focusableElements = null;

            // Create Bootstrap modal instance
            const modalInstance = new bootstrap.Modal(modal, {
                backdrop: 'static',
                keyboard: true
            });

            // Function to get all focusable elements in the modal
            const getFocusableElements = () => {
                return modal.querySelectorAll(
                    'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
                );
            };

            // Create a MutationObserver to watch for Bootstrap adding unwanted attributes
            const observer = new MutationObserver((mutations) => {
                mutations.forEach((mutation) => {
                    if (mutation.type === 'attributes') {
                        if (mutation.attributeName === 'aria-hidden') {
                            modal.removeAttribute('aria-hidden');
                        }
                        if (mutation.attributeName === 'class' && modal.classList.contains('fade')) {
                            modal.classList.remove('fade');
                        }
                    }
                });
            });

            // Start observing the modal
            observer.observe(modal, {
                attributes: true,
                attributeFilter: ['aria-hidden', 'class']
            });

            // Handle modal events
            modal.addEventListener('show.bs.modal', () => {
                previousActiveElement = document.activeElement;
                focusableElements = Array.from(getFocusableElements());
            });

            modal.addEventListener('shown.bs.modal', () => {
                // Focus the confirm button
                const confirmButton = modal.querySelector('#sensorToggleConfirm');
                if (confirmButton) {
                    confirmButton.focus();
                }
            });

            modal.addEventListener('hide.bs.modal', () => {
                // Ensure focus is removed from modal elements before hiding
                if (document.activeElement && modal.contains(document.activeElement)) {
                    document.activeElement.blur();
                }
            });

            modal.addEventListener('hidden.bs.modal', () => {
                // Return focus to the previous element after a short delay
                if (previousActiveElement && previousActiveElement.focus) {
                    // Small delay to ensure proper focus management
                    setTimeout(() => {
                        previousActiveElement.focus();
                    }, 0);
                }
            });

            // Handle keyboard navigation
            modal.addEventListener('keydown', (e) => {
                if (!focusableElements) return;
                
                if (e.key === 'Tab') {
                    const firstFocusable = focusableElements[0];
                    const lastFocusable = focusableElements[focusableElements.length - 1];

                    // If shift+tab and on first element, move to last
                    if (e.shiftKey && document.activeElement === firstFocusable) {
                        e.preventDefault();
                        lastFocusable.focus();
                    }
                    // If tab and on last element, move to first
                    else if (!e.shiftKey && document.activeElement === lastFocusable) {
                        e.preventDefault();
                        firstFocusable.focus();
                    }
                }
            });

            // Store the modal instance
            modal._bsModal = modalInstance;
        }

        document.querySelectorAll('.sensor-status-toggle').forEach(toggle => {
            // Remove any existing event listeners
            const oldHandler = toggle._changeHandler;
            if (oldHandler) {
                toggle.removeEventListener('change', oldHandler);
            }

            // Create new handler
            const changeHandler = async function(e) {
                e.preventDefault();
                
                const sensorId = this.dataset.sensorId;
                const placeSlug = this.dataset.placeSlug;
                const newStatus = this.checked;
                const sensorRow = this.closest('tr');
                
                // Store the toggle element for later reference
                const toggleElement = this;
                
                // Revert the checkbox state until confirmed
                this.checked = !newStatus;
                
                const confirmMessage = newStatus ? 
                    'Are you sure you want to activate this sensor?' : 
                    'Are you sure you want to deactivate this sensor?';

                // Get the modal and update its content
                const modal = document.getElementById('sensorToggleConfirmModal');
                const modalInstance = modal._bsModal;
                modal.querySelector('.modal-body').textContent = confirmMessage;

                // Set up the confirmation action
                const confirmButton = modal.querySelector('#sensorToggleConfirm');
                const handleConfirm = async () => {
                    // Remove focus from the confirm button before hiding modal
                    confirmButton.blur();
                    
                    // Hide modal first
                    modalInstance.hide();
                    
                    // Remove the event listener
                    confirmButton.removeEventListener('click', handleConfirm);

                    // Wait a brief moment for the modal to fully hide
                    await new Promise(resolve => setTimeout(resolve, 50));

                    const result = await toggleActiveManager.toggleStatus('sensor', sensorId, placeSlug, newStatus);
                    
                    if (!result) {
                        toggleElement.checked = !newStatus;
                        return;
                    }

                    // Update the toggle state
                    toggleElement.checked = result.is_active;
                    
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
            };

            // Store the handler for future cleanup
            toggle._changeHandler = changeHandler;
            
            // Add new event listener
            toggle.addEventListener('change', changeHandler);
        });
    }
};

// Visibility Toggle System
const visibilityToggleManager = {
    initializeLocationNav() {
        // Initialize list card switch
        const hideInactiveListSwitch = document.getElementById('hideInactiveLocationsListCard');
        if (hideInactiveListSwitch) {
            const locationRows = document.querySelectorAll('.location-row[data-location-active]');
            const locationMarkers = document.querySelectorAll('.location-marker[data-location-active]');

            const filterLocations = () => {
                const hideInactive = hideInactiveListSwitch.checked;
                
                // Filter location rows in the list
                locationRows.forEach(row => {
                    const isActive = row.getAttribute('data-location-active') === 'true';
                    row.classList.toggle('d-none', hideInactive && !isActive);
                });
                
                // Filter location markers on the site plan
                locationMarkers.forEach(marker => {
                    const isActive = marker.getAttribute('data-location-active') === 'true';
                    marker.classList.toggle('d-none', hideInactive && !isActive);
                });
            };

            // Initial filter
            filterLocations();
            // Filter on toggle change
            hideInactiveListSwitch.addEventListener('change', filterLocations);
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

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize device and sensor toggle functionality
    toggleActiveManager.initializeDeviceToggles();
    toggleActiveManager.initializeSensorToggles();
    
    // Initialize visibility toggle functionality
    visibilityToggleManager.initializeLocationNav();
    visibilityToggleManager.initializeDeviceNav();
    visibilityToggleManager.initializeDeviceList();
    visibilityToggleManager.initializeSensorList();
});

// Export for use in other modules
window.toggleActiveManager = toggleActiveManager;
window.visibilityToggleManager = visibilityToggleManager; 