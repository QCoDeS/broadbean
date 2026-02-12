/**
 * Segment Library Component
 * Handles the segment library panel with drag-and-drop functionality
 */

// Centralized segment default parameters configuration
const SEGMENT_DEFAULTS = {
    'ramp': { 
        start: 0.0, 
        stop: 1.0 
    },
    'sine': { 
        frequency: 1e6, 
        phase: 0, 
        offset: 0.0 
    },
    'gaussian': { 
        width: 0.1e-6, 
        center: 0e-6 
    },
    'exponential': { 
        time_constant: 0.33e-6, 
        type: 'rise' 
    },
    'waituntil': { 
        absolute_time: 1e-6 
    },
    'custom': { 
        expression: 't, amp, tau: amp * exp(-t / tau)', 
        params_json: '{"amp": 2, "tau": 0.33e-6}' 
    }
};

// Export for use in other modules
window.SEGMENT_DEFAULTS = SEGMENT_DEFAULTS;

class SegmentLibrary {
    constructor() {
        this.segmentTypes = [];
        this.container = document.getElementById('segment-types');
        
        this.loadSegmentTypes();
        this.bindEvents();
    }

    async loadSegmentTypes() {
        try {
            const response = await fetch('/api/segments/');
            const data = await response.json();
            this.segmentTypes = data.segments;
            this.render();
        } catch (error) {
            console.error('Failed to load segment types:', error);
            this.showError('Failed to load segment types');
        }
    }

    render() {
        this.container.innerHTML = '';
        
        this.segmentTypes.forEach(segmentType => {
            const segmentItem = this.createSegmentItem(segmentType);
            this.container.appendChild(segmentItem);
        });
    }

    createSegmentItem(segmentType) {
        const item = document.createElement('div');
        item.className = 'segment-item';
        item.draggable = true;
        item.dataset.segmentType = segmentType.id;
        
        // Create header with icon and name on same line
        const header = document.createElement('div');
        header.className = 'segment-item-header';
        
        // Create segment icon with preview
        const icon = document.createElement('div');
        icon.className = 'segment-icon';
        icon.style.backgroundColor = segmentType.color;
        
        // Add a mini preview of the waveform shape
        const preview = this.createMiniPreview(segmentType.id, segmentType.color);
        icon.appendChild(preview);
        
        // Create name
        const name = document.createElement('div');
        name.className = 'segment-name';
        name.textContent = segmentType.name;
        
        header.appendChild(icon);
        header.appendChild(name);
        
        // Create description
        const description = document.createElement('div');
        description.className = 'segment-description';
        description.textContent = segmentType.description;
        
        item.appendChild(header);
        item.appendChild(description);
        
        // Add drag event listeners
        this.addDragListeners(item, segmentType);
        
        return item;
    }

    createMiniPreview(type, color) {
        const canvas = document.createElement('canvas');
        canvas.width = 40;
        canvas.height = 30;
        canvas.style.width = '40px';
        canvas.style.height = '30px';
        
        const ctx = canvas.getContext('2d');
        
        // Generate preview waveform
        const points = 40;
        const amplitude = 12; // Half height minus padding
        const centerY = 15;
        
        ctx.strokeStyle = 'white';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        
        for (let i = 0; i < points; i++) {
            const x = i;
            const t = i / (points - 1); // normalized time 0-1
            let y = centerY;
            
            switch (type) {
                case 'ramp':
                    y = centerY - amplitude * t;
                    break;
                case 'sine':
                    y = centerY - amplitude * Math.sin(2 * Math.PI * t * 2);
                    break;
                case 'gaussian':
                    const sigma = 0.2;
                    const mu = 0.5;
                    y = centerY - amplitude * Math.exp(-0.5 * Math.pow((t - mu) / sigma, 2));
                    break;
                case 'exponential':
                    y = centerY - amplitude * (1 - Math.exp(-5 * t));
                    break;
                case 'waituntil':
                    // Show a flat line with a step at the end to indicate waiting
                    y = centerY;
                    break;
                case 'custom':
                    y = centerY - amplitude * Math.sin(2 * Math.PI * t) * Math.exp(-2 * t);
                    break;
                default:
                    y = centerY - amplitude * t;
            }
            
            if (i === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        }
        
        ctx.stroke();
        
        return canvas;
    }

    addDragListeners(item, segmentType) {
        item.addEventListener('dragstart', (e) => {
            e.dataTransfer.setData('text/plain', segmentType.id);
            e.dataTransfer.effectAllowed = 'copy';
            
            item.classList.add('dragging');
            
            // Create a custom drag image
            const dragImage = this.createDragImage(segmentType);
            e.dataTransfer.setDragImage(dragImage, 25, 15);
        });
        
        item.addEventListener('dragend', (e) => {
            item.classList.remove('dragging');
        });
        
        // Add click handler for quick add to timeline
        item.addEventListener('click', () => {
            this.addToTimeline(segmentType.id);
        });
    }

    createDragImage(segmentType) {
        const dragImage = document.createElement('div');
        dragImage.style.position = 'absolute';
        dragImage.style.top = '-1000px';
        dragImage.style.left = '-1000px';
        dragImage.style.width = '80px';
        dragImage.style.height = '30px';
        dragImage.style.backgroundColor = segmentType.color;
        dragImage.style.color = 'white';
        dragImage.style.display = 'flex';
        dragImage.style.alignItems = 'center';
        dragImage.style.justifyContent = 'center';
        dragImage.style.borderRadius = '4px';
        dragImage.style.fontSize = '11px';
        dragImage.style.fontWeight = '500';
        dragImage.textContent = segmentType.name;
        
        document.body.appendChild(dragImage);
        
        // Remove the drag image after a short delay
        setTimeout(() => {
            if (dragImage.parentNode) {
                dragImage.parentNode.removeChild(dragImage);
            }
        }, 100);
        
        return dragImage;
    }

    addToTimeline(segmentTypeId) {
        // Notify the timeline to add a new segment
        window.dispatchEvent(new CustomEvent('addSegmentToTimeline', {
            detail: { type: segmentTypeId }
        }));
    }

    bindEvents() {
        // Listen for global settings changes
        document.getElementById('sample-rate')?.addEventListener('change', (e) => {
            this.notifySettingChange('sampleRate', parseFloat(e.target.value));
        });
        
        document.getElementById('time-scale')?.addEventListener('change', (e) => {
            this.notifySettingChange('timeScale', parseFloat(e.target.value));
        });
    }

    notifySettingChange(setting, value) {
        window.dispatchEvent(new CustomEvent('settingChanged', {
            detail: { setting, value }
        }));
    }

    showError(message) {
        CommonUtils.showError(message, this.container);
    }

    // Public API
    getSegmentType(id) {
        return this.segmentTypes.find(type => type.id === id);
    }

    getAllSegmentTypes() {
        return [...this.segmentTypes];
    }
}

// Export for use in main application
window.SegmentLibrary = SegmentLibrary;
