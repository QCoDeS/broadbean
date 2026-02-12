/**
 * Elements Library Component for Designer
 * Displays saved waveform elements that can be loaded into the designer timeline for editing
 */

class ElementsLibraryDesigner {
    constructor() {
        this.elements = [];
        this.container = document.getElementById('elements-library');
        this.refreshBtn = document.getElementById('refresh-elements-btn');
        
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadElements();
    }

    bindEvents() {
        if (this.refreshBtn) {
            this.refreshBtn.addEventListener('click', () => {
                this.loadElements();
            });
        }
    }

    async loadElements() {
        try {
            this.showLoading();

            const response = await fetch('/api/elements/');
            const data = await response.json();

            if (!response.ok || !data.success) {
                throw new Error(data.error || 'Failed to load elements');
            }

            this.elements = data.elements;
            this.render();

        } catch (error) {
            console.error('Failed to load elements:', error);
            this.showError(error.message);
        }
    }

    showLoading() {
        this.container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-spinner fa-spin"></i>
                <p>Loading elements...</p>
            </div>
        `;
    }

    showError(message) {
        this.container.innerHTML = '';
        this.container.appendChild(
            CommonUtils.createEmptyState('fa-exclamation-triangle', 'Error', message)
        );
    }

    render() {
        if (this.elements.length === 0) {
            this.container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-inbox"></i>
                    <p class="empty-state-title">No Elements</p>
                    <p class="empty-state-text">Save waveform elements to load them here for editing</p>
                </div>
            `;
            return;
        }

        this.container.innerHTML = '';

        this.elements.forEach(element => {
            const card = this.createElementCard(element);
            this.container.appendChild(card);
        });
    }

    createElementCard(element) {
        const card = document.createElement('div');
        card.className = 'library-card';
        card.dataset.elementId = element.id;

        // Format duration
        const duration = CommonUtils.formatDuration(element.duration);
        const sampleRate = CommonUtils.formatSampleRate(element.sample_rate);

        card.innerHTML = `
            <div class="library-card-header">
                <span class="library-card-title">${CommonUtils.escapeHtml(element.name)}</span>
                <button class="library-card-delete-btn delete-element-btn" data-element-id="${element.id}" title="Delete">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
            ${element.description ? `<p class="library-card-description">${CommonUtils.escapeHtml(element.description)}</p>` : ''}
            <div class="element-card-actions">
                <button class="btn btn-sm btn-primary load-element-btn" data-element-id="${element.id}">
                    <i class="fas fa-download"></i> Load
                </button>
                <button class="btn btn-sm btn-warning edit-element-btn" data-element-id="${element.id}">
                    <i class="fas fa-edit"></i> Edit
                </button>
            </div>
        `;

        // Bind load button event
        const loadBtn = card.querySelector('.load-element-btn');
        loadBtn.addEventListener('click', (e) => {
            e.preventDefault();
            this.loadElementToTimeline(element);
        });

        // Bind edit button event
        const editBtn = card.querySelector('.edit-element-btn');
        editBtn.addEventListener('click', (e) => {
            e.preventDefault();
            this.editElement(element);
        });

        // Bind delete button event
        const deleteBtn = card.querySelector('.delete-element-btn');
        deleteBtn.addEventListener('click', (e) => {
            e.preventDefault();
            this.showDeleteConfirmation(element);
        });

        return card;
    }

    async loadElementToTimeline(element) {
        try {
            // Show loading state
            this.showLoadingOverlay('Loading element to timeline...');

            // Start element loading mode to prevent selection conflicts
            if (window.waveformDesigner) {
                window.waveformDesigner.startElementLoading();
            }

            // Fetch the detailed element data
            const response = await fetch(`/api/elements/${element.id}/`);
            const data = await response.json();

            if (!response.ok || !data.success) {
                throw new Error(data.error || 'Failed to load element details');
            }

            const elementData = data.element;

            // Load element data into timeline (appending to existing segments)
            await this.loadElementChannels(elementData);

            // Finish element loading and select first segment
            if (window.waveformDesigner) {
                window.waveformDesigner.finishElementLoading(true);
            }

            // Update preview
            if (window.waveformDesigner && window.waveformDesigner.previewPanel) {
                window.waveformDesigner.previewPanel.updatePreview();
            }

            this.hideLoadingOverlay();

            // Show success message
            this.showSuccessMessage(`Element "${element.name}" loaded successfully!`);

        } catch (error) {
            console.error('Failed to load element to timeline:', error);
            
            // Ensure loading state is cleared on error
            if (window.waveformDesigner) {
                window.waveformDesigner.finishElementLoading(false);
            }
            
            this.hideLoadingOverlay();
            this.showErrorMessage('Failed to load element: ' + error.message);
        }
    }

    async loadElementChannels(elementData) {
        const timeline = window.waveformDesigner?.timeline;
        if (!timeline) {
            throw new Error('Timeline not available');
        }

        console.log('=== START LOADING ELEMENT ===');
        console.log('Loading element with data:', elementData);
        console.log('Channels data:', elementData.channels);

        // Process the channels data - handle both old format (object) and new format (array)
        let channels;
        if (Array.isArray(elementData.channels)) {
            // New format: array of channel objects
            channels = elementData.channels;
        } else {
            // Old format: object with channel names as keys
            channels = Object.entries(elementData.channels).map(([name, data]) => ({
                name: name,
                ...data
            }));
        }
        
        for (const channelData of channels) {
            console.log(`\n--- Processing channel: ${channelData.name} ---`);
            console.log('Channel data:', channelData);
            
            // Add channel to timeline if not exists
            let channel = timeline.channels.find(c => c.name === channelData.name);
            if (!channel) {
                channel = timeline.addChannel(channelData.name);
                if (channelData.color) {
                    channel.color = channelData.color;
                }
            }

            // Load segments for this channel
            if (channelData.segments && Array.isArray(channelData.segments)) {
                console.log(`Loading ${channelData.segments.length} segments for channel ${channelData.name}`);
                for (let i = 0; i < channelData.segments.length; i++) {
                    const segmentData = channelData.segments[i];
                    console.log(`\n  Segment ${i + 1}/${channelData.segments.length}:`);
                    console.log('  - Type:', segmentData.type);
                    console.log('  - Name:', segmentData.name);
                    console.log('  - Duration:', segmentData.duration);
                    console.log('  - Parameters from DB:', segmentData.parameters);
                    console.log('  - Amplitude from DB:', segmentData.amplitude);
                    
                    // Add segment to channel
                    const segment = timeline.addSegmentToChannel(segmentData.type, channel.id);
                    if (segment) {
                        console.log('  Created segment with ID:', segment.id);
                        console.log('  Initial default parameters:', JSON.stringify(segment.parameters));
                        
                        // Update segment properties
                        this.updateSegmentProperties(segment, segmentData);
                        
                        // Check what's in the timeline's segments array
                        const timelineSegment = timeline.segments.find(s => s.id === segment.id);
                        console.log('  After updateSegmentProperties:');
                        console.log('    - segment.parameters:', JSON.stringify(segment.parameters));
                        console.log('    - timelineSegment.parameters:', JSON.stringify(timelineSegment?.parameters));
                        console.log('    - Are they the same object?', segment === timelineSegment);
                    } else {
                        console.error('  Failed to create segment for type:', segmentData.type);
                    }
                }
            } else {
                console.log('No segments found for channel:', channelData.name);
            }
        }

        console.log('\n=== BEFORE RENDER ===');
        console.log('All timeline segments:', timeline.segments.map(s => ({
            id: s.id,
            type: s.type,
            name: s.name,
            parameters: s.parameters
        })));

        // Re-render timeline
        timeline.render();
        
        console.log('=== END LOADING ELEMENT ===\n');
    }

    generateUniqueName(proposedName, currentSegmentId) {
        const timeline = window.waveformDesigner?.timeline;
        if (!timeline) {
            return proposedName;
        }

        // Get all existing segment names except the current segment being updated
        const existingNames = timeline.segments
            .filter(s => s.id !== currentSegmentId)
            .map(s => s.name);

        // If the proposed name doesn't conflict, use it as-is
        if (!existingNames.includes(proposedName)) {
            return proposedName;
        }

        // Extract the base type and current suffix from the proposed name
        // Expected format: "type_suffix" (e.g., "ramp_a", "sine_b")
        const match = proposedName.match(/^(.+?)_([a-z]+)$/);
        if (!match) {
            // If name doesn't match expected format, just append a counter
            let counter = 1;
            let newName = `${proposedName}_${counter}`;
            while (existingNames.includes(newName)) {
                counter++;
                newName = `${proposedName}_${counter}`;
            }
            return newName;
        }

        const [, baseType, ] = match;

        // Helper function to convert letter suffix to index (a=0, b=1, ..., z=25, aa=26, etc.)
        const lettersToIndex = (letters) => {
            let index = 0;
            for (let i = 0; i < letters.length; i++) {
                index = index * 26 + (letters.charCodeAt(i) - 96);
            }
            return index - 1;
        };

        // Helper function to convert index to letter suffix (0=a, 1=b, ..., 25=z, 26=aa, etc.)
        const indexToLetters = (index) => {
            let result = '';
            index += 1;
            while (index > 0) {
                index -= 1;
                result = String.fromCharCode(97 + (index % 26)) + result;
                index = Math.floor(index / 26);
            }
            return result || 'a';
        };

        // Find the next available suffix
        let suffixIndex = timeline.segments.length; // Start from total count
        let newName = `${baseType}_${indexToLetters(suffixIndex)}`;
        
        while (existingNames.includes(newName)) {
            suffixIndex++;
            newName = `${baseType}_${indexToLetters(suffixIndex)}`;
        }

        return newName;
    }

    updateSegmentProperties(segment, segmentData) {
        console.log('Updating segment properties for:', segment.type, 'with data:', segmentData);
        console.log('Initial segment state:', segment);
        
        // Get time unit conversion info from properties panel (if available)
        const getTimeConversion = () => {
            if (window.propertiesPanel && typeof window.propertiesPanel.getTimeScaleInfo === 'function') {
                return window.propertiesPanel.getTimeScaleInfo();
            }
            // Default to microseconds if properties panel not available
            return { factor: 1e6, symbol: 'μs' };
        };
        
        // Note: All time values from DB are in seconds, no conversion needed when loading
        // The properties panel handles conversion for display
        
        // Update basic properties
        if (segmentData.duration !== undefined) {
            segment.duration = segmentData.duration;
        }
        
        // Handle amplitude specially for ramp segments
        if (segment.type === 'ramp') {
            // For ramp segments, don't set amplitude directly - use start/end amplitudes
            console.log('Processing ramp segment - skipping amplitude, using start/end amplitudes');
        } else if (segmentData.amplitude !== undefined) {
            segment.amplitude = segmentData.amplitude;
        }
        
        // Handle name with uniqueness check
        if (segmentData.name !== undefined) {
            const uniqueName = this.generateUniqueName(segmentData.name, segment.id);
            segment.name = uniqueName;
            console.log('Assigned unique name:', uniqueName);
        }

        // Update parameters - replace defaults with saved parameters
        if (segmentData.parameters) {
            console.log('Setting parameters:', segmentData.parameters, 'replacing existing:', segment.parameters);
            
            // Replace parameters completely for loaded elements
            // Note: All time values from DB are in seconds, stored as-is
            // The properties panel handles conversion to display units
            segment.parameters = {...segmentData.parameters};
            console.log('Final parameters after replacement:', segment.parameters);
        }

        // Update markers
        if (segmentData.markers) {
            if (!segment.markers) {
                segment.markers = {
                    marker1: { delay: 0, duration: 0 },
                    marker2: { delay: 0, duration: 0 }
                };
            }
            // Merge saved markers with existing defaults
            Object.assign(segment.markers, segmentData.markers);
        }

        console.log('Final updated segment:', segment);
        
        // Persist changes back to the timeline
        if (window.waveformDesigner && window.waveformDesigner.timeline) {
            window.waveformDesigner.timeline.updateSegment(segment.id, {
                duration: segment.duration,
                amplitude: segment.amplitude,
                name: segment.name,
                parameters: segment.parameters,
                markers: segment.markers
            });
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
        // Create a temporary success message
        const successDiv = document.createElement('div');
        successDiv.className = 'alert alert-success';
        successDiv.style.position = 'fixed';
        successDiv.style.top = '20px';
        successDiv.style.right = '20px';
        successDiv.style.zIndex = '9999';
        successDiv.innerHTML = `
            <i class="fas fa-check-circle"></i> ${message}
        `;

        document.body.appendChild(successDiv);

        // Remove after 3 seconds
        setTimeout(() => {
            if (successDiv.parentNode) {
                successDiv.parentNode.removeChild(successDiv);
            }
        }, 3000);
    }

    showErrorMessage(message) {
        // Create a temporary error message
        const errorDiv = document.createElement('div');
        errorDiv.className = 'alert alert-danger';
        errorDiv.style.position = 'fixed';
        errorDiv.style.top = '20px';
        errorDiv.style.right = '20px';
        errorDiv.style.zIndex = '9999';
        errorDiv.innerHTML = `
            <i class="fas fa-exclamation-circle"></i> ${message}
        `;

        document.body.appendChild(errorDiv);

        // Remove after 5 seconds
        setTimeout(() => {
            if (errorDiv.parentNode) {
                errorDiv.parentNode.removeChild(errorDiv);
            }
        }, 5000);
    }

    async editElement(element) {
        try {
            // Show loading state
            this.showLoadingOverlay('Loading element for editing...');

            // Start element loading mode to prevent selection conflicts
            if (window.waveformDesigner) {
                window.waveformDesigner.startElementLoading();
            }

            // Fetch the detailed element data
            const response = await fetch(`/api/elements/${element.id}/`);
            const data = await response.json();

            if (!response.ok || !data.success) {
                throw new Error(data.error || 'Failed to load element details');
            }

            const elementData = data.element;

            // Clear current timeline
            if (window.waveformDesigner && window.waveformDesigner.timeline) {
                window.waveformDesigner.timeline.clearAll();
            }

            // Set global sample rate to match the element
            const sampleRateInput = document.getElementById('sample-rate');
            if (sampleRateInput) {
                sampleRateInput.value = elementData.sample_rate;
                // Trigger change event to update the application state
                sampleRateInput.dispatchEvent(new Event('change'));
            }

            // Load element data into timeline
            await this.loadElementChannels(elementData);

            // Enter edit mode in the main designer
            if (window.waveformDesigner) {
                window.waveformDesigner.enterEditMode(elementData);
                window.waveformDesigner.finishElementLoading(true);
            }

            // Update preview
            if (window.waveformDesigner && window.waveformDesigner.previewPanel) {
                window.waveformDesigner.previewPanel.updatePreview();
            }

            this.hideLoadingOverlay();

            // Show success message
            this.showSuccessMessage(`Element "${element.name}" loaded for editing!`);

        } catch (error) {
            console.error('Failed to load element for editing:', error);
            
            // Ensure loading state is cleared on error
            if (window.waveformDesigner) {
                window.waveformDesigner.finishElementLoading(false);
            }
            
            this.hideLoadingOverlay();
            this.showErrorMessage('Failed to load element for editing: ' + error.message);
        }
    }

    getElement(elementId) {
        return this.elements.find(el => el.id === elementId);
    }

    async showDeleteConfirmation(element) {
        const details = {
            'Duration': CommonUtils.formatDuration(element.duration),
            'Channels': element.num_channels.toString(),
            'Sample Rate': CommonUtils.formatSampleRate(element.sample_rate)
        };
        
        const confirmed = await ModalUtils.showConfirm(
            `Are you sure you want to delete the waveform element "${element.name}"?\n\nThis action cannot be undone.`,
            'Delete Waveform Element'
        );
        
        if (confirmed) {
            await this.deleteElement(element);
        }
    }

    async deleteElement(element) {
        try {
            // Show loading overlay
            this.showLoadingOverlay('Deleting element...');

            const response = await fetch(`/api/waveform/delete/${element.id}/`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                }
            });

            const data = await response.json();

            if (!response.ok || !data.success) {
                throw new Error(data.error || 'Failed to delete element');
            }

            this.hideLoadingOverlay();

            // Show success message
            this.showSuccessMessage(data.message);

            // Reload elements list
            await this.loadElements();

        } catch (error) {
            console.error('Failed to delete element:', error);
            this.hideLoadingOverlay();
            this.showErrorMessage('Failed to delete element: ' + error.message);
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
