// Date Range Filter Logic
document.addEventListener('DOMContentLoaded', function() {
    // Date range selector logic
    const dateRangeSelect = document.getElementById('dateRange');
    const customDateFields = document.querySelectorAll('.custom-date-range');
    const startDateInput = document.getElementById('startDate');
    const endDateInput = document.getElementById('endDate');
    
    // Initialize date inputs with defaults
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    
    // Format date as YYYY-MM-DD
    const formatDate = (date) => {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    };
    
    // Set today as the default end date
    endDateInput.value = formatDate(today);
    
    // Set 7 days ago as the default start date
    const sevenDaysAgo = new Date(today);
    sevenDaysAgo.setDate(today.getDate() - 7);
    startDateInput.value = formatDate(sevenDaysAgo);
    
    // Handle date range changes
    dateRangeSelect.addEventListener('change', function() {
        const selectedValue = this.value;
        
        // Show/hide custom date fields
        if (selectedValue === 'custom') {
            customDateFields.forEach(field => field.style.display = 'block');
        } else {
            customDateFields.forEach(field => field.style.display = 'none');
            
            // Set appropriate date ranges based on selection
            const today = new Date();
            let startDate = new Date(today);
            
            switch(selectedValue) {
                case 'yesterday':
                    startDate.setDate(today.getDate() - 1);
                    endDate = new Date(startDate);
                    break;
                case 'last7':
                    startDate.setDate(today.getDate() - 7);
                    endDate = new Date(today);
                    break;
                case 'last30':
                    startDate.setDate(today.getDate() - 30);
                    endDate = new Date(today);
                    break;
                case 'thisMonth':
                    startDate = new Date(today.getFullYear(), today.getMonth(), 1);
                    endDate = new Date(today);
                    break;
                case 'lastMonth':
                    startDate = new Date(today.getFullYear(), today.getMonth() - 1, 1);
                    endDate = new Date(today.getFullYear(), today.getMonth(), 0);
                    break;
            }
            
            // Update input fields even though they're hidden (for form submission)
            startDateInput.value = formatDate(startDate);
            endDateInput.value = formatDate(endDate);
        }
    });
    
    // Convert "Download Games" button to "Fetch Games" and update logic
    const fetchBtn = document.getElementById('fetchBtn');
    if (fetchBtn) {
        fetchBtn.addEventListener('click', function() {
            // Disable button to prevent multiple clicks
            this.disabled = true;
            this.innerHTML = '<i class="bi bi-hourglass-split"></i> Fetching Games...';
            
            // Get filter values
            const dateRange = document.getElementById('dateRange').value;
            const startDate = document.getElementById('startDate').value;
            const endDate = document.getElementById('endDate').value;
            const timeControl = document.getElementById('timeControl').value;
            
            // Build request payload
            const payload = {
                filters: {
                    dateRange: dateRange,
                    startDate: startDate,
                    endDate: endDate,
                    timeControl: timeControl
                }
            };
            
            // Use fetch to submit request
            fetch('/download', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify(payload)
            })
            .then(response => {
                // Handle both JSON responses and redirects
                if (response.redirected) {
                    window.location.href = response.url;
                    return Promise.reject('Redirected');
                }
                return response.json();
            })
            .then(data => {
                if (data.status === 'success') {
                    // Re-enable button with success indicator
                    this.innerHTML = '<i class="bi bi-download"></i> Fetch Games';
                    this.disabled = false;
                    
                    // Enable analyze button if download was successful
                    setTimeout(() => {
                        document.getElementById('analyzeBtn').disabled = false;
                    }, 1000);
                } else {
                    // Re-enable button with error indicator
                    this.innerHTML = '<i class="bi bi-download"></i> Fetch Games';
                    this.disabled = false;
                    alert('Error: ' + data.message);
                }
            })
            .catch(error => {
                if (error === 'Redirected') return;
                console.error('Error:', error);
                this.innerHTML = '<i class="bi bi-download"></i> Fetch Games';
                this.disabled = false;
                alert('An error occurred while fetching games.');
            });
        });
    }
    
    // Clear History Button
    const clearHistoryBtn = document.getElementById('clearHistoryBtn');
    if (clearHistoryBtn) {
        clearHistoryBtn.addEventListener('click', function() {
            if (confirm('Are you sure you want to clear your games history? This action cannot be undone.')) {
                this.disabled = true;
                this.innerHTML = '<i class="bi bi-hourglass-split"></i> Clearing...';
                
                fetch('/api/clear_history', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        alert('Games history cleared successfully');
                        window.location.reload();
                    } else {
                        alert('Error: ' + data.message);
                        this.disabled = false;
                        this.innerHTML = '<i class="bi bi-trash"></i> Clear Games History';
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('An error occurred while clearing games history.');
                    this.disabled = false;
                    this.innerHTML = '<i class="bi bi-trash"></i> Clear Games History';
                });
            }
        });
    }
    
    // Export Buttons
    const exportFormats = ['Excel', 'Csv', 'Json'];
    exportFormats.forEach(format => {
        const btn = document.getElementById(`export${format}`);
        if (btn) {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                
                fetch('/api/export_raw_games', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify({
                        format: format.toLowerCase()
                    })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success' && data.download_url) {
                        // Create a temporary link and trigger download
                        const link = document.createElement('a');
                        link.href = data.download_url;
                        link.download = data.filename || `games_export.${format.toLowerCase()}`;
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);
                    } else {
                        alert(data.message || `Error exporting to ${format}`);
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert(`An error occurred while exporting to ${format}`);
                });
            });
        }
    });
});

// Format time control from seconds to minutes
function formatTimeControl(seconds) {
    if (!seconds) return "Unknown";
    
    // Parse the time control
    let baseTime, increment = 0;
    
    if (typeof seconds === 'string') {
        if (seconds.includes('+')) {
            const parts = seconds.split('+');
            baseTime = parseInt(parts[0], 10);
            increment = parseInt(parts[1], 10);
        } else {
            baseTime = parseInt(seconds, 10);
        }
    } else {
        baseTime = seconds;
    }
    
    // Convert to minutes
    const minutes = Math.floor(baseTime / 60);
    const remainingSeconds = baseTime % 60;
    
    // Format the display
    let display = '';
    if (minutes > 0) {
        display += `${minutes}min`;
    }
    
    if (remainingSeconds > 0 || minutes === 0) {
        display += `${display ? ' ' : ''}${remainingSeconds}sec`;
    }
    
    if (increment > 0) {
        display += ` +${increment}sec`;
    }
    
    return display;
}

// Add this function to window scope for global access
window.formatTimeControl = formatTimeControl;

// Update any existing time control displays
function updateTimeControlDisplays() {
    document.querySelectorAll('.time-control-display').forEach(element => {
        const seconds = element.getAttribute('data-seconds');
        if (seconds) {
            element.textContent = formatTimeControl(seconds);
        }
    });
}

// Run once DOM is loaded
document.addEventListener('DOMContentLoaded', updateTimeControlDisplays);