// Chart.js configuration and initialization
class SensorChart {
    constructor(canvasId, options = {}) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) return;

        this.ctx = this.canvas.getContext('2d');
        this.chart = null;
        this.options = {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: options.label || 'Sensor Readings',
                    data: [],
                    borderWidth: 2,
                    tension: 0.3,
                    fill: false,
                    pointRadius: 3,
                    pointHoverRadius: 5
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: {
                    duration: 750,
                    easing: 'easeInOutQuart'
                },
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: 'minute',
                            displayFormats: {
                                minute: 'HH:mm'
                            }
                        }
                    },
                    y: {
                        beginAtZero: true
                    }
                },
                plugins: {
                    tooltip: {
                        enabled: true,
                        callbacks: {
                            label: function(context) {
                                return `Value: ${context.parsed.y}${options.unit || ''}`;
                            }
                        }
                    },
                    legend: {
                        display: false
                    }
                }
            }
        };

        // Apply CSS variables to chart
        const style = getComputedStyle(document.documentElement);
        this.options.data.datasets[0].borderColor = style.getPropertyValue('--chart-line-color').trim();
        this.options.scales.x.grid = { color: style.getPropertyValue('--chart-grid-color').trim() };
        this.options.scales.y.grid = { color: style.getPropertyValue('--chart-grid-color').trim() };
        this.options.plugins.tooltip.backgroundColor = style.getPropertyValue('--chart-tooltip-bg').trim();
        this.options.plugins.tooltip.titleFont.family = style.getPropertyValue('--sensor-font-mono');
        this.options.plugins.tooltip.bodyFont.family = style.getPropertyValue('--sensor-font-mono');
    }

    init(data = []) {
        if (!this.canvas) return;
        
        // Destroy existing chart if it exists
        if (this.chart) {
            this.chart.destroy();
        }

        // Format data for the chart
        const formattedData = data.map(reading => ({
            x: new Date(reading.timestamp),
            y: reading.value
        }));

        this.options.data.datasets[0].data = formattedData;
        this.chart = new Chart(this.ctx, this.options);
    }

    update(newData) {
        if (!this.chart) return;
        
        const formattedData = newData.map(reading => ({
            x: new Date(reading.timestamp),
            y: reading.value
        }));

        this.chart.data.datasets[0].data = formattedData;
        this.chart.update('none'); // Update without animation
    }
}

// Initialize chart when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    const readingsChart = document.getElementById('readingsChart');
    if (!readingsChart) return;

    // Get sensor data from the page
    const sensor = readingsChart.closest('[data-sensor-id]');
    if (!sensor) return;

    const sensorId = sensor.dataset.sensorId;
    const sensorUnit = sensor.dataset.unit || '';
    const sensorName = sensor.dataset.name || 'Sensor Readings';

    // Initialize the chart
    const chart = new SensorChart('readingsChart', {
        label: sensorName,
        unit: sensorUnit
    });

    // Fetch initial data
    fetchSensorReadings(sensorId).then(data => {
        chart.init(data);
    });

    // Update readings every minute
    setInterval(() => {
        fetchSensorReadings(sensorId).then(data => {
            chart.update(data);
        });
    }, 60000);
});

// Helper function to fetch sensor readings
async function fetchSensorReadings(sensorId) {
    try {
        const response = await fetch(`/api/sensors/${sensorId}/readings/`);
        if (!response.ok) throw new Error('Failed to fetch sensor readings');
        return await response.json();
    } catch (error) {
        console.error('Error fetching sensor readings:', error);
        return [];
    }
} 