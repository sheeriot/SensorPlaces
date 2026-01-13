// Modal content loading is handled by HTMX directly via hx-get on trigger buttons.
// This file handles buttons using data-hx-get pattern.
document.addEventListener('DOMContentLoaded', function () {
    const htmxModal = document.getElementById('htmx-modal');
    if (htmxModal) {
        htmxModal.addEventListener('show.bs.modal', function (event) {
            const triggerElement = event.relatedTarget;
            if (triggerElement) {
                // Handle data-hx-get pattern (buttons without hx-get)
                const url = triggerElement.getAttribute('data-hx-get');
                const targetSelector = triggerElement.getAttribute('data-hx-target');
                if (url && targetSelector && !triggerElement.hasAttribute('hx-get')) {
                    const targetElement = htmx.find(targetSelector);
                    if (targetElement) {
                        htmx.ajax('GET', url, {
                            target: targetElement,
                            swap: 'innerHTML'
                        });
                    }
                }
            }
        });
    }
});
