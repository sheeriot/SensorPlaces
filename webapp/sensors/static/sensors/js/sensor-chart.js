document.addEventListener('DOMContentLoaded', function() {
    const graphCard = document.getElementById('sensor-graph-card');
    if (!graphCard) {
        return;
    }

    const chartCanvas = document.getElementById('sensorChart');
    if (!chartCanvas) {
        return;
    }

    const sensorId = graphCard.dataset.sensorId;
    const placeSlug = graphCard.dataset.placeSlug;
    const apiUrl = graphCard.dataset.apiUrl;
    const sensorType = graphCard.dataset.sensorType;
    
    let chart;
    let rawData = [];

    function filterOutliers(data) {
        if (sensorType === 'humidity' && data.length > 0) {
            return data.filter(item => item[1] <= 100);
        }

        if (sensorType === 'rainfall_total' || data.length < 4) {
            return data;
        }
        const values = data.map(item => item[1]).sort((a, b) => a - b);
        const q1 = values[Math.floor(values.length * 0.25)];
        const q3 = values[Math.floor(values.length * 0.75)];
        const iqr = q3 - q1;
        const maxValue = q3 + iqr * 1.5;
        const minValue = q1 - iqr * 1.5;

        return data.filter(item => item[1] >= minValue && item[1] <= maxValue);
    }

    function renderChart(data) {
        if (chart) {
            chart.destroy();
        }

        const labels = data.map(item => new Date(item[0]));
        const values = data.map(item => item[1]);
        
        const durationDays = (labels.length > 1) ? (labels[labels.length - 1] - labels[0]) / (1000 * 60 * 60 * 24) : 0;

        chart = new Chart(chartCanvas.getContext('2d'), {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Sensor Reading',
                    data: values,
                    borderColor: 'rgba(75, 192, 192, 1)',
                    borderWidth: 1,
                    showLine: false,
                    pointRadius: 3,
                    pointBackgroundColor: 'rgba(75, 192, 192, 1)'
                }]
            },
            options: {
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: durationDays <= 3 ? 'hour' : 'day',
                            displayFormats: {
                                hour: 'MMM d, h a',
                                day: 'MMM d'
                            }
                        }
                    },
                    y: {
                        beginAtZero: false
                    }
                }
            }
        });

        const dataPointsContainer = document.getElementById('data-points');
        if (dataPointsContainer) {
            if (data.length > 0) {
                let table = '<table class="table table-sm table-striped">';
                table += '<thead><tr><th>Timestamp</th><th>Value</th></tr></thead><tbody>';
                data.forEach(item => {
                    table += `<tr><td>${new Date(item[0]).toLocaleString()}</td><td>${item[1]}</td></tr>`;
                });
                table += '</tbody></table>';
                dataPointsContainer.innerHTML = table;
            } else {
                dataPointsContainer.innerHTML = '<p class="text-muted">No data available for this time range.</p>';
            }
        }
    }
    
    async function fetchData(startDate, endDate) {
        const url = `${apiUrl}?start=${startDate.toISOString()}&end=${endDate.toISOString()}`;
        
        try {
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            rawData = await response.json();
            
            const filterSwitch = document.getElementById('filter-outliers-switch');
            const dataToRender = filterSwitch.checked ? filterOutliers(rawData) : rawData;
            renderChart(dataToRender);

        } catch (error) {
            console.error('Error fetching or rendering chart:', error);
            const dataPointsContainer = document.getElementById('data-points');
            if (dataPointsContainer) {
                dataPointsContainer.innerHTML = '<p class="text-danger">Error loading data.</p>';
            }
        }
    }

    const startDatePicker = document.getElementById('start-date-picker');
    const endDatePicker = document.getElementById('end-date-picker');
    const applyButton = document.getElementById('apply-date-range');
    const filterSwitch = document.getElementById('filter-outliers-switch');
    const presetButtons = document.querySelectorAll('.date-range-preset');

    const endDate = new Date();
    const startDate = new Date();
    startDate.setDate(endDate.getDate() - 7);

    startDatePicker.value = startDate.toISOString().split('T')[0];
    endDatePicker.value = endDate.toISOString().split('T')[0];

    if (applyButton) {
        applyButton.addEventListener('click', () => {
            const start = new Date(startDatePicker.value);
            const end = new Date(endDatePicker.value);
            fetchData(start, end);
            presetButtons.forEach(btn => btn.classList.remove('active'));
        });
    }

    presetButtons.forEach(button => {
        button.addEventListener('click', () => {
            presetButtons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');

            const range = button.dataset.range;
            const end = new Date();
            let start = new Date();
            
            if (range.endsWith('h')) {
                start.setHours(end.getHours() - parseInt(range));
            } else if (range.endsWith('d')) {
                start.setDate(end.getDate() - parseInt(range));
            }

            startDatePicker.value = start.toISOString().split('T')[0];
            endDatePicker.value = end.toISOString().split('T')[0];
            fetchData(start, end);
        });
    });

    if (filterSwitch) {
        filterSwitch.addEventListener('change', () => {
            const originalCount = rawData.length;
            const dataToRender = filterSwitch.checked ? filterOutliers(rawData) : rawData;
            const filteredCount = dataToRender.length;

            if (filterSwitch.checked) {
                const removedCount = originalCount - filteredCount;
                if (window.toastSystem) {
                    window.toastSystem.show({ message: `Filter removed ${removedCount} outliers.`, type: 'info' });
                }
            } else {
                if (window.toastSystem) {
                    window.toastSystem.show({ message: 'Outlier filter disabled.', type: 'info' });
                }
            }

            renderChart(dataToRender);
        });
    }

    fetchData(startDate, endDate);
}); 