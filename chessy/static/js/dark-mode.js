// Fix for Dark Mode Toggle
document.addEventListener('DOMContentLoaded', function() {
    // Get current theme from body class
    const currentTheme = document.body.classList.contains('dark-mode') ? 'dark-mode' : 'light';
    
    // Initialize theme button
    const themeBtn = document.getElementById('themeToggle');
    if (themeBtn) {
        themeBtn.addEventListener('click', function() {
            // Toggle body class directly first for immediate feedback
            document.body.classList.toggle('dark-mode');
            
            // Then send request to server to save preference
            fetch('/api/toggle_theme', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                console.log('Theme updated to:', data.theme);
            })
            .catch(error => {
                console.error('Error toggling theme:', error);
            });
        });
    }
});