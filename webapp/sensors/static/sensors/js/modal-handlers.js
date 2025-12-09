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
                // This is often too aggressive and can cause issues if another modal
                // is still active or being animated. Bootstrap should handle this.
                // const backdrops = document.querySelectorAll('.modal-backdrop');
                // backdrops.forEach(backdrop => backdrop.remove());
                //
                // document.body.classList.remove('modal-open');
                // document.body.style.overflow = '';
                // document.body.style.paddingRight = '';
            });
        } else {
            if (scriptConfig.debug) console.error('[ModalLifecycle] Could not find #htmx-modal to attach listener.');
        }

        const mapplanModalContainer = document.getElementById('mapplan-modal');
        if (mapplanModalContainer) {
            document.body.addEventListener('htmx:afterOnLoad', function(event) {
                if (scriptConfig.debug) console.log('[HTMX afterOnLoad] Event triggered. Detail Target ID:', event.detail.target.id, 'Target Element:', event.detail.target);

                const modalContent = event.detail.target;
                if (modalContent.id === 'mapplan-modal-content') {
                    if (scriptConfig.debug) console.log('[MapplanModal] HTMX content loaded into mapplan-modal.');

                    const mapContainer = modalContent.querySelector('#placeMapContainer');

                    if (mapContainer) {
                        if (scriptConfig.debug) console.log('[MapplanModal] Found #placeMapContainer, initializing map popout.');
                        if (window.placeMapPopout && typeof window.placeMapPopout.initialize === 'function') {
                            window.placeMapPopout.initialize(modalContent);
                        } else {
                            console.error('[MapplanModal] placeMapPopout.initialize is not available.');
                        }
                    }
                }
            });
        }
    }

    /**
     * Initializes the draggable and resizable functionality for the mapplan modal.
     */
    function initializeMapplanModal() {
        const modal = $('#mapplan-modal');
        if (modal.length) {
            // Make mapplan modals draggable by their header.
            modal.draggable({
                handle: ".modal-header",
                containment: "window"
            });

            // Make mapplan modals resizable.
            modal.find('.modal-content').resizable({
                minHeight: 200,
                minWidth: 300,
                handles: "n, e, s, w, ne, se, sw, nw"
            });

            // When the modal is shown, ensure it's brought to the front and focused.
            modal.on('shown.bs.modal', function() {
                if (scriptConfig.debug) console.log('[MapplanModal] #mapplan-modal shown.bs.modal event triggered.');
                const zIndex = 1050;
                $(this).css('z-index', zIndex);
            });
        }
    }

    // Initialize all modal handlers
    initializeDeleteConfirmationInput();
    initializeModalLifecycleLogging();
    initializeMapplanModal();
});
