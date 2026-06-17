/**
 * Common Utilities
 * Shared utility functions used across the waveform designer application
 */

class CommonUtils {
    /**
     * Format duration in human-readable units
     * @param {number} duration - Duration in seconds
     * @returns {string} Formatted duration string
     */
    static formatDuration(duration) {
        if (duration === null || duration === undefined) {
            return 'N/A';
        }

        if (duration < 1e-6) {
            return `${(duration * 1e9).toFixed(2)} ns`;
        } else if (duration < 1e-3) {
            return `${(duration * 1e6).toFixed(2)} μs`;
        } else if (duration < 1) {
            return `${(duration * 1e3).toFixed(2)} ms`;
        } else {
            return `${duration.toFixed(3)} s`;
        }
    }

    /**
     * Format sample rate in human-readable units
     * @param {number} rate - Sample rate in Hz
     * @returns {string} Formatted sample rate string
     */
    static formatSampleRate(rate) {
        if (rate === null || rate === undefined) {
            return 'N/A';
        }

        if (rate >= 1e9) {
            return `${(rate / 1e9).toFixed(2)} GHz`;
        } else if (rate >= 1e6) {
            return `${(rate / 1e6).toFixed(2)} MHz`;
        } else if (rate >= 1e3) {
            return `${(rate / 1e3).toFixed(2)} kHz`;
        } else {
            return `${rate.toFixed(0)} Hz`;
        }
    }

    /**
     * Escape HTML to prevent XSS attacks
     * @param {string} text - Text to escape
     * @returns {string} Escaped HTML string
     */
    static escapeHtml(text) {
        if (text === null || text === undefined) {
            return '';
        }
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Create a standardized empty state UI element
     * @param {string} icon - FontAwesome icon class (e.g., 'fa-list')
     * @param {string} title - Title text
     * @param {string} message - Optional message text
     * @returns {HTMLElement} Empty state div element
     */
    static createEmptyState(icon, title, message = '') {
        const emptyState = document.createElement('div');
        emptyState.className = 'empty-state';
        emptyState.style.cssText = 'padding: 40px 20px; text-align: center; color: #95a5a6;';

        emptyState.innerHTML = `
            <i class="fas ${icon}" style="font-size: 3rem; margin-bottom: 15px; opacity: 0.3;"></i>
            <p class="empty-state-title" style="font-size: 1.1rem; font-weight: 500; margin-bottom: 8px; color: #7f8c8d;">${CommonUtils.escapeHtml(title)}</p>
            ${message ? `<p class="empty-state-text" style="font-size: 0.9rem; color: #95a5a6;">${CommonUtils.escapeHtml(message)}</p>` : ''}
        `;

        return emptyState;
    }

    /**
     * Show an error message (console and optional UI)
     * @param {string} message - Error message
     * @param {HTMLElement} container - Optional container to display error in
     */
    static showError(message, container = null) {
        console.error('Error:', message);

        if (container) {
            const errorDiv = document.createElement('div');
            errorDiv.className = 'alert alert-danger';
            errorDiv.style.cssText = 'margin: 20px; padding: 15px; border-radius: 4px;';
            errorDiv.innerHTML = `
                <i class="fas fa-exclamation-circle"></i>
                <strong>Error:</strong> ${CommonUtils.escapeHtml(message)}
            `;
            container.innerHTML = '';
            container.appendChild(errorDiv);
        }
    }

    /**
     * Format a number value based on its magnitude
     * @param {number} value - Number to format
     * @param {number} decimals - Number of decimal places
     * @returns {string} Formatted number string
     */
    static formatNumber(value, decimals = 2) {
        if (value === null || value === undefined || isNaN(value)) {
            return 'N/A';
        }
        return value.toFixed(decimals);
    }

    /**
     * Debounce function to limit rapid function calls
     * @param {Function} func - Function to debounce
     * @param {number} wait - Wait time in milliseconds
     * @returns {Function} Debounced function
     */
    static debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    /**
     * Deep clone an object
     * @param {Object} obj - Object to clone
     * @returns {Object} Cloned object
     */
    static deepClone(obj) {
        if (obj === null || typeof obj !== 'object') {
            return obj;
        }
        return JSON.parse(JSON.stringify(obj));
    }

    /**
     * Generate a unique ID
     * @returns {string} Unique identifier
     */
    static generateId() {
        return `id_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    /**
     * Check if a value is a valid number
     * @param {any} value - Value to check
     * @returns {boolean} True if valid number
     */
    static isValidNumber(value) {
        return typeof value === 'number' && !isNaN(value) && isFinite(value);
    }

    /**
     * Clamp a value between min and max
     * @param {number} value - Value to clamp
     * @param {number} min - Minimum value
     * @param {number} max - Maximum value
     * @returns {number} Clamped value
     */
    static clamp(value, min, max) {
        return Math.min(Math.max(value, min), max);
    }

    /**
     * Show loading overlay
     * @param {string} message - Loading message to display
     */
    static showLoading(message = 'Loading...') {
        let overlay = document.getElementById('loading-overlay');
        if (!overlay) {
            // Create overlay if it doesn't exist
            overlay = document.createElement('div');
            overlay.id = 'loading-overlay';
            overlay.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.5);
                display: flex;
                justify-content: center;
                align-items: center;
                z-index: 9999;
            `;
            overlay.innerHTML = `
                <div style="background: white; padding: 30px; border-radius: 8px; text-align: center;">
                    <i class="fas fa-spinner fa-spin" style="font-size: 2rem; color: #3498db; margin-bottom: 15px;"></i>
                    <p id="loading-message" style="margin: 0; font-size: 1rem; color: #2c3e50;">${this.escapeHtml(message)}</p>
                </div>
            `;
            document.body.appendChild(overlay);
        } else {
            overlay.style.display = 'flex';
            const messageEl = overlay.querySelector('#loading-message');
            if (messageEl) {
                messageEl.textContent = message;
            }
        }
    }

    /**
     * Hide loading overlay
     */
    static hideLoading() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.style.display = 'none';
        }
    }

    /**
     * Show a temporary toast notification
     * @param {string} message - Message to display
     * @param {string} type - Type of message: 'info', 'success', 'warning', 'error'
     * @param {number} duration - Duration in milliseconds (default: 3000)
     */
    static showToast(message, type = 'info', duration = 3000) {
        const colors = {
            info: '#3498db',
            success: '#27ae60',
            warning: '#f39c12',
            error: '#e74c3c'
        };

        const notification = document.createElement('div');
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: ${colors[type] || colors.info};
            color: white;
            padding: 12px 20px;
            border-radius: 4px;
            z-index: 10000;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            font-size: 14px;
            max-width: 500px;
            animation: slideDown 0.3s ease-out;
        `;
        notification.textContent = message;

        document.body.appendChild(notification);

        setTimeout(() => {
            if (notification.parentNode) {
                notification.style.animation = 'slideUp 0.3s ease-out';
                setTimeout(() => {
                    if (notification.parentNode) {
                        notification.parentNode.removeChild(notification);
                    }
                }, 300);
            }
        }, duration);
    }
}

// Export for use in other modules
window.CommonUtils = CommonUtils;
