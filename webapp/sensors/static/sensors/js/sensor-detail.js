document.addEventListener('DOMContentLoaded', function () {
    const sensorDetailConfig = {
        debug: true 
    };

    // Delete sensor modal logic
    const deleteSensorModal = document.getElementById('deleteSensorModal');
    if (deleteSensorModal) {
        deleteSensorModal.addEventListener('show.bs.modal', async function (event) {
            const button = event.relatedTarget;
            const url = button.dataset.url;
            const modalContent = deleteSensorModal.querySelector('.modal-content');

            try {
                const data = await window.utils.fetchWithCSRF(url, { method: 'GET', headers: { 'Content-Type': 'application/json' } });
                modalContent.innerHTML = data.html;
                const deleteForm = modalContent.querySelector('#deleteSensorForm');
                if (deleteForm) {
                    deleteForm.addEventListener('submit', async function (e) {
                        e.preventDefault();
                        try {
                            const formData = new FormData(deleteForm);
                            // Note: fetchWithCSRF expects a JSON body, so we convert FormData if needed.
                            // For this form, the body is empty and the action is in the URL, so we can pass an empty body.
                            const data = await window.utils.fetchWithCSRF(deleteForm.action, {
                                method: 'POST',
                                body: JSON.stringify({}) // Sending empty JSON body as FormData is not directly supported
                            });
                            if (data.success) {
                                window.location.href = data.redirect_url;
                            }
                        } catch (error) {
                            console.error('Error submitting delete form:', error);
                        }
                    });
                }
            } catch (error) {
                console.error('Error fetching delete modal content:', error);
                modalContent.innerHTML = '<p class="text-danger">Could not load content. Please try again.</p>';
            }
        });
    }

    // Graph type change and save logic
    // Scope the search to the main content area to avoid grabbing a card from the sidebar list
    const mainContentArea = document.querySelector('.col-md-8');
    const sensorCard = mainContentArea ? mainContentArea.querySelector('.card[data-sensor-id]') : null;

    if (sensorCard) {
        const sensorId = sensorCard.dataset.sensorId;
        const placeSlug = document.getElementById('sensor-graph-card')?.dataset.placeSlug;
        // Find the select element within this specific card
        const select = sensorCard.querySelector(`select[name="graph_type"]`);

        if (sensorDetailConfig.debug) {
            console.log('sensor-detail.js: Initialized. Sensor ID:', sensorId);
            if (select) {
                console.log('sensor-detail.js: Graph type selector found:', select);
            } else {
                console.error('sensor-detail.js: Graph type selector NOT found inside the main sensor card!');
            }
        }

        if (select && placeSlug) {
            select.addEventListener('change', async function() {
                if (sensorDetailConfig.debug) {
                    console.log('sensor-detail.js: Graph type changed to:', this.value);
                }
                const newGraphType = this.value;
                const url = `/api/${placeSlug}/sensor/${sensorId}/update-graph-type/`;
                
                try {
                    const data = await window.utils.fetchWithCSRF(url, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ graph_type: newGraphType })
                    });

                    if (data.success) {
                        const graphCard = document.getElementById('sensor-graph-card');
                        if (graphCard) {
                            graphCard.dataset.graphType = newGraphType;
                            const event = new CustomEvent('graphTypeChange', { detail: { newType: newGraphType } });
                            if (sensorDetailConfig.debug) {
                                console.log('sensor-detail.js: Dispatching graphTypeChange event with detail:', event.detail);
                            }
                            graphCard.dispatchEvent(event);
                        }
                    } else {
                        alert('Error saving graph type: ' + (data.error || 'Unknown error'));
                    }
                } catch (error) {
                    console.error('Error saving graph type:', error);
                    alert('An error occurred while saving the graph type.');
                }
            });
        }
    }

    // Clipboard copy logic
    function showCopySuccess(button) {
        const icon = button.querySelector('i');
        const originalIconClass = icon.className;
        icon.className = 'bi bi-check-lg text-success';
        setTimeout(() => {
            icon.className = originalIconClass;
        }, 2000);
    }

    function fallbackCopyTextToClipboard(text, button) {
        const textArea = document.createElement("textarea");
        textArea.value = text;
        
        // Avoid scrolling to bottom
        textArea.style.top = "0";
        textArea.style.left = "0";
        textArea.style.position = "fixed";

        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();

        try {
            const successful = document.execCommand('copy');
            if (successful) {
                showCopySuccess(button);
            } else {
                console.error('Fallback: Unable to copy');
                prompt('Could not copy automatically. Please copy this URL:', text);
            }
        } catch (err) {
            console.error('Fallback: Oops, unable to copy', err);
            prompt('Could not copy automatically. Please copy this URL:', text);
        }

        document.body.removeChild(textArea);
    }

    function handleCopy(button, getUrlCallback) {
        const urlToCopy = getUrlCallback();
        if (!urlToCopy) return; // Callback can return null to cancel

        // Use modern clipboard API if available and in a secure context
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(urlToCopy).then(() => {
                showCopySuccess(button);
            }).catch(err => {
                console.error('Could not copy URL with modern API, trying fallback: ', err);
                fallbackCopyTextToClipboard(urlToCopy, button);
            });
        } else {
            // Fallback for insecure contexts (HTTP) or older browsers
            fallbackCopyTextToClipboard(urlToCopy, button);
        }
    }

    // Helper function to format a local date string (YYYY-MM-DD) into a UTC datetime string (YYYYMMDDHHMM)
    const formatLocalDateAsUTC = (dateString, isEndDate = false) => {
        // By appending T00:00:00, new Date() parses the string in the local timezone.
        const timePart = isEndDate ? 'T23:59:59' : 'T00:00:00';
        const localDate = new Date(dateString + timePart);

        const year = localDate.getUTCFullYear();
        const month = (localDate.getUTCMonth() + 1).toString().padStart(2, '0');
        const day = localDate.getUTCDate().toString().padStart(2, '0');
        const hours = localDate.getUTCHours().toString().padStart(2, '0');
        const minutes = localDate.getUTCMinutes().toString().padStart(2, '0');
        
        return `${year}${month}${day}${hours}${minutes}`;
    };

    const copyRelativeUrlBtn = document.getElementById('copy-relative-url-btn');
    if (copyRelativeUrlBtn) {
        copyRelativeUrlBtn.addEventListener('click', function(e) {
            e.preventDefault();
            handleCopy(this, () => {
                const activePreset = document.querySelector('.date-range-preset.active');
                if (!activePreset || !activePreset.dataset.range) {
                    alert("Please select a relative time range first (e.g., 7d).");
                    return null;
                }

                const graphCard = document.getElementById('sensor-graph-card');
                const placeSlug = graphCard.dataset.placeSlug;
                const sensorId = graphCard.dataset.sensorId;
                const delta = activePreset.dataset.range;

                let url = new URL(window.location.origin);
                url.pathname = `/${placeSlug}/sensor/${sensorId}/delta/${delta}/`;
                return url.href;
            });
        });
    }

    const copyAbsoluteUrlBtn = document.getElementById('copy-absolute-url-btn');
    if (copyAbsoluteUrlBtn) {
        copyAbsoluteUrlBtn.addEventListener('click', function(e) {
            e.preventDefault();
            handleCopy(this, () => {
                const startDatePicker = document.getElementById('start-date-picker');
                const endDatePicker = document.getElementById('end-date-picker');
                const startVal = startDatePicker.value;
                const endVal = endDatePicker.value;

                if (!startVal || !endVal) {
                    alert("Please select a start and end date first.");
                    return null;
                }
                
                const graphCard = document.getElementById('sensor-graph-card');
                const placeSlug = graphCard.dataset.placeSlug;
                const sensorId = graphCard.dataset.sensorId;
                
                let url = new URL(window.location.origin);
                url.pathname = `/${placeSlug}/sensor/${sensorId}/${formatLocalDateAsUTC(startVal)}/${formatLocalDateAsUTC(endVal, true)}/`;
                return url.href;
            });
        });
    }

    const applyDateRangeBtn = document.getElementById('apply-date-range');
    if(applyDateRangeBtn) {
        applyDateRangeBtn.addEventListener('click', function(event) {
            event.preventDefault(); // Prevent default form submission/page reload

            const startDatePicker = document.getElementById('start-date-picker');
            const endDatePicker = document.getElementById('end-date-picker');
            const startDate = startDatePicker.value;
            const endDate = endDatePicker.value;

            if (startDate && endDate) {
                const graphCard = document.getElementById('sensor-graph-card');
                const placeSlug = graphCard.dataset.placeSlug;
                const sensorId = graphCard.dataset.sensorId;

                const startUTC = formatLocalDateAsUTC(startDate, false);
                const endUTC = formatLocalDateAsUTC(endDate, true);

                // Construct the base path and the API URL with query parameters
                const basePath = `/${placeSlug}/sensor/${sensorId}/${startUTC}/${endUTC}/`;
                const apiUrl = new URL(graphCard.dataset.apiUrl, window.location.origin);
                apiUrl.searchParams.set('start_date', startUTC);
                apiUrl.searchParams.set('end_date', endUTC);

                // Dispatch a custom event with the API URL for the chart to listen to
                const dateEvent = new CustomEvent('dateRangeApplied', { 
                    detail: { 
                        apiUrl: apiUrl.toString(),
                        basePath: basePath
                    } 
                });
                graphCard.dispatchEvent(dateEvent);

                // Update the browser's URL without reloading the page
                window.history.pushState({}, '', basePath);
            } else {
                alert('Please select both a start and end date.');
            }
        });
    }
});
