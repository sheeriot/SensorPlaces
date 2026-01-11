/**
 * JavaScript for InfluxDB Sensor Discovery feature.
 * Handles error messages, preview chart rendering, and field selection UI.
 */

(function() {
    'use strict';

    // Handle discovery form errors
    document.body.addEventListener('htmx:responseError', function(evt) {
        const xhr = evt.detail.xhr;
        const path = (xhr && xhr.responseURL) || '';
        if (path.includes('discover') || path.includes('bulk-create') || path.includes('preview-field')) {
            console.error('[InfluxDiscovery] Request error:', path);

            try {
                const errorData = JSON.parse(xhr.responseText);
                if (errorData.error) {
                    if (window.toastSystem && typeof window.toastSystem.show === 'function') {
                        window.toastSystem.show(`Error: ${errorData.error}`, 'error');
                    } else {
                        alert(`Error: ${errorData.error}`);
                    }
                }
            } catch (e) {
                console.error('[InfluxDiscovery] Non-JSON error response');
            }
        }
    });

    /**
     * Initialize field tree selection UI after HTMX swap
     */
    function initFieldTreeUI() {
        const selectAllCheckbox = document.getElementById('select-all-fields');
        const fieldCheckboxes = document.querySelectorAll('.field-checkbox');
        const createBtn = document.getElementById('create-sensors-btn');
        const createBtnText = document.getElementById('create-btn-text');

        if (!createBtn || fieldCheckboxes.length === 0) {
            return;
        }

        function updateCreateButton() {
            const checkedCount = document.querySelectorAll('.field-checkbox:checked').length;
            createBtn.disabled = checkedCount === 0;
            if (checkedCount > 0) {
                createBtnText.textContent = `Create ${checkedCount} Sensor${checkedCount !== 1 ? 's' : ''}`;
            } else {
                createBtnText.textContent = 'Create Sensors';
            }
        }

        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener('change', function() {
                fieldCheckboxes.forEach(cb => {
                    cb.checked = this.checked;
                });
                updateCreateButton();
            });
        }

        fieldCheckboxes.forEach(cb => {
            cb.addEventListener('change', updateCreateButton);
        });

        // Initial state
        updateCreateButton();
        console.log('[InfluxDiscovery] Field tree UI initialized with', fieldCheckboxes.length, 'fields');
    }

    // Initialize field tree UI when discovery results are loaded
    document.body.addEventListener('htmx:afterSwap', function(evt) {
        const target = evt.detail.target;

        if (target && target.id === 'discovery-results') {
            console.log('[InfluxDiscovery] Discovery results loaded');
            initFieldTreeUI();
        }
    });

    /**
     * Create preview chart from data attributes on the container element.
     * Called when preview modal is shown.
     */
    function createPreviewChart() {
        console.log('[InfluxDiscovery] createPreviewChart called');

        const container = document.getElementById('preview-chart-container');
        const canvas = document.getElementById('preview-chart-canvas');

        console.log('[InfluxDiscovery] Container:', container);
        console.log('[InfluxDiscovery] Canvas:', canvas);

        if (!container || !canvas) {
            console.error('[InfluxDiscovery] Chart container or canvas not found');
            return;
        }

        // Log container dimensions
        console.log('[InfluxDiscovery] Container dimensions:', container.offsetWidth, 'x', container.offsetHeight);

        if (typeof Chart === 'undefined') {
            console.error('[InfluxDiscovery] Chart.js not loaded');
            return;
        }

        // Get data from data attributes
        const dataJson = container.dataset.chartData;
        const field = container.dataset.chartField;

        console.log('[InfluxDiscovery] Data JSON length:', dataJson ? dataJson.length : 0);
        console.log('[InfluxDiscovery] Data JSON first 200 chars:', dataJson ? dataJson.substring(0, 200) : 'null');
        console.log('[InfluxDiscovery] Field:', field);

        if (!dataJson) {
            console.error('[InfluxDiscovery] No chart data found');
            return;
        }

        try {
            const rawData = JSON.parse(dataJson);
            const chartData = rawData.map(item => ({
                x: new Date(item.time),
                y: item.value
            })).sort((a, b) => a.x - b.x);

            // Destroy existing chart if present
            const existingChart = Chart.getChart(canvas);
            if (existingChart) {
                existingChart.destroy();
            }

            new Chart(canvas.getContext('2d'), {
                type: 'line',
                data: {
                    datasets: [{
                        label: field,
                        data: chartData,
                        borderColor: 'rgba(75, 192, 192, 1)',
                        backgroundColor: 'rgba(75, 192, 192, 0.2)',
                        tension: 0.1,
                        pointRadius: 3,
                        fill: false
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            type: 'time',
                            time: {
                                tooltipFormat: 'MMM d, yyyy HH:mm:ss'
                            },
                            title: {
                                display: true,
                                text: 'Time'
                            }
                        },
                        y: {
                            title: {
                                display: true,
                                text: 'Value'
                            },
                            beginAtZero: false
                        }
                    },
                    plugins: {
                        legend: {
                            display: true,
                            position: 'top'
                        }
                    }
                }
            });

            console.log('[InfluxDiscovery] Preview chart created with', chartData.length, 'points');
        } catch (e) {
            console.error('[InfluxDiscovery] Error creating chart:', e);
        }
    }

    // When preview modal content is swapped, show modal and create chart
    document.body.addEventListener('htmx:afterSwap', function(evt) {
        const target = evt.detail.target;

        if (target && target.id === 'preview-modal-content') {
            console.log('[InfluxDiscovery] Preview content loaded into modal');

            const modalEl = document.getElementById('preview-modal');
            if (!modalEl) {
                console.error('[InfluxDiscovery] Preview modal not found');
                return;
            }

            const modal = bootstrap.Modal.getOrCreateInstance(modalEl);

            // Check if modal is already visible
            if (modalEl.classList.contains('show')) {
                console.log('[InfluxDiscovery] Modal already shown, creating chart now');
                setTimeout(createPreviewChart, 100);
            } else {
                console.log('[InfluxDiscovery] Waiting for modal to show...');
                modalEl.addEventListener('shown.bs.modal', function onShown() {
                    console.log('[InfluxDiscovery] Modal shown event fired');
                    createPreviewChart();
                }, { once: true });
                modal.show();
            }
        }
    });
})();
