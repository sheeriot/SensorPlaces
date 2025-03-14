// Configuration
const activeStatusConfig = {
    debug: true
};

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
        label.textContent = checkbox.checked ? 'Active' : 'inactive';
    }

    // Update help text visibility
    const helpText = container.querySelector('[data-active-checkbox-help]');
    if (helpText) {
        if (!checkbox.checked || checkbox.disabled) {
            helpText.classList.remove('d-none');
        } else {
            helpText.classList.add('d-none');
        }
    }

    // Update visual state
    container.classList.toggle('opacity-50', checkbox.disabled);
    container.classList.toggle('text-muted', checkbox.disabled);
}

function initializeActiveStatusCheckbox() {
    const forms = document.querySelectorAll('form');
    const formData = [];

    forms.forEach(form => {
        const activeCheckbox = form.querySelector('input#id_is_active[data-active-checkbox]');
        if (!activeCheckbox) return;  // Skip forms without our target checkbox

        const container = activeCheckbox.closest('.form-check');
        if (!container) return;

        // Find closest card if it exists
        const card = form.closest('.card');
        const helpText = container.querySelector('[data-active-checkbox-help]');

        // Collect data for reporting
        formData.push({
            'Form ID': form.id || '(no id)',
            'Card ID': card ? card.id || '(no id)' : 'Not in card',
            'Checkbox ID': activeCheckbox.id,
            'Is Disabled': activeCheckbox.disabled,
            'Help Text': helpText ? helpText.textContent.trim() : 'No help text',
            'Current State': activeCheckbox.checked ? 'Active' : 'Inactive',
            'Container Classes': container.className
        });

        // Set up event listeners
        initializeCheckbox(activeCheckbox);
    });

    // Report findings
    if (formData.length > 0) {
        console.group('Active Status Checkbox Report');
        console.log(`Found ${formData.length} form(s) with active status checkboxes`);
        console.table(formData);
        console.groupEnd();
    } else {
        console.log('No forms found with active status checkboxes');
    }
}

function initializeCheckbox(checkbox) {
    const container = checkbox.closest('.form-check');
    if (!container) return;

    // Set initial UI state based on Django-provided state
    updateCheckboxUI(container, checkbox);

    // Listen for location status changes
    container.addEventListener('locationStatusChanged', function(e) {
        const forceInactive = container.dataset.forceInactive === 'true';
        checkbox.disabled = forceInactive;
        if (forceInactive) {
            checkbox.checked = false;
        }
        updateCheckboxUI(container, checkbox);
    });

    // Handle checkbox change by user
    checkbox.addEventListener('change', function() {
        updateCheckboxUI(container, checkbox);
    });
}

// Initialize only once when DOM is ready
document.addEventListener('DOMContentLoaded', initializeActiveStatusCheckbox);

// Optional: Check for dynamically added checkboxes
const observer = new MutationObserver(function(mutations) {
    mutations.forEach(function(mutation) {
        mutation.addedNodes.forEach(function(node) {
            if (node.nodeType === Node.ELEMENT_NODE) {
                const newCheckboxes = node.querySelectorAll('input[data-active-checkbox]:not([data-initialized])');
                newCheckboxes.forEach(initializeCheckbox);
            }
        });
    });
});

document.addEventListener('DOMContentLoaded', function() {
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
});