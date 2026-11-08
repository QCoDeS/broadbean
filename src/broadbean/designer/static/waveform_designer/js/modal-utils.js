/**
 * Modal Utilities
 * Reusable modal dialogs for confirmations and alerts
 */

class ModalUtils {
    /**
     * Show a confirmation modal
     * @param {string} message - The confirmation message
     * @param {string} title - Optional title (default: "Confirm")
     * @returns {Promise<boolean>} - Resolves to true if confirmed, false if cancelled
     */
    static showConfirm(message, title = 'Confirm') {
        return new Promise((resolve) => {
            // Create modal HTML
            const modalHtml = `
                <div class="custom-modal" id="confirm-modal" style="display: flex;">
                    <div class="custom-modal-backdrop"></div>
                    <div class="custom-modal-dialog">
                        <div class="custom-modal-content">
                            <div class="custom-modal-header">
                                <h5 class="custom-modal-title">
                                    <i class="fas fa-question-circle"></i> ${CommonUtils.escapeHtml(title)}
                                </h5>
                            </div>
                            <div class="custom-modal-body">
                                <p>${CommonUtils.escapeHtml(message)}</p>
                            </div>
                            <div class="custom-modal-footer">
                                <button type="button" class="custom-modal-btn custom-modal-btn-secondary" id="confirm-cancel">
                                    <i class="fas fa-times"></i> Cancel
                                </button>
                                <button type="button" class="custom-modal-btn custom-modal-btn-danger" id="confirm-ok">
                                    <i class="fas fa-check"></i> Confirm
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            // Add to document
            const modalContainer = document.createElement('div');
            modalContainer.innerHTML = modalHtml;
            document.body.appendChild(modalContainer);

            const modal = document.getElementById('confirm-modal');
            const okBtn = document.getElementById('confirm-ok');
            const cancelBtn = document.getElementById('confirm-cancel');

            // Handle OK
            const handleOk = () => {
                cleanup();
                resolve(true);
            };

            // Handle Cancel
            const handleCancel = () => {
                cleanup();
                resolve(false);
            };

            // Cleanup function
            const cleanup = () => {
                if (modalContainer.parentNode) {
                    modalContainer.parentNode.removeChild(modalContainer);
                }
            };

            // Bind events
            okBtn.addEventListener('click', handleOk);
            cancelBtn.addEventListener('click', handleCancel);

            // Click backdrop to cancel
            const backdrop = modal.querySelector('.custom-modal-backdrop');
            backdrop.addEventListener('click', handleCancel);

            // ESC key to cancel
            const handleEscape = (e) => {
                if (e.key === 'Escape') {
                    handleCancel();
                    document.removeEventListener('keydown', handleEscape);
                }
            };
            document.addEventListener('keydown', handleEscape);

            // Focus OK button
            setTimeout(() => okBtn.focus(), 100);
        });
    }

    /**
     * Show an alert modal
     * @param {string} message - The alert message
     * @param {string} title - Optional title (default: "Alert")
     * @param {string} type - Optional type: 'info', 'success', 'warning', 'error' (default: 'info')
     * @returns {Promise<void>} - Resolves when dismissed
     */
    static showAlert(message, title = 'Alert', type = 'info') {
        return new Promise((resolve) => {
            // Icon based on type
            const icons = {
                info: 'fa-info-circle',
                success: 'fa-check-circle',
                warning: 'fa-exclamation-triangle',
                error: 'fa-exclamation-circle'
            };
            const icon = icons[type] || icons.info;

            // Create modal HTML
            const modalHtml = `
                <div class="custom-modal" id="alert-modal" style="display: flex;">
                    <div class="custom-modal-backdrop"></div>
                    <div class="custom-modal-dialog">
                        <div class="custom-modal-content">
                            <div class="custom-modal-header">
                                <h5 class="custom-modal-title">
                                    <i class="fas ${icon}"></i> ${CommonUtils.escapeHtml(title)}
                                </h5>
                            </div>
                            <div class="custom-modal-body">
                                <p>${CommonUtils.escapeHtml(message)}</p>
                            </div>
                            <div class="custom-modal-footer">
                                <button type="button" class="custom-modal-btn custom-modal-btn-primary" id="alert-ok">
                                    <i class="fas fa-check"></i> OK
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            // Add to document
            const modalContainer = document.createElement('div');
            modalContainer.innerHTML = modalHtml;
            document.body.appendChild(modalContainer);

            const modal = document.getElementById('alert-modal');
            const okBtn = document.getElementById('alert-ok');

            // Handle OK
            const handleOk = () => {
                cleanup();
                resolve();
            };

            // Cleanup function
            const cleanup = () => {
                if (modalContainer.parentNode) {
                    modalContainer.parentNode.removeChild(modalContainer);
                }
            };

            // Bind events
            okBtn.addEventListener('click', handleOk);

            // Click backdrop to dismiss
            const backdrop = modal.querySelector('.custom-modal-backdrop');
            backdrop.addEventListener('click', handleOk);

            // ESC or Enter key to dismiss
            const handleKey = (e) => {
                if (e.key === 'Escape' || e.key === 'Enter') {
                    handleOk();
                    document.removeEventListener('keydown', handleKey);
                }
            };
            document.addEventListener('keydown', handleKey);

            // Focus OK button
            setTimeout(() => okBtn.focus(), 100);
        });
    }

    /**
     * Show a warning modal with details
     * @param {string} message - The warning message
     * @param {string} title - Optional title (default: "Warning")
     * @param {Object} details - Optional details object with key-value pairs
     * @returns {Promise<void>} - Resolves when dismissed
     */
    static showWarning(message, title = 'Warning', details = null) {
        return new Promise((resolve) => {
            // Build details HTML if provided
            let detailsHtml = '';
            if (details) {
                const detailItems = Object.entries(details)
                    .map(([key, value]) => `<div><strong>${CommonUtils.escapeHtml(key)}:</strong> ${CommonUtils.escapeHtml(String(value))}</div>`)
                    .join('');
                detailsHtml = `
                    <div style="
                        background: #fff3cd;
                        border: 1px solid #ffeaa7;
                        border-radius: 4px;
                        padding: 10px;
                        margin: 10px 0;
                        font-size: 14px;
                    ">
                        ${detailItems}
                    </div>
                `;
            }

            // Create modal HTML
            const modalHtml = `
                <div class="custom-modal" id="warning-modal" style="display: flex;">
                    <div class="custom-modal-backdrop"></div>
                    <div class="custom-modal-dialog">
                        <div class="custom-modal-content">
                            <div class="custom-modal-header" style="background: #fff3cd; border-bottom: 1px solid #ffeaa7;">
                                <h5 class="custom-modal-title" style="color: #856404;">
                                    <i class="fas fa-exclamation-triangle"></i> ${CommonUtils.escapeHtml(title)}
                                </h5>
                            </div>
                            <div class="custom-modal-body">
                                <p>${CommonUtils.escapeHtml(message)}</p>
                                ${detailsHtml}
                            </div>
                            <div class="custom-modal-footer">
                                <button type="button" class="custom-modal-btn custom-modal-btn-warning" id="warning-ok">
                                    <i class="fas fa-check"></i> OK
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            // Add to document
            const modalContainer = document.createElement('div');
            modalContainer.innerHTML = modalHtml;
            document.body.appendChild(modalContainer);

            const modal = document.getElementById('warning-modal');
            const okBtn = document.getElementById('warning-ok');

            // Handle OK
            const handleOk = () => {
                cleanup();
                resolve();
            };

            // Cleanup function
            const cleanup = () => {
                if (modalContainer.parentNode) {
                    modalContainer.parentNode.removeChild(modalContainer);
                }
            };

            // Bind events
            okBtn.addEventListener('click', handleOk);

            // Click backdrop to dismiss
            const backdrop = modal.querySelector('.custom-modal-backdrop');
            backdrop.addEventListener('click', handleOk);

            // ESC or Enter key to dismiss
            const handleKey = (e) => {
                if (e.key === 'Escape' || e.key === 'Enter') {
                    handleOk();
                    document.removeEventListener('keydown', handleKey);
                }
            };
            document.addEventListener('keydown', handleKey);

            // Focus OK button
            setTimeout(() => okBtn.focus(), 100);
        });
    }

    /**
     * Show an info modal with optional code example
     * @param {string} message - The info message
     * @param {string} title - Optional title (default: "Information")
     * @param {string} example - Optional code example to display
     * @returns {Promise<void>} - Resolves when dismissed
     */
    static showInfo(message, title = 'Information', example = null) {
        return new Promise((resolve) => {
            // Build example HTML if provided
            let exampleHtml = '';
            if (example) {
                exampleHtml = `
                    <div style="
                        background: white;
                        padding: 8px;
                        border-radius: 3px;
                        font-family: monospace;
                        font-size: 13px;
                        margin-top: 8px;
                        color: #2c3e50;
                        border: 1px solid #e0e0e0;
                        white-space: pre-wrap;
                    ">${CommonUtils.escapeHtml(example)}</div>
                `;
            }

            // Create modal HTML
            const modalHtml = `
                <div class="custom-modal" id="info-modal" style="display: flex;">
                    <div class="custom-modal-backdrop"></div>
                    <div class="custom-modal-dialog">
                        <div class="custom-modal-content">
                            <div class="custom-modal-header">
                                <h5 class="custom-modal-title">
                                    <i class="fas fa-info-circle"></i> ${CommonUtils.escapeHtml(title)}
                                </h5>
                            </div>
                            <div class="custom-modal-body">
                                <p>${CommonUtils.escapeHtml(message)}</p>
                                ${exampleHtml}
                            </div>
                            <div class="custom-modal-footer">
                                <button type="button" class="custom-modal-btn custom-modal-btn-primary" id="info-ok">
                                    <i class="fas fa-check"></i> OK
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            // Add to document
            const modalContainer = document.createElement('div');
            modalContainer.innerHTML = modalHtml;
            document.body.appendChild(modalContainer);

            const modal = document.getElementById('info-modal');
            const okBtn = document.getElementById('info-ok');

            // Handle OK
            const handleOk = () => {
                cleanup();
                resolve();
            };

            // Cleanup function
            const cleanup = () => {
                if (modalContainer.parentNode) {
                    modalContainer.parentNode.removeChild(modalContainer);
                }
            };

            // Bind events
            okBtn.addEventListener('click', handleOk);

            // Click backdrop to dismiss
            const backdrop = modal.querySelector('.custom-modal-backdrop');
            backdrop.addEventListener('click', handleOk);

            // ESC or Enter key to dismiss
            const handleKey = (e) => {
                if (e.key === 'Escape' || e.key === 'Enter') {
                    handleOk();
                    document.removeEventListener('keydown', handleKey);
                }
            };
            document.addEventListener('keydown', handleKey);

            // Focus OK button
            setTimeout(() => okBtn.focus(), 100);
        });
    }

    /**
     * Show a save modal for saving/updating items
     * @param {Object} options - Configuration options
     * @param {string} options.title - Modal title
     * @param {string} options.nameLabel - Label for name field
     * @param {string} options.namePlaceholder - Placeholder for name field
     * @param {string} options.descriptionLabel - Label for description field
     * @param {boolean} options.showDescription - Whether to show description field
     * @param {string} options.initialName - Initial value for name field
     * @param {string} options.initialDescription - Initial value for description field
     * @param {string} options.saveButtonText - Text for save button
     * @param {Function} options.onSave - Callback function(name, description) to execute on save
     * @returns {Promise<boolean>} - Resolves to true if saved, false if cancelled
     */
    static showSaveModal(options = {}) {
        return new Promise((resolve, reject) => {
            const modal = document.getElementById('save-sequence-modal');
            if (!modal) {
                reject(new Error('Save modal not found in page'));
                return;
            }

            // Get modal elements
            const modalTitle = modal.querySelector('.custom-modal-title');
            const nameInput = document.getElementById('save-sequence-name');
            const descriptionInput = document.getElementById('save-sequence-description');
            const nameError = document.getElementById('save-seq-name-error');
            const saveBtn = document.getElementById('save-seq-modal-save');
            const cancelBtn = document.getElementById('save-seq-modal-cancel');
            const closeBtn = document.getElementById('save-seq-modal-close');

            // Set modal content based on options
            if (options.title && modalTitle) {
                const icon = modalTitle.querySelector('i');
                modalTitle.innerHTML = '';
                if (icon) {
                    modalTitle.appendChild(icon.cloneNode(true));
                    modalTitle.appendChild(document.createTextNode(' ' + options.title));
                } else {
                    modalTitle.textContent = options.title;
                }
            }

            if (nameInput) {
                nameInput.value = options.initialName || '';
                if (options.namePlaceholder) {
                    nameInput.placeholder = options.namePlaceholder;
                }
            }

            if (descriptionInput) {
                descriptionInput.value = options.initialDescription || '';
            }

            if (saveBtn && options.saveButtonText) {
                const icon = saveBtn.querySelector('i');
                saveBtn.innerHTML = '';
                if (icon) {
                    saveBtn.appendChild(icon.cloneNode(true));
                    saveBtn.appendChild(document.createTextNode(' ' + options.saveButtonText));
                } else {
                    saveBtn.textContent = options.saveButtonText;
                }
            }

            // Clear any previous validation errors
            if (nameInput) {
                nameInput.classList.remove('is-invalid');
            }
            if (nameError) {
                nameError.style.display = 'none';
            }

            // Show modal
            modal.style.display = 'flex';

            // Focus name input
            setTimeout(() => {
                if (nameInput) {
                    nameInput.focus();
                    nameInput.select();
                }
            }, 100);

            // Validation function
            const validateName = () => {
                if (!nameInput || !nameInput.value.trim()) {
                    if (nameInput) {
                        nameInput.classList.add('is-invalid');
                    }
                    if (nameError) {
                        nameError.style.display = 'block';
                    }
                    return false;
                }
                if (nameInput) {
                    nameInput.classList.remove('is-invalid');
                }
                if (nameError) {
                    nameError.style.display = 'none';
                }
                return true;
            };

            // Handle save
            const handleSave = async () => {
                if (!validateName()) {
                    return;
                }

                const name = nameInput ? nameInput.value.trim() : '';
                const description = descriptionInput ? descriptionInput.value.trim() : '';

                try {
                    // Call the onSave callback if provided
                    if (options.onSave) {
                        await options.onSave(name, description);
                    }
                    cleanup();
                    resolve(true);
                } catch (error) {
                    // If onSave throws an error, don't close modal
                    // The caller will handle showing the error
                    throw error;
                }
            };

            // Handle cancel
            const handleCancel = () => {
                cleanup();
                reject(new Error('Save cancelled'));
            };

            // Cleanup function
            const cleanup = () => {
                modal.style.display = 'none';
                if (nameInput) {
                    nameInput.value = '';
                    nameInput.classList.remove('is-invalid');
                }
                if (descriptionInput) {
                    descriptionInput.value = '';
                }
                if (nameError) {
                    nameError.style.display = 'none';
                }

                // Remove event listeners
                if (saveBtn) saveBtn.removeEventListener('click', handleSave);
                if (cancelBtn) cancelBtn.removeEventListener('click', handleCancel);
                if (closeBtn) closeBtn.removeEventListener('click', handleCancel);
                if (nameInput) nameInput.removeEventListener('keypress', handleEnter);
                document.removeEventListener('keydown', handleEscape);
            };

            // Bind events
            if (saveBtn) {
                saveBtn.addEventListener('click', handleSave);
            }
            if (cancelBtn) {
                cancelBtn.addEventListener('click', handleCancel);
            }
            if (closeBtn) {
                closeBtn.addEventListener('click', handleCancel);
            }

            // Enter key in name field triggers save
            const handleEnter = (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    handleSave();
                }
            };
            if (nameInput) {
                nameInput.addEventListener('keypress', handleEnter);
            }

            // ESC key to cancel
            const handleEscape = (e) => {
                if (e.key === 'Escape') {
                    handleCancel();
                }
            };
            document.addEventListener('keydown', handleEscape);

            // Click backdrop to cancel
            const backdrop = modal.querySelector('.custom-modal-backdrop');
            if (backdrop) {
                backdrop.addEventListener('click', handleCancel);
            }
        });
    }

}
