// Configuration
const deviceFormConfig = {
    debug: true
};

function initializeDeviceForm() {
    if (deviceFormConfig.debug) console.log('[Device Form] Initializing');
    
    const form = document.getElementById('device-form');
    if (!form) {
        if (deviceFormConfig.debug) console.log('[Device Form] No device form found');
        return;
    }
    
    const locationSelect = form.querySelector('#id_location');
    const activeCheckbox = form.querySelector('#id_is_active');
    const helpText = form.querySelector('.form-text');
    
    if (!locationSelect || !activeCheckbox) {
        if (deviceFormConfig.debug) console.log('[Device Form] Missing required elements');
        return;
    }

    function handleLocationChange(select) {
        const locationId = select.value;
        if (!locationId) return;

        const isLocationActive = select.getAttribute(`data-is-active-${locationId}`) === 'true';
        
        if (deviceFormConfig.debug) {
            console.log('[Device Form] Location change:', {
                locationId,
                isLocationActive
            });
        }

        // Update checkbox based on location status
        activeCheckbox.disabled = !isLocationActive;
        
        if (!isLocationActive) {
            activeCheckbox.checked = false;
            if (helpText) {
                helpText.textContent = "Device cannot be active when its location is inactive";
                helpText.classList.remove('d-none');
            }
        } else {
            activeCheckbox.checked = true;
            if (helpText) {
                helpText.classList.add('d-none');
            }
        }

        // Update label text
        const label = activeCheckbox.nextElementSibling;
        if (label) {
            label.textContent = activeCheckbox.checked ? 'Active' : 'inactive';
        }
    }
    
    // Set initial state and add listener
    handleLocationChange(locationSelect);
    locationSelect.addEventListener('change', function() {
        handleLocationChange(this);
    });
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', initializeDeviceForm); 