const scriptConfig = {
    debug: false
};

document.body.addEventListener('htmx:afterSwap', function (evt) {
    const targetId = evt.detail.target.id;
    if (scriptConfig.debug) {
        console.log(`[HTMX-Handler] 'htmx:afterSwap' event processed for target #${targetId}.`);
    }

    const triggerHeader = evt.detail.xhr.getResponseHeader('HX-Trigger');
    if (!triggerHeader) {
        return;
    }

    try {
        const triggers = JSON.parse(triggerHeader);

        // Handle 'closeModal' trigger
        if (triggers.closeModal) {
            const modalSelector = triggers.closeModal;
            if (scriptConfig.debug) {
                console.log(`[HTMX-Handler] Received 'closeModal' trigger for selector: ${modalSelector}`);
            }
            const modalElement = document.querySelector(modalSelector);
            if (modalElement) {
                const modal = bootstrap.Modal.getInstance(modalElement);
                if (modal) {
                    modal.hide();
                }
            }
        }

        // Handle 'showToast' trigger
        if (triggers.showToast) {
            if (window.toastSystem && typeof window.toastSystem.show === 'function') {
                window.toastSystem.show(triggers.showToast.message, triggers.showToast.type);
            }
        }

        // Handle simple string-based triggers for other custom events
        Object.keys(triggers).forEach(key => {
            if (triggers[key] === true) {
                htmx.trigger('body', key, {});
            }
        });

    } catch (e) {
        console.error("[HTMX-Handler] Error parsing HX-Trigger header:", e);
    }
});
