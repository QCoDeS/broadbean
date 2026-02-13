/**
 * Timeline Cards Component
 * Handles card-based timeline where segments are displayed as HTML cards in channel rows
 */

// Helper function: Convert numeric index to letter suffix
function indexToLetters(index) {
    let result = '';
    index += 1;
    while (index > 0) {
        index -= 1;
        result = String.fromCharCode(97 + (index % 26)) + result;
        index = Math.floor(index / 26);
    }
    return result || 'a';
}

class TimelineCards {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.channels = [];
        this.segments = [];
        this.selectedSegment = null;

        // Counter to ensure unique IDs during bulk operations
        this.idCounter = 0;

        // Drag reorder managers for each channel (initialized when channels are rendered)
        this.dragReorderManagers = new Map();

        this.initializeDefaultChannel();
        this.render();
        this.setupEventListeners();
    }

    // Channel Management
    initializeDefaultChannel() {
        if (this.channels.length === 0) {
            this.addChannel('Channel 1');
        }
    }

    addChannel(name = null) {
        const channelId = `channel_${Date.now()}`;
        const channelNumber = this.channels.length + 1;
        const defaultName = name || `Channel ${channelNumber}`;

        const channel = {
            id: channelId,
            name: defaultName,
            color: this.getChannelColor(channelNumber),
            segments: []
        };

        this.channels.push(channel);
        this.render();
        this.notifyChannelAdded(channel);

        return channel;
    }

    removeChannel(channelId) {
        const index = this.channels.findIndex(c => c.id === channelId);
        if (index !== -1 && this.channels.length > 1) {
            // Remove all segments from this channel
            const channel = this.channels[index];
            channel.segments.forEach(segment => {
                const segIndex = this.segments.findIndex(s => s.id === segment.id);
                if (segIndex !== -1) {
                    this.segments.splice(segIndex, 1);
                }
            });

            this.channels.splice(index, 1);
            this.render();
            this.notifyChannelRemoved(channelId);
        }
    }

    getChannelColor(channelNumber) {
        const colors = [
            '#3498db', '#e74c3c', '#2ecc71', '#f39c12',
            '#9b59b6', '#1abc9c', '#34495e', '#e67e22'
        ];
        return colors[(channelNumber - 1) % colors.length];
    }

    // Segment Management
    addSegmentToChannel(type, channelId) {
        const channel = this.channels.find(c => c.id === channelId);
        if (!channel) {
            console.error('Channel not found:', channelId);
            return null;
        }

        // Generate unique ID that works for bulk operations
        const isLoadingElement = window.waveformDesigner?.isLoadingElement || false;
        let id;
        if (isLoadingElement) {
            // During bulk loading, use timestamp + counter to ensure uniqueness
            this.idCounter++;
            id = `${Date.now()}_${this.idCounter}`;
        } else {
            // For normal operations, use simple timestamp
            id = Date.now().toString();
        }

        const sampleRate = this.getSampleRate();
        const minDuration = 1 / sampleRate;
        const defaultDuration = Math.max(1e-6, minDuration);

        const totalSegments = this.getAllSegmentCount();
        const letterSuffix = indexToLetters(totalSegments);
        const defaultName = `${type}_${letterSuffix}`;

        const segment = {
            id: id,
            type: type,
            name: defaultName,
            duration: defaultDuration,
            amplitude: type !== 'ramp' ? 1.0 : undefined,
            color: this.getSegmentColor(type),
            parameters: this.getDefaultParameters(type),
            channelId: channelId,
            markers: {
                marker1: { delay: 0, duration: 0 },
                marker2: { delay: 0, duration: 0 }
            }
        };

        channel.segments.push(segment);
        this.segments.push(segment);

        // Auto-select the newly added segment (unless loading an element in bulk)
        if (!isLoadingElement) {
            this.selectSegment(segment);
            this.render();
        }

        this.notifySegmentAdded(segment);

        return segment;
    }

    removeSegment(segmentId) {
        // Find and remove from segments array
        const segIndex = this.segments.findIndex(s => s.id === segmentId);
        if (segIndex !== -1) {
            const segment = this.segments[segIndex];
            this.segments.splice(segIndex, 1);

            // Remove from channel
            const channel = this.channels.find(c => c.id === segment.channelId);
            if (channel) {
                const channelSegIndex = channel.segments.findIndex(s => s.id === segmentId);
                if (channelSegIndex !== -1) {
                    channel.segments.splice(channelSegIndex, 1);
                }
            }

            if (this.selectedSegment && this.selectedSegment.id === segmentId) {
                this.selectedSegment = null;
            }

            this.render();
            this.notifySegmentRemoved(segmentId);
        }
    }

    selectSegment(segment) {
        // Ensure only one segment is selected
        if (this.selectedSegment && this.selectedSegment.id === segment?.id) {
            return; // Already selected
        }

        // Clear previous selection
        this.selectedSegment = null;

        // Set new selection
        this.selectedSegment = segment;

        // Only render if not in bulk loading mode
        const isLoadingElement = window.waveformDesigner?.isLoadingElement || false;
        if (!isLoadingElement) {
            this.render();
        }

        this.notifySegmentSelected(segment);
    }

    updateSegment(segmentId, updates) {
        const segment = this.segments.find(s => s.id === segmentId);
        if (segment) {
            Object.assign(segment, updates);
            this.render();
            this.notifySegmentUpdated(segment);
        }
    }

    getSegmentColor(type) {
        const colors = {
            'ramp': '#3498db',
            'sine': '#e74c3c',
            'square': '#f39c12',
            'gaussian': '#9b59b6',
            'exponential': '#2ecc71',
            'custom': '#34495e'
        };
        return colors[type] || '#95a5a6';
    }

    getDefaultParameters(type) {
        console.log('Getting default parameters for type:', type);
        console.log('window.SEGMENT_DEFAULTS available:', !!window.SEGMENT_DEFAULTS);
        console.log('window.SEGMENT_DEFAULTS content:', window.SEGMENT_DEFAULTS);
        const defaults = window.SEGMENT_DEFAULTS?.[type] || {};
        console.log('Retrieved defaults for', type, ':', defaults);
        return defaults;
    }

    getSampleRate() {
        if (window.propertiesPanel && window.propertiesPanel.sampleRate) {
            return window.propertiesPanel.sampleRate;
        }
        return window.waveformDesignerSettings?.defaultSampleRate || 25e9;
    }

    getAllSegmentCount() {
        let count = 0;
        for (const channel of this.channels) {
            count += channel.segments.length;
        }
        return count;
    }

    // Rendering
    render() {
        this.container.innerHTML = '';

        if (this.channels.length === 0) {
            this.renderPlaceholder();
        } else {
            this.container.classList.add('has-content');
            this.channels.forEach(channel => this.renderChannel(channel));
        }
    }

    renderPlaceholder() {
        this.container.classList.remove('has-content');
        this.container.innerHTML = `
            <div class="timeline-placeholder">
                <i class="fas fa-wave-square"></i>
                <p>Click "Add Channel" to get started, then drag segments from the library</p>
            </div>
        `;
    }

    renderChannel(channel) {
        const channelRow = document.createElement('div');
        channelRow.className = 'channel-row';
        channelRow.dataset.channelId = channel.id;

        // Channel header
        const header = document.createElement('div');
        header.className = 'channel-header';
        header.innerHTML = `
            <div class="channel-info">
                <div class="channel-color-indicator" style="background-color: ${channel.color};"></div>
                <span class="channel-name">${channel.name}</span>
            </div>
            <div class="channel-actions">
                ${this.channels.length > 1 ? `
                    <button class="channel-action-btn delete" data-action="delete">
                        <i class="fas fa-trash"></i>
                    </button>
                ` : ''}
            </div>
        `;

        // Channel segments container
        const segmentsContainer = document.createElement('div');
        segmentsContainer.className = channel.segments.length === 0 ? 'channel-segments empty' : 'channel-segments';
        segmentsContainer.dataset.channelId = channel.id;

        // Render segments
        channel.segments.forEach(segment => {
            const segmentCard = this.createSegmentCard(segment);
            segmentsContainer.appendChild(segmentCard);
        });

        channelRow.appendChild(header);
        channelRow.appendChild(segmentsContainer);
        this.container.appendChild(channelRow);

        // Setup drag and drop for channel
        this.setupChannelDragDrop(segmentsContainer, channel.id);

        // Setup drag-to-reorder for segments within the channel
        this.setupSegmentReordering(segmentsContainer, channel.id);
    }

    setupSegmentReordering(container, channelId) {
        // Clean up existing manager for this channel if any
        if (this.dragReorderManagers.has(channelId)) {
            this.dragReorderManagers.get(channelId).destroy();
        }

        // Create new drag reorder manager for this channel
        const manager = new DragReorderManager({
            container: container,
            cardSelector: '.segment-card',
            orientation: 'horizontal',
            dragDataType: 'application/x-segment-reorder',
            getCardId: (card) => card.dataset.segmentId,
            canDragCard: (card) => {
                // Allow dragging unless it's being clicked on an action button
                return !card.querySelector('.segment-card-actions:hover');
            },
            onReorder: (data) => {
                this.handleSegmentReorder(channelId, data);
            }
        });

        this.dragReorderManagers.set(channelId, manager);
    }

    handleSegmentReorder(channelId, data) {
        const channel = this.channels.find(c => c.id === channelId);
        if (!channel) return;

        // Find the indices
        const draggedIndex = channel.segments.findIndex(s => s.id === data.draggedId);
        const targetIndex = channel.segments.findIndex(s => s.id === data.targetId);

        if (draggedIndex === -1 || targetIndex === -1) return;

        // Calculate new index based on drop position
        let newIndex = targetIndex;
        if (data.position === 'after') {
            newIndex = targetIndex + 1;
        }

        // Adjust if dragging from before the target
        if (draggedIndex < targetIndex && data.position === 'before') {
            newIndex = targetIndex - 1;
        }

        // Don't do anything if dropping in the same position
        if (draggedIndex === newIndex || (draggedIndex + 1 === newIndex && data.position === 'after')) {
            return;
        }

        // Perform the reorder
        const [movedSegment] = channel.segments.splice(draggedIndex, 1);
        channel.segments.splice(newIndex, 0, movedSegment);

        // Re-render and notify
        this.render();
        this.notifySegmentUpdated(movedSegment);
    }

    createSegmentCard(segment) {
        const card = document.createElement('div');
        card.className = 'segment-card';
        card.dataset.segmentId = segment.id;
        card.dataset.type = segment.type;
        card.draggable = true;

        if (this.selectedSegment && this.selectedSegment.id === segment.id) {
            card.classList.add('selected');
        }

        const icon = this.getSegmentIcon(segment.type);

        // For waituntil segments, show absolute_time instead of duration
        let timeDisplay;
        if (segment.type === 'waituntil') {
            const absoluteTime = segment.parameters?.absolute_time || 0;
            timeDisplay = `
                <div class="segment-detail">
                    <i class="fas fa-stopwatch"></i>
                    <span class="segment-detail-value">Until: ${CommonUtils.formatDuration(absoluteTime)}</span>
                </div>
            `;
        } else {
            const duration = CommonUtils.formatDuration(segment.duration);
            timeDisplay = `
                <div class="segment-detail">
                    <i class="fas fa-clock"></i>
                    <span class="segment-detail-value">${duration}</span>
                </div>
            `;
        }

        card.innerHTML = `
            <div class="segment-card-header">
                <i class="segment-card-icon ${icon}"></i>
                <span class="segment-card-title">${segment.name || segment.type}</span>
                <div class="segment-card-actions">
                    <button class="segment-action-btn move-left" data-action="move-left" title="Move Left" ${this.isFirstSegment(segment) ? 'disabled' : ''}>
                        <i class="fas fa-arrow-left"></i>
                    </button>
                    <button class="segment-action-btn move-right" data-action="move-right" title="Move Right" ${this.isLastSegment(segment) ? 'disabled' : ''}>
                        <i class="fas fa-arrow-right"></i>
                    </button>
                    <button class="segment-action-btn delete" data-action="delete">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            </div>
            <div class="segment-card-body">
                ${timeDisplay}
                ${this.getAmplitudeDisplay(segment)}
            </div>
        `;

        // Event listeners
        card.addEventListener('click', (e) => {
            if (!e.target.closest('.segment-action-btn')) {
                this.selectSegment(segment);
            }
        });

        card.addEventListener('dragstart', (e) => {
            card.classList.add('dragging');
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', segment.id);
        });

        card.addEventListener('dragend', () => {
            card.classList.remove('dragging');
        });

        // Add event listeners for move buttons
        const moveLeftBtn = card.querySelector('.segment-action-btn.move-left');
        const moveRightBtn = card.querySelector('.segment-action-btn.move-right');
        const deleteBtn = card.querySelector('.segment-action-btn.delete');

        if (moveLeftBtn) {
            moveLeftBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.moveSegment(segment, 'left');
            });
        }

        if (moveRightBtn) {
            moveRightBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.moveSegment(segment, 'right');
            });
        }

        if (deleteBtn) {
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.removeSegment(segment.id);
            });
        }

        return card;
    }

    getSegmentIcon(type) {
        const icons = {
            'ramp': 'fas fa-chart-line',
            'sine': 'fas fa-wave-square',
            'square': 'fas fa-square',
            'gaussian': 'fas fa-mountain',
            'exponential': 'fas fa-chart-area',
            'custom': 'fas fa-pencil-alt',
            'waituntil': 'fas fa-minus'
        };
        return icons[type] || 'fas fa-wave-square';
    }

    getAmplitudeDisplay(segment) {
        if (segment.type === 'ramp') {
            // For ramp segments, show start and stop amplitudes
            const startAmp = segment.parameters?.start || segment.arguments?.start || 0;
            const stopAmp = segment.parameters?.stop || segment.arguments?.stop || 0;
            return `
                <div class="segment-detail">
                    <i class="fas fa-signal"></i>
                    <span class="segment-detail-value">${startAmp} - ${stopAmp}V</span>
                </div>
            `;
        } else if (segment.type === 'waituntil') {
            // waituntil segments have no amplitude property
            return '';
        } else if (segment.amplitude !== undefined) {
            // For other segments with single amplitude
            return `
                <div class="segment-detail">
                    <i class="fas fa-signal"></i>
                    <span class="segment-detail-value">${segment.amplitude} V</span>
                </div>
            `;
        }
        return '';
    }

    // Segment Movement Helper Methods
    isFirstSegment(segment) {
        const channel = this.channels.find(c => c.id === segment.channelId);
        if (!channel || channel.segments.length === 0) return true;
        return channel.segments[0].id === segment.id;
    }

    isLastSegment(segment) {
        const channel = this.channels.find(c => c.id === segment.channelId);
        if (!channel || channel.segments.length === 0) return true;
        return channel.segments[channel.segments.length - 1].id === segment.id;
    }

    moveSegment(segment, direction) {
        const channel = this.channels.find(c => c.id === segment.channelId);
        if (!channel) return;

        const segmentIndex = channel.segments.findIndex(s => s.id === segment.id);
        if (segmentIndex === -1) return;

        let newIndex;
        if (direction === 'left') {
            if (segmentIndex === 0) return; // Already first
            newIndex = segmentIndex - 1;
        } else if (direction === 'right') {
            if (segmentIndex === channel.segments.length - 1) return; // Already last
            newIndex = segmentIndex + 1;
        } else {
            return;
        }

        // Move the segment in the channel
        const [movedSegment] = channel.segments.splice(segmentIndex, 1);
        channel.segments.splice(newIndex, 0, movedSegment);

        // Re-render to reflect the new order
        this.render();
        this.notifySegmentUpdated(segment);
    }

    // Drag and Drop
    setupEventListeners() {
        // Channel action buttons
        this.container.addEventListener('click', (e) => {
            const channelBtn = e.target.closest('.channel-action-btn');
            if (channelBtn) {
                const action = channelBtn.dataset.action;
                const channelRow = channelBtn.closest('.channel-row');
                const channelId = channelRow.dataset.channelId;

                if (action === 'delete') {
                    this.removeChannel(channelId);
                }
            }
        });
    }

    setupChannelDragDrop(container, channelId) {
        let dropIndicator = null;
        let dropPosition = null;
        let dropTargetCard = null;

        const createDropIndicator = () => {
            if (!dropIndicator) {
                dropIndicator = document.createElement('div');
                dropIndicator.className = 'drop-indicator drop-indicator-horizontal';
                dropIndicator.style.display = 'none';
            }
            return dropIndicator;
        };

        const showLibraryDropIndicator = (card, position) => {
            const indicator = createDropIndicator();
            const rect = card.getBoundingClientRect();
            const containerRect = container.getBoundingClientRect();
            const gapSize = 15;
            const halfGap = gapSize / 2;

            indicator.style.width = '4px';
            const extendedHeight = rect.height + 40;
            indicator.style.height = `${extendedHeight}px`;
            indicator.style.top = `${rect.top - containerRect.top + container.scrollTop - 20}px`;

            if (position === 'before') {
                indicator.style.left = `${rect.left - containerRect.left + container.scrollLeft - halfGap - 2}px`;
            } else {
                indicator.style.left = `${rect.right - containerRect.left + container.scrollLeft + halfGap - 2}px`;
            }

            indicator.style.display = 'block';

            if (!indicator.parentNode) {
                container.style.position = 'relative';
                container.appendChild(indicator);
            }
        };

        const hideLibraryDropIndicator = () => {
            if (dropIndicator) {
                dropIndicator.style.display = 'none';
            }
        };

        container.addEventListener('dragover', (e) => {
            // Check if this is a reorder drag (custom data type set by DragReorderManager)
            const isReorderDrag = e.dataTransfer.types.includes('application/x-segment-reorder');

            if (isReorderDrag) {
                return; // Let the reorder manager handle it
            }

            // This is a library drag
            e.preventDefault();
            e.stopPropagation();
            e.dataTransfer.dropEffect = 'copy';
            container.closest('.channel-row').classList.add('drag-over');

            // Find the card under the cursor
            const card = e.target.closest('.segment-card');

            if (card) {
                // Calculate drop position
                const rect = card.getBoundingClientRect();
                const midPoint = rect.left + rect.width / 2;
                dropPosition = e.clientX < midPoint ? 'before' : 'after';
                dropTargetCard = card;

                showLibraryDropIndicator(card, dropPosition);
            } else {
                // No card under cursor, will add to end
                dropPosition = null;
                dropTargetCard = null;
                hideLibraryDropIndicator();
            }
        });

        container.addEventListener('dragleave', (e) => {
            if (e.target === container || !container.contains(e.relatedTarget)) {
                container.closest('.channel-row').classList.remove('drag-over');
                hideLibraryDropIndicator();
                dropPosition = null;
                dropTargetCard = null;
            }
        });

        container.addEventListener('drop', (e) => {
            e.preventDefault();
            e.stopPropagation();
            container.closest('.channel-row').classList.remove('drag-over');
            hideLibraryDropIndicator();

            const segmentType = e.dataTransfer.getData('text/plain');

            // Check if this is from the library (not an internal segment drag)
            if (segmentType && !this.segments.find(s => s.id === segmentType)) {
                console.log('Dropping segment type:', segmentType, 'into channel:', channelId);

                // Add segment at the appropriate position
                const segment = this.addSegmentToChannelAtPosition(segmentType, channelId, dropTargetCard, dropPosition);

                // Reset drop tracking
                dropPosition = null;
                dropTargetCard = null;
            }
        });
    }

    addSegmentToChannelAtPosition(type, channelId, targetCard, position) {
        const channel = this.channels.find(c => c.id === channelId);
        if (!channel) {
            console.error('Channel not found:', channelId);
            return null;
        }

        // Generate unique ID
        const isLoadingElement = window.waveformDesigner?.isLoadingElement || false;
        let id;
        if (isLoadingElement) {
            this.idCounter++;
            id = `${Date.now()}_${this.idCounter}`;
        } else {
            id = Date.now().toString();
        }

        const sampleRate = this.getSampleRate();
        const minDuration = 1 / sampleRate;
        const defaultDuration = Math.max(1e-6, minDuration);

        const totalSegments = this.getAllSegmentCount();
        const letterSuffix = indexToLetters(totalSegments);
        const defaultName = `${type}_${letterSuffix}`;

        const segment = {
            id: id,
            type: type,
            name: defaultName,
            duration: defaultDuration,
            amplitude: type !== 'ramp' ? 1.0 : undefined,
            color: this.getSegmentColor(type),
            parameters: this.getDefaultParameters(type),
            channelId: channelId,
            markers: {
                marker1: { delay: 0, duration: 0 },
                marker2: { delay: 0, duration: 0 }
            }
        };

        // Determine insertion index
        let insertIndex = channel.segments.length; // Default: add to end

        if (targetCard && position) {
            const targetSegmentId = targetCard.dataset.segmentId;
            const targetIndex = channel.segments.findIndex(s => s.id === targetSegmentId);

            if (targetIndex !== -1) {
                insertIndex = position === 'before' ? targetIndex : targetIndex + 1;
            }
        }

        // Insert segment at the calculated position
        channel.segments.splice(insertIndex, 0, segment);
        this.segments.push(segment);

        // Auto-select the newly added segment
        if (!isLoadingElement) {
            this.selectSegment(segment);
            this.render();
        }

        this.notifySegmentAdded(segment);

        return segment;
    }

    // Notifications
    notifySegmentAdded(segment) {
        window.dispatchEvent(new CustomEvent('segmentAdded', { detail: segment }));
    }

    notifySegmentRemoved(segmentId) {
        window.dispatchEvent(new CustomEvent('segmentRemoved', { detail: { id: segmentId } }));
    }

    notifySegmentSelected(segment) {
        window.dispatchEvent(new CustomEvent('segmentSelected', { detail: segment }));
    }

    notifySegmentUpdated(segment) {
        window.dispatchEvent(new CustomEvent('segmentUpdated', { detail: segment }));
    }

    notifyChannelAdded(channel) {
        window.dispatchEvent(new CustomEvent('channelAdded', { detail: channel }));
    }

    notifyChannelRemoved(channelId) {
        window.dispatchEvent(new CustomEvent('channelRemoved', { detail: { id: channelId } }));
    }

    // Public API
    getSegments() {
        return [...this.segments];
    }

    clearAll() {
        this.segments = [];
        this.channels = [];
        this.selectedSegment = null;
        this.initializeDefaultChannel();
        this.render();
        window.dispatchEvent(new CustomEvent('segmentsCleared'));
    }

    // Force re-render after element loading is complete
    forceRender() {
        this.render();
    }
}

// Export for use in main application
window.TimelineCards = TimelineCards;
