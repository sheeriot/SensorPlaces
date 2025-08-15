document.addEventListener('DOMContentLoaded', function() {
    // --- InfluxDB fields toggle ---
    const dataTypeSelectForInflux = document.getElementById('id_data_type');
    if (dataTypeSelectForInflux) {
        toggleInfluxFields();
        dataTypeSelectForInflux.addEventListener('change', toggleInfluxFields);
    }

    // --- Override toggles ---
    const unitOverride = document.getElementById('id_unit_override');
    const unitSelect = document.getElementById('id_unit');
    const dataTypeOverride = document.getElementById('id_data_type_override');
    const dataTypeSelect = document.getElementById('id_data_type');

    if (unitOverride && unitSelect) {
        unitOverride.addEventListener('change', function() {
            unitSelect.disabled = !this.checked;
        });
    }

    if (dataTypeOverride && dataTypeSelect) {
        dataTypeOverride.addEventListener('change', function() {
            dataTypeSelect.disabled = !this.checked;
        });
    }

    // --- Add Influx Source Modal ---
    const addSourceBtn = document.getElementById('add-influx-source-btn');
    const modalElement = document.getElementById('add-influx-source-modal');
    if (addSourceBtn && modalElement) {
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
                handleModalFormSubmission(form, modal, modalBody, influxSourceSelect);
            });
        });
    }
});

function toggleInfluxFields() {
    const dataTypeSelect = document.getElementById('id_data_type');
    const influxFields = document.getElementById('influx-fields');

    if (dataTypeSelect && influxFields) {
        const isInflux = dataTypeSelect.value.startsWith('INFLUX');
        influxFields.style.display = isInflux ? 'block' : 'none';
    }
}

function handleModalFormSubmission(form, modal, modalBody, influxSourceSelect) {
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
                handleModalFormSubmission(modalBody.querySelector('form'), modal, modalBody, influxSourceSelect);
            }
        });
    });
} 