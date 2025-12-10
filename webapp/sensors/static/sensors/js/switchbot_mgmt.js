// This script handles behaviors on the SwitchBot management page

// This function initializes the logic for the import options modal.
// It needs to be called after the modal content is loaded by HTMX.
function initializeImportOptions() {
    const modalContent = document.getElementById('htmx-modal-content');
    if (!modalContent) return;

    const locationSelect = modalContent.querySelector('#location-select');
    const activeCheckbox = modalContent.querySelector('#is-active-checkbox');
    const activeHelpText = modalContent.querySelector('#is-active-help');

    if (locationSelect && activeCheckbox && activeHelpText) {
        locationSelect.addEventListener('change', function () {
            const selectedOption = this.options[this.selectedIndex];
            const isActive = selectedOption.getAttribute('data-is-active') === 'true';

            if (isActive) {
                activeCheckbox.disabled = false;
                activeCheckbox.checked = true;
                activeHelpText.textContent = 'Uncheck to import the device as Inactive, even though the location is Active.';
            } else {
                activeCheckbox.disabled = true;
                activeCheckbox.checked = false;
                activeHelpText.textContent = 'Device must be Inactive because the location is Inactive.';
            }
        });
    }
}

// Main event listeners
document.body.addEventListener('htmx:afterSwap', function(event) {
    // After HTMX loads content into the modal, check if it's our import form
    if (event.detail.target.id === 'htmx-modal-content') {
        initializeImportOptions();
    }
});
