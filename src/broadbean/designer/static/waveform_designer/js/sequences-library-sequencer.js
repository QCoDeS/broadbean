/**
 * Sequences Library Component for Sequencer
 * Displays saved waveform sequences that can be loaded into the sequencer timeline for editing
 */

class SequencesLibrarySequencer {
    constructor() {
        this.sequences = [];
        this.container = document.getElementById('sequences-library');
        this.refreshBtn = document.getElementById('refresh-sequences-btn');
        
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadSequences();
    }

    bindEvents() {
        if (this.refreshBtn) {
            this.refreshBtn.addEventListener('click', () => {
                this.loadSequences();
            });
        }
    }

    async loadSequences() {
        try {
            this.showLoading();

            const response = await fetch('/api/sequences/');
            const data = await response.json();

            if (!response.ok || !data.success) {
                throw new Error(data.error || 'Failed to load sequences');
            }

            this.sequences = data.sequences;
            this.render();

        } catch (error) {
            console.error('Failed to load sequences:', error);
            this.showError(error.message);
        }
    }

    showLoading() {
        this.container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-spinner fa-spin"></i>
                <p>Loading sequences...</p>
            </div>
        `;
    }

    showError(message) {
        this.container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-exclamation-triangle"></i>
                <p class="empty-state-title">Error</p>
                <p class="empty-state-text">${message}</p>
            </div>
        `;
    }

    render() {
        if (this.sequences.length === 0) {
            this.container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-inbox"></i>
                    <p class="empty-state-title">No Sequences</p>
                    <p class="empty-state-text">Save waveform sequences to load them here for editing</p>
                </div>
            `;
            return;
        }

        this.container.innerHTML = '';

        this.sequences.forEach(sequence => {
            const card = this.createSequenceCard(sequence);
            this.container.appendChild(card);
        });
    }

    createSequenceCard(sequence) {
        const card = document.createElement('div');
        card.className = 'library-card';
        card.dataset.sequenceId = sequence.id;

        // Format duration
        const duration = CommonUtils.formatDuration(sequence.total_duration);

        card.innerHTML = `
            <div class="library-card-header">
                <span class="library-card-title">${CommonUtils.escapeHtml(sequence.name)}</span>
                <button class="library-card-delete-btn delete-sequence-btn" data-sequence-id="${sequence.id}" title="Delete">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
            <div class="library-card-info">
                <i class="fas fa-list"></i> ${sequence.num_positions} position${sequence.num_positions !== 1 ? 's' : ''}
            </div>
            ${sequence.description ? `<p class="library-card-description">${CommonUtils.escapeHtml(sequence.description)}</p>` : ''}
            <div class="element-card-actions">
                <button class="btn btn-sm btn-primary load-sequence-btn" data-sequence-id="${sequence.id}">
                    <i class="fas fa-download"></i> Load
                </button>
                <button class="btn btn-sm btn-warning edit-sequence-btn" data-sequence-id="${sequence.id}">
                    <i class="fas fa-edit"></i> Edit
                </button>
            </div>
        `;

        // Bind load button event
        const loadBtn = card.querySelector('.load-sequence-btn');
        loadBtn.addEventListener('click', (e) => {
            e.preventDefault();
            this.loadSequenceToTimeline(sequence);
        });

        // Bind edit button event
        const editBtn = card.querySelector('.edit-sequence-btn');
        editBtn.addEventListener('click', (e) => {
            e.preventDefault();
            this.editSequence(sequence);
        });

        // Bind delete button event
        const deleteBtn = card.querySelector('.delete-sequence-btn');
        deleteBtn.addEventListener('click', (e) => {
            e.preventDefault();
            this.showDeleteConfirmation(sequence);
        });

        return card;
    }

    async loadSequenceToTimeline(sequence) {
        try {
            // Show loading state
            this.showLoadingOverlay('Loading sequence to timeline...');

            // Start sequence loading mode to prevent conflicts
            if (window.sequencerApp) {
                window.sequencerApp.startSequenceLoading();
            }

            // Fetch the detailed sequence data
            const response = await fetch(`/api/sequences/${sequence.id}/`);
            const data = await response.json();

            if (!response.ok || !data.success) {
                throw new Error(data.error || 'Failed to load sequence details');
            }

            const sequenceData = data.sequence;

            // Clear current timeline
            if (window.sequencerApp && window.sequencerApp.timeline) {
                window.sequencerApp.timeline.clearSequence();
            }

            // Load sequence data into timeline
            await this.loadSequenceElements(sequenceData);

            // Finish sequence loading
            if (window.sequencerApp) {
                window.sequencerApp.finishSequenceLoading(true);
            }

            // Update preview
            if (window.sequencerApp && window.sequencerApp.preview) {
                window.sequencerApp.preview.updatePreview();
            }

            this.hideLoadingOverlay();

            // Show success message
            this.showSuccessMessage(`Sequence "${sequence.name}" loaded successfully!`);

        } catch (error) {
            console.error('Failed to load sequence to timeline:', error);
            
            // Ensure loading state is cleared on error
            if (window.sequencerApp) {
                window.sequencerApp.finishSequenceLoading(false);
            }
            
            this.hideLoadingOverlay();
            CommonUtils.showError('Failed to load sequence: ' + error.message);
        }
    }

    async loadSequenceElements(sequenceData) {
        const timeline = window.sequencerApp?.timeline;
        if (!timeline) {
            throw new Error('Timeline not available');
        }

        console.log('Loading sequence with data:', sequenceData);

        // Reconstruct the sequence from element data
        if (sequenceData.elements && Array.isArray(sequenceData.elements)) {
            // Clear existing sequence first
            timeline.clearSequence();
            
            for (const elementData of sequenceData.elements) {
                console.log('Loading sequence element:', elementData);
                
                try {
                    // Fetch the full element data from the API
                    const elementResponse = await fetch(`/api/elements/${elementData.element_id}/`);
                    const elementResult = await elementResponse.json();
                    
                    if (!elementResponse.ok || !elementResult.success) {
                        throw new Error(`Failed to fetch element ${elementData.element_id}: ${elementResult.error}`);
                    }
                    
                    const fullElementData = elementResult.element;
                    
                    // Add element to timeline using the correct method
                    timeline.addElement(fullElementData);
                    
                    // Update the element with the sequence-specific properties
                    const updates = {
                        trigger_input: elementData.trigger_input,
                        repetitions: elementData.repetitions,
                        goto: elementData.goto_position
                    };
                    
                    // Include flags if they exist in the saved sequence
                    if (elementData.flags) {
                        updates.flags = elementData.flags;
                    }
                    
                    timeline.updateElement(elementData.position, updates);
                    
                } catch (error) {
                    console.error('Failed to load element:', elementData, error);
                    throw new Error(`Failed to load element "${elementData.element_name}": ${error.message}`);
                }
            }
        }

        // Timeline renders automatically when elements are added
    }

    async editSequence(sequence) {
        try {
            // Show loading state
            this.showLoadingOverlay('Loading sequence for editing...');

            // Start sequence loading mode
            if (window.sequencerApp) {
                window.sequencerApp.startSequenceLoading();
            }

            // Fetch the detailed sequence data
            const response = await fetch(`/api/sequences/${sequence.id}/`);
            const data = await response.json();

            if (!response.ok || !data.success) {
                throw new Error(data.error || 'Failed to load sequence details');
            }

            const sequenceData = data.sequence;

            // Clear current timeline
            if (window.sequencerApp && window.sequencerApp.timeline) {
                window.sequencerApp.timeline.clearSequence();
            }

            // Load sequence data into timeline
            await this.loadSequenceElements(sequenceData);

            // Enter edit mode in the main sequencer
            if (window.sequencerApp) {
                window.sequencerApp.enterEditMode(sequenceData);
                window.sequencerApp.finishSequenceLoading(true);
            }

            // Update preview
            if (window.sequencerApp && window.sequencerApp.preview) {
                window.sequencerApp.preview.updatePreview();
            }

            this.hideLoadingOverlay();

            // Show success message
            this.showSuccessMessage(`Sequence "${sequence.name}" loaded for editing!`);

        } catch (error) {
            console.error('Failed to load sequence for editing:', error);
            
            // Ensure loading state is cleared on error
            if (window.sequencerApp) {
                window.sequencerApp.finishSequenceLoading(false);
            }
            
            this.hideLoadingOverlay();
            CommonUtils.showError('Failed to load sequence for editing: ' + error.message);
        }
    }

    showLoadingOverlay(message = 'Loading...') {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.querySelector('p').textContent = message;
            overlay.style.display = 'flex';
        }
    }

    hideLoadingOverlay() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.style.display = 'none';
        }
    }

    showSuccessMessage(message) {
        CommonUtils.showSuccess(message);
    }

    formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString();
    }

    getSequence(sequenceId) {
        return this.sequences.find(seq => seq.id === sequenceId);
    }

    showDeleteConfirmation(sequence) {
        // Create confirmation dialog
        const modal = document.createElement('div');
        modal.className = 'custom-modal';
        modal.innerHTML = `
            <div class="custom-modal-backdrop"></div>
            <div class="custom-modal-dialog">
                <div class="custom-modal-content">
                    <div class="custom-modal-header" style="background: #e74c3c;">
                        <h5 class="custom-modal-title">
                            <i class="fas fa-exclamation-triangle"></i> Delete Waveform Sequence
                        </h5>
                        <button type="button" class="custom-modal-close">&times;</button>
                    </div>
                    <div class="custom-modal-body">
                        <div class="warning-content">
                            <div class="warning-icon" style="background: #e74c3c;">
                                <i class="fas fa-trash"></i>
                            </div>
                            <div class="warning-text">
                                <h6>Confirm Deletion</h6>
                                <p>Are you sure you want to delete the waveform sequence <strong>"${CommonUtils.escapeHtml(sequence.name)}"</strong>?</p>
                                <div class="warning-details">
                                    <div><strong>Duration:</strong> ${CommonUtils.formatDuration(sequence.total_duration)}</div>
                                    <div><strong>Positions:</strong> ${sequence.num_positions}</div>
                                    <div><strong>Created:</strong> ${this.formatDate(sequence.created_at)}</div>
                                </div>
                                <p class="warning-note">
                                    <i class="fas fa-exclamation-circle"></i>
                                    This action cannot be undone.
                                </p>
                            </div>
                        </div>
                    </div>
                    <div class="custom-modal-footer">
                        <button type="button" class="custom-modal-btn custom-modal-btn-secondary cancel-btn">
                            <i class="fas fa-times"></i> Cancel
                        </button>
                        <button type="button" class="custom-modal-btn custom-modal-btn-danger confirm-btn">
                            <i class="fas fa-trash"></i> Delete Sequence
                        </button>
                    </div>
                </div>
            </div>
        `;

        // Add to document
        document.body.appendChild(modal);

        // Show modal
        modal.style.display = 'block';

        // Bind events
        const closeBtn = modal.querySelector('.custom-modal-close');
        const cancelBtn = modal.querySelector('.cancel-btn');
        const confirmBtn = modal.querySelector('.confirm-btn');
        const backdrop = modal.querySelector('.custom-modal-backdrop');

        const closeModal = () => {
            modal.style.display = 'none';
            document.body.removeChild(modal);
        };

        closeBtn.addEventListener('click', closeModal);
        cancelBtn.addEventListener('click', closeModal);
        backdrop.addEventListener('click', closeModal);

        confirmBtn.addEventListener('click', async () => {
            closeModal();
            await this.deleteSequence(sequence);
        });
    }

    async deleteSequence(sequence) {
        try {
            // Show loading overlay
            this.showLoadingOverlay('Deleting sequence...');

            const response = await fetch(`/api/sequences/delete/${sequence.id}/`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                }
            });

            const data = await response.json();

            if (!response.ok || !data.success) {
                throw new Error(data.error || 'Failed to delete sequence');
            }

            this.hideLoadingOverlay();

            // Show success message
            this.showSuccessMessage(data.message);

            // Reload sequences list
            await this.loadSequences();

        } catch (error) {
            console.error('Failed to delete sequence:', error);
            this.hideLoadingOverlay();
            CommonUtils.showError('Failed to delete sequence: ' + error.message);
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
}
