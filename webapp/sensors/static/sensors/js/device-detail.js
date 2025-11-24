document.addEventListener('DOMContentLoaded', function () {

    document.body.addEventListener('sensorAdded', function (evt) {
        console.group("Caught sensorAdded event");
        const detail = evt.detail;
        console.log("Detail:", detail);

        const deviceId = detail.deviceId;
        const deviceWrapper = document.getElementById(`device-context-wrapper-${deviceId}`);

        if (!deviceWrapper) {
            console.error(`Could not find device context wrapper #device-context-wrapper-${deviceId}`);
            console.groupEnd();
            return;
        }

        // 1. Append the new sensor row
        const sensorHTML = detail.sensorHTML;
        if (sensorHTML) {
            const sensorList = deviceWrapper.querySelector(`#sensor-list-${deviceId}`);
            if (sensorList) {
                sensorList.insertAdjacentHTML('beforeend', sensorHTML);
                console.log("Appended new sensor row.");
            } else {
                console.error(`Could not find sensor list container #sensor-list-${deviceId}`);
            }
        }

        // 2. Hide the "no sensors" message
        const noSensorsMessage = deviceWrapper.querySelector(`#no-sensors-message-${deviceId}`);
        if (noSensorsMessage) {
            noSensorsMessage.classList.add('d-none');
            console.log("Hid 'no sensors' message.");
        }

        // 3. Increment the sensor count
        const sensorCountEl = deviceWrapper.querySelector(`#sensor-count-${deviceId}`);
        if (sensorCountEl) {
            let currentCount = parseInt(sensorCountEl.textContent.trim(), 10);
            if (!isNaN(currentCount)) {
                sensorCountEl.textContent = currentCount + 1;
                console.log(`Incremented sensor count for device #${deviceId}`);
            }
        } else {
            console.error(`Could not find sensor count element #sensor-count-${deviceId} to increment.`);
        }

        // 4. Update the button in the modal
        const sensorType = detail.sensorType;
        if (sensorType) {
            const form = document.getElementById(`add-sensor-form-${sensorType}`);
            if (form) {
                form.innerHTML = `<button type="button" class="btn btn-sm btn-success" disabled><i class="bi bi-check-circle"></i> Added</button>`;
            } else {
                console.error(`Could not find form #add-sensor-form-${sensorType} to update.`);
            }
        }
        console.groupEnd();
    });

    document.body.addEventListener('sensorDeleted', function (evt) {
        console.group("Caught sensorDeleted event");
        const detail = evt.detail;
        console.log("Detail:", detail);

        const sensorId = detail.sensorId;
        const deviceId = detail.deviceId;
        const deviceWrapper = document.getElementById(`device-context-wrapper-${deviceId}`);

        if (!deviceWrapper) {
            console.error(`Could not find device context wrapper #device-context-wrapper-${deviceId}`);
            console.groupEnd();
            return;
        }

        // 1. Remove the sensor row
        const sensorRow = deviceWrapper.querySelector(`#sensor-row-${sensorId}`);
        if (sensorRow) {
            sensorRow.remove();
            console.log(`Removed sensor row #sensor-row-${sensorId}`);
        } else {
            console.error(`Could not find sensor row #sensor-row-${sensorId} to remove.`);
        }

        // 2. Decrement the sensor count
        const sensorCountEl = deviceWrapper.querySelector(`#sensor-count-${deviceId}`);
        if (sensorCountEl) {
            let currentCount = parseInt(sensorCountEl.textContent.trim(), 10);
            if (!isNaN(currentCount) && currentCount > 0) {
                sensorCountEl.textContent = currentCount - 1;
                console.log(`Decremented sensor count for device #${deviceId}`);
            }
        } else {
            console.error(`Could not find sensor count element #sensor-count-${deviceId}`);
        }

        // 3. Close the modal
        const modalElement = document.getElementById('modal-container');
        if (modalElement) {
            const modal = bootstrap.Modal.getInstance(modalElement);
            if (modal) {
                modal.hide();
                console.log("Delete confirmation modal hidden.");
            }
        }

        console.groupEnd();
    });

    document.body.addEventListener('sensorAlreadyExists', function (evt) {
        console.group("Caught sensorAlreadyExists event");
        const detail = evt.detail;
        console.log("Detail:", detail);

        const sensorType = detail.sensorType;
        if (sensorType) {
            const form = document.getElementById(`add-sensor-form-${sensorType}`);
            if (form) {
                form.innerHTML = `<span class="badge bg-info">Already Exists</span>`;
            } else {
                console.error(`Could not find form #add-sensor-form-${sensorType} to update.`);
            }
        }
        console.groupEnd();
    });
});
