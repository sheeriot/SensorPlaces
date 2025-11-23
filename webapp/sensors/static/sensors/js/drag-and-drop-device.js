document.addEventListener('DOMContentLoaded', function () {
    const draggables = document.querySelectorAll('.device-row[draggable="true"]');
    const dropzones = document.querySelectorAll('#place-nav-card .list-group-item[data-location-id]');
    const modalContainer = document.getElementById('modal-container');
    const modalContent = document.getElementById('modal-content');

    if (!modalContainer || !modalContent) {
        console.error('Modal container or content not found. Cannot initialize drag-and-drop move.');
        return;
    }

    if (dropzones.length === 0) {
        console.warn('No dropzones found on the page. Drag-and-drop will not be initialized for locations.');
    }

    let draggedItem = null;

    draggables.forEach(draggable => {
        draggable.addEventListener('dragstart', function (e) {
            console.log('dragstart: Fired for element:', this);
            draggedItem = this; // Use `this` which refers to the `tr` element the listener is on.
            // Use a class to indicate dragging state, it's cleaner than direct style manipulation
            this.classList.add('dragging');
        });

        draggable.addEventListener('dragend', function (e) {
            this.classList.remove('dragging');
            draggedItem = null;
        });
    });

    dropzones.forEach(dropzone => {
        dropzone.addEventListener('dragover', function (e) {
            e.preventDefault();
            const locationId = this.dataset.locationId;
            // Prevent dropping on the 'unassigned-devices' location if it exists in the nav
            if (locationId && locationId !== 'unassigned-devices') {
                this.classList.add('bg-primary', 'bg-opacity-10');
            }
        });

        dropzone.addEventListener('dragleave', function (e) {
            this.classList.remove('bg-primary', 'bg-opacity-10');
        });

        dropzone.addEventListener('drop', function (e) {
            e.preventDefault();
            console.log('drop: Fired on element:', this);
            this.classList.remove('bg-primary', 'bg-opacity-10');

            if (!draggedItem) {
                console.error('Drop event fired, but no draggedItem was set.');
                return;
            }

            console.log('drop: Dragged item is:', draggedItem);
            console.log('drop: Dragged item dataset:', draggedItem.dataset);

            const deviceId = draggedItem.dataset.deviceId;
            console.log('drop: Device ID from dataset:', deviceId);

            const deviceName = draggedItem.querySelector('td:first-child span')?.textContent || 'this device';
            const newLocationId = this.dataset.locationId;
            const newLocationName = this.querySelector('.fw-bold')?.textContent || 'this location';
            const placeSlug = document.body.dataset.placeSlug;

            if (!newLocationId || newLocationId === 'unassigned-devices') {
                console.warn('drop: Invalid drop target (unassigned or missing ID). Aborting.');
                return;
            }

            if (!deviceId) {
                console.error('drop: Could not determine deviceId. Aborting move.');
                if (window.ToastUi) {
                    window.ToastUi.error('Could not identify the device to move. Please refresh and try again.');
                }
                return;
            }

            const moveUrl = `/api/${placeSlug}/device/${deviceId}/move/`;

            // 1. Populate and show the modal
            const modalInstance = new bootstrap.Modal(modalContainer);
            modalContent.innerHTML = `
                <div class="modal-header">
                    <h5 class="modal-title">Confirm Device Move</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <p>Are you sure you want to move <strong>${deviceName}</strong> to <strong>${newLocationName}</strong>?</p>
                    <div class="form-check mt-3">
                        <input class="form-check-input" type="checkbox" name="make_active" id="makeActiveCheckbox" checked>
                        <label class="form-check-label" for="makeActiveCheckbox">
                            Activate this device upon moving
                        </label>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button id="confirmMoveBtn" type="button" class="btn btn-primary"
                            hx-post="${moveUrl}"
                            hx-vals='${JSON.stringify({"location_id": newLocationId})}'
                            hx-include="[name='make_active']"
                            hx-swap="none"
                            data-device-id="${deviceId}">
                        Confirm Move
                    </button>
                </div>
            `;

            // 2. Process HTMX attributes
            htmx.process(modalContent);
            modalInstance.show();
        });
    });

    // 3. Listen for the HTMX response and update UI
    document.body.addEventListener('htmx:afterRequest', function (evt) {
        const xhr = evt.detail.xhr;
        const target = evt.detail.target;

        // Check if the request was successful and originated from our confirm button
        if (evt.detail.successful && target.id === 'confirmMoveBtn') {
            const data = JSON.parse(xhr.responseText);
            const deviceId = target.dataset.deviceId;
            const deviceRow = document.querySelector(`.device-row[data-device-id="${deviceId}"]`);

            if (data.success) {
                // Close the modal
                const modalInstance = bootstrap.Modal.getInstance(modalContainer);
                if (modalInstance) {
                    modalInstance.hide();
                }

                // Show success toast
                if (window.ToastUi) {
                    window.ToastUi.success(data.message);
                }

                // Remove the device from the list
                if (deviceRow) {
                    deviceRow.style.transition = 'opacity 0.5s ease';
                    deviceRow.style.opacity = '0';
                    setTimeout(() => deviceRow.remove(), 500);
                }

                // Update UI counts
                updateCounts(data);

            } else {
                if (window.ToastUi) {
                    window.ToastUi.error(`Error: ${data.error || 'An unknown error occurred.'}`);
                }
            }
        } else if (!evt.detail.successful && target.id === 'confirmMoveBtn') {
            // Handle failed requests (e.g., server error)
            if (window.ToastUi) {
                window.ToastUi.error('A server error occurred while moving the device.');
            }
        }
    });

    function updateCounts(data) {
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

    function getCsrfToken() {
        const csrfInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
        return csrfInput ? csrfInput.value : '';
    }

    // Add CSRF token to all HTMX POST requests
    document.body.addEventListener('htmx:configRequest', function(evt) {
        if (evt.detail.verb === 'post') {
            evt.detail.headers['X-CSRFToken'] = getCsrfToken();
        }
    });
});
