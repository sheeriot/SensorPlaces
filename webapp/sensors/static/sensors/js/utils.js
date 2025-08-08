// Function to format a date object or string into a standardized timestamp format.
function formatTimestamp(date) {
    const d = (date instanceof Date) ? date : new Date(date);
    if (isNaN(d)) {
        return 'Invalid Date';
    }

    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    const dateStr = `${year}/${month}/${day}`;

    const timeStr = d.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
    });

    const shortTZ = new Intl.DateTimeFormat('en', { timeZoneName: 'short' })
        .formatToParts(d)
        .find(part => part.type === 'timeZoneName')?.value || '';

    const offset = -d.getTimezoneOffset();
    const offsetHours = Math.floor(Math.abs(offset) / 60);
    const offsetMinutes = Math.abs(offset) % 60;
    const offsetString = `${offset >= 0 ? '+' : '-'}${String(offsetHours).padStart(2, '0')}${String(offsetMinutes).padStart(2, '0')}`;
    
    return `${dateStr} ${timeStr} ${offsetString} (${shortTZ})`;
}
