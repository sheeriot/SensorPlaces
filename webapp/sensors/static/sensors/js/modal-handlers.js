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
    function initializeModalCleanup() {
        const modalContainer = document.getElementById('modal-container');
        if (modalContainer) {
            modalContainer.addEventListener('hidden.bs.modal', function () {
                const modalContent = modalContainer.querySelector('#modal-content');
                if (modalContent) {
                    modalContent.innerHTML = '';
                    if (scriptConfig.debug) {
                        console.log('[ModalCleanup] Cleared modal content');
                    }
                }

                // Force cleanup of any lingering backdrops and body styles.
                // This is a robust fix for the "frozen screen" issue that can happen
                // when HTMX and Bootstrap modals interact.
                const backdrops = document.querySelectorAll('.modal-backdrop');
                backdrops.forEach(backdrop => backdrop.remove());

                document.body.classList.remove('modal-open');
                document.body.style.overflow = '';
                document.body.style.paddingRight = '';
            });
        }
    }

    // Initialize all modal handlers
    initializeDeleteConfirmationInput();
    initializeModalCleanup();
});
