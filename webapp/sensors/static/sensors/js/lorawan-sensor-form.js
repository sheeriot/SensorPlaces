document.addEventListener('DOMContentLoaded', function() {
    const addSourceBtn = document.getElementById('add-influx-source-btn');
    const modalElement = document.getElementById('add-influx-source-modal');
    const modal = new bootstrap.Modal(modalElement);
    const modalBody = modalElement.querySelector('.modal-body');
    const influxSourceSelect = document.getElementById('id_influx_source');

    addSourceBtn.addEventListener('click', function(e) {
        e.preventDefault();
        fetch(this.href, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
            .then(response => response.text())
            .then(html => {
                modalBody.innerHTML = html;
                modal.show();
                const form = modalBody.querySelector('form');
                handleModalFormSubmission(form);
            });
    });

    function handleModalFormSubmission(form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            const formData = new FormData(form);
            fetch(form.action, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': formData.get('csrfmiddlewaretoken'),
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const newOption = new Option(data.name, data.pk, true, true);
                    influxSourceSelect.appendChild(newOption);
                    modal.hide();
                } else {
                    // Handle form errors
                    modalBody.innerHTML = data.html;
                    handleModalFormSubmission(modalBody.querySelector('form'));
                }
            });
        });
    }
}); 