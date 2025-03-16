// Configuration
const activeStatusConfig = {
    debug: true
};

function initializeActiveStatusCheckbox() {
    const forms = document.querySelectorAll('.model-form');
    console.log('[Active Status Checkbox Forms] Found', forms.length, 'forms');
    const formData = [];

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
        if (activeStatusConfig.debug) {
            console.log('[Active Status Checkbox] formCheck:', formCheckData);
        }

        // Set up event listeners
        watchCheckbox(formCheck);
    });
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
        label.textContent = checkbox.checked ? 
            checkbox.dataset.activeLabel : 
            checkbox.dataset.inactiveLabel;
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
    }

    // Update visual state
    container.classList.toggle('opacity-50', checkbox.disabled);
    container.classList.toggle('text-muted', checkbox.disabled);
}

// Initialize only once when DOM is ready
document.addEventListener('DOMContentLoaded', initializeActiveStatusCheckbox);
