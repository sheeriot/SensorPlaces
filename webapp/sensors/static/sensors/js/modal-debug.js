// To enable debugging, define `modalConfig = { debug: true }` before this script.
var modalConfig = {};
modalConfig.debug = false;


if (modalConfig.debug) {
    console.log('[ModalDebug] Modal debugging enabled.');

    document.addEventListener('DOMContentLoaded', () => {
        const modal = document.getElementById('modal-container');
        if (modal) {
            console.log('[ModalDebug] Found modal container.');

            modal.addEventListener('show.bs.modal', function (event) {
                console.log('[ModalDebug] Event "show.bs.modal" triggered.', {
                    relatedTarget: event.relatedTarget
                });
            });

            modal.addEventListener('shown.bs.modal', function () {
                console.log('[ModalDebug] Event "shown.bs.modal" triggered.');
            });

            modal.addEventListener('hide.bs.modal', function () {
                // Fix for Aria warning: Remove focus from any element within the modal
                // before it becomes hidden.
                if (document.activeElement && modal.contains(document.activeElement)) {
                    document.activeElement.blur();
                }
                console.log('[ModalDebug] Event "hide.bs.modal" triggered.');
            });

            modal.addEventListener('hidden.bs.modal', function () {
                console.log('[ModalDebug] Event "hidden.bs.modal" triggered.');
            });

            const modalContent = document.getElementById('modal-content');
            if (modalContent) {
                console.log('[ModalDebug] Found modal content area.');
                modalContent.addEventListener('htmx:afterOnLoad', function(evt) {
                    console.log('[ModalDebug] Event "htmx:afterOnLoad" triggered for modal content.', {
                        xhr: evt.detail.xhr
                    });
                });
            } else {
                console.error('[ModalDebug] Modal content area #modal-content not found.');
            }
        } else {
            console.error('[ModalDebug] Modal container #modal-container not found.');
        }
    });
}
