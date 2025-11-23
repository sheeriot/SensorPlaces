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
    debug: true,
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
            const headerToggles = ['device', 'sensor'].map(type => ({
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
        const bodyToggles = ['device', 'sensor'].map(type => ({
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

    async toggleStatus(modelType, id) {
        const placeSlug = document.body.dataset.placeSlug;
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

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();

            if (toggleActiveConfig.debug) {
                console.debug('Server Response:', data);
            }

            if (data.success) {
                // Find all elements that match this model type and ID
                const wrappers = document.querySelectorAll(`.toggle-button-wrapper[data-${modelType}-id="${id}"]`);
                const rows = document.querySelectorAll(`[data-${modelType}-id="${id}"]`);

                // Find the hideInactive state for this model type
                const hideInactiveState = this.getHideInactiveState(modelType);

                // Update all toggle buttons
                const toggleButtons = document.querySelectorAll(`.toggle-active-button[data-${modelType}-id="${id}"]`);
                toggleButtons.forEach(button => {
                    // Update button state
                    const newStatus = data.new_state;
                    button.setAttribute('data-current-status', newStatus);
                    button.checked = newStatus;

                    // Update parent wrapper's data attribute as well
                    const wrapper = button.closest('.toggle-button-wrapper');
                    if (wrapper) {
                        wrapper.setAttribute(`data-${modelType}-active`, newStatus);
                    }
                });

                // Update row styles
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
                    row.setAttribute(`data-${modelType}-active`, data.new_state.toString());

                    // Update classes based on active state
                    if (data.new_state) {
                        row.classList.remove('opacity-50', 'text-muted', 'd-none');
                        // Also remove from cells for consistency
                        Array.from(row.children).forEach(cell => {
                            cell.classList.remove('opacity-50', 'text-muted');
                        });
                    } else {
                        // Don't apply to the whole row, apply to cells instead to keep toggle visible
                        row.classList.remove('opacity-50', 'text-muted');
                        Array.from(row.children).forEach(cell => {
                            if (cell.querySelector('.toggle-button-wrapper')) {
                                // This cell contains the toggle, so don't fade it.
                                cell.classList.remove('opacity-50', 'text-muted');
                            } else {
                                // Fade all other cells.
                                cell.classList.add('opacity-50', 'text-muted');
                            }
                        });

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
                            label.textContent = data.new_state ? 'Active' : 'Inactive';
                            label.classList.toggle('text-success', data.new_state);
                            label.classList.toggle('text-danger', !data.new_state);
                        }
                    });

                    // Handle device detail card if it exists
                    if (modelType === 'device') {
                        const deviceDetailCard = document.getElementById('device-detail-card');
                        const sensorsCard = document.getElementById('sensors-card');

                        if (deviceDetailCard && sensorsCard) {
                            if (data.new_state) {
                                // If device is now active, remove opacity and show the switch
                                deviceDetailCard.classList.remove('opacity-50');
                                sensorsCard.classList.remove('opacity-50');

                                const hideInactiveSwitch = sensorsCard.querySelector('#hide-inactive-switch-container');
                                if (hideInactiveSwitch) {
                                    hideInactiveSwitch.classList.remove('d-none');
                                }

                                const inactiveBadge = deviceDetailCard.querySelector('#device-inactive-badge');
                                if (inactiveBadge) {
                                    inactiveBadge.classList.add('d-none');
                                }
                            } else {
                                // If device is now inactive, add opacity and hide the switch
                                deviceDetailCard.classList.add('opacity-50');
                                sensorsCard.classList.add('opacity-50');

                                const hideInactiveSwitch = sensorsCard.querySelector('#hide-inactive-switch-container');
                                if (hideInactiveSwitch) {
                                    hideInactiveSwitch.classList.add('d-none');
                                }

                                const inactiveBadge = deviceDetailCard.querySelector('#device-inactive-badge');
                                if (inactiveBadge) {
                                    inactiveBadge.classList.remove('d-none');
                                }
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

                // Handle card-level updates
                const card = document.querySelector(`.card[data-${modelType}-id="${id}"]`);
                if (card) {
                    if (data.new_state) {
                        card.classList.remove('opacity-50', 'text-muted');
                    } else {
                        card.classList.add('opacity-50', 'text-muted');
                    }
                }

                // Update label text
                const toggleContainer = document.getElementById(`toggle-container-${modelType}-${id}`);
                if (toggleContainer) {
                    const label = toggleContainer.querySelector('label');
                    if (label) {
                        label.textContent = data.new_state ? 'Active' : 'inactive';
                        if (data.new_state) {
                            label.classList.remove('text-danger');
                        } else {
                            label.classList.add('text-danger');
                        }
                    }
                }

                // Handle child toggles based on parent type
                if (modelType === 'device') {
                    this.updateChildTogglesForDevice(id, data.new_state);
                }

                // Handle map markers if this is a place toggle
                if (modelType === 'place') {
                    this.updateMapMarkers(id, data.new_state, hideInactiveState);
                }

                return data;
            } else if (data.status === 'warning') {
                // Handle warning status
                if (toggleActiveConfig.debug) {
                    console.warn('Toggle Status Warning:', data.message);
                }

                this.showToast({
                    message: data.message,
                    type: 'warning',
                    addToHistory: true
                });

                return data;
            } else {
                throw new Error(data.message || `Failed to update ${modelType} status`);
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

    // Add helper methods to update child toggles
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
document.addEventListener('DOMContentLoaded', () => {
    document.body.addEventListener('change', function(event) {
        if (event.target.matches('.toggle-active-button')) {
            if (toggleActiveConfig.debug) {
                console.group('Toggle Active Button Change Event');
                console.debug('Target:', event.target);
            }

            const button = event.target;
            const modelType = button.dataset.modelType;
            const id = button.dataset[`${modelType}Id`];
            const wasChecked = button.checked;
            const objectName = button.dataset.objectName || modelType;

            if (toggleActiveConfig.debug) {
                console.debug('Model Type:', modelType);
                console.debug('ID:', id);
                console.debug('wasChecked:', wasChecked);
                console.debug('Object Name:', objectName);
            }

            // Prevent default and immediately revert the visual state
            event.preventDefault();
            button.checked = !wasChecked;
            if (toggleActiveConfig.debug) console.debug('Reverted checkbox state to:', button.checked);


            // If a popover already exists for this button, do nothing
            if (bootstrap.Popover.getInstance(button)) {
                if (toggleActiveConfig.debug) {
                    console.debug('Popover already exists, exiting.');
                    console.groupEnd();
                }
                return;
            }

            if (toggleActiveConfig.debug) console.debug('Creating popover...');

            const popoverContent = () => {
                const container = document.createElement('div');
                const newStatus = wasChecked ? 'active' : 'inactive';
                container.innerHTML = `
                    <p class="mb-2">Set <strong>${objectName}</strong> to ${newStatus}?</p>
                    <div class="d-flex justify-content-end">
                        <button class="btn btn-sm btn-secondary me-2 popover-cancel">Cancel</button>
                        <button class="btn btn-sm btn-primary popover-confirm">Confirm</button>
                    </div>
                `;
                return container;
            };

            const popover = new bootstrap.Popover(button, {
                content: popoverContent,
                html: true,
                placement: 'top',
                trigger: 'manual',
                customClass: 'shadow'
            });

            popover.show();
            if (toggleActiveConfig.debug) console.debug('Popover shown.');

            const popoverEl = document.getElementById(button.getAttribute('aria-describedby'));

            const disposePopover = () => {
                // Remove the event listener to avoid memory leaks
                document.removeEventListener('click', outsideClickHandler, true);
                if (bootstrap.Popover.getInstance(button)) {
                    if (toggleActiveConfig.debug) console.debug('Disposing popover.');
                    popover.dispose();
                }
                if (toggleActiveConfig.debug) console.groupEnd();
            };

            const outsideClickHandler = (e) => {
                // If the click is outside the popover and the button, dispose of the popover.
                if (popoverEl && !popoverEl.contains(e.target) && e.target !== button) {
                    if (toggleActiveConfig.debug) console.debug('Clicked outside, disposing popover.');
                    disposePopover();
                }
            };

            // Use capture phase to ensure this runs before other click events
            document.addEventListener('click', outsideClickHandler, true);

            popoverEl.addEventListener('click', function(e) {
                if (e.target.matches('.popover-confirm')) {
                    if (toggleActiveConfig.debug) console.debug('Confirm button clicked.');
                    toggleActiveManager.toggleStatus(modelType, id)
                        .then(result => {
                            if (toggleActiveConfig.debug) {
                                console.debug('toggleStatus finished successfully.', result);
                            }
                        })
                        .catch(error => {
                            if (toggleActiveConfig.debug) {
                                console.error('toggleStatus failed.', error);
                            }
                        })
                        .finally(() => {
                            disposePopover();
                        });
                } else if (e.target.matches('.popover-cancel')) {
                     if (toggleActiveConfig.debug) console.debug('Cancel button clicked.');
                     disposePopover();
                }
            });
        }
    });
});

// Export for use in other modules
window.toggleActiveManager = toggleActiveManager;
