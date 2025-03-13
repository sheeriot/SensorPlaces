// Configuration
const activeStatusConfig = {
    debug: true
};

// Active Status Checkbox functionality
function initializeActiveStatusCheckbox() {
    if (activeStatusConfig.debug) console.log('[Active Status Checkbox] Initializing');
    
    // Find all checkboxes with our data attribute
    const checkboxes = document.querySelectorAll('input[data-active-checkbox]');
    if (activeStatusConfig.debug) {
        console.log('[Active Status Checkbox] Found checkboxes:', checkboxes);
    }

    checkboxes.forEach(checkbox => {
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
    });
    
    if (activeStatusConfig.debug) console.log('[Active Status Checkbox] Initialization complete');
    return true;
}

window.activeStatusCheckbox = {
    config: { debug: true },
    initialize: initializeActiveStatusCheckbox
};

// Re-initialize on any dynamic content changes
const observer = new MutationObserver(function(mutations) {
    mutations.forEach(function(mutation) {
        if (mutation.addedNodes.length) {
            if (activeStatusConfig.debug) console.log('[Active Status Checkbox] DOM changed, re-initializing');
            initializeActiveStatusCheckbox();
        }
    });
});

observer.observe(document.body, {
    childList: true,
    subtree: true
});

// Add a delayed check
setTimeout(() => {
    if (activeStatusConfig.debug) {
        console.log('[Active Status Checkbox] Delayed DOM check:', {
            checkboxes: document.querySelectorAll('input[data-active-checkbox]'),
            helpText: document.querySelectorAll('[data-active-checkbox-help]'),
            formText: document.querySelectorAll('.form-text')
        });
    }
    initializeActiveStatusCheckbox();  // One final initialization attempt
}, 1000);