// Configuration
const activeStatusConfig = {
    debug: false
};

// Active Status Checkbox functionality
function initializeActiveStatusCheckbox() {
    if (activeStatusConfig.debug) console.log('[Active Status Checkbox] Initializing');
    
    // Find all checkboxes with our data attribute
    const checkboxes = document.querySelectorAll('input[data-active-checkbox]');
    if (activeStatusConfig.debug) {
        console.log('[Active Status Checkbox] Found checkboxes:', checkboxes);
    }

    // Get all unique parent forms to observe
    const formsToWatch = new Set();
    checkboxes.forEach(checkbox => {
        const form = checkbox.closest('form');
        if (form) formsToWatch.add(form);
    });

    // Disconnect any existing observer
    if (window.activeStatusObserver) {
        window.activeStatusObserver.disconnect();
    }

    // Create new observer with specific targets
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            // Only process if new nodes were added
            if (!mutation.addedNodes.length) return;

            // Check if any added nodes contain our checkbox
            const hasNewCheckbox = Array.from(mutation.addedNodes).some(node => {
                if (node.nodeType !== Node.ELEMENT_NODE) return false;
                return node.matches('input[data-active-checkbox]') || 
                       node.querySelector('input[data-active-checkbox]');
            });

            if (hasNewCheckbox) {
                if (activeStatusConfig.debug) console.log('[Active Status Checkbox] New checkbox detected, initializing');
                initializeCheckbox(mutation.target);
            }
        });
    });

    // Store observer reference
    window.activeStatusObserver = observer;

    // Watch only the forms containing our checkboxes
    formsToWatch.forEach(form => {
        observer.observe(form, {
            childList: true,
            subtree: true,
            attributes: false,
            characterData: false
        });
        if (activeStatusConfig.debug) console.log('[Active Status Checkbox] Observing form:', form.id || 'unnamed form');
    });

    // Initialize each checkbox
    checkboxes.forEach(initializeCheckbox);
    
    if (activeStatusConfig.debug) console.log('[Active Status Checkbox] Initialization complete');
    return true;
}

// Separate checkbox initialization logic
function initializeCheckbox(checkbox) {
    // Skip if already initialized
    if (checkbox.dataset.initialized) return;
    checkbox.dataset.initialized = 'true';

    // Get the container using closest
    const container = checkbox.closest('.form-check');
    if (!container) {
        if (activeStatusConfig.debug) console.log('[Active Status Checkbox] No container found for checkbox:', checkbox);
        return;
    }

    // Listen for location status changes
    container.addEventListener('locationStatusChanged', function(e) {
        if (activeStatusConfig.debug) {
            console.log('[Active Status Checkbox] Location status changed event:', {
                detail: e.detail,
                checkbox: checkbox.checked,
                disabled: checkbox.disabled
            });
        }
        
        // Update checkbox state based on force-inactive
        const forceInactive = container.dataset.forceInactive === 'true';
        checkbox.disabled = forceInactive;
        
        if (forceInactive) {
            checkbox.checked = false;
            // Update help text if provided
            const helpText = container.querySelector('[data-active-checkbox-help]');
            if (helpText && container.dataset.inactiveReason) {
                helpText.textContent = container.dataset.inactiveReason;
                helpText.classList.remove('d-none');
            }
        }

        // Update label text
        const label = container.querySelector('label');
        if (label) {
            label.textContent = checkbox.checked ? 'Active' : 'inactive';
        }

        if (activeStatusConfig.debug) {
            console.log('[Active Status Checkbox] Updated state:', {
                checked: checkbox.checked,
                disabled: checkbox.disabled,
                label: label?.textContent
            });
        }
    });

    if (activeStatusConfig.debug) {
        console.log('[Active Status Checkbox] Container details:', {
            html: container.outerHTML,
            classes: container.className,
            children: Array.from(container.children).map(child => child.outerHTML)
        });
    }

    // Get help text element - look in the entire form
    const form = checkbox.closest('form');
    if (activeStatusConfig.debug) {
        console.log('[Active Status Checkbox] Form details:', {
            id: form?.id,
            html: form?.outerHTML,
            helpTextElements: Array.from(form?.querySelectorAll('[data-active-checkbox-help]') || []).map(el => ({
                html: el.outerHTML,
                classes: el.className,
                display: window.getComputedStyle(el).display
            })),
            allFormText: Array.from(form?.querySelectorAll('.form-text') || []).map(el => ({
                html: el.outerHTML,
                classes: el.className,
                display: window.getComputedStyle(el).display
            }))
        });
    }

    const helpText = form?.querySelector('[data-active-checkbox-help]');
    
    if (activeStatusConfig.debug) {
        console.log('[Active Status Checkbox] Help text details:', {
            found: !!helpText,
            element: helpText,
            html: helpText?.outerHTML,
            classes: helpText?.className,
            display: helpText ? window.getComputedStyle(helpText).display : null,
            parent: helpText?.parentElement?.outerHTML
        });
    }

    // Set initial state
    if (activeStatusConfig.debug) console.log('[Active Status Checkbox] Initial state:', checkbox.checked);
    if (helpText) {
        if (checkbox.checked) {
            if (activeStatusConfig.debug) console.log('[Active Status Checkbox] Hiding help text initially');
            helpText.classList.add('d-none');
        } else {
            if (activeStatusConfig.debug) console.log('[Active Status Checkbox] Showing help text initially');
            helpText.classList.remove('d-none');
        }
    } else {
        console.log('[Active Status Checkbox] Warning: No help text found for checkbox:', checkbox.id);
    }

    // Handle checkbox change
    checkbox.addEventListener('change', function(e) {
        if (activeStatusConfig.debug) {
            console.log('[Active Status Checkbox] Change event:', {
                checked: this.checked,
                helpText: helpText?.outerHTML,
                helpTextDisplay: helpText ? window.getComputedStyle(helpText).display : null
            });
        }
        
        // Show/hide help text if it exists
        if (helpText) {
            if (!this.checked) {
                if (activeStatusConfig.debug) console.log('[Active Status Checkbox] Displaying help text');
                helpText.classList.remove('d-none');
            } else {
                if (activeStatusConfig.debug) console.log('[Active Status Checkbox] Hiding help text');
                helpText.classList.add('d-none');
            }
        }

        // Update label text
        const label = container.querySelector('label');
        if (label) {
            label.textContent = this.checked ? 'Active' : 'inactive';
            if (activeStatusConfig.debug) console.log('[Active Status Checkbox] Updated label to:', label.textContent);
        }
    });
}

// Initialize once when DOM is ready
document.addEventListener('DOMContentLoaded', initializeActiveStatusCheckbox);

// Optional: Keep the delayed check but only run if not already initialized
setTimeout(() => {
    const uninitializedCheckboxes = document.querySelectorAll('input[data-active-checkbox]:not([data-initialized])');
    if (uninitializedCheckboxes.length > 0) {
        if (activeStatusConfig.debug) console.log('[Active Status Checkbox] Found uninitialized checkboxes in delayed check');
        initializeActiveStatusCheckbox();
    }
}, 1000);