document.addEventListener('DOMContentLoaded', function() {
    const scriptConfig = {
        debug: true // Set to false in production
    };

    // Centralized function to format all timestamps in a given container
    function formatAllTimestamps(container) {
        if (scriptConfig.debug) console.log('[formatAllTimestamps] Searching for timestamps to format in:', container);

        // Find elements that need full timestamp formatting
        const fullTimestampElements = container.querySelectorAll('.format-timestamp-full');
        fullTimestampElements.forEach(el => {
            const timestamp = el.getAttribute('data-timestamp');
            if (timestamp) {
                if (scriptConfig.debug) console.log(`[formatAllTimestamps] Formatting full timestamp for: ${timestamp}`);
                el.textContent = window.utils.formatTimestamp(timestamp);
            }
        });
    }

    // Run on initial page load
    formatAllTimestamps(document.body);

    // Run after any HTMX content is swapped into the page
    document.body.addEventListener('htmx:afterSwap', function(evt) {
        if (scriptConfig.debug) console.log('[htmx:afterSwap] HTMX content swapped, formatting new timestamps.');
        // The new content is in evt.detail.target
        formatAllTimestamps(evt.detail.target);
    });

    document.body.addEventListener('htmx:afterRequest', function(evt) {
        const triggerHeader = evt.detail.xhr.getResponseHeader('HX-Trigger');
        if (triggerHeader) {
            try {
                const triggers = JSON.parse(triggerHeader);
                if (scriptConfig.debug) console.log("[Global HX-Trigger] Parsed triggers:", triggers);

                if (triggers.closeModal) {
                    const modalElement = document.querySelector(triggers.closeModal);
                    if (modalElement) {
                        const modal = bootstrap.Modal.getInstance(modalElement);
                        if (modal) {
                            modal.hide();
                        }
                    }
                }

                if (triggers.showToast) {
                    if (window.toastSystem && typeof window.toastSystem.show === 'function') {
                        window.toastSystem.show(triggers.showToast.message, triggers.showToast.type);
                    } else {
                        console.error('[Global HX-Trigger] window.toastSystem.show is not available.');
                    }
                }

                // Handle simple string-based triggers for backward compatibility or other uses
                Object.keys(triggers).forEach(key => {
                    if (triggers[key] === true) {
                        htmx.trigger('body', key, {});
                    }
                });

            } catch (e) {
                console.error("[Global HX-Trigger] Error parsing HX-Trigger header:", e);
            }
        }
    });
});
