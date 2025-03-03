/**
 * Background Task Indicator
 * Provides real-time updates for background tasks with minimal UI interruption
 */

class BackgroundTaskIndicator {
    constructor() {
        this.taskTypes = ['download', 'analyze'];
        this.refreshInterval = 2000; // Check for updates every 2 seconds
        this.intervalId = null;
        this.lastNotificationId = 0;
        
        // Create UI elements
        this.createIndicator();
        
        // Start monitoring
        this.startMonitoring();
    }

    checkTaskStatus() {
        fetch('/api/task_status')
            .then(response => response.json())
            .then(data => {
                this.updateIndicator(data);
                this.updateButtonStates(data);
            })
            .catch(error => console.error('Error checking task status:', error));
    }
    
    // New method to update button states based on task status
    updateButtonStates(data) {
        const downloadBtn = document.getElementById('downloadBtn');
        const analyzeBtn = document.getElementById('analyzeBtn');
        const advancedAnalysisBtn = document.getElementById('advancedAnalysisBtn');
        const aiInsightsBtn = document.getElementById('aiInsightsBtn');
        
        if (!downloadBtn || !analyzeBtn) return;
        
        // If download is running, disable download button
        if (data.download.running) {
            downloadBtn.disabled = true;
            downloadBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Downloading...';
        } else {
            downloadBtn.disabled = false;
            downloadBtn.innerHTML = '<i class="bi bi-download"></i> Download New Games';
        }
        
        // If analyze is running, disable analyze button
        if (data.analyze.running) {
            analyzeBtn.disabled = true;
            analyzeBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Analyzing...';
        } else if (document.getElementById('app-data')?.getAttribute('data-has-data') === 'true') {
            analyzeBtn.disabled = false;
            analyzeBtn.innerHTML = '<i class="bi bi-graph-up"></i> Analyze Games';
        }
        
        // Advanced analysis is only enabled if basic analysis is done
        if (advancedAnalysisBtn) {
            if (window.analysisCompleted) {
                advancedAnalysisBtn.disabled = false;
            } else {
                advancedAnalysisBtn.disabled = true;
            }
        }
        
        // AI Insights is only enabled if advanced analysis is done
        if (aiInsightsBtn) {
            if (window.advancedAnalysisCompleted) {
                aiInsightsBtn.disabled = false;
            } else {
                aiInsightsBtn.disabled = true;
            }
        }
    }
    
    checkNotifications() {
        fetch('/api/notifications')
            .then(response => response.json())
            .then(notifications => {
                if (notifications && notifications.length > 0) {
                    notifications.forEach(notification => {
                        this.showNotification(notification);
                        
                        // Set flags based on notification content
                        if (notification.type === 'success') {
                            if (notification.title === 'Analysis Complete') {
                                window.analysisCompleted = true;
                                
                                // Refresh the page after a short delay to show updated stats
                                setTimeout(() => {
                                    window.location.reload();
                                }, 2000);
                            } else if (notification.title === 'Advanced Analysis Complete') {
                                window.advancedAnalysisCompleted = true;
                            }
                        }
                    });
                }
            })
            .catch(error => console.error('Error checking notifications:', error));
    }
    
    createIndicator() {
        // Create indicator container
        const container = document.createElement('div');
        container.id = 'background-task-indicator';
        container.className = 'background-indicator';
        container.innerHTML = `
            <div class="indicator-toggle">
                <i class="bi bi-arrow-clockwise"></i>
                <span class="indicator-badge" style="display: none;"></span>
            </div>
            <div class="indicator-panel" style="display: none;">
                <div class="panel-header">
                    <h6>Background Tasks</h6>
                    <button class="btn-close btn-sm"></button>
                </div>
                <div class="panel-content">
                    <div class="task-list"></div>
                </div>
            </div>
        `;
        
        // Add to document
        document.body.appendChild(container);
        
        // Add event listeners
        const toggle = container.querySelector('.indicator-toggle');
        const panel = container.querySelector('.indicator-panel');
        const closeBtn = panel.querySelector('.btn-close');
        
        toggle.addEventListener('click', () => {
            panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
        });
        
        closeBtn.addEventListener('click', () => {
            panel.style.display = 'none';
        });
    }
    
    startMonitoring() {
        this.intervalId = setInterval(() => {
            this.checkTaskStatus();
            this.checkNotifications();
        }, this.refreshInterval);
    }
    
    stopMonitoring() {
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }
    }
    
    checkTaskStatus() {
        fetch('/api/task_status')
            .then(response => response.json())
            .then(data => this.updateIndicator(data))
            .catch(error => console.error('Error checking task status:', error));
    }
    
    checkNotifications() {
        fetch('/api/notifications')
            .then(response => response.json())
            .then(notifications => {
                if (notifications && notifications.length > 0) {
                    notifications.forEach(notification => {
                        this.showNotification(notification);
                    });
                }
            })
            .catch(error => console.error('Error checking notifications:', error));
    }
    
    updateIndicator(data) {
        const indicator = document.getElementById('background-task-indicator');
        const toggle = indicator.querySelector('.indicator-toggle');
        const badge = indicator.querySelector('.indicator-badge');
        const taskList = indicator.querySelector('.task-list');
        
        // Check if any tasks are running
        const runningTasks = this.taskTypes.filter(type => data[type].running);
        
        if (runningTasks.length > 0) {
            // Update toggle animation
            toggle.classList.add('active');
            
            // Update badge
            badge.style.display = 'flex';
            badge.textContent = runningTasks.length;
            
            // Clear task list and add running tasks
            taskList.innerHTML = '';
            
            this.taskTypes.forEach(type => {
                const taskData = data[type];
                if (taskData.running) {
                    const taskElement = this.createTaskElement(type, taskData);
                    taskList.appendChild(taskElement);
                }
            });
        } else {
            // No running tasks
            toggle.classList.remove('active');
            badge.style.display = 'none';
            
            // Show no tasks message if panel is empty
            if (taskList.children.length === 0) {
                taskList.innerHTML = '<div class="p-3 text-center text-muted">No active background tasks</div>';
            }
        }
    }
    
    createTaskElement(type, data) {
        const typeNames = {
            'download': 'Downloading Games',
            'analyze': 'Analyzing Games'
        };
        
        const taskElement = document.createElement('div');
        taskElement.className = 'task-item';
        taskElement.id = `task-${type}`;
        
        taskElement.innerHTML = `
            <div class="task-title">
                <span>${typeNames[type]}</span>
                <small>${this.formatElapsedTime(data.elapsed_seconds)}</small>
            </div>
            <div class="task-status">${data.status || 'Processing...'}</div>
            <div class="task-progress">
                <div class="task-progress-bar" style="width: ${data.percentage}%"></div>
            </div>
            <div class="task-details">
                ${data.current}/${data.total} games processed
            </div>
        `;
        
        return taskElement;
    }
    
    showNotification(data) {
        const id = ++this.lastNotificationId;
        const notification = document.createElement('div');
        notification.className = `notification ${data.type}`;
        notification.id = `notification-${id}`;
        
        notification.innerHTML = `
            <div class="notification-close">&times;</div>
            <div class="notification-title">${data.title}</div>
            <div class="notification-message">${data.message}</div>
        `;
        
        document.body.appendChild(notification);
        
        // Add close button handler
        const closeBtn = notification.querySelector('.notification-close');
        closeBtn.addEventListener('click', () => {
            this.removeNotification(id);
        });
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            this.removeNotification(id);
        }, 5000);
    }
    
    removeNotification(id) {
        const notification = document.getElementById(`notification-${id}`);
        if (notification) {
            notification.style.animation = 'fadeOut 0.3s ease-out';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }
    }
    
    formatElapsedTime(seconds) {
        if (!seconds) return '0s';
        
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = Math.floor(seconds % 60);
        
        if (minutes === 0) {
            return `${remainingSeconds}s`;
        } else {
            return `${minutes}m ${remainingSeconds}s`;
        }
    }
}

// Initialize the indicator when document is ready
document.addEventListener('DOMContentLoaded', () => {
    window.backgroundTaskIndicator = new BackgroundTaskIndicator();
});

    
 