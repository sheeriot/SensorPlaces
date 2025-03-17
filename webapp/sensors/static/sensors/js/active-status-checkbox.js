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
        if (activeStatusConfig.debug) {
            console.log('[Active Status] Location status changed:', {
                isLocationActive: e.detail.isLocationActive,
                checkboxState: e.detail.checkboxState ? 'Active' : 'Inactive'
            });
        }
        
        // Store inactive reason if provided
        if (e.detail.inactiveReason) {
            checkboxContainer.dataset.inactiveReason = e.detail.inactiveReason;
        } else {
            delete checkboxContainer.dataset.inactiveReason;
        }
        
        // Update the UI to match the checkbox state
        updateCheckboxUI(checkboxContainer, checkbox);
    });

    // Handle checkbox change by another script or by user
    checkbox.addEventListener('change', function() {
        updateCheckboxUI(checkboxContainer, checkbox);
        
        // Log change event if debug is enabled
        if (activeStatusConfig.debug) {
            console.log('[Active Status] Checkbox changed:', {
                'ID': checkbox.id || '(no id)',
                'New State': checkbox.checked ? 'Active' : 'Inactive',
                'Disabled': checkbox.disabled ? 'Yes' : 'No'
            });
        }
    });
}

function updateCheckboxUI(container, checkbox) {
    // Update label text
    const label = container.querySelector('label');
    if (label) {
        const newLabelText = checkbox.checked ? 
            checkbox.dataset.activeLabel || 'Active' : 
            checkbox.dataset.inactiveLabel || 'inactive';
            
        label.textContent = newLabelText;
    }

    // Update help text visibility and content
    const helpText = container.querySelector('[data-help-text-container]');
    if (helpText) {
        if (checkbox.checked) {
            // Hide help text when active
            helpText.classList.add('d-none');
        } else {
            // Show help text when inactive
            helpText.classList.remove('d-none');
            
            // Update help text content if we have a reason
            const helpTextContent = helpText.querySelector('.form-text');
            if (helpTextContent && container.dataset.inactiveReason) {
                helpTextContent.textContent = container.dataset.inactiveReason;
            }
        }
    }

    // Update visual state
    container.classList.toggle('opacity-50', checkbox.disabled);
    container.classList.toggle('text-muted', checkbox.disabled);
    
    if (activeStatusConfig.debug) {
        console.log('[Active Status] UI updated:', {
            'State': checkbox.checked ? 'Active' : 'Inactive',
            'Disabled': checkbox.disabled ? 'Yes' : 'No',
            'Label': label ? label.textContent : '(no label)',
            'Help Text': helpText ? (checkbox.checked ? 'Hidden' : 'Visible') : '(no help text)'
        });
    }
}

// Initialize only once when DOM is ready
document.addEventListener('DOMContentLoaded', initializeActiveStatusCheckbox);
