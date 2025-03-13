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
        checkboxes.forEach(checkbox => {
            console.log('[Active Status Checkbox] Checkbox details:', {
                html: checkbox.outerHTML,
                id: checkbox.id,
                dataset: checkbox.dataset,
                parent: checkbox.parentElement?.outerHTML
            });
        });
    }

    checkboxes.forEach(checkbox => {
        // Get the container using closest
        const container = checkbox.closest('.form-check');
        if (!container) {
            if (activeStatusConfig.debug) console.log('[Active Status Checkbox] No container found for checkbox:', checkbox);
            return;
        }

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

// Initialize immediately since we're being loaded after DOM is ready

initializeActiveStatusCheckbox();

// Add a delayed check to see if any elements were added after initial load
setTimeout(() => {
    if (activeStatusConfig.debug) console.log('[Active Status Checkbox] Delayed DOM check:', {
        checkboxes: document.querySelectorAll('input[data-active-checkbox]'),
        helpText: document.querySelectorAll('[data-active-checkbox-help]'),
        formText: document.querySelectorAll('.form-text')
    });
}, 1000);