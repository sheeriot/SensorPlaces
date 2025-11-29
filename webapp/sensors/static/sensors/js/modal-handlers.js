document.addEventListener('DOMContentLoaded', function() {
    const scriptConfig = {
        debug: false
    };

    console.log(`modalHandlersConfig.debug status: ${scriptConfig.debug}`);

    if (scriptConfig.debug) {
        console.log('Script modal-handlers.js loaded.');
    }

    /**
     * Attaches generic Bootstrap and HTMX event loggers to a modal.
     * @param {string} modalId The ID of the modal element to debug.
     */
    function initializeModalDebug(modalId) {
        if (!scriptConfig.debug) return;

        const modal = document.getElementById(modalId);
        if (modal) {
            console.log(`[ModalDebug] Initializing listeners for #${modalId}`);

            modal.addEventListener('show.bs.modal', (event) => {
                console.log(`[ModalDebug] #${modalId} Event: show.bs.modal`, { relatedTarget: event.relatedTarget });
            });
            modal.addEventListener('shown.bs.modal', () => {
                console.log(`[ModalDebug] #${modalId} Event: shown.bs.modal`);
            });
            modal.addEventListener('hide.bs.modal', () => {
                console.log(`[ModalDebug] #${modalId} Event: hide.bs.modal`);
            });
            modal.addEventListener('hidden.bs.modal', () => {
                console.log(`[ModalDebug] #${modalId} Event: hidden.bs.modal`);
            });

            // Listen for HTMX content loads within the modal
            modal.addEventListener('htmx:afterOnLoad', (evt) => {
                console.log(`[ModalDebug] #${modalId} Event: htmx:afterOnLoad`, { xhr: evt.detail.xhr });
            });
        } else {
            console.warn(`[ModalDebug] Modal element #${modalId} not found.`);
        }
    }

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
            });
        }
    }

    // Initialize all modal handlers
    initializeDeleteConfirmationInput();
    initializeModalCleanup();

    // Initialize debug listeners for all known modals if debug is on
    if (scriptConfig.debug) {
        initializeModalDebug('deleteLocationModal');
        initializeModalDebug('siteplan-view-modal');
        initializeModalDebug('siteplan-editor');
        initializeModalDebug('modal-container'); // Generic HTMX modal container
    }
});
