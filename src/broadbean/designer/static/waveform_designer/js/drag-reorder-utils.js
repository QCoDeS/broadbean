/**
 * Drag Reorder Utilities
 * Reusable drag-and-drop reordering functionality for card-based layouts
 */

class DragReorderManager {
    constructor(options = {}) {
        this.container = options.container;
        this.cardSelector = options.cardSelector || '.draggable-card';
        this.onReorder = options.onReorder || (() => {});
        this.orientation = options.orientation || 'horizontal';
        this.dragDataType = options.dragDataType || 'application/x-card-reorder';
        this.getCardId = options.getCardId || ((card) => card.dataset.id);
        this.canDragCard = options.canDragCard || (() => true);

        this.draggedCard = null;
        this.dropIndicator = null;
        this.currentDropTarget = null;
        this.dropPosition = null; // 'before' or 'after'

        this.init();
    }

    init() {
        if (!this.container) {
            console.error('DragReorderManager: container is required');
            return;
        }

        this.createDropIndicator();
        this.setupEventListeners();
    }

    createDropIndicator() {
        this.dropIndicator = document.createElement('div');
        this.dropIndicator.className = `drop-indicator drop-indicator-${this.orientation}`;
        this.dropIndicator.style.display = 'none';
    }

    setupEventListeners() {
        // Use event delegation for dynamic cards
        this.container.addEventListener('dragstart', (e) => this.handleDragStart(e));
        this.container.addEventListener('dragend', (e) => this.handleDragEnd(e));
        this.container.addEventListener('dragover', (e) => this.handleDragOver(e));
        this.container.addEventListener('dragleave', (e) => this.handleDragLeave(e));
        this.container.addEventListener('drop', (e) => this.handleDrop(e));
    }

    handleDragStart(e) {
        const card = e.target.closest(this.cardSelector);
        if (!card || !this.canDragCard(card)) {
            return;
        }

        this.draggedCard = card;
        const cardId = this.getCardId(card);

        // Set custom data type to distinguish from library drags
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData(this.dragDataType, cardId);

        // Add visual feedback
        setTimeout(() => {
            card.classList.add('drag-reorder-source');
        }, 0);
    }

    handleDragEnd(e) {
        const card = e.target.closest(this.cardSelector);
        if (card) {
            card.classList.remove('drag-reorder-source');
        }

        this.hideDropIndicator();
        this.clearDropTarget();
        this.draggedCard = null;
    }

    handleDragOver(e) {
        // Only handle reorder drags
        if (!e.dataTransfer.types.includes(this.dragDataType)) {
            return;
        }

        e.preventDefault();
        e.stopPropagation();
        e.dataTransfer.dropEffect = 'move';

        const card = e.target.closest(this.cardSelector);
        if (!card || card === this.draggedCard) {
            this.hideDropIndicator();
            return;
        }

        // Calculate drop position based on cursor position
        const rect = card.getBoundingClientRect();
        let dropPosition;

        if (this.orientation === 'horizontal') {
            const midPoint = rect.left + rect.width / 2;
            dropPosition = e.clientX < midPoint ? 'before' : 'after';
        } else {
            const midPoint = rect.top + rect.height / 2;
            dropPosition = e.clientY < midPoint ? 'before' : 'after';
        }

        // Update drop indicator
        this.showDropIndicator(card, dropPosition);
        this.currentDropTarget = card;
        this.dropPosition = dropPosition;

        // Add hover class
        card.classList.add('drag-reorder-target');
    }

    handleDragLeave(e) {
        const card = e.target.closest(this.cardSelector);
        if (card && !card.contains(e.relatedTarget)) {
            card.classList.remove('drag-reorder-target');
        }
    }

    handleDrop(e) {
        // Only handle reorder drags
        if (!e.dataTransfer.types.includes(this.dragDataType)) {
            return;
        }

        e.preventDefault();
        e.stopPropagation();

        const draggedId = e.dataTransfer.getData(this.dragDataType);

        if (!this.currentDropTarget || !this.draggedCard) {
            this.hideDropIndicator();
            this.clearDropTarget();
            return;
        }

        const targetId = this.getCardId(this.currentDropTarget);

        // Don't do anything if dropping on itself
        if (draggedId === targetId) {
            this.hideDropIndicator();
            this.clearDropTarget();
            return;
        }

        // Call the reorder callback
        this.onReorder({
            draggedId: draggedId,
            targetId: targetId,
            position: this.dropPosition,
            draggedCard: this.draggedCard,
            targetCard: this.currentDropTarget
        });

        this.hideDropIndicator();
        this.clearDropTarget();
    }

    showDropIndicator(card, position) {
        const rect = card.getBoundingClientRect();
        const containerRect = this.container.getBoundingClientRect();

        // Gap size from CSS (--spacing-lg = 15px)
        const gapSize = 15;
        const halfGap = gapSize / 2;

        if (this.orientation === 'horizontal') {
            this.dropIndicator.style.width = '2px';
            // Make the line extend 20px above and below the card
            const extendedHeight = rect.height + 40;
            this.dropIndicator.style.height = `${extendedHeight}px`;
            this.dropIndicator.style.top = `${rect.top - containerRect.top + this.container.scrollTop - 20}px`;

            if (position === 'before') {
                // Position in the center of the gap before the card
                this.dropIndicator.style.left = `${rect.left - containerRect.left + this.container.scrollLeft - halfGap - 1}px`;
            } else {
                // Position in the center of the gap after the card
                this.dropIndicator.style.left = `${rect.right - containerRect.left + this.container.scrollLeft + halfGap - 1}px`;
            }
        } else {
            // Make the line extend 20px to the left and right of the card
            const extendedWidth = rect.width + 40;
            this.dropIndicator.style.width = `${extendedWidth}px`;
            this.dropIndicator.style.height = '2px';
            this.dropIndicator.style.left = `${rect.left - containerRect.left + this.container.scrollLeft - 20}px`;

            if (position === 'before') {
                // Position in the center of the gap before the card
                this.dropIndicator.style.top = `${rect.top - containerRect.top + this.container.scrollTop - halfGap - 1}px`;
            } else {
                // Position in the center of the gap after the card
                this.dropIndicator.style.top = `${rect.bottom - containerRect.top + this.container.scrollTop + halfGap - 1}px`;
            }
        }

        this.dropIndicator.style.display = 'block';

        // Append to container if not already there
        if (!this.dropIndicator.parentNode) {
            this.container.style.position = 'relative';
            this.container.appendChild(this.dropIndicator);
        }
    }

    hideDropIndicator() {
        if (this.dropIndicator) {
            this.dropIndicator.style.display = 'none';
        }
    }

    clearDropTarget() {
        if (this.currentDropTarget) {
            this.currentDropTarget.classList.remove('drag-reorder-target');
            this.currentDropTarget = null;
        }
        this.dropPosition = null;
    }

    destroy() {
        this.hideDropIndicator();
        if (this.dropIndicator && this.dropIndicator.parentNode) {
            this.dropIndicator.parentNode.removeChild(this.dropIndicator);
        }
        this.draggedCard = null;
        this.currentDropTarget = null;
    }
}

// Export for use in other modules
window.DragReorderManager = DragReorderManager;
