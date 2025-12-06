document.addEventListener('DOMContentLoaded', function() {
    const scriptConfig = {
        debug: true // Set to false in production
    };

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
