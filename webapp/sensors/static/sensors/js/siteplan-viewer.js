document.addEventListener('DOMContentLoaded', function() {
    const container = document.getElementById('siteplan-container');
    if (!container) {
        return;
    }

    const imageUrl = container.dataset.imageUrl;
    const locations = JSON.parse(container.dataset.locations);

    if (imageUrl) {
        const img = new Image();
        img.src = imageUrl;
        img.onload = function() {
            container.style.width = `${img.width}px`;
            container.style.height = `${img.height}px`;
            container.style.backgroundImage = `url(${imageUrl})`;
            container.style.position = 'relative';

            locations.forEach(location => {
                const marker = document.createElement('a');
                marker.href = location.url;
                marker.className = 'siteplan-marker';
                marker.style.position = 'absolute';
                marker.style.left = `${location.x_pos}%`;
                marker.style.top = `${location.y_pos}%`;
                marker.title = location.name;
                
                const icon = document.createElement('i');
                icon.className = 'bi bi-geo-alt-fill';
                marker.appendChild(icon);

                container.appendChild(marker);
            });
        };
    }
}); 