document.addEventListener('DOMContentLoaded', function () {
    const deviceMoveConfig = {
        debug: true
    };

    if (deviceMoveConfig.debug) console.log('Device Move script loaded.');

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

                    // Ensure complete cleanup of backdrop and body styles
                    // This fixes the issue where the background remains dimmed and page is frozen
                    setTimeout(() => {
                        // 1. Remove backdrops
                        document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());

                        // 2. Reset body styles (restore scrolling)
                        document.body.classList.remove('modal-open');
                        document.body.style.overflow = '';
                        document.body.style.paddingRight = '';

                        // 3. Ensure the modal container itself is hidden and interaction is restored
                        modalContainer.classList.remove('show');
                        modalContainer.style.display = 'none';
                        modalContainer.setAttribute('aria-hidden', 'true');
                        modalContainer.removeAttribute('aria-modal');
                        modalContainer.removeAttribute('role');

                        // 4. Clear content
                        const content = modalContainer.querySelector('.modal-content');
                        if (content) content.innerHTML = '';
                    }, 300); // Small delay to let Bootstrap animations finish

                    // 2. Show Toast
                    if (window.ToastUi) {
                        window.ToastUi.success(data.message);
                    }

                    // 3. Remove the device row from the Unassigned list
                    // The API response includes device info? Not explicitly the ID in top level,
                    // but we can assume the form action URL has the ID or we can find it.
                    // Actually, the View returns 'old_location_id', 'new_location_id', etc.
                    // But we need the device ID to remove the specific row.

                    // We can find the device ID from the form action URL or context?
                    // Or we can assume the user hasn't clicked another move button in the meantime.

                    // Better: The row removal logic.
                    // We need to identify WHICH device row to remove.
                    // Since we just submitted a form for a specific device...
                    // The form's action URL is like /api/.../device/<pk>/move/

                    const actionUrl = target.getAttribute('action') || target.getAttribute('hx-post'); // hx-post is on the form
                    // Extract ID from URL: .../device/123/move/
                    const match = actionUrl.match(/\/device\/(\d+)\/move\//);
                    if (match && match[1]) {
                        const deviceId = match[1];
                        const deviceRow = document.querySelector(`.device-row[data-device-id="${deviceId}"]`);

                        if (deviceRow) {
                            deviceRow.style.transition = 'opacity 0.5s ease';
                            deviceRow.style.opacity = '0';

                            setTimeout(() => {
                                const parentContainer = deviceRow.parentElement;
                                deviceRow.remove();

                                // Check for empty state
                                if (parentContainer && parentContainer.closest('#unassigned-devices-card')) {
                                    const remainingDevices = parentContainer.querySelectorAll('.device-row');
                                    if (remainingDevices.length === 0) {
                                        const emptyStateHtml = `
                                            <div class="text-center p-3 text-muted">
                                                <p class="mb-0">No unassigned devices found.</p>
                                            </div>`;
                                        parentContainer.insertAdjacentHTML('beforeend', emptyStateHtml);
                                    }
                                }
                            }, 500);
                        }
                    }

                    // 4. Update Counts
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
