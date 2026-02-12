/**
 * Sequence Timeline Component
 * Manages the sequence of waveform elements with drag-and-drop
 */

class SequenceTimeline {
    constructor() {
        this.sequenceElements = [];
        this.selectedPosition = null;
        this.container = document.getElementById('sequence-timeline');
        this.positionCountBadge = document.getElementById('position-count');
        this.durationBadge = document.getElementById('total-duration-badge');
        
        // Drag reorder manager for sequence positions
        this.dragReorderManager = null;
        
        this.init();
    }

    init() {
        this.setupDropZone();
        this.render();
        this.setupPositionReordering();
    }
    
    setupPositionReordering() {
        // Clean up existing manager if any
        if (this.dragReorderManager) {
            this.dragReorderManager.destroy();
        }

        // Create drag reorder manager for sequence positions
        this.dragReorderManager = new DragReorderManager({
            container: this.container,
            cardSelector: '.sequence-position',
            orientation: 'horizontal',
            dragDataType: 'application/x-position-reorder',
            getCardId: (card) => card.dataset.position,
            canDragCard: (card) => {
                // Allow dragging unless it's being clicked on an action button
                return !card.querySelector('.position-btn:hover');
            },
            onReorder: (data) => {
                this.handlePositionReorder(data);
            }
        });
    }

    handlePositionReorder(data) {
        const draggedPos = parseInt(data.draggedId);
        const targetPos = parseInt(data.targetId);
        
        // Calculate new position based on drop location
        let newPos = targetPos;
        if (data.position === 'after') {
            newPos = targetPos + 1;
        }
        
        // Adjust if dragging from before the target
        if (draggedPos < targetPos && data.position === 'before') {
            newPos = targetPos - 1;
        }
        
        // Don't do anything if dropping in the same position
        if (draggedPos === newPos || (draggedPos + 1 === newPos && data.position === 'after')) {
            return;
        }
        
        // Perform the reorder
        this.moveElement(draggedPos, newPos);
    }

    setupDropZone() {
        this.container.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'copy';
        });

        this.container.addEventListener('drop', (e) => {
            e.preventDefault();
            
            try {
                const elementData = JSON.parse(e.dataTransfer.getData('application/json'));
                this.addElement(elementData);
            } catch (error) {
                console.error('Failed to add element:', error);
            }
        });
    }

    addElement(elementData) {
        const position = this.sequenceElements.length + 1;
        
        const sequenceElement = {
            position: position,
            element_id: elementData.id,
            element: elementData,
            trigger_input: 0,
            repetitions: 1,
            goto: position < this.sequenceElements.length ? position + 1 : 1
        };

        this.sequenceElements.push(sequenceElement);
        this.updateGotoDefaults();
        this.render();
        this.updateStats();
        
        // Auto-scroll to the newly added element
        this.scrollToEnd();
        
        // Notify other components
        this.dispatchChange();
    }

    updateGotoDefaults() {
        // Update goto to loop back to first element for the last position
        this.sequenceElements.forEach((elem, index) => {
            if (index === this.sequenceElements.length - 1) {
                elem.goto = 1; // Loop back to first
            } else {
                elem.goto = elem.position + 1; // Go to next
            }
        });
    }

    removeElement(position) {
        const index = this.sequenceElements.findIndex(el => el.position === position);
        if (index !== -1) {
            this.sequenceElements.splice(index, 1);
            // Renumber positions
            this.sequenceElements.forEach((el, idx) => {
                el.position = idx + 1;
            });
            this.updateGotoDefaults();
            this.render();
            this.updateStats();
            this.dispatchChange();
        }
    }

    moveElement(fromPosition, toPosition) {
        const fromIndex = this.sequenceElements.findIndex(el => el.position === fromPosition);
        const toIndex = toPosition - 1;
        
        if (fromIndex !== -1 && toIndex >= 0 && toIndex < this.sequenceElements.length) {
            const element = this.sequenceElements.splice(fromIndex, 1)[0];
            this.sequenceElements.splice(toIndex, 0, element);
            
            // Renumber positions
            this.sequenceElements.forEach((el, idx) => {
                el.position = idx + 1;
            });
            
            this.updateGotoDefaults();
            this.render();
            this.updateStats();
            this.dispatchChange();
        }
    }

    selectElement(position) {
        this.selectedPosition = position;
        this.render();
        
        const element = this.sequenceElements.find(el => el.position === position);
        if (element) {
            this.dispatchSelection(element);
        }
    }

    updateElement(position, updates) {
        const element = this.sequenceElements.find(el => el.position === position);
        if (element) {
            Object.assign(element, updates);
            this.render();
            this.updateStats();
            
            // Re-select the element to update inspector with new values
            if (this.selectedPosition === position) {
                this.dispatchSelection(element);
            }
            
            this.dispatchChange();
        }
    }

    render() {
        if (this.sequenceElements.length === 0) {
            this.container.classList.remove('has-elements');
            this.container.innerHTML = `
                <div class="timeline-placeholder">
                    <i class="fas fa-list"></i>
                    <p>Drag elements from the library to build your sequence</p>
                </div>
            `;
            return;
        }

        this.container.classList.add('has-elements');
        this.container.innerHTML = '';

        this.sequenceElements.forEach(seqElement => {
            const card = this.createPositionCard(seqElement);
            this.container.appendChild(card);
        });
    }

    createPositionCard(seqElement) {
        const card = document.createElement('div');
        card.className = 'sequence-position';
        card.dataset.position = seqElement.position;
        
        if (seqElement.position === this.selectedPosition) {
            card.classList.add('selected');
        }

        const duration = CommonUtils.formatDuration(seqElement.element.duration * seqElement.repetitions);
        const gotoText = seqElement.goto === 1 ? 'Loop to start' : `Position ${seqElement.goto}`;
        const triggerName = this.formatTriggerName(seqElement.trigger_input);

        card.innerHTML = `
            <div class="position-header">
                <span class="position-number">Position ${seqElement.position}</span>
                <div class="position-actions">
                    <button class="position-btn move-left" title="Move Left" ${seqElement.position === 1 ? 'disabled' : ''}>
                        <i class="fas fa-arrow-left"></i>
                    </button>
                    <button class="position-btn move-right" title="Move Right" ${seqElement.position === this.sequenceElements.length ? 'disabled' : ''}>
                        <i class="fas fa-arrow-right"></i>
                    </button>
                    <button class="position-btn delete" title="Delete">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
            <div class="position-name">${CommonUtils.escapeHtml(seqElement.element.name)}</div>
            <div class="position-details">
                <div class="position-detail">
                    <i class="fas fa-bolt"></i>
                    <span>Trigger: <span class="position-detail-value">${triggerName}</span></span>
                </div>
                <div class="position-detail">
                    <i class="fas fa-redo"></i>
                    <span>Repeat: <span class="position-detail-value">${seqElement.repetitions}x</span></span>
                </div>
                <div class="position-detail">
                    <i class="fas fa-clock"></i>
                    <span>Duration: <span class="position-detail-value">${duration}</span></span>
                </div>
                <div class="position-detail">
                    <i class="fas fa-arrow-right"></i>
                    <span>Goto: <span class="position-detail-value">${gotoText}</span></span>
                </div>
            </div>
        `;

        // Click to select
        card.addEventListener('click', (e) => {
            if (!e.target.closest('.position-btn')) {
                this.selectElement(seqElement.position);
            }
        });

        // Move buttons
        const moveLeftBtn = card.querySelector('.move-left');
        const moveRightBtn = card.querySelector('.move-right');
        const deleteBtn = card.querySelector('.delete');

        if (moveLeftBtn) {
            moveLeftBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.moveElement(seqElement.position, seqElement.position - 1);
            });
        }

        if (moveRightBtn) {
            moveRightBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.moveElement(seqElement.position, seqElement.position + 1);
            });
        }

        if (deleteBtn) {
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.removeElement(seqElement.position);
            });
        }

        return card;
    }

    updateStats() {
        // Update position count
        if (this.positionCountBadge) {
            this.positionCountBadge.textContent = `${this.sequenceElements.length} position${this.sequenceElements.length !== 1 ? 's' : ''}`;
        }

        // Calculate total duration
        let totalDuration = 0;
        this.sequenceElements.forEach(elem => {
            totalDuration += elem.element.duration * elem.repetitions;
        });

        if (this.durationBadge) {
            this.durationBadge.textContent = CommonUtils.formatDuration(totalDuration);
        }
    }

    formatTriggerName(triggerValue) {
        const triggerNames = {
            0: 'Cont.',
            1: 'A',
            2: 'B',
            3: 'Int.'
        };
        return triggerNames[triggerValue] || triggerValue;
    }

    getSequenceData() {
        return this.sequenceElements.map(elem => ({
            element_id: elem.element_id,
            position: elem.position,
            trigger_input: elem.trigger_input,
            repetitions: elem.repetitions,
            goto: elem.goto,
            flags: elem.flags || null
        }));
    }

    scrollToEnd() {
        // Scroll to the end of the horizontal timeline to show the newly added element
        if (this.container && this.sequenceElements.length > 0) {
            setTimeout(() => {
                this.container.scrollLeft = this.container.scrollWidth;
            }, 100); // Small delay to ensure the DOM has updated
        }
    }

    scrollToElement(position) {
        // Scroll to show a specific element
        if (this.container) {
            const card = this.container.querySelector(`[data-position="${position}"]`);
            if (card) {
                card.scrollIntoView({ 
                    behavior: 'smooth', 
                    block: 'nearest', 
                    inline: 'center' 
                });
            }
        }
    }

    clearSequence() {
        this.sequenceElements = [];
        this.selectedPosition = null;
        this.render();
        this.updateStats();
        this.dispatchChange();
    }

    dispatchChange() {
        window.dispatchEvent(new CustomEvent('sequenceChanged', {
            detail: { elements: this.sequenceElements }
        }));
    }

    dispatchSelection(element) {
        window.dispatchEvent(new CustomEvent('elementSelected', {
            detail: { element: element }
        }));
    }
}
