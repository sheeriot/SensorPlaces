document.addEventListener('DOMContentLoaded', function() {
    const scriptConfig = {
        debug: false
    };
    if (scriptConfig.debug) console.log(`modalHandlersConfig.debug status: ${scriptConfig.debug}`);

    /**
     * Initializes a confirmation input field within a modal.
     * Disables a submit button until the user types the expected value.
     */
    function initializeDeleteConfirmationInput() {
        // This handler is designed to be generic. It's attached to the body
        // and listens for an HTMX event that fires after content is loaded into a modal.
        document.body.addEventListener('htmx:afterOnLoad', function(event) {
            const modalContent = event.target;
            const confirmInput = modalContent.querySelector('.delete-confirm-input');
            const deleteButton = modalContent.querySelector('.confirm-delete-button');

            if (confirmInput && deleteButton) {
                const expectedCount = confirmInput.dataset.expected;
                if (scriptConfig.debug) {
                    console.log('Found delete confirmation input. Expected value:', expectedCount);
                }

                confirmInput.addEventListener('input', function() {
                    deleteButton.disabled = confirmInput.value !== expectedCount;
                });
            }
        });
    }

    /**
     * Initializes generic modal cleanup.
     * Clears the modal content when hidden to ensure fresh loading on next trigger.
     */
    function initializeModalLifecycleLogging() {
        const modalContainer = document.getElementById('htmx-modal');
        if (modalContainer) {
            if (scriptConfig.debug) console.log('[ModalLifecycle] Attached lifecycle listeners to #htmx-modal.');

            modalContainer.addEventListener('show.bs.modal', function(event) {
                if (scriptConfig.debug) console.log('[ModalLifecycle] #htmx-modal show.bs.modal event triggered.');
            });

            modalContainer.addEventListener('shown.bs.modal', function(event) {
                if (scriptConfig.debug) console.log('[ModalLifecycle] #htmx-modal shown.bs.modal event triggered.');
            });

            modalContainer.addEventListener('hide.bs.modal', function() {
                if (scriptConfig.debug) console.log('[ModalLifecycle] #htmx-modal hide.bs.modal event triggered.');
            });

            modalContainer.addEventListener('hidden.bs.modal', function () {
                if (scriptConfig.debug) console.log('[ModalLifecycle] #htmx-modal hidden.bs.modal event triggered. Cleaning up.');

                const modalContent = modalContainer.querySelector('#htmx-modal-content');
                if (modalContent) {
                    modalContent.innerHTML = '';
                    if (scriptConfig.debug) {
                        console.log('[ModalLifecycle] Cleared modal content from #htmx-modal-content');
                    }
                } else {
                    if (scriptConfig.debug) console.log('[ModalLifecycle] #htmx-modal-content not found.');
                }

                // Force cleanup of any lingering backdrops and body styles.
                const backdrops = document.querySelectorAll('.modal-backdrop');
                backdrops.forEach(backdrop => backdrop.remove());

                document.body.classList.remove('modal-open');
                document.body.style.overflow = '';
                document.body.style.paddingRight = '';
            });
        } else {
            if (scriptConfig.debug) console.error('[ModalLifecycle] Could not find #htmx-modal to attach listener.');
        }
    }

    // Initialize all modal handlers
    initializeDeleteConfirmationInput();
    initializeModalLifecycleLogging();
});
