/**
 * Main Waveform Sequencer Application
 * Coordinates all sequencer components
 */

class WaveformSequencer {
    constructor() {
        this.library = null;
        this.timeline = null;
        this.inspector = null;
        this.preview = null;
        
        this.isInitialized = false;
        
        this.init();
    }

    async init() {
        try {
            await this.initializeComponents();
            this.setupHeaderControls();
            
            // Make globally accessible for cross-component communication
            window.sequencerApp = this;
            
            this.isInitialized = true;
            console.log('Waveform Sequencer initialized successfully');
            
        } catch (error) {
            console.error('Failed to initialize Waveform Sequencer:', error);
            this.showError('Failed to initialize application');
        }
    }

    async initializeComponents() {
        // Initialize components in order
        this.library = new ElementLibrary();
        this.sequencesLibrary = new SequencesLibrarySequencer();
        this.timeline = new SequenceTimeline();
        this.inspector = new ElementInspector();
        this.preview = new SequencePreview();
    }

    setupHeaderControls() {
        // Save sequence button
        const saveBtn = document.getElementById('save-sequence-btn');
        if (saveBtn) {
            saveBtn.addEventListener('click', () => {
                this.saveSequence();
            });
        }

        // Clear sequence button
        const clearBtn = document.getElementById('clear-sequence-btn');
        if (clearBtn) {
            clearBtn.addEventListener('click', async () => {
                const confirmed = await ModalUtils.showConfirm(
                    'Clear entire sequence? This action cannot be undone.',
                    'Clear Sequence'
                );
                if (confirmed) {
                    this.clearSequence();
                }
            });
        }
    }

    clearSequence() {
        if (this.timeline) {
            this.timeline.clearSequence();
        }
        this.showMessage('Sequence cleared');
    }

    async saveSequence() {
        try {
            // Check if there's a sequence to save
            if (!this.timeline || this.timeline.sequenceElements.length === 0) {
                this.showError('No sequence to save. Add elements first.');
                return;
            }

            // Show save modal
            await this.showSaveModal();

        } catch (error) {
            if (error.message !== 'Save cancelled') {
                console.error('Save failed:', error);
                this.showError(`Save failed: ${error.message}`);
            }
        }
    }

    async showSaveModal() {
        const isUpdate = this.editMode && this.editMode.active;
        
        const result = await ModalUtils.showSaveModal({
            title: isUpdate ? 'Update Waveform Sequence' : 'Save Waveform Sequence',
            nameLabel: 'Sequence Name',
            namePlaceholder: 'Enter sequence name',
            descriptionLabel: 'Description (optional)',
            showDescription: true,
            initialName: isUpdate ? this.editMode.originalName : '',
            initialDescription: isUpdate ? this.editMode.originalDescription || '' : '',
            saveButtonText: isUpdate ? 'Update Sequence' : 'Save Sequence',
            onSave: async (name, description) => {
                await this.performSaveSequence(name, description);
            }
        });
        
        return result;
    }

    async performSaveSequence(name, description) {
        const sequenceData = this.timeline.getSequenceData();

        // Determine if we're updating or creating new
        const isUpdate = this.editMode && this.editMode.active;
        
        // Prepare save data
        const saveData = {
            name: name,
            description: description,
            elements: sequenceData
        };

        // Add sequence ID if updating
        if (isUpdate) {
            saveData.id = this.editMode.sequenceId;
        }

        this.showLoading(isUpdate ? 'Updating sequence...' : 'Saving sequence...');

        try {
            // Determine the URL and method based on operation
            let url, method;
            if (isUpdate) {
                url = `/api/sequences/${this.editMode.sequenceId}/`;
                method = 'PUT';
            } else {
                url = '/api/sequence/save/';
                method = 'POST';
            }

            // Send to backend
            const response = await fetch(url, {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify(saveData)
            });

            this.hideLoading();

            const result = await response.json();

            if (!response.ok || !result.success) {
                throw new Error(result.error || `${isUpdate ? 'Update' : 'Save'} failed: ${response.status}`);
            }

            this.showMessage(`Sequence "${result.name || name}" ${isUpdate ? 'updated' : 'saved'} successfully!`);
            
            // If we updated a sequence, exit edit mode and refresh the sequences library
            if (isUpdate) {
                this.exitEditMode();
                if (this.sequencesLibrary) {
                    this.sequencesLibrary.loadSequences();
                }
            }
        } catch (error) {
            this.hideLoading();
            throw error;
        }
    }

    getCSRFToken() {
        // Get CSRF token from Django
        const cookieValue = document.cookie
            .split('; ')
            .find(row => row.startsWith('csrftoken='))
            ?.split('=')[1];
        
        return cookieValue || '';
    }

    showLoading(message = 'Loading...') {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.style.display = 'flex';
            const text = overlay.querySelector('p');
            if (text) {
                text.textContent = message;
            }
        }
    }

    hideLoading() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.style.display = 'none';
        }
    }

    showMessage(message, type = 'info') {
        // Simple notification system
        const notification = document.createElement('div');
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: ${type === 'error' ? '#e74c3c' : '#27ae60'};
            color: white;
            padding: 12px 20px;
            border-radius: 4px;
            z-index: 10000;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            font-size: 14px;
        `;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 3000);
    }

    showError(message) {
        this.showMessage(message, 'error');
    }

    // Methods called by SequencesLibrarySequencer
    startSequenceLoading() {
        // Prevent user interactions during sequence loading
        this.isLoading = true;
        console.log('Started sequence loading mode');
    }

    finishSequenceLoading(success) {
        // Re-enable user interactions after sequence loading
        this.isLoading = false;
        if (success) {
            console.log('Sequence loading completed successfully');
            // Refresh the sequences library to show any changes
            if (this.sequencesLibrary) {
                this.sequencesLibrary.loadSequences();
            }
        } else {
            console.log('Sequence loading failed');
        }
    }

    enterEditMode(sequenceData) {
        // Enter edit mode for a loaded sequence
        this.editMode = {
            active: true,
            sequenceId: sequenceData.id,
            originalName: sequenceData.name,
            originalDescription: sequenceData.description
        };
        
        console.log(`Entered edit mode for sequence: ${sequenceData.name}`);
        
        // Update UI to show edit mode
        this.updateEditModeUI(true);
    }

    exitEditMode() {
        // Exit edit mode
        this.editMode = null;
        this.updateEditModeUI(false);
        console.log('Exited edit mode');
    }

    updateEditModeUI(inEditMode) {
        // Update header to show edit mode status
        const header = document.querySelector('.designer-header h1');
        if (header) {
            if (inEditMode && this.editMode) {
                header.textContent = `Waveform Sequencer - Editing: ${this.editMode.originalName}`;
                header.style.color = '#f39c12'; // Orange color for edit mode
            } else {
                header.textContent = 'Waveform Sequencer';
                header.style.color = ''; // Reset to default
            }
        }

        // Update save button text and color if in edit mode
        const saveBtn = document.getElementById('save-sequence-btn');
        if (saveBtn) {
            if (inEditMode) {
                saveBtn.innerHTML = '<i class="fas fa-save"></i> Update Sequence';
                saveBtn.className = 'btn btn-warning'; // Orange color for update mode
            } else {
                saveBtn.innerHTML = '<i class="fas fa-save"></i> Save Sequence';
                saveBtn.className = 'btn btn-success'; // Green color for save mode
            }
        }
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.sequencerApp = new WaveformSequencer();
});
