/**
 * Element Inspector Component
 * Displays and allows editing of sequence element properties
 */

class ElementInspector {
    constructor() {
        this.currentElement = null;
        this.container = document.getElementById('element-inspector-content');
        this.listContainer = document.getElementById('sequence-element-list');
        this.selectedElements = new Set();
        this.bulkEditMode = false;
        this.sequenceElements = [];
        
        this.init();
    }

    init() {
        this.bindEvents();
        this.showEmpty();
    }

    bindEvents() {
        // Listen for element selection
        window.addEventListener('elementSelected', (e) => {
            this.showElement(e.detail.element);
        });

        // Listen for sequence changes to update list
        window.addEventListener('sequenceChanged', (e) => {
            this.updateList(e.detail.elements);
        });
    }

    showEmpty() {
        this.container.innerHTML = `
            <p class="no-selection">Select an element in the timeline to edit its properties</p>
        `;
        this.currentElement = null;
    }

    showElement(sequenceElement) {
        this.currentElement = sequenceElement;
        
        const element = sequenceElement.element;
        const duration = CommonUtils.formatDuration(element.duration);
        const sampleRate = CommonUtils.formatSampleRate(element.sample_rate);

        this.container.innerHTML = `
            <div class="element-info-box">
                <div class="element-info-title">${CommonUtils.escapeHtml(element.name)}</div>
                <div class="element-info-item">
                    <span>Duration:</span>
                    <span class="element-info-value">${duration}</span>
                </div>
                <div class="element-info-item">
                    <span>Channels:</span>
                    <span class="element-info-value">${element.num_channels}</span>
                </div>
                <div class="element-info-item">
                    <span>Sample Rate:</span>
                    <span class="element-info-value">${sampleRate}</span>
                </div>
            </div>

            <form class="inspector-form" id="element-inspector-form">
                <div class="form-group">
                    <label for="trigger-input">Trigger Input</label>
                    <select id="trigger-input" class="form-control">
                        <option value="0" ${sequenceElement.trigger_input === 0 ? 'selected' : ''}>Continue</option>
                        <option value="1" ${sequenceElement.trigger_input === 1 ? 'selected' : ''}>Trigger A</option>
                        <option value="2" ${sequenceElement.trigger_input === 2 ? 'selected' : ''}>Trigger B</option>
                        <option value="3" ${sequenceElement.trigger_input === 3 ? 'selected' : ''}>Internal Clock</option>
                    </select>
                    <small class="form-help-text">Hardware trigger input to use for this element</small>
                </div>

                <div class="form-group">
                    <label for="repetitions">Number of Repetitions</label>
                    <input type="number" id="repetitions" class="form-control" 
                           value="${sequenceElement.repetitions}" min="1" max="65536" step="1">
                    <small class="form-help-text">How many times to repeat this element (1-65536)</small>
                </div>

                <div class="form-group">
                    <label for="goto-position">Go To Position</label>
                    <select id="goto-position" class="form-control">
                        ${this.generateGotoOptions(sequenceElement)}
                    </select>
                    <small class="form-help-text">Next position after this element completes</small>
                </div>
            </form>

            ${this.generateFlagsCard(sequenceElement)}
        `;

        // Bind form events
        this.bindFormEvents();
        this.bindFlagsEvents();
    }

    generateGotoOptions(sequenceElement) {
        const timeline = window.sequencerApp?.timeline;
        if (!timeline) return '';

        const numPositions = timeline.sequenceElements.length;
        let options = '';

        for (let i = 1; i <= numPositions; i++) {
            const selected = sequenceElement.goto === i ? 'selected' : '';
            const label = i === 1 ? 'Loop to start' : `Position ${i}`;
            options += `<option value="${i}" ${selected}>${label}</option>`;
        }

        return options;
    }

    bindFormEvents() {
        const form = document.getElementById('element-inspector-form');
        if (!form) return;

        const triggerInput = document.getElementById('trigger-input');
        const repetitions = document.getElementById('repetitions');
        const gotoPosition = document.getElementById('goto-position');

        if (triggerInput) {
            triggerInput.addEventListener('change', (e) => {
                this.updateElementProperty('trigger_input', parseInt(e.target.value));
            });
        }

        if (repetitions) {
            repetitions.addEventListener('change', (e) => {
                let value = parseInt(e.target.value);
                // Validate range
                if (value < 1) value = 1;
                if (value > 65536) value = 65536;
                e.target.value = value;
                this.updateElementProperty('repetitions', value);
            });
        }

        if (gotoPosition) {
            gotoPosition.addEventListener('change', (e) => {
                this.updateElementProperty('goto', parseInt(e.target.value));
            });
        }
    }

    updateElementProperty(property, value) {
        if (!this.currentElement) return;

        const timeline = window.sequencerApp?.timeline;
        if (timeline) {
            const updates = {};
            updates[property] = value;
            timeline.updateElement(this.currentElement.position, updates);
        }
    }

    updateList(sequenceElements) {
        if (!this.listContainer) return;
        
        this.sequenceElements = sequenceElements;

        if (sequenceElements.length === 0) {
            this.listContainer.innerHTML = `
                <div class="empty-state" style="padding: 20px 10px;">
                    <i class="fas fa-list"></i>
                    <p style="font-size: 12px; margin-top: 8px;">No elements in sequence</p>
                </div>
            `;
            this.selectedElements.clear();
            this.updateBulkEditMode();
            return;
        }

        // Create list header with select all checkbox
        const header = this.createListHeader();
        
        // Create list items
        const listItems = sequenceElements.map(seqElement => this.createListItem(seqElement));

        // Clear and rebuild container
        this.listContainer.innerHTML = '';
        this.listContainer.appendChild(header);
        listItems.forEach(item => this.listContainer.appendChild(item));

        // Update bulk edit mode UI
        this.updateBulkEditMode();
    }

    createListHeader() {
        const header = document.createElement('div');
        header.className = 'sequence-list-header';
        
        const isAllSelected = this.sequenceElements.length > 0 && 
                             this.sequenceElements.every(el => this.selectedElements.has(el.position));
        
        header.innerHTML = `
            <div class="sequence-list-header-content">
                <label class="sequence-list-select-all">
                    <input type="checkbox" id="select-all-checkbox" ${isAllSelected ? 'checked' : ''}>
                    <span>Select All (${this.selectedElements.size} selected)</span>
                </label>
            </div>
        `;
        
        // Bind select all checkbox
        const selectAllCheckbox = header.querySelector('#select-all-checkbox');
        selectAllCheckbox.addEventListener('change', (e) => {
            this.selectAllElements(e.target.checked);
        });
        
        return header;
    }

    createListItem(seqElement) {
        const item = document.createElement('div');
        item.className = 'sequence-list-item';
        item.dataset.position = seqElement.position;

        const isSelected = this.selectedElements.has(seqElement.position);
        const isCurrentElement = this.currentElement && this.currentElement.position === seqElement.position;

        if (isCurrentElement) {
            item.classList.add('selected');
        }
        
        if (isSelected) {
            item.classList.add('selected-for-bulk');
        }

        item.innerHTML = `
            <label class="sequence-list-item-checkbox" onclick="event.stopPropagation()">
                <input type="checkbox" ${isSelected ? 'checked' : ''}>
            </label>
            <span class="sequence-list-number">${seqElement.position}</span>
            <span class="sequence-list-name">${CommonUtils.escapeHtml(seqElement.element.name)}</span>
            <i class="fas fa-chevron-right sequence-list-icon"></i>
        `;

        // Bind checkbox event
        const checkbox = item.querySelector('input[type="checkbox"]');
        checkbox.addEventListener('change', (e) => {
            e.stopPropagation();
            this.toggleElementSelection(seqElement.position, e.target.checked);
        });

        // Bind item click event (for individual selection in timeline)
        item.addEventListener('click', () => {
            const timeline = window.sequencerApp?.timeline;
            if (timeline) {
                timeline.selectElement(seqElement.position);
            }
        });

        return item;
    }

    // Bulk Selection Methods
    selectAllElements(selected) {
        if (selected) {
            this.sequenceElements.forEach(el => this.selectedElements.add(el.position));
        } else {
            this.selectedElements.clear();
        }
        this.updateSelectionUI();
        this.updateBulkEditMode();
    }

    toggleElementSelection(position, selected) {
        if (selected) {
            this.selectedElements.add(position);
        } else {
            this.selectedElements.delete(position);
        }
        this.updateSelectionUI();
        this.updateBulkEditMode();
    }

    updateSelectionUI() {
        // Update select all checkbox
        const selectAllCheckbox = document.getElementById('select-all-checkbox');
        if (selectAllCheckbox) {
            const isAllSelected = this.sequenceElements.length > 0 && 
                                 this.sequenceElements.every(el => this.selectedElements.has(el.position));
            selectAllCheckbox.checked = isAllSelected;
            
            // Update label text
            const label = selectAllCheckbox.nextElementSibling;
            if (label) {
                label.textContent = `Select All (${this.selectedElements.size} selected)`;
            }
        }

        // Update individual checkboxes and styling
        this.sequenceElements.forEach(seqElement => {
            const item = this.listContainer.querySelector(`[data-position="${seqElement.position}"]`);
            if (item) {
                const checkbox = item.querySelector('input[type="checkbox"]');
                const isSelected = this.selectedElements.has(seqElement.position);
                
                if (checkbox) {
                    checkbox.checked = isSelected;
                }
                
                if (isSelected) {
                    item.classList.add('selected-for-bulk');
                } else {
                    item.classList.remove('selected-for-bulk');
                }
            }
        });
    }

    updateBulkEditMode() {
        const hasSelection = this.selectedElements.size > 0;
        
        if (hasSelection && !this.bulkEditMode) {
            this.showBulkEditControls();
            this.bulkEditMode = true;
        } else if (!hasSelection && this.bulkEditMode) {
            this.hideBulkEditControls();
            this.bulkEditMode = false;
        }
    }

    showBulkEditControls() {
        if (this.selectedElements.size === 0) return;

        // Get the first selected element to determine number of channels
        const firstPosition = Array.from(this.selectedElements)[0];
        const firstElement = this.sequenceElements.find(el => el.position === firstPosition);
        const numChannels = firstElement?.element?.num_channels || 0;

        // Show bulk edit form instead of individual element form
        this.container.innerHTML = `
            <div class="bulk-edit-info">
                <h5><i class="fas fa-edit"></i> Bulk Edit (${this.selectedElements.size} elements)</h5>
                <p class="bulk-edit-description">Changes will be applied to all selected elements</p>
            </div>

            <form class="inspector-form bulk-edit-form" id="bulk-edit-form">
                <div class="form-group">
                    <label for="bulk-trigger-input">Trigger Input</label>
                    <select id="bulk-trigger-input" class="form-control">
                        <option value="">Keep current values</option>
                        <option value="0">Continue</option>
                        <option value="1">Trigger A</option>
                        <option value="2">Trigger B</option>
                        <option value="3">Internal Clock</option>
                    </select>
                    <small class="form-help-text">Hardware trigger input to use for selected elements</small>
                </div>

                <div class="form-group">
                    <label for="bulk-repetitions">Number of Repetitions</label>
                    <input type="number" id="bulk-repetitions" class="form-control" 
                           placeholder="Keep current values" min="1" max="65536" step="1">
                    <small class="form-help-text">How many times to repeat selected elements (1-65536)</small>
                </div>
            </form>

            ${this.generateBulkFlagsSection(numChannels)}

            <div class="bulk-edit-actions" style="margin-top: 15px;">
                <button type="button" class="btn btn-primary" id="apply-bulk-changes">
                    <i class="fas fa-check"></i> Apply Changes
                </button>
                <button type="button" class="btn btn-secondary" id="cancel-bulk-edit">
                    <i class="fas fa-times"></i> Cancel
                </button>
            </div>
        `;

        this.bindBulkEditEvents();
    }

    generateBulkFlagsSection(numChannels) {
        if (!numChannels || numChannels === 0) {
            return '';
        }

        const flagOptions = [
            { value: '', label: 'Keep current values' },
            { value: 0, label: 'None' },
            { value: 1, label: 'High' },
            { value: 2, label: 'Low' },
            { value: 3, label: 'Toggle' },
            { value: 4, label: 'Pulse' }
        ];

        const optionsHtml = flagOptions.map(opt => 
            `<option value="${opt.value}"${opt.value === '' ? ' selected' : ''}>${opt.label}</option>`
        ).join('');

        let channelsHtml = '';
        for (let channel = 1; channel <= numChannels; channel++) {
            channelsHtml += `
                <div class="flags-channel-group">
                    <label class="flags-channel-label">Channel ${channel}</label>
                    <div class="flags-row">
                        ${this.generateBulkFlagDropdown(channel, 'A', 0, optionsHtml)}
                        ${this.generateBulkFlagDropdown(channel, 'B', 1, optionsHtml)}
                        ${this.generateBulkFlagDropdown(channel, 'C', 2, optionsHtml)}
                        ${this.generateBulkFlagDropdown(channel, 'D', 3, optionsHtml)}
                    </div>
                </div>
            `;
        }

        return `
            <div class="element-flags-card">
                <div class="flags-card-header">
                    <i class="fas fa-flag"></i>
                    <span>Element Flags</span>
                </div>
                <div class="flags-card-body">
                    ${channelsHtml}
                </div>
            </div>
        `;
    }

    generateBulkFlagDropdown(channel, flagLabel, flagIndex, optionsHtml) {
        return `
            <div class="flag-group">
                <label for="bulk-flag-ch${channel}-${flagLabel}" class="flag-label">${flagLabel}</label>
                <select id="bulk-flag-ch${channel}-${flagLabel}" 
                        class="form-control flag-select bulk-flag-select" 
                        data-channel="${channel}" 
                        data-flag-index="${flagIndex}">
                    ${optionsHtml}
                </select>
            </div>
        `;
    }

    hideBulkEditControls() {
        this.bulkEditMode = false;
        if (this.currentElement) {
            this.showElement(this.currentElement);
        } else {
            this.showEmpty();
        }
    }

    bindBulkEditEvents() {
        const applyBtn = document.getElementById('apply-bulk-changes');
        const cancelBtn = document.getElementById('cancel-bulk-edit');

        if (applyBtn) {
            applyBtn.addEventListener('click', () => {
                this.applyBulkChanges();
            });
        }

        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => {
                this.selectedElements.clear();
                this.updateSelectionUI();
                this.updateBulkEditMode();
            });
        }
    }

    applyBulkChanges() {
        const triggerInput = document.getElementById('bulk-trigger-input');
        const repetitions = document.getElementById('bulk-repetitions');
        const timeline = window.sequencerApp?.timeline;

        if (!timeline) return;

        // Apply updates to each selected element
        this.selectedElements.forEach(position => {
            const updates = {};
            
            // Only update properties that have values
            if (triggerInput && triggerInput.value !== '') {
                updates.trigger_input = parseInt(triggerInput.value);
            }
            
            if (repetitions && repetitions.value !== '') {
                let value = parseInt(repetitions.value);
                // Validate range
                if (value < 1) value = 1;
                if (value > 65536) value = 65536;
                updates.repetitions = value;
            }

            // Collect flag updates
            const bulkFlagSelects = document.querySelectorAll('.bulk-flag-select');
            if (bulkFlagSelects.length > 0) {
                // Get the current element to preserve existing flags
                const seqElement = this.sequenceElements.find(el => el.position === position);
                if (seqElement) {
                    // Start with existing flags or empty object
                    const flags = seqElement.flags ? JSON.parse(JSON.stringify(seqElement.flags)) : {};
                    
                    // Update flags that have been changed (not "Keep current values")
                    bulkFlagSelects.forEach(select => {
                        if (select.value !== '') {
                            const channel = parseInt(select.dataset.channel);
                            const flagIndex = parseInt(select.dataset.flagIndex);
                            const flagValue = parseInt(select.value);
                            
                            const channelKey = `channel_${channel}`;
                            // Initialize channel flags if not present
                            if (!flags[channelKey]) {
                                flags[channelKey] = [0, 0, 0, 0];
                            }
                            
                            // Update the specific flag
                            flags[channelKey][flagIndex] = flagValue;
                        }
                    });
                    
                    // Only include flags in updates if any were changed
                    const hasChangedFlags = Array.from(bulkFlagSelects).some(select => select.value !== '');
                    if (hasChangedFlags) {
                        updates.flags = flags;
                    }
                }
            }

            // Apply updates if there are any
            if (Object.keys(updates).length > 0) {
                timeline.updateElement(position, updates);
            }
        });

        // Clear selection and return to normal mode
        this.selectedElements.clear();
        this.updateSelectionUI();
        this.updateBulkEditMode();
    }

    // Element Flags Methods
    generateFlagsCard(sequenceElement) {
        const element = sequenceElement.element;
        const numChannels = element.num_channels;
        
        if (!numChannels || numChannels === 0) {
            return '';
        }

        // Get existing flags or initialize with defaults
        const flags = sequenceElement.flags || {};
        
        let channelsHtml = '';
        for (let channel = 1; channel <= numChannels; channel++) {
            const channelKey = `channel_${channel}`;
            const channelFlags = flags[channelKey] || [0, 0, 0, 0]; // Default to None
            
            channelsHtml += `
                <div class="flags-channel-group">
                    <label class="flags-channel-label">Channel ${channel}</label>
                    <div class="flags-row">
                        ${this.generateFlagDropdown(channel, 'A', 0, channelFlags[0])}
                        ${this.generateFlagDropdown(channel, 'B', 1, channelFlags[1])}
                        ${this.generateFlagDropdown(channel, 'C', 2, channelFlags[2])}
                        ${this.generateFlagDropdown(channel, 'D', 3, channelFlags[3])}
                    </div>
                </div>
            `;
        }

        return `
            <div class="element-flags-card">
                <div class="flags-card-header">
                    <i class="fas fa-flag"></i>
                    <span>Element Flags</span>
                </div>
                <div class="flags-card-body">
                    ${channelsHtml}
                </div>
            </div>
        `;
    }

    generateFlagDropdown(channel, flagLabel, flagIndex, selectedValue) {
        const options = [
            { value: 0, label: 'None' },
            { value: 1, label: 'High' },
            { value: 2, label: 'Low' },
            { value: 3, label: 'Toggle' },
            { value: 4, label: 'Pulse' }
        ];

        const optionsHtml = options.map(opt => 
            `<option value="${opt.value}" ${opt.value === selectedValue ? 'selected' : ''}>${opt.label}</option>`
        ).join('');

        return `
            <div class="flag-group">
                <label for="flag-ch${channel}-${flagLabel}" class="flag-label">${flagLabel}</label>
                <select id="flag-ch${channel}-${flagLabel}" 
                        class="form-control flag-select" 
                        data-channel="${channel}" 
                        data-flag-index="${flagIndex}">
                    ${optionsHtml}
                </select>
            </div>
        `;
    }

    bindFlagsEvents() {
        const flagSelects = document.querySelectorAll('.flag-select');
        
        flagSelects.forEach(select => {
            select.addEventListener('change', (e) => {
                this.updateFlag(e.target);
            });
        });
    }

    updateFlag(selectElement) {
        if (!this.currentElement) return;

        const channel = parseInt(selectElement.dataset.channel);
        const flagIndex = parseInt(selectElement.dataset.flagIndex);
        const flagValue = parseInt(selectElement.value);

        // Get current flags or initialize
        const flags = this.currentElement.flags || {};
        const channelKey = `channel_${channel}`;
        const channelFlags = flags[channelKey] || [0, 0, 0, 0];
        
        // Update the specific flag
        channelFlags[flagIndex] = flagValue;
        flags[channelKey] = channelFlags;

        // Update element property
        this.updateElementProperty('flags', flags);
    }
}
