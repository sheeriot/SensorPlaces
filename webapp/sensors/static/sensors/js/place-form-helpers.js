document.addEventListener('DOMContentLoaded', function () {
    const form = document.querySelector('form');
    const isActiveCheckbox = document.getElementById('id_is_active');
    const confirmationModal = new bootstrap.Modal(document.getElementById('deactivationModal'));
    const placeName = document.getElementById('deactivationModal').dataset.placeName;
    const confirmationInput = document.getElementById('deactivationConfirmationName');
    const confirmButton = document.getElementById('confirmDeactivation');
    let deactivating = false;

    if (isActiveCheckbox) {
        form.addEventListener('submit', function (event) {
            if (deactivating) {
                return;
            }

            if (!isActiveCheckbox.checked) {
                event.preventDefault();
                confirmationModal.show();
            }
        });

        confirmButton.addEventListener('click', function () {
            if (confirmationInput.value === placeName) {
                deactivating = true;
                form.submit();
            } else {
                alert('The name you entered does not match the place name. Please try again.');
            }
        });
    }
});
