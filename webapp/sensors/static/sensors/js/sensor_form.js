document.addEventListener('DOMContentLoaded', function () {
    const dataTypeSelect = document.getElementById('id_data_type');
    const influxFields = document.querySelector('.influx-fields');

    function toggleInfluxFields() {
        if (dataTypeSelect.value === 'INFLUX') {
            influxFields.style.display = '';
        } else {
            influxFields.style.display = 'none';
        }
    }

    // Initial check
    toggleInfluxFields();

    // Event listener
    dataTypeSelect.addEventListener('change', toggleInfluxFields);
}); 