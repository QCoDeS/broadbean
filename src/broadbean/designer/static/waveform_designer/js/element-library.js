/**
 * Element Library Component
 * Displays saved waveform elements that can be dragged into the sequence
 */

class ElementLibrary {
    constructor() {
        this.elements = [];
        this.container = document.getElementById('element-library');
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
                    <p class="empty-state-text">Create waveform elements in the Designer first</p>
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
        card.draggable = true;
        card.dataset.elementId = element.id;

        // Format duration
        const duration = CommonUtils.formatDuration(element.duration);
        const sampleRate = CommonUtils.formatSampleRate(element.sample_rate);

        card.innerHTML = `
            <div class="library-card-header">
                ${CommonUtils.escapeHtml(element.name)}
            </div>
            <div class="library-card-info">
                <i class="fas fa-signal"></i> ${element.num_channels} channel${element.num_channels !== 1 ? 's' : ''}
            </div>
            <div class="library-card-info">
                <i class="fas fa-tachometer-alt"></i> ${sampleRate}
            </div>
            ${element.description ? `<p class="library-card-description">${CommonUtils.escapeHtml(element.description)}</p>` : ''}
        `;

        // Drag events
        card.addEventListener('dragstart', (e) => {
            e.dataTransfer.effectAllowed = 'copy';
            e.dataTransfer.setData('application/json', JSON.stringify(element));
            card.classList.add('dragging');
        });

        card.addEventListener('dragend', () => {
            card.classList.remove('dragging');
        });

        return card;
    }

    getElement(elementId) {
        return this.elements.find(el => el.id === elementId);
    }
}
