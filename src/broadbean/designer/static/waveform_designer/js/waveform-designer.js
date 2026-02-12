/**
 * Main Waveform Designer Application
 * Coordinates all components and handles global application state
 */

class WaveformDesigner {
    constructor() {
        this.timeline = null;
        this.segmentLibrary = null;
        this.propertiesPanel = null;
        this.previewPanel = null;
        
        // Centralized selection management
        this.selectedSegment = null;
        this.isLoadingElement = false;
        
        // Edit mode management
        this.editingElementId = null;
        this.originalElementData = null;
        
        this.isInitialized = false;
        
        this.init();
    }

    async init() {
        try {
            await this.initializeComponents();
            this.bindGlobalEvents();
            this.setupHeaderControls();
            
            this.isInitialized = true;
            console.log('Waveform Designer initialized successfully');
            
        } catch (error) {
            console.error('Failed to initialize Waveform Designer:', error);
            this.showError('Failed to initialize application');
        }
    }

    async initializeComponents() {
        // Initialize components in order
        this.timeline = new TimelineCards('channel-timeline');
        this.segmentLibrary = new SegmentLibrary();
        this.elementsLibrary = new ElementsLibraryDesigner();
        this.propertiesPanel = new PropertiesPanel();
        this.previewPanel = new PreviewPanel();
        
        // Set up cross-references
        this.propertiesPanel.setReferences(this.timeline, this.segmentLibrary);
        this.previewPanel.setReferences(this.timeline);
        
        // Set global reference for cross-component access
        window.propertiesPanel = this.propertiesPanel;
        window.waveformDesigner = this;
        
        // Wait for segment library to load
        await this.waitForSegmentLibrary();
    }

    async waitForSegmentLibrary() {
        let attempts = 0;
        const maxAttempts = 50; // 5 seconds max
        
        while (attempts < maxAttempts && this.segmentLibrary.segmentTypes.length === 0) {
            await new Promise(resolve => setTimeout(resolve, 100));
            attempts++;
        }
        
        if (this.segmentLibrary.segmentTypes.length === 0) {
            throw new Error('Failed to load segment types');
        }
    }

    bindGlobalEvents() {
        // Listen for timeline events to coordinate other panels
        window.addEventListener('addSegmentToTimeline', (e) => {
            if (this.timeline) {
                this.timeline.addSegment(e.detail.type);
            }
        });

        // Centralized selection management
        window.addEventListener('segmentSelected', (e) => {
            this.handleSegmentSelection(e.detail);
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            this.handleKeyboardShortcuts(e);
        });

        // Window resize
        window.addEventListener('resize', () => {
            this.handleResize();
        });

    }
    // Centralized selection management methods
    handleSegmentSelection(segment) {
        // Ignore selection events during bulk loading
        if (this.isLoadingElement) {
            return;
        }

        // Update centralized selection state
        this.selectedSegment = segment;
        
        // Ensure timeline selection is in sync
        if (this.timeline && this.timeline.selectedSegment !== segment) {
            this.timeline.selectedSegment = segment;
            this.timeline.render();
        }
        
        // Ensure properties panel is in sync
        if (this.propertiesPanel && this.propertiesPanel.selectedSegment !== segment) {
            this.propertiesPanel.selectedSegment = segment;
            this.propertiesPanel.renderProperties();
        }
    }

    selectSegment(segment) {
        // Public method for external components to trigger selection
        this.handleSegmentSelection(segment);
        
        // Dispatch event for any other listeners
        window.dispatchEvent(new CustomEvent('segmentSelected', { detail: segment }));
    }

    startElementLoading() {
        this.isLoadingElement = true;
        this.selectedSegment = null;
        
        // Reset ID counter for consistent unique ID generation during bulk loading
        if (this.timeline) {
            this.timeline.idCounter = 0;
        }
    }

    finishElementLoading(selectFirstSegment = true) {
        this.isLoadingElement = false;
        
        // Force re-render timeline to ensure proper visual state
        if (this.timeline) {
            this.timeline.forceRender();
        }
        
        // Process any pending selection events
        if (this.propertiesPanel && this.propertiesPanel.pendingSelection) {
            const pendingSegment = this.propertiesPanel.pendingSelection;
            this.propertiesPanel.pendingSelection = null;
            this.selectSegment(pendingSegment);
        } else if (selectFirstSegment && this.timeline && this.timeline.segments.length > 0) {
            // Select the first segment of the loaded element
            const firstSegment = this.timeline.segments[0];
            this.selectSegment(firstSegment);
        }
        
    }

    // Edit mode management methods
    enterEditMode(elementData) {
        this.editingElementId = elementData.id;
        this.originalElementData = elementData;
        this.updateEditModeUI(true);
    }

    exitEditMode() {
        this.editingElementId = null;
        this.originalElementData = null;
        this.updateEditModeUI(false);
    }

    isInEditMode() {
        return this.editingElementId !== null;
    }

    updateEditModeUI(isEditMode) {
        const saveBtn = document.getElementById('save-btn');
        const header = document.querySelector('.designer-header h1');

        if (isEditMode && this.originalElementData) {
            // Update save button
            if (saveBtn) {
                saveBtn.innerHTML = '<i class="fas fa-save"></i> Update Element';
                saveBtn.classList.remove('btn-success');
                saveBtn.classList.add('btn-warning');
            }

            // Update header to show edit mode
            if (header) {
                header.innerHTML = `
                    Waveform Designer 
                    <span class="edit-mode-indicator">
                        <i class="fas fa-edit"></i> 
                        Editing: ${this.originalElementData.name}
                    </span>
                `;
            }
        } else {
            // Reset to normal mode
            if (saveBtn) {
                saveBtn.innerHTML = '<i class="fas fa-save"></i> Save';
                saveBtn.classList.remove('btn-warning');
                saveBtn.classList.add('btn-success');
            }

            if (header) {
                header.textContent = 'Waveform Designer';
            }
        }
    }

    setupHeaderControls() {
        // Save button
        const saveBtn = document.getElementById('save-btn');
        if (saveBtn) {
            saveBtn.addEventListener('click', () => {
                this.saveWaveform();
            });
        }

        // Clear all button
        const clearBtn = document.getElementById('clear-btn');
        if (clearBtn) {
            clearBtn.addEventListener('click', async () => {
                const confirmed = await ModalUtils.showConfirm(
                    'Clear all segments? This action cannot be undone.',
                    'Clear All Segments'
                );
                if (confirmed) {
                    this.clearAll();
                }
            });
        }

        // Export button
        const exportBtn = document.getElementById('export-btn');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => {
                this.exportWaveform();
            });
        }

        // Add Channel button
        document.getElementById('add-channel-btn')?.addEventListener('click', () => {
            this.addChannel();
        });
    }

    handleKeyboardShortcuts(e) {
        // Delete key
        if (e.key === 'Delete' || e.key === 'Backspace') {
            const selectedSegment = this.propertiesPanel?.getSelectedSegment();
            if (selectedSegment && !this.isUserTyping()) {
                e.preventDefault();
                ModalUtils.showConfirm('Delete selected segment?', 'Delete Segment')
                    .then(confirmed => {
                        if (confirmed) {
                            this.timeline?.removeSegment(selectedSegment.id);
                        }
                    });
            }
        }
    }

    /**
     * Check if the user is currently typing in an input field
     * @returns {boolean} True if user is typing, false otherwise
     */
    isUserTyping() {
        const activeElement = document.activeElement;
        
        // Check for input elements
        if (activeElement.tagName === 'INPUT' || activeElement.tagName === 'TEXTAREA') {
            return true;
        }
        
        // Check for contenteditable elements
        if (activeElement.contentEditable === 'true') {
            return true;
        }
        
        // Check if we're in a modal dialog
        if (activeElement.closest('.modal')) {
            return true;
        }
        
        // Check for specific input types that should be protected
        if (activeElement.type === 'text' || 
            activeElement.type === 'email' || 
            activeElement.type === 'password' || 
            activeElement.type === 'number' ||
            activeElement.type === 'search') {
            return true;
        }
        
        return false;
    }

    handleResize() {
        // Re-render timeline cards
        this.timeline?.render();
        
        // Resize Plotly plot
        if (this.previewPanel?.plotDiv) {
            Plotly.Plots.resize(this.previewPanel.plotDiv);
        }
    }

    clearAll() {
        this.timeline?.clearAll();
    }

    addChannel() {
        console.log('Add channel button clicked!');
        if (this.timeline) {
            console.log('Timeline object exists, calling addChannel');
            const channel = this.timeline.addChannel();
            console.log('Channel created:', channel);
            this.showMessage(`Added ${channel.name}`);
        } else {
            console.log('Timeline object is null!');
        }
    }

    showLoading(message = 'Loading...') {
        CommonUtils.showLoading(message);
    }

    hideLoading() {
        CommonUtils.hideLoading();
    }

    showMessage(message, type = 'info') {
        CommonUtils.showToast(message, type === 'error' ? 'error' : 'success');
    }

    showError(message) {
        CommonUtils.showToast(message, 'error');
    }

    async saveWaveform() {
        try {
            // Get current waveform data
            const channels = this.timeline?.channels || [];

            // Check if there's any data to save
            if (channels.length === 0 || 
                !channels.some(ch => ch.segments && ch.segments.length > 0)) {
                this.showError('No waveform data to save. Add segments first.');
                return;
            }

            // Show save modal
            await this.showSaveModal();

        } catch (error) {
            console.error('Save failed:', error);
            this.showError(`Save failed: ${error.message}`);
        }
    }

    showSaveModal() {
        return new Promise((resolve, reject) => {
            const modal = document.getElementById('save-waveform-modal');
            const nameInput = document.getElementById('save-element-name');
            const descriptionInput = document.getElementById('save-element-description');
            const saveBtn = document.getElementById('save-modal-save');
            const cancelBtn = document.getElementById('save-modal-cancel');
            const closeBtn = document.getElementById('save-modal-close');
            const nameError = document.getElementById('save-name-error');
            const modalTitle = modal.querySelector('.custom-modal-title');

            // Configure modal for edit vs create mode
            const isEditMode = this.isInEditMode();
            
            if (isEditMode && this.originalElementData) {
                // Pre-populate with existing data for edit mode
                nameInput.value = this.originalElementData.name;
                descriptionInput.value = this.originalElementData.description || '';
                modalTitle.innerHTML = '<i class="fas fa-edit"></i> Update Waveform Element';
                saveBtn.innerHTML = '<i class="fas fa-save"></i> Update Element';
            } else {
                // Clear values for create mode
                nameInput.value = '';
                descriptionInput.value = '';
                modalTitle.innerHTML = '<i class="fas fa-save"></i> Save Waveform Element';
                saveBtn.innerHTML = '<i class="fas fa-save"></i> Save Element';
            }

            nameInput.classList.remove('is-invalid');
            nameError.style.display = 'none';

            // Show modal
            modal.style.display = 'flex';

            // Focus on name input
            setTimeout(() => nameInput.focus(), 100);

            // Validate name
            const validateName = () => {
                const name = nameInput.value.trim();
                if (!name) {
                    nameInput.classList.add('is-invalid');
                    nameError.style.display = 'block';
                    return false;
                }
                nameInput.classList.remove('is-invalid');
                nameError.style.display = 'none';
                return true;
            };

            // Handle save button click
            const handleSave = async () => {
                if (!validateName()) {
                    return;
                }

                const name = nameInput.value.trim();
                const description = descriptionInput.value.trim();

                // Hide modal
                modal.style.display = 'none';

                // Remove event listeners
                cleanup();

                // Perform save
                try {
                    await this.performSave(name, description);
                    resolve();
                } catch (error) {
                    reject(error);
                }
            };

            // Handle cancel
            const handleCancel = () => {
                modal.style.display = 'none';
                cleanup();
                reject(new Error('Save cancelled'));
            };

            // Cleanup function
            const cleanup = () => {
                saveBtn.removeEventListener('click', handleSave);
                cancelBtn.removeEventListener('click', handleCancel);
                closeBtn.removeEventListener('click', handleCancel);
                nameInput.removeEventListener('keypress', handleKeyPress);
            };

            // Handle enter key in name input
            const handleKeyPress = (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    handleSave();
                }
            };

            // Add event listeners
            saveBtn.addEventListener('click', handleSave);
            cancelBtn.addEventListener('click', handleCancel);
            closeBtn.addEventListener('click', handleCancel);
            nameInput.addEventListener('keypress', handleKeyPress);
        });
    }

    async performSave(name, description) {
        const channels = this.timeline?.channels || [];
        const sampleRate = this.propertiesPanel?.getSampleRate() || 1e9;
        const isEditMode = this.isInEditMode();

        // Prepare save data
        const saveData = {
            name: name,
            description: description,
            channels: channels.map(channel => ({
                name: channel.name,
                color: channel.color,
                segments: channel.segments.map(seg => ({
                    type: seg.type,
                    name: seg.name,
                    duration: seg.duration,
                    amplitude: seg.amplitude,
                    parameters: seg.parameters || {},
                    markers: seg.markers || { 
                        marker1: { delay: 0, duration: 0 }, 
                        marker2: { delay: 0, duration: 0 } 
                    }
                }))
            })),
            sample_rate: sampleRate
        };

        const loadingMessage = isEditMode ? 'Updating waveform element...' : 'Saving waveform element...';
        this.showLoading(loadingMessage);

        try {
            let url, method;
            
            if (isEditMode) {
                // Update existing element
                url = `/api/waveform/update/${this.editingElementId}/`;
                method = 'PUT';
            } else {
                // Create new element
                url = '/api/waveform/save/';
                method = 'POST';
            }

            // Send to backend
            const response = await fetch(url, {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(saveData)
            });

            this.hideLoading();

            const result = await response.json();

            if (!response.ok || !result.success) {
                throw new Error(result.error || `${isEditMode ? 'Update' : 'Save'} failed: ${response.status}`);
            }

            const successMessage = isEditMode ? 
                `Waveform element "${result.name}" updated successfully!` :
                `Waveform element "${result.name}" saved successfully!`;
            
            this.showMessage(successMessage);

            // Exit edit mode after successful update
            if (isEditMode) {
                this.exitEditMode();
            }

            // Refresh elements library to show updated data
            if (this.elementsLibrary) {
                this.elementsLibrary.loadElements();
            }

        } catch (error) {
            this.hideLoading();
            throw error;
        }
    }

    async exportWaveform() {
        try {
            // Get current waveform data
            const channels = this.timeline?.channels || [];
            const segments = this.timeline?.getSegments() || [];

            // Check if there's any data to export
            if (channels.length === 0 || 
                !channels.some(ch => ch.segments && ch.segments.length > 0)) {
                this.showError('No waveform data to export. Add segments first.');
                return;
            }

            // Get sample rate
            const sampleRate = this.propertiesPanel?.getSampleRate() || 1e9;

            // Generate filename with timestamp
            const now = new Date();
            const timestamp = now.toISOString().replace(/[:.]/g, '-').slice(0, -5);
            const filename = `waveform_design_${timestamp}`;

            // Prepare export data
            const exportData = {
                channels: channels.map(channel => ({
                    name: channel.name,
                    color: channel.color,
                    segments: channel.segments.map(seg => ({
                        type: seg.type,
                        name: seg.name,
                        duration: seg.duration,
                        amplitude: seg.amplitude,
                        parameters: seg.parameters || {},
                        markers: seg.markers || { 
                            marker1: { delay: 0, duration: 0 }, 
                            marker2: { delay: 0, duration: 0 } 
                        }
                    }))
                })),
                sample_rate: sampleRate,
                filename: filename
            };

            this.showLoading('Exporting waveform...');

            // Send to backend
            const response = await fetch('/api/waveform/export/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(exportData)
            });

            this.hideLoading();

            if (!response.ok) {
                throw new Error(`Export failed: ${response.status}`);
            }

            // Get the JSON blob and trigger download
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${filename}.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);

            this.showMessage('Waveform exported successfully!');

        } catch (error) {
            this.hideLoading();
            console.error('Export failed:', error);
            this.showError(`Export failed: ${error.message}`);
        }
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.waveformDesigner = new WaveformDesigner();
});
