document.addEventListener('DOMContentLoaded', function () {
    const htmxModal = document.getElementById('htmx-modal');
    if (htmxModal) {
        htmxModal.addEventListener('show.bs.modal', function (event) {
            const triggerElement = event.relatedTarget;
            if (triggerElement) {
                const url = triggerElement.getAttribute('data-hx-get');
                const target = triggerElement.getAttribute('hx-target');

                if (url && target) {
                    htmx.ajax('GET', url, {
                        target: target,
                        swap: 'innerHTML'
                    });
                }
            }
        });
    }
});
