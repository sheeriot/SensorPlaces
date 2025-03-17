// Configuration
const activeStatusConfig = {
    debug: true  // Set to false to disable verbose logging
};

function initializeActiveStatusCheckbox() {
    const forms = document.querySelectorAll('.model-form');
    
    // Create a table for form data if debug is enabled
    if (activeStatusConfig.debug) {
        console.log('[Active Status] Found', forms.length, 'forms');
        console.table(Array.from(forms).map(form => ({
            'Form ID': form.id || '(no id)',
            'Form Classes': form.className
        })));
    }
    
    const checkboxData = [];

    forms.forEach(form => {
        // Try multiple strategies to find the active checkbox
        let activeCheckboxContainer = form.querySelector('.active-checkbox');
        
        if (!activeCheckboxContainer) {
            // Try finding by input name
            activeCheckboxContainer = form.querySelector('input[name="is_active"]');
        }
        
        if (!activeCheckboxContainer) {
            // Try finding by ID pattern
            activeCheckboxContainer = form.querySelector('input[id*="active-checkbox"]');
        }
        
        if (!activeCheckboxContainer) {
            if (activeStatusConfig.debug) {
                console.log('[Active Status] No checkbox found on form', form.id);
            }
            return;
        }

        // Find form check element
        const formCheck = activeCheckboxContainer.closest('.form-check');
        if (!formCheck) {
            if (activeStatusConfig.debug) {
                console.log('[Active Status] No form-check container found for checkbox');
            }
            return;
        }

        // Add to checkbox data array for table display
        if (activeStatusConfig.debug) {
            checkboxData.push({
                'Form': form.id || '(no id)',
                'Checkbox ID': activeCheckboxContainer.id || '(no id)',
                'State': activeCheckboxContainer.checked ? 'Active' : 'Inactive',
                'Disabled': activeCheckboxContainer.disabled ? 'Yes' : 'No'
            });
        }

        // Set up event listeners
        watchCheckbox(activeCheckboxContainer);
    });
    
    // Display checkbox data table if debug is enabled
    if (activeStatusConfig.debug && checkboxData.length > 0) {
        console.log('[Active Status] Checkboxes found:');
        console.table(checkboxData);
    }
}

function watchCheckbox(checkbox) {
    // Find the container for this checkbox
    const checkboxContainer = checkbox.closest('.form-check');
    if (!checkboxContainer) return;

    // Listen for location status changes
    checkboxContainer.addEventListener('locationStatusChanged', function(e) {
        const { isLocationActive, checkboxState, checkboxDisabled, inactiveReason } = e.detail;
        
        console.log("[Active Status] Location status changed:", {
            isLocationActive: isLocationActive,
            checkboxState: checkboxState,
            disabled: checkboxDisabled,
            hasInactiveReason: !!inactiveReason
        });

        // Find the help text container within the same form-check div
        const helpTextContainer = checkboxContainer.querySelector('[data-help-text-container]');
        
        if (helpTextContainer) {
            if (inactiveReason) {
                // Show both the location reason and the impact on sensors if device was originally active
                const wasOriginallyActive = checkbox.getAttribute('data-isactive-original') === 'true';
                const sensorImpactText = wasOriginallyActive ? 
                    `<div class="mt-2">Existing sensors will stop collecting data.</div>` : '';
                helpTextContainer.innerHTML = `${inactiveReason}${sensorImpactText}`;
                helpTextContainer.classList.remove('d-none');
            } else {
                helpTextContainer.classList.add('d-none');
            }
        }
        
        // Update the UI to match the checkbox state
        updateCheckboxUI(checkboxContainer, checkbox);
    });

    // Handle checkbox change by another script or by user
    checkbox.addEventListener('change', function() {
        const helpTextContainer = checkboxContainer.querySelector('[data-help-text-container]');
        if (helpTextContainer) {
            const wasOriginallyActive = checkbox.getAttribute('data-isactive-original') === 'true';
            if (!checkbox.checked && wasOriginallyActive) {
                helpTextContainer.innerHTML = `<i class="bi bi-exclamation-triangle me-2"></i>
                    Existing sensors will stop collecting data.`;
                helpTextContainer.classList.remove('d-none');
            } else {
                helpTextContainer.classList.add('d-none');
            }
        }
        
        updateCheckboxUI(checkboxContainer, checkbox);
        
        // Log change event if debug is enabled
        if (activeStatusConfig.debug) {
            console.log('[Active Status] Checkbox changed:', {
                'ID': checkbox.id || '(no id)',
                'New State': checkbox.checked ? 'Active' : 'Inactive',
                'Disabled': checkbox.disabled ? 'Yes' : 'No',
                'Was Originally Active': checkbox.getAttribute('data-isactive-original') === 'true'
            });
        }
    });
}

function updateCheckboxUI(container, checkbox) {
    if (!checkbox || !container) return;

    // Update label text
    const label = container.querySelector('label');
    if (label) {
        const newLabelText = checkbox.checked ? 
            checkbox.dataset.activeLabel || 'Active' : 
            checkbox.dataset.inactiveLabel || 'inactive';
        label.textContent = newLabelText;
    }

    // Update container classes
    container.classList.toggle('opacity-50', checkbox.disabled);
    container.classList.toggle('text-muted', checkbox.disabled);
    
    if (activeStatusConfig.debug) {
        const helpTextContainer = container.querySelector('[data-help-text-container]');
        console.log('[Active Status] UI updated:', {
            'State': checkbox.checked ? 'Active' : 'Inactive',
            'Disabled': checkbox.disabled ? 'Yes' : 'No',
            'Label': label ? label.textContent : '(no label)',
            'Help Text': helpTextContainer ? (helpTextContainer.classList.contains('d-none') ? 'Hidden' : 'Visible') : '(no help text)',
            'Was Originally Active': checkbox.getAttribute('data-isactive-original') === 'true'
        });
    }
}

// Initialize only once when DOM is ready
document.addEventListener('DOMContentLoaded', initializeActiveStatusCheckbox);
