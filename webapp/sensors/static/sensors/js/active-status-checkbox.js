// Configuration
const activeStatusConfig = {
    debug: true
};

function initializeActiveStatusCheckbox() {
    const forms = document.querySelectorAll('.model-form');
    console.log('[Active Status Checkbox Forms] Found', forms.length, 'forms');
    
    // Create a table for form data if debug is enabled
    if (activeStatusConfig.debug) {
        console.log('%c[Active Status] Forms Found', 'background: #f0f0f0; color: #333; padding: 3px 5px; border-radius: 3px; font-weight: bold;');
        console.table(Array.from(forms).map(form => ({
            'Form ID': form.id || '(no id)',
            'Form Classes': form.className,
            'Form Action': form.action || '(no action)'
        })));
    }
    
    const formData = [];
    const checkboxData = [];

    forms.forEach(form => {
        // Find active checkbox container
        const activeCheckboxContainer = form.querySelector('.active-checkbox');
        if (!activeCheckboxContainer) {
            console.log(
                '[Active Status Checkbox] No active checkbox container found on form',
                form.id
            );
            return;
        }

        // Find form check element
        const formCheck = activeCheckboxContainer.closest('.active-checkbox');
        if (!formCheck) {
            if (activeStatusConfig.debug) {
                console.log(
                    '[Active Status Checkbox] EXIT - No form-check found on form',
                    form.id
                );
            }
            return;
        } else {
            if (activeStatusConfig.debug) {
                console.log('[Active Status Checkbox] formCheck:', formCheck);
                console.log('[Active Status Checkbox] formCheck outerHTML:', formCheck.outerHTML);
            }
        }

        // Find closest card if it exists
        const card = form.closest('.card');

        // Work with attributes
        const dataActiveHelpText = formCheck.querySelector('[data-active-checkbox-help]');
        if (activeStatusConfig.debug) {
            console.log('[Active Status Checkbox] Data Active Help Text:', dataActiveHelpText);
            console.log('[Active Status Checkbox] Dataset:', formCheck.dataset);
        }

        // Collect data for reporting
        const formCheckData = {
            'Form ID': form.id || '(no id)',
            'Card ID': card ? card.id || '(no id)' : 'Not in card',
            'Checkbox ID': formCheck.id,
            'Is Disabled': formCheck.disabled,
            'Current State': formCheck.checked ? 'Active' : 'inactive',
            'Container Classes': formCheck.className
        };
        
        // Add to checkbox data array for table display
        checkboxData.push({
            'Form ID': form.id || '(no id)',
            'Checkbox ID': formCheck.id || '(no id)',
            'Current State': formCheck.checked ? 'Active' : 'inactive',
            'Expected Label': formCheck.checked ? 
                (formCheck.dataset.activeLabel || 'Active') : 
                (formCheck.dataset.inactiveLabel || 'inactive'),
            'Actual Label': form.querySelector('label[for="' + formCheck.id + '"]')?.textContent.trim() || '(no label)',
            'Is Correct': form.querySelector('label[for="' + formCheck.id + '"]')?.textContent.trim() === 
                (formCheck.checked ? 
                    (formCheck.dataset.activeLabel || 'Active') : 
                    (formCheck.dataset.inactiveLabel || 'inactive')) ? 'Yes' : 'No',
            'Is Disabled': formCheck.disabled ? 'Yes' : 'No'
        });
        
        if (activeStatusConfig.debug) {
            console.log('[Active Status Checkbox] formCheck:', formCheckData);
        }

        // Set up event listeners
        watchCheckbox(formCheck);
    });
    
    // Display checkbox data table if debug is enabled
    if (activeStatusConfig.debug && checkboxData.length > 0) {
        console.log('%c[Active Status] Checkboxes Found', 'background: #e6f7ff; color: #0066cc; padding: 3px 5px; border-radius: 3px; font-weight: bold;');
        console.table(checkboxData);
    }
}

function watchCheckbox(checkbox) {
    const checkboxContainer = checkbox.closest('.form-check')
    if (checkboxContainer) {
        if (activeStatusConfig.debug) console.log('[Active Status Checkbox] Watching Container:', checkboxContainer)
    } else {
        if (activeStatusConfig.debug) console.log('[Active Status Checkbox] No checkbox to watch')
        return
    }

    // Do NOT set initial UI state based on Django-provided template. Do check for bad settings.
    // updateCheckboxUI(checkboxContainer, checkbox);

    // Listen for location status changes
    // checkboxContainer.addEventListener('locationStatusChanged', function(e) {
    //     const forceInactive = checkboxContainer.dataset.forceInactive === 'true';
    //     checkbox.disabled = forceInactive;
    //     if (forceInactive) {
    //         checkbox.checked = false;
    //     }
    //     updateCheckboxUI(container, checkbox);
    // });

    // Handle checkbox change by another script or by user
    checkbox.addEventListener('change', function() {
        updateCheckboxUI(checkboxContainer, checkbox);
        
        // Log change event if debug is enabled
        if (activeStatusConfig.debug) {
            console.log('%c[Active Status] Checkbox Changed', 'background: #e8f5e9; color: #2e7d32; padding: 3px 5px; border-radius: 3px;');
            console.table({
                'Checkbox ID': checkbox.id || '(no id)',
                'New State': checkbox.checked ? 'Active' : 'inactive',
                'Expected Label': checkbox.checked ? 
                    (checkbox.dataset.activeLabel || 'Active') : 
                    (checkbox.dataset.inactiveLabel || 'inactive'),
                'Is Disabled': checkbox.disabled ? 'Yes' : 'No'
            });
        }
    });
}

function updateCheckboxUI(container, checkbox) {
    if (activeStatusConfig.debug) {
        console.log('[Active Status Checkbox] Updating UI:', {
            checked: checkbox.checked,
            disabled: checkbox.disabled,
            container: container
        });
    }

    // Update label text
    const label = container.querySelector('label');
    if (label) {
        const newLabelText = checkbox.checked ? 
            checkbox.dataset.activeLabel || 'Active' : 
            checkbox.dataset.inactiveLabel || 'inactive';
            
        label.textContent = newLabelText;
        
        if (activeStatusConfig.debug) {
            console.log('[Active Status Checkbox] Label updated:', {
                'Checkbox ID': checkbox.id || '(no id)',
                'Old Text': label.textContent,
                'New Text': newLabelText,
                'Success': label.textContent === newLabelText ? 'Yes' : 'No'
            });
        }
    }

    // Update help text visibility
    const helpText = container.querySelector('[data-help-text-container]');
    if (helpText) {
        if (checkbox.checked) {
            // Hide help text when active
            helpText.classList.add('d-none');
        } else {
            // Show help text when inactive
            helpText.classList.remove('d-none');
        }
        
        if (activeStatusConfig.debug) {
            console.log('[Active Status Checkbox] Help text visibility updated:', {
                'Checkbox ID': checkbox.id || '(no id)',
                'Help Text Visible': !checkbox.checked ? 'Yes' : 'No'
            });
        }
    }

    // Update visual state
    container.classList.toggle('opacity-50', checkbox.disabled);
    container.classList.toggle('text-muted', checkbox.disabled);
    
    if (activeStatusConfig.debug) {
        console.log('[Active Status Checkbox] Container styles updated:', {
            'Checkbox ID': checkbox.id || '(no id)',
            'Opacity Applied': checkbox.disabled ? 'Yes' : 'No',
            'Text Muted Applied': checkbox.disabled ? 'Yes' : 'No'
        });
    }
}

// Initialize only once when DOM is ready
document.addEventListener('DOMContentLoaded', initializeActiveStatusCheckbox);
