// Configuration
const deviceFormManager = {
    config: {
        debug: true,
    },

    init() {
        if (this.config.debug) console.log('[DeviceForm] Initializing');

        const deviceForm = document.getElementById('device-form');
        if (!deviceForm) {
            if (this.config.debug) console.error('[DeviceForm] Could not find form #device-form');
            return;
        }

        const locationSelect = deviceForm.querySelector('select[name="location"]');
        if (!locationSelect) {
            if (this.config.debug) console.error('[DeviceForm] Could not find location select element.');
            return;
        }

        const activeCheckbox = deviceForm.querySelector('.active-status-checkbox');
        if (activeCheckbox) {
            activeCheckbox.addEventListener('change', (event) => {
                if (this.config.debug) console.log('%c--- Active Checkbox Changed ---', 'color: green; font-weight: bold;');
                const isChecked = event.currentTarget.checked;
                const label = deviceForm.querySelector(`label[for="${activeCheckbox.id}"]`);
                if (label) {
                    label.textContent = isChecked ? 'Active' : 'inactive';
                    if (this.config.debug) console.log(`[DeviceForm] Label updated to "${label.textContent}"`);
                }
            });
        }

        locationSelect.addEventListener('change', (event) => {
            if (this.config.debug) console.log('%c--- Location Select Changed ---', 'color: blue; font-weight: bold;');
            this.handleLocationChange(event.currentTarget, deviceForm);
        });

        if (this.config.debug) console.log('[DeviceForm] Performing initial state sync.');
        this.handleLocationChange(locationSelect, deviceForm);
    },

    handleLocationCreated(event) {
        if (this.config.debug) {
            console.log('[DeviceForm] handleLocationCreated triggered.');
            console.table(event.detail);
        }

        const { id, name } = event.detail;
        const locationSelect = document.getElementById('id_location');

        if (locationSelect) {
            if (this.config.debug) console.log('[DeviceForm] Found location select. Updating options and disabling field.');

            // Clear existing options
            while (locationSelect.firstChild) {
                locationSelect.removeChild(locationSelect.firstChild);
            }

            // Add the new option and assume it's active
            locationSelect.dataset[`isactive-${id}`] = 'true';
            locationSelect.dataset[`locationname-${id}`] = name;

            const newOption = new Option(name, id, true, true);
            locationSelect.add(newOption, null);

            // Disable the select field to "lock in" the new location
            locationSelect.disabled = true;

            // Manually trigger the change event to update UI state
            if (this.config.debug) console.log('[DeviceForm] Dispatching change event on location select.');
            locationSelect.dispatchEvent(new Event('change'));
        } else {
            if (this.config.debug) console.error('[DeviceForm] Could not find location select to update.');
        }
    },

    handleLocationChange(select, form) {
        try {
            if (this.config.debug) console.log('[DeviceForm] handleLocationChange triggered.');

            const locationId = select.value;

            const locationIsActive = select.dataset[`isactive-${locationId}`] === 'true';
            const locationName = select.dataset[`locationname-${locationId}`];
            const locationSlug = select.dataset[`locationslug-${locationId}`];

            if (this.config.debug) {
                console.log(`[DeviceForm] Location Change Details (ID: ${locationId})`);
                console.table({
                    "Is Active": locationIsActive,
                    "Name": locationName,
                    "Slug": locationSlug
                });
            }

            const activeCheckbox = form.querySelector('.active-status-checkbox');
            const activeCheckboxLabel = form.querySelector(`label[for="${activeCheckbox.id}"]`);
            const helpTextContainer = form.querySelector('[data-help-text-container]');
            const container = form.querySelector('.is-active-container');

            if (this.config.debug && !activeCheckboxLabel) {
                console.warn(`[DeviceForm] Could not find label for checkbox #${activeCheckbox.id}`);
            }

            // --- UI Updates ---
            if (locationIsActive) {
                if (this.config.debug) console.log('[DeviceForm] UI UPDATE: Location is ACTIVE. Enabling checkbox.');
                activeCheckbox.disabled = false;
                activeCheckbox.checked = true;
                if (activeCheckboxLabel) activeCheckboxLabel.textContent = 'Active';
                container.classList.remove('opacity-50');
                helpTextContainer.classList.add('d-none');
                helpTextContainer.innerHTML = '';
            } else {
                if (this.config.debug) console.log('[DeviceForm] UI UPDATE: Location is INACTIVE. Disabling checkbox.');
                activeCheckbox.disabled = true;
                activeCheckbox.checked = false;
                if (activeCheckboxLabel) activeCheckboxLabel.textContent = 'inactive';
                container.classList.add('opacity-50');
                const reason = `<div class="form-text text-warning-emphasis"><i class="bi bi-exclamation-triangle me-2"></i>This device will be inactive because Location "${locationName}" is inactive.</div>`;
                helpTextContainer.innerHTML = reason;
                helpTextContainer.classList.remove('d-none');
            }

            // Update Breadcrumb
            const breadcrumb = document.getElementById('breadcrumb-location');
            if (breadcrumb) {
                if (this.config.debug) console.log(`[DeviceForm] Updating breadcrumb to "${locationName}"`);

                breadcrumb.textContent = locationName;

                const placeSlug = document.body.dataset.placeSlug;
                if (placeSlug && placeSlug !== 'none') {
                    breadcrumb.href = `/sensors/${placeSlug}/location/${locationSlug}/`;
                    if (this.config.debug) console.log(`[DeviceForm] New breadcrumb URL: ${breadcrumb.href}`);
                } else {
                    if (this.config.debug) console.warn('[DeviceForm] Could not find place slug on body tag.');
                }

            } else {
                if (this.config.debug) console.warn('[DeviceForm] Could not find breadcrumb element #breadcrumb-location');
            }

            if (this.config.debug) {
                console.log(`[DeviceForm] Final Checkbox State:`);
                console.table({
                    "Checked": activeCheckbox.checked,
                    "Disabled": activeCheckbox.disabled,
                    "Label": activeCheckboxLabel ? activeCheckboxLabel.textContent : 'N/A'
                });
            }
        } catch (error) {
            console.error('[DeviceForm] Error in handleLocationChange:', error);
        }
    }
};

document.addEventListener('DOMContentLoaded', () => {
    deviceFormManager.init();

    document.body.addEventListener('htmx:beforeSwap', function(evt) {
        if (deviceFormManager.config.debug) {
            console.log('[DeviceForm] htmx:beforeSwap event triggered.');
            console.log('Event detail:', evt.detail);
        }

        const triggerHeader = evt.detail.xhr.getResponseHeader('HX-Trigger');
        if (triggerHeader) {
            if (deviceFormManager.config.debug) console.log(`[DeviceForm] Found HX-Trigger: ${triggerHeader}`);
            try {
                const data = JSON.parse(triggerHeader);
                if (data.locationCreated) {
                    if (deviceFormManager.config.debug) console.log('[DeviceForm] locationCreated trigger found. Handling event.');
                    deviceFormManager.handleLocationCreated({ detail: data.locationCreated });

                    const modalElement = document.getElementById('modal-container');
                    if (modalElement) {
                        const modal = bootstrap.Modal.getInstance(modalElement);
                        if (modal) {
                            if (deviceFormManager.config.debug) console.log('[DeviceForm] Closing modal.');
                            modal.hide();
                        } else {
                            if (deviceFormManager.config.debug) console.log('[DeviceForm] Modal instance not found, cannot close.');
                        }
                    }

                    // We've handled this response, so we don't want HTMX to swap anything.
                    evt.detail.shouldSwap = false;
                }
            } catch (e) {
                console.error("Error parsing HX-Trigger header", e);
            }
        }
    });
});
