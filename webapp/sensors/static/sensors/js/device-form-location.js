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

        // Get the checkbox container
        const container = activeCheckbox.closest('.form-check');
        if (!container) return;

        // Update data attributes on container
        container.dataset.forceInactive = (!isLocationActive).toString();
        container.dataset.inactiveReason = isLocationActive ? '' : 
            `Device cannot be active when its location is inactive`;

        // Dispatch custom event for active-status-checkbox.js to handle
        const event = new CustomEvent('locationStatusChanged', {
            detail: {
                isLocationActive,
                originalState: activeCheckbox.dataset.originalState === 'true'
            }
        });
        container.dispatchEvent(event);
    }
    
    // Store original state when form initializes
    activeCheckbox.dataset.originalState = activeCheckbox.checked;
    
    // Set initial state and add listener
    handleLocationChange(locationSelect);
    locationSelect.addEventListener('change', function() {
        handleLocationChange(this);
    });
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', initializeDeviceForm); 