const sensorFormManager = {
    config: {
        debug: false,
    },

    init() {
        if (this.config.debug) console.log('[SensorForm] Initializing');

        // --- InfluxDB fields toggle ---
        const dataStoreSelectForInflux = document.getElementById('id_data_store');
        if (dataStoreSelectForInflux) {
            this.toggleInfluxFields();
            dataStoreSelectForInflux.addEventListener('change', () => this.toggleInfluxFields());
        }

        // --- Override toggles ---
        this.initOverride('unit');
        this.initOverride('min_value');
        this.initOverride('max_value');

        // --- Add Influx Source Modal ---
        const addSourceBtn = document.getElementById('add-influx-source-btn');
        if (addSourceBtn) {
            addSourceBtn.addEventListener('click', (e) => this.handleAddInfluxStoreClick(e));
        }

        // --- Sensor Type Change Handler ---
        const sensorTypeSelect = document.getElementById('id_sensor_type');
        if (sensorTypeSelect) {
            sensorTypeSelect.addEventListener('change', () => this.handleSensorTypeChange());
            // Fire on initial load to set form state
            this.handleSensorTypeChange();
        }

        // --- Data Store Change Handler ---
        // Just for Influx toggling now
        const dataStoreSelect = document.getElementById('id_data_store');
        if (dataStoreSelect) {
            // dataStoreSelect.addEventListener('change', () => this.handleDataStoreSelection()); // Removed override logic
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
                        // 'data_store': defaults.dataStore || '', // Removed
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
            if (this.config.debug) console.log('[SensorForm] No sensor type selected.');
            return {};
        }

        const defaults = {
            unitId: selectedOption.dataset.unitId,
            graphType: selectedOption.dataset.graphType,
            minValue: selectedOption.dataset.minValue,
            maxValue: selectedOption.dataset.maxValue,
        };

        if (this.config.debug) {
            console.log('[SensorForm] Found defaults for selected sensor type:', {
                unitId: defaults.unitId,
                graphType: defaults.graphType,
                minValue: defaults.minValue,
                maxValue: defaults.maxValue
            });
        }
        return defaults;
    },

    async handleAddInfluxStoreClick(e) {
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
                    const influxSourceSelect = document.getElementById('id_influx_store');
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
        const dependentFields = document.getElementById('sensor-type-dependent-fields');
        const graphTypeContainer = document.getElementById('graph_type_container');

        if (this.config.debug) console.log(`[SensorForm] Sensor Type changed to: ${selectedOption.value}`);

        if (selectedOption && selectedOption.value) {
            dependentFields.classList.remove('d-none');
            graphTypeContainer.classList.remove('d-none');
            const data = this.getSensorTypeDefaults();
            if (this.config.debug) console.log('[SensorForm] Read SensorType data from attributes:', data);

            this.updateFormFields(data);
        } else {
            dependentFields.classList.add('d-none');
            graphTypeContainer.classList.add('d-none');
        }
    },

    updateFormFields(data) {
        const fields = {
            unit: document.getElementById('id_unit'),
            graph_type: document.getElementById('id_graph_type'),
            min_value: document.getElementById('id_min_value'),
            max_value: document.getElementById('id_max_value')
        };
        const overrides = {
            unit: document.getElementById('id_unit_override'),
            min_value: document.getElementById('id_min_value_override'),
            max_value: document.getElementById('id_max_value_override'),
        };

        if (fields.unit && !overrides.unit.checked) {
            if (this.config.debug) console.log(`[SensorForm] Setting unit to default: ${data.unitId}`);
            fields.unit.value = data.unitId || '';
        }
        if (fields.graph_type) {
            if (this.config.debug) console.log(`[SensorForm] Setting graph type to default: ${data.graphType}`);
            fields.graph_type.value = data.graphType || 'LINE';
        }
        if (fields.min_value && !overrides.min_value.checked) {
            const placeholder = data.minValue !== null && data.minValue !== undefined ? data.minValue : 'Not set';
            if (this.config.debug) console.log(`[SensorForm] Setting min value placeholder to default: ${placeholder}`);
            fields.min_value.placeholder = placeholder;
            fields.min_value.value = '';
        }
        if (fields.max_value && !overrides.max_value.checked) {
            const placeholder = data.maxValue !== null && data.maxValue !== undefined ? data.maxValue : 'Not set';
            if (this.config.debug) console.log(`[SensorForm] Setting max value placeholder to default: ${placeholder}`);
            fields.max_value.placeholder = placeholder;
            fields.max_value.value = '';
        }
        if (this.config.debug) console.log('[SensorForm] Form fields updated with defaults.');
    },

    // handleDataStoreSelection() { ... } // Removed entire method


    toggleInfluxFields() {
        const dataStoreSelect = document.getElementById('id_data_store');
        const influxFields = document.getElementById('influx-fields');

        if (dataStoreSelect && influxFields) {
            const isInflux = dataStoreSelect.value.startsWith('INFLUX');
            if (isInflux) {
                influxFields.classList.remove('d-none');
            } else {
                influxFields.classList.add('d-none');
            }
        }
    }
};

document.addEventListener('DOMContentLoaded', () => sensorFormManager.init());
