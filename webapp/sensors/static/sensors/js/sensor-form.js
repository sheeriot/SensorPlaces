const sensorFormManager = {
    config: {
        debug: false,
    },

    init() {
        if (this.config.debug) console.log('[SensorForm] Initializing');

        // --- InfluxDB fields toggle ---
        const dataTypeSelectForInflux = document.getElementById('id_data_type');
        if (dataTypeSelectForInflux) {
            this.toggleInfluxFields();
            dataTypeSelectForInflux.addEventListener('change', () => this.toggleInfluxFields());
        }

        // --- Override toggles ---
        this.initOverride('unit');
        // this.initOverride('data_type'); // Removed
        this.initOverride('min_value');
        this.initOverride('max_value');

        // --- Add Influx Source Modal ---
        const addSourceBtn = document.getElementById('add-influx-source-btn');
        if (addSourceBtn) {
            addSourceBtn.addEventListener('click', (e) => this.handleAddInfluxSourceClick(e));
        }

        // --- Sensor Type Change Handler ---
        const sensorTypeSelect = document.getElementById('id_sensor_type');
        if (sensorTypeSelect) {
            sensorTypeSelect.addEventListener('change', () => this.handleSensorTypeChange());
        }

        // --- Data Type Change Handler ---
        // Just for Influx toggling now
        const dataTypeSelect = document.getElementById('id_data_type');
        if (dataTypeSelect) {
            // dataTypeSelect.addEventListener('change', () => this.handleDataTypeSelection()); // Removed override logic
        }
    },

    initOverride(type) {
        const overrideCheckbox = document.getElementById(`id_${type}_override`);
        const targetInput = document.getElementById(`id_${type}`);

        if (overrideCheckbox && targetInput) {
            targetInput.disabled = !overrideCheckbox.checked;
            overrideCheckbox.addEventListener('change', function() {
                targetInput.disabled = !this.checked;
                if (!this.checked) {
                    const defaults = sensorFormManager.getSensorTypeDefaults();
                    const defaultValue = {
                        'unit': defaults.unitId || '',
                        // 'data_type': defaults.dataType || '', // Removed
                        'min_value': '',
                        'max_value': ''
                    }[type];

                    targetInput.value = defaultValue;
                    if (type === 'min_value' || type === 'max_value') {
                        const placeholderValue = {
                            'min_value': defaults.minValue,
                            'max_value': defaults.maxValue
                        }[type];
                        targetInput.placeholder = placeholderValue !== '' ? placeholderValue : 'Not set';
                    }
                }
            });
        }
    },

    getSensorTypeDefaults() {
        const sensorTypeSelect = document.getElementById('id_sensor_type');
        const selectedOption = sensorTypeSelect.options[sensorTypeSelect.selectedIndex];
        if (!selectedOption || !selectedOption.value) {
            return {};
        }
        return {
            unitId: selectedOption.dataset.defaultUnitId,
            // dataType: selectedOption.dataset.defaultDataType, // Removed
            minValue: selectedOption.dataset.minValue,
            maxValue: selectedOption.dataset.maxValue,
        };
    },

    async handleAddInfluxSourceClick(e) {
        e.preventDefault();
        const url = e.currentTarget.href;
        const modalElement = document.getElementById('add-influx-source-modal');
        if (!modalElement) return;

        const modal = new bootstrap.Modal(modalElement);
        const modalBody = modalElement.querySelector('.modal-body');

        try {
            const response = await window.utils.fetchWithCSRF(url);
            if (!response.ok) throw new Error('Failed to load form.');

            const html = await response.text();
            modalBody.innerHTML = html;
            modal.show();

            const form = modalBody.querySelector('form');
            this.handleModalFormSubmission(form, modal, modalBody);
        } catch (error) {
            if (this.config.debug) console.error('[SensorForm] Error loading Influx Source form:', error);
        }
    },

    async handleModalFormSubmission(form, modal, modalBody) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(form);

            try {
                const response = await window.utils.fetchWithCSRF(form.action, {
                    method: 'POST',
                    body: formData,
                });

                const data = await response.json();

                if (data.success) {
                    const influxSourceSelect = document.getElementById('id_influx_source');
                    if (influxSourceSelect) {
                        const newOption = new Option(data.name, data.pk, true, true);
                        influxSourceSelect.appendChild(newOption);
                    }
                    modal.hide();
                } else {
                    modalBody.innerHTML = data.html;
                    const newForm = modalBody.querySelector('form');
                    this.handleModalFormSubmission(newForm, modal, modalBody);
                }
            } catch (error) {
                if (this.config.debug) console.error('[SensorForm] Error submitting Influx Source form:', error);
            }
        });
    },

    handleSensorTypeChange() {
        const sensorTypeSelect = document.getElementById('id_sensor_type');
        const selectedOption = sensorTypeSelect.options[sensorTypeSelect.selectedIndex];

        if (this.config.debug) console.log(`[SensorForm] Sensor Type changed to: ${selectedOption.value}`);

        const data = this.getSensorTypeDefaults();
        if (this.config.debug) console.log('[SensorForm] Read SensorType data from attributes:', data);

        this.updateFormFields(data);
        // this.handleDataTypeSelection(); // Removed
    },

    updateFormFields(data) {
        const fields = {
            unit: document.getElementById('id_unit'),
            data_type: document.getElementById('id_data_type'),
            min_value: document.getElementById('id_min_value'),
            max_value: document.getElementById('id_max_value')
        };
        const overrides = {
            unit: document.getElementById('id_unit_override'),
            data_type: document.getElementById('id_data_type_override'),
        };

        if (fields.unit && !overrides.unit.checked) {
            fields.unit.value = data.unitId || ''; // Corrected property name from defaults object
        }
        // if (fields.data_type && !overrides.data_type.checked) {
        //     fields.data_type.value = data.default_data_type || '';
        // }
        if (fields.min_value) {
            fields.min_value.placeholder = data.minValue !== undefined ? data.minValue : 'Not set'; // Corrected property name
        }
        if (fields.max_value) {
            fields.max_value.placeholder = data.maxValue !== undefined ? data.maxValue : 'Not set'; // Corrected property name
        }
        if (this.config.debug) console.log('[SensorForm] Form fields updated with defaults.');
    },

    // handleDataTypeSelection() { ... } // Removed entire method


    toggleInfluxFields() {
        const dataTypeSelect = document.getElementById('id_data_type');
        const influxFields = document.getElementById('influx-fields');

        if (dataTypeSelect && influxFields) {
            const isInflux = dataTypeSelect.value.startsWith('INFLUX');
            influxFields.style.display = isInflux ? 'block' : 'none';
        }
    }
};

document.addEventListener('DOMContentLoaded', () => sensorFormManager.init());
