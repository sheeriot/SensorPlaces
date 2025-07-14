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
                    stepped: 'after',
                    fill: 'origin',
                    pointRadius: 1,
                    pointHoverRadius: 5,
                    xAxisID: 'x' // Plot on the primary time axis
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: {
                    duration: 0, // Disable animation for performance
                },
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                scales: {
                    x: { 
                        type: 'time',
                        time: {
                            unit: 'hour',
                            stepSize: 2,
                            displayFormats: { hour: 'HH:mm' }
                        },
                        ticks: {
                            major: { enabled: false }, // No day boundary lines on this axis
                            source: 'auto',
                            maxRotation: 0,
                            autoSkip: true,
                        },
                        grid: {
                            drawOnChartArea: true, 
                        },
                        border: {
                            display: false
                        }
                    },
                    x2: { 
                        type: 'time',
                        time: {
                            unit: 'day',
                            displayFormats: { day: 'eeee MMM dd yyyy' }
                        },
                        ticks: {
                            // Ensure the text color is correct and no tick mark is drawn
                            color: getComputedStyle(document.documentElement).getPropertyValue('--bs-body-color').trim(),
                            font: {
                                weight: 'bold',
                                size: 14,
                            }
                        },
                        grid: {
                            drawOnChartArea: false,
                            drawTicks: false, // Explicitly hide the tick marks
                        },
                        border: {
                            display: false
                        },
                        afterFit: (axis) => {
                            axis.height = axis.options.ticks.font.size * 1.5;
                        },
                        afterBuildTicks: (axis) => {
                            const chart = axis.chart;
                            const chartMin = chart.options.scales.x.min;
                            const chartMax = chart.options.scales.x.max;
                            
                            const newTicks = [];
                            
                            axis.ticks.forEach(tick => {
                                const tickDate = new Date(tick.value);
                                const dayStart = new Date(tickDate).setHours(0, 0, 0, 0);
                                const dayEnd = new Date(new Date(tickDate).setHours(23, 59, 59, 999));

                                const visibleDayStart = Math.max(dayStart, chartMin);
                                const visibleDayEnd = Math.min(dayEnd, chartMax);
                                
                                if (visibleDayStart < visibleDayEnd) {
                                    const midpoint = visibleDayStart + (visibleDayEnd - visibleDayStart) / 2;
                                    newTicks.push({
                                        ...tick,
                                        value: midpoint
                                    });
                                }
                            });
                            
                            axis.ticks = newTicks;
                        }
                    },
                    y: {
                        beginAtZero: true,
                        grid: {}
                    }
                },
                plugins: {
                    tooltip: {
                        enabled: true,
                        callbacks: {
                            label: function(context) {
                                return `Value: ${context.parsed.y}${options.unit || ''}`;
                            }
                        },
                        titleFont: {},
                        bodyFont: {}
                    },
                    legend: {
                        display: false
                    },
                    zoom: {
                        pan: {
                            enabled: true,
                            mode: 'x',
                        },
                        zoom: {
                            wheel: {
                                enabled: true,
                            },
                            pinch: {
                                enabled: true
                            },
                            mode: 'x',
                            onZoomComplete: ({chart}) => {
                                document.getElementById('reset-zoom-btn').classList.remove('d-none');
                            }
                        }
                    }
                }
            }
        };

        if (options.min) {
            this.options.options.scales.x.min = options.min;
            this.options.options.scales.x2.min = options.min;
        }
        if (options.max) {
            this.options.options.scales.x.max = options.max;
            this.options.options.scales.x2.max = options.max;
        }
    }

    init(data = []) {
        if (!this.canvas) return;
        
        // Destroy existing chart if it exists
        if (this.chart) {
            this.chart.destroy();
        }

        // Apply CSS variables to chart
        const style = getComputedStyle(document.documentElement);
        this.options.data.datasets[0].borderColor = style.getPropertyValue('--chart-line-color').trim();
        this.options.options.scales.x.grid.color = style.getPropertyValue('--chart-grid-color').trim();
        this.options.options.scales.y.grid.color = style.getPropertyValue('--chart-grid-color').trim();
        this.options.options.plugins.tooltip.backgroundColor = style.getPropertyValue('--chart-tooltip-bg').trim();
        this.options.options.plugins.tooltip.titleFont.family = style.getPropertyValue('--sensor-font-mono');
        this.options.options.plugins.tooltip.bodyFont.family = style.getPropertyValue('--sensor-font-mono');

        // Format data for the chart, injecting zero values for gaps
        const processedData = [];
        if (data.length > 0) {
            processedData.push({
                x: new Date(data[0].timestamp),
                y: data[0].value
            });

            for (let i = 1; i < data.length; i++) {
                const prev = data[i - 1];
                const curr = data[i];
                const prevTime = new Date(prev.timestamp).getTime();
                const currTime = new Date(curr.timestamp).getTime();

                // If there's a gap of more than 5 minutes, inject zero points
                const fiveMinutes = 5 * 60 * 1000;
                if (currTime - prevTime > fiveMinutes) {
                    processedData.push({ x: prevTime + 1, y: 0 }); // drop to zero
                    processedData.push({ x: currTime - 1, y: 0 }); // hold zero until next reading
                }
                
                processedData.push({
                    x: currTime,
                    y: curr.value
                });
            }
        }
        
        this.options.data.datasets[0].data = processedData;
        this.chart = new Chart(this.ctx, this.options);
    }

    update(newData) {
        if (!this.chart) return;
        
        // Format data for the chart, injecting zero values for gaps
        const processedData = [];
        if (newData.length > 0) {
            processedData.push({
                x: new Date(newData[0].timestamp),
                y: newData[0].value
            });

            for (let i = 1; i < newData.length; i++) {
                const prev = newData[i - 1];
                const curr = newData[i];
                const prevTime = new Date(prev.timestamp).getTime();
                const currTime = new Date(curr.timestamp).getTime();

                // If there's a gap of more than 5 minutes, inject zero points
                const fiveMinutes = 5 * 60 * 1000;
                if (currTime - prevTime > fiveMinutes) {
                    processedData.push({ x: prevTime + 1, y: 0 }); // drop to zero
                    processedData.push({ x: currTime - 1, y: 0 }); // hold zero until next reading
                }
                
                processedData.push({
                    x: currTime,
                    y: curr.value
                });
            }
        }

        this.chart.data.datasets[0].data = processedData;
        this.chart.update('none'); // Update without animation
    }

    resetZoom() {
        if(this.chart) {
            this.chart.resetZoom();
            document.getElementById('reset-zoom-btn').classList.add('d-none');
        }
    }
}

// Initialize chart when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    const debug = false; // Set to true to see console logs

    const readingsChartContainer = document.querySelector('.readings-chart-container');
    if (!readingsChartContainer) return;

    const sensorId = readingsChartContainer.dataset.sensorId;
    const placeSlug = readingsChartContainer.dataset.placeSlug;
    const sensorUnit = readingsChartContainer.dataset.unit || '';
    const sensorName = readingsChartContainer.dataset.name || 'Sensor Readings';

    const canvas = readingsChartContainer.querySelector('canvas');
    if (!canvas) return;
    const canvasId = `readings-chart-${sensorId}`;
    canvas.id = canvasId;

    // --- Chart State ---
    let currentRangeDays = 1; // Default to 1 day
    let chartInstance = null;
    let updateInterval = null;

    // Initialize the chart
    const chart = new SensorChart(canvasId, {
        label: sensorName,
        unit: sensorUnit,
    });
    
    const updateReadingsTable = (start, end) => {
        let url = `/api/${placeSlug}/sensor/${sensorId}/readings_table/`;
        if (start && end) {
            url += `?start=${start.toISOString()}&end=${end.toISOString()}`;
        }
        
        fetch(url)
            .then(response => response.json())
            .then(data => {
                const tableContainer = document.getElementById('readings-table-container');
                if (tableContainer) {
                    tableContainer.innerHTML = data.html;
                }
            })
            .catch(error => console.error('Error fetching readings table:', error));
    };

    const updateChartForRange = (days) => {
        currentRangeDays = days;
        const now = new Date();
        const start = new Date(now.getTime() - (days * 24 * 60 * 60 * 1000));
        
        if (debug) {
            console.log(`Fetching for last ${days} day(s)`);
            console.log("Chart Range (Local Time):", {
                start: start.toLocaleString(),
                end: now.toLocaleString()
            });
        }
        
        // Update both chart and table
        updateReadingsTable(start, now);
        
        fetchSensorReadings(sensorId, placeSlug, start, now).then(data => {
            if (debug) {
                console.log("Fetched Data Points:", data.length);
            }

            // Set chart axis limits
            chart.options.options.scales.x.min = start.getTime();
            chart.options.options.scales.x.max = now.getTime();
            chart.options.options.scales.x2.min = start.getTime();
            chart.options.options.scales.x2.max = now.getTime();
            
            // Adapt time step for the new range
            const timeStep = getAdaptiveTimeStep(start, now);
            chart.options.options.scales.x.time.unit = timeStep.unit;
            chart.options.options.scales.x.time.stepSize = timeStep.stepSize;

            if (!chart.chart) {
                chart.init(data);
                chartInstance = chart; // Store instance
            } else {
                chart.update(data);
                chart.resetZoom();
            }
            
            // Set up or reset the refresh interval
            if (updateInterval) clearInterval(updateInterval);
            updateInterval = setInterval(refreshChartData, 60000);
        });
    };
    
    const refreshChartData = () => {
        const now = new Date();
        const start = new Date(now.getTime() - (currentRangeDays * 24 * 60 * 60 * 1000));
        
        if(debug) console.log(`Refreshing data for range: ${currentRangeDays} day(s)`);

        fetchSensorReadings(sensorId, placeSlug, start, now).then(newData => {
            if (chartInstance) {
                chartInstance.update(newData);
                 if(debug) console.log('Chart data refreshed.');
            }
        });
    };

    // Initial load (last 24 hours)
    updateChartForRange(1);

    // Event listeners for time range buttons
    document.querySelectorAll('.btn-toolbar[role="toolbar"] .btn-group[aria-label="Time range"] button').forEach(button => {
        button.addEventListener('click', () => {
            const rangeDays = parseInt(button.dataset.range, 10);
            updateChartForRange(rangeDays);
        });
    });

    // Event listener for reset zoom button
    document.getElementById('reset-zoom-btn').addEventListener('click', () => {
        if(chartInstance) chartInstance.resetZoom();
    });
});

/**
 * Calculates the appropriate time unit and step size for the chart axis.
 * @param {Date} min The start date of the range.
 * @param {Date} max The end date of the range.
 * @returns {{unit: string, stepSize: number}}
 */
function getAdaptiveTimeStep(min, max) {
    const durationHours = (max.getTime() - min.getTime()) / (1000 * 60 * 60);

    if (durationHours <= 2) {
        return { unit: 'minute', stepSize: 15 };
    }
    if (durationHours <= 24) { // 1 day
        return { unit: 'hour', stepSize: 2 };
    }
    if (durationHours <= 3 * 24) { // 3 days
        return { unit: 'hour', stepSize: 6 };
    }
    if (durationHours <= 7 * 24) { // 7 days
        return { unit: 'day', stepSize: 1 };
    }
    if (durationHours <= 30 * 24) { // 30 days
        return { unit: 'day', stepSize: 3 };
    }
    // Default for longer ranges
    return { unit: 'week', stepSize: 1 };
}

// Helper function to fetch sensor readings
async function fetchSensorReadings(sensorId, placeSlug, start, end) {
    let url = `/api/${placeSlug}/sensor/${sensorId}/readings/`;
    if (start && end) {
        url += `?start=${start.toISOString()}&end=${end.toISOString()}`;
    }

    try {
        const response = await fetch(url);
        if (!response.ok) throw new Error('Failed to fetch sensor readings');
        return await response.json();
    } catch (error) {
        console.error('Error fetching sensor readings:', error);
        return [];
    }
}