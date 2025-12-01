document.addEventListener('DOMContentLoaded', function () {
    const deviceMoveConfig = {
        debug: false
    };

    const modalContainer = document.getElementById('modal-container');

    // Listen for HTMX requests to handle the move form submission
    document.body.addEventListener('htmx:afterRequest', function (evt) {
        const target = evt.detail.target;
        const xhr = evt.detail.xhr;

        // Check if this request came from our move form
        if (target.id === 'moveDeviceForm' && evt.detail.successful) {
            if (deviceMoveConfig.debug) console.log('Move device form submitted successfully.');

            try {
                const data = JSON.parse(xhr.responseText);
                if (data.success) {
                    // 1. Close Modal
                    const modalInstance = bootstrap.Modal.getInstance(modalContainer);
                    if (modalInstance) {
                        modalInstance.hide();
                    } else {
                        // Fallback if instance is lost
                        const newInstance = new bootstrap.Modal(modalContainer);
                        newInstance.hide();
                    }

                    // The 'hidden.bs.modal' event listener in modal-handlers.js will now handle cleanup.

                    // 2. Show Toast
                    if (window.ToastUi) {
                        window.ToastUi.success(data.message);
                    }

                    // 3. Remove the device row from the Unassigned list
                    const actionUrl = target.getAttribute('action') || target.getAttribute('hx-post');
                    const match = actionUrl.match(/\/device\/(\d+)\/move\//);

                    if (match && match[1]) {
                        const deviceId = match[1];
                        const deviceRow = document.querySelector(`#unassigned-devices-card .device-row[data-device-id="${deviceId}"]`);

                        if (deviceRow) {
                            // Fade out and remove the row from the unassigned list
                            deviceRow.style.transition = 'opacity 0.5s ease';
                            deviceRow.style.opacity = '0';

                            setTimeout(() => {
                                const parentContainer = deviceRow.parentElement;
                                deviceRow.remove();

                                // Update the count badge for unassigned devices
                                const unassignedCard = document.getElementById('unassigned-devices-card');
                                if (unassignedCard) {
                                    const countBadge = unassignedCard.querySelector('.card-header .badge');
                                    if (countBadge) {
                                        const currentCount = parseInt(countBadge.textContent, 10);
                                        if (!isNaN(currentCount)) {
                                            countBadge.textContent = Math.max(0, currentCount - 1);
                                        }
                                    }
                                }

                                // Check for empty state in unassigned list
                                if (parentContainer) {
                                    const remainingDevices = parentContainer.querySelectorAll('.device-row');
                                    if (remainingDevices.length === 0) {
                                        const emptyStateHtml = `
                                            <div class="text-center p-3 text-muted">
                                                <p class="mb-0">No unassigned devices found.</p>
                                            </div>`;
                                        parentContainer.insertAdjacentHTML('beforeend', emptyStateHtml);
                                    }
                                }
                            }, 500); // Wait for fade out
                        }
                    }

                    // 4. Add the device row to the new location
                    if (data.device_row_html && data.new_location_id) {
                        // Find the new location's row in the main device list
                        const locationRow = document.querySelector(`.location-row[data-location-id="${data.new_location_id}"]`);

                        if (locationRow) {
                            // Insert the new device row right after the location header
                            locationRow.insertAdjacentHTML('afterend', data.device_row_html);
                            const newDeviceRow = locationRow.nextElementSibling;

                            // Animate the new row appearing
                            if (newDeviceRow && newDeviceRow.classList.contains('device-row')) {
                                newDeviceRow.style.opacity = '0';
                                newDeviceRow.style.transition = 'opacity 0.5s ease';
                                setTimeout(() => {
                                    newDeviceRow.style.opacity = '1';
                                }, 100); // Short delay to ensure transition applies
                            }
                        }
                    }

                    // 5. Update Counts
                    if (typeof updateCounts === 'function') {
                        updateCounts(data);
                    } else {
                        // Fallback local updateCounts if global one isn't available
                        _localUpdateCounts(data);
                    }

                } else {
                    if (window.ToastUi) {
                        window.ToastUi.error(`Error: ${data.error || 'An unknown error occurred.'}`);
                    }
                }
            } catch (e) {
                console.error('Error parsing move response:', e);
                if (window.ToastUi) {
                    window.ToastUi.error('An error occurred processing the server response.');
                }
            }
        }
    });

    function _localUpdateCounts(data) {
        // Update new location count in the nav
        const newLocationCountEl = document.querySelector(`#location-${data.new_location_id}-active`);
        if (newLocationCountEl) {
            newLocationCountEl.textContent = data.new_location_active_count;
        }

        // Update main place counts in the live counts card
        const liveCounts = data.place_counts;
        if (liveCounts) {
            const activeEl = document.getElementById('live-devices-active');
            const totalEl = document.getElementById('live-devices-total');
            if (activeEl) activeEl.textContent = liveCounts.devices_active;
            if (totalEl) totalEl.textContent = liveCounts.devices_total;
        }
    }
});
