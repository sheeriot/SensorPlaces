// Configuration
const deviceFormConfig = {
    debug: true  // Set to false to disable verbose logging
};

function initializeDeviceForm() {
    if (deviceFormConfig.debug) console.log('[Device Form] Initializing');
    
    const form = document.getElementById('device-form');
    if (!form) {
        console.log('[Device Form] No device form found');
        return;
    }
    
    console.log('[Device Form] Found form:', form.id);
    
    // Try multiple selector strategies to find the location select
    let locationSelect = form.querySelector('#id_location');
    if (!locationSelect) {
        locationSelect = form.querySelector('#div_id_location select');
    }
    if (!locationSelect) {
        locationSelect = form.querySelector('select[name="location"]');
    }
    
    // Try multiple selector strategies to find the active checkbox
    let activeCheckbox = form.querySelector('input[name="is_active"]');
    if (!activeCheckbox) {
        activeCheckbox = form.querySelector('#div_id_is_active input[type="checkbox"]');
    }
    
    if (!locationSelect || !activeCheckbox) {
        console.log('[Device Form] Missing required elements:', {
            locationSelect: locationSelect ? 'Found' : 'Missing',
            activeCheckbox: activeCheckbox ? 'Found' : 'Missing'
        });
        return;
    }
    
    console.log('[Device Form] Ready:', {
        locationSelect: locationSelect.id || 'unnamed',
        activeCheckbox: activeCheckbox.id || 'unnamed',
        initialState: activeCheckbox.checked ? 'Active' : 'Inactive'
    });

    function handleLocationChange(select) {
        const locationId = select.value;
        if (!locationId) return;

        const isLocationActive = select.getAttribute(`data-is-active-${locationId}`) === 'true';
        const locationName = select.options[select.selectedIndex].text;
        
        if (deviceFormConfig.debug) {
            console.log('[Device Form] Location selected:', {
                id: locationId,
                name: locationName,
                isActive: isLocationActive
            });
        }
        
        // Get the checkbox container
        const container = activeCheckbox.closest('.form-check');
        if (!container) return;

        // Store location active state as data attribute
        container.dataset.locationActive = isLocationActive.toString();
        
        // Only modify the checkbox state (checked/unchecked and enabled/disabled)
        if (!isLocationActive) {
            // If location is inactive, force checkbox to be unchecked and disabled
            activeCheckbox.checked = false;
            activeCheckbox.disabled = true;
            
            if (deviceFormConfig.debug) {
                console.log('[Device Form] Location inactive - disabling checkbox');
            }
        } else {
            // If location is active, enable the checkbox and restore original state
            activeCheckbox.disabled = false;
            
            // Only restore the original state if we're coming from an inactive location
            if (container.dataset.previousLocationActive === 'false') {
                // Use the original state we saved when form initialized
                activeCheckbox.checked = activeCheckbox.dataset.originalState === 'true';
                
                if (deviceFormConfig.debug) {
                    console.log('[Device Form] Restoring checkbox state:', {
                        location: locationName,
                        originalState: activeCheckbox.dataset.originalState === 'true',
                        checked: activeCheckbox.checked
                    });
                }
            }
        }
        
        // Store current location state for next change
        container.dataset.previousLocationActive = isLocationActive.toString();

        // Dispatch custom event for active-status-checkbox.js to handle UI updates
        const event = new CustomEvent('locationStatusChanged', {
            detail: {
                isLocationActive,
                checkboxState: activeCheckbox.checked,
                checkboxDisabled: activeCheckbox.disabled,
                inactiveReason: isLocationActive ? '' : 'Device cannot be active when its location is inactive'
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