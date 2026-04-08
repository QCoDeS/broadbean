/**
 * Parametric Sequence Generator
 * Allows users to create parametric sequences from existing elements
 */

// Global state
let currentElement = null;
let selectedSegments = new Map(); // Map<segmentKey, segmentData>
let parameterConfigs = new Map(); // Map<paramKey, config>

// Global sequence element settings
let globalTriggerInput = 1; // Default: Trigger A
let globalRepetitions = 1;
let globalFlags = {}; // Will be populated based on number of channels

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    loadElements();
    initializeLoopConfig();
    initializeGlobalSettings();
    attachEventListeners();
});

/**
 * Load all available waveform elements
 */
async function loadElements() {
    try {
        const response = await fetch('/api/elements/');
        const data = await response.json();

        if (data.success) {
            displayElements(data.elements);
        } else {
            showError('Failed to load elements: ' + data.error);
        }
    } catch (error) {
        console.error('Error loading elements:', error);
        showError('Failed to load elements');
    }
}

/**
 * Display elements in the library panel
 */
function displayElements(elements) {
    const container = document.getElementById('element-library');

    if (elements.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-inbox"></i>
                <p>No elements available</p>
                <p class="small">Create elements in the Designer first</p>
            </div>
        `;
        return;
    }

    container.innerHTML = '';

    elements.forEach(element => {
        const card = document.createElement('div');
        card.className = 'library-card';
        card.dataset.elementId = element.id;

        card.innerHTML = `
            <div class="library-card-header">${element.name}</div>
            ${element.description ? `<p class="library-card-description">${CommonUtils.escapeHtml(element.description)}</p>` : ''}
        `;

        card.addEventListener('click', () => selectElement(element.id));
        container.appendChild(card);
    });
}

/**
 * Select an element and load its structure
 */
async function selectElement(elementId) {
    try {
        showLoading('Loading element...');

        const response = await fetch(`/api/elements/${elementId}/`);
        const data = await response.json();

        hideLoading();

        if (data.success) {
            currentElement = data.element;

            // Update UI
            document.querySelectorAll('.element-card').forEach(card => {
                card.classList.toggle('selected', card.dataset.elementId == elementId);
            });

            // Clear previous selections
            selectedSegments.clear();
            parameterConfigs.clear();

            // Generate flags UI based on number of channels
            generateGlobalFlags(currentElement.num_channels);

            // Display element structure
            displayElementStructure();
            updateSweepConfig();
            updateGenerateButton();
        } else {
            showError('Failed to load element: ' + data.error);
        }
    } catch (error) {
        hideLoading();
        console.error('Error loading element:', error);
        showError('Failed to load element');
    }
}

/**
 * Display the element structure (channels and segments) using timeline-style cards
 */
function displayElementStructure() {
    const container = document.getElementById('segment-selector');

    if (!currentElement) {
        container.innerHTML = `
            <div class="no-element-loaded">
                <i class="fas fa-arrow-left"></i>
                <p>Load an element to configure parameter sweeps</p>
            </div>
        `;
        return;
    }

    container.innerHTML = '';

    const channels = currentElement.channels || [];
    const elementData = currentElement.element_data || {};

    // Create a mapping of (channel, segment_index) to actual broadbean segment name
    const segmentNameMap = {};
    for (const [channelStr, channelData] of Object.entries(elementData)) {
        if (!/^\d+$/.test(channelStr)) continue; // Skip non-numeric keys
        const channelIdx = parseInt(channelStr) - 1; // Convert to 0-indexed

        // Get segment keys and sort them (segment_0, segment_1, etc.)
        const segmentKeys = Object.keys(channelData)
            .filter(k => k.startsWith('segment_'))
            .sort();

        segmentKeys.forEach((segKey, segmentIdx) => {
            const segData = channelData[segKey];
            if (segData && typeof segData === 'object' && segData.name) {
                segmentNameMap[`${channelIdx}_${segmentIdx}`] = segData.name;
            }
        });
    }

    channels.forEach((channel, channelIdx) => {
        const channelDiv = document.createElement('div');
        channelDiv.className = 'channel-segments';

        const channelHeader = document.createElement('div');
        channelHeader.className = 'channel-header';
        channelHeader.innerHTML = `<i class="fas fa-signal"></i> Channel ${channelIdx + 1}`;
        channelDiv.appendChild(channelHeader);

        const segments = channel.segments || [];

        const segmentsRow = document.createElement('div');
        segmentsRow.className = 'segments-card-row';

        segments.forEach((segment, segmentIdx) => {
            const segmentKey = `ch${channelIdx}_seg${segmentIdx}`;

            // Get the actual segment name from element_data
            const actualSegmentName = segmentNameMap[`${channelIdx}_${segmentIdx}`];

            // Create an enhanced segment object with the actual name
            const enhancedSegment = {
                ...segment,
                actualName: actualSegmentName || segment.name // Fallback to channels name if not in element_data
            };

            const segmentCard = createSegmentCard(enhancedSegment, channelIdx, segmentIdx, segmentKey);
            segmentsRow.appendChild(segmentCard);
        });

        channelDiv.appendChild(segmentsRow);
        container.appendChild(channelDiv);
    });
}

/**
 * Create a segment card (timeline style) with checkbox
 */
function createSegmentCard(segment, channelIdx, segmentIdx, segmentKey) {
    const card = document.createElement('div');
    card.className = 'segment-card';
    card.dataset.segmentKey = segmentKey;

    const icon = getSegmentIcon(segment.type);

    // Use actualName if available (from element_data), otherwise fall back to name from channels
    const displayName = segment.actualName || segment.name || segment.type;

    // Format duration or absolute time
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
        <div class="segment-card-checkbox">
            <input type="checkbox" id="seg-${segmentKey}"
                   data-segment-key="${segmentKey}"
                   data-channel-idx="${channelIdx}"
                   data-segment-idx="${segmentIdx}">
        </div>
        <div class="segment-card-content">
            <div class="segment-card-header">
                <i class="segment-card-icon ${icon}"></i>
                <span class="segment-card-title">${displayName}</span>
            </div>
            <div class="segment-card-body">
                ${timeDisplay}
                ${getAmplitudeDisplay(segment)}
            </div>
        </div>
    `;

    // Add event listener to checkbox
    const checkbox = card.querySelector('input[type="checkbox"]');
    checkbox.addEventListener('change', (e) => {
        handleSegmentSelection(e.target.checked, channelIdx, segmentIdx, segment);
        card.classList.toggle('selected', e.target.checked);
    });

    return card;
}

/**
 * Get segment icon class based on type
 */
function getSegmentIcon(type) {
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


/**
 * Get amplitude display for segment
 */
function getAmplitudeDisplay(segment) {
    if (segment.type === 'ramp') {
        const startAmp = segment.parameters?.start || 0;
        const stopAmp = segment.parameters?.stop || 0;
        return `
            <div class="segment-detail">
                <i class="fas fa-signal"></i>
                <span class="segment-detail-value">${startAmp} - ${stopAmp}V</span>
            </div>
        `;
    } else if (segment.amplitude !== undefined) {
        return `
            <div class="segment-detail">
                <i class="fas fa-signal"></i>
                <span class="segment-detail-value">${segment.amplitude} V</span>
            </div>
        `;
    }
    return '';
}

/**
 * Handle segment selection/deselection
 */
function handleSegmentSelection(isSelected, channelIdx, segmentIdx, segment) {
    const segmentKey = `ch${channelIdx}_seg${segmentIdx}`;

    if (isSelected) {
        selectedSegments.set(segmentKey, {
            channelIdx,
            segmentIdx,
            segment,
            parameters: getAvailableParameters(segment)
        });
    } else {
        selectedSegments.delete(segmentKey);

        // Remove all parameter configs for this segment
        const keysToDelete = [];
        parameterConfigs.forEach((config, key) => {
            if (key.startsWith(segmentKey + '_')) {
                keysToDelete.push(key);
            }
        });
        keysToDelete.forEach(key => parameterConfigs.delete(key));
    }

    updateSweepConfig();
    updateGenerateButton();
}

/**
 * Get available parameters for a segment type
 */
function getAvailableParameters(segment) {
    const type = segment.type;
    const params = segment.parameters || {};

    const paramList = [];

    switch (type) {
        case 'ramp':
            paramList.push(
                { name: 'duration', label: 'Duration', value: segment.duration },
                { name: 'start', label: 'Start', value: params.start || 0 },
                { name: 'stop', label: 'Stop', value: params.stop || 1 }
            );
            break;

        case 'sine':
            paramList.push(
                { name: 'duration', label: 'Duration', value: segment.duration },
                { name: 'amplitude', label: 'Amplitude', value: segment.amplitude || 1 },
                { name: 'frequency', label: 'Frequency', value: params.frequency || 1e6 },
                { name: 'phase', label: 'Phase', value: params.phase || 0 },
                { name: 'offset', label: 'Offset', value: params.offset || 0 }
            );
            break;

        case 'gaussian':
            paramList.push(
                { name: 'duration', label: 'Duration', value: segment.duration },
                { name: 'amplitude', label: 'Amplitude', value: segment.amplitude || 1 },
                { name: 'width', label: 'Width', value: params.width },
                { name: 'center', label: 'Center', value: params.center },
                { name: 'offset', label: 'Offset', value: params.offset || 0 }
            );
            break;

        case 'exponential':
            paramList.push(
                { name: 'duration', label: 'Duration', value: segment.duration },
                { name: 'amplitude', label: 'Amplitude', value: segment.amplitude || 1 },
                { name: 'time_constant', label: 'Time Constant', value: params.time_constant }
            );
            break;

        case 'waituntil':
            paramList.push(
                { name: 'absolute_time', label: 'Absolute Time', value: params.absolute_time }
            );
            break;

        case 'custom':
            paramList.push(
                { name: 'duration', label: 'Duration', value: segment.duration }
            );
            // Could add custom parameters from params_json here
            break;

        default:
            paramList.push(
                { name: 'duration', label: 'Duration', value: segment.duration }
            );
    }

    return paramList;
}

/**
 * Update the sweep configuration display
 */
function updateSweepConfig() {
    const container = document.getElementById('sweep-config');

    if (selectedSegments.size === 0) {
        container.innerHTML = `
            <div class="empty-state">
                Select segment parameters above to configure sweeps
            </div>
        `;
        return;
    }

    // BUGFIX: Preserve current loop selections from DOM before rebuilding
    const loopSelects = container.querySelectorAll('select[data-field="loop"]');
    loopSelects.forEach(select => {
        const paramKey = select.dataset.paramKey;
        const selectedLoop = parseInt(select.value);
        const config = parameterConfigs.get(paramKey);
        if (config) {
            config.loop = selectedLoop;
            parameterConfigs.set(paramKey, config);
        }
    });

    container.innerHTML = '';

    selectedSegments.forEach((segmentData, segmentKey) => {
        const { channelIdx, segmentIdx, segment, parameters } = segmentData;

        const segmentGroup = document.createElement('div');
        segmentGroup.style.marginBottom = '1.5rem';

        // Use actualName if available
        const displayName = segment.actualName || segment.name || `Segment ${segmentIdx + 1}`;

        const groupTitle = document.createElement('h5');
        groupTitle.textContent = `Channel ${channelIdx + 1} - ${displayName}`;
        groupTitle.style.marginBottom = '0.75rem';
        segmentGroup.appendChild(groupTitle);

        parameters.forEach(param => {
            const paramKey = `${segmentKey}_${param.name}`;
            const paramGroup = createParameterGroup(paramKey, segmentData, param);
            segmentGroup.appendChild(paramGroup);
        });

        container.appendChild(segmentGroup);
    });
}

/**
 * Create a parameter group UI element
 */
function createParameterGroup(paramKey, segmentData, param) {
    const group = document.createElement('div');
    group.className = 'param-group';

    // Header with checkbox
    const header = document.createElement('div');
    header.className = 'param-group-header';

    const checkboxLabel = document.createElement('div');
    checkboxLabel.className = 'param-checkbox';

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.id = `param-${paramKey}`;
    checkbox.checked = parameterConfigs.has(paramKey);

    checkbox.addEventListener('change', (e) => {
        handleParameterToggle(e.target.checked, paramKey, segmentData, param);
    });

    checkboxLabel.appendChild(checkbox);

    const label = document.createElement('label');
    label.htmlFor = `param-${paramKey}`;
    label.className = 'param-group-title';
    label.textContent = param.label;
    label.style.cursor = 'pointer';
    checkboxLabel.appendChild(label);

    header.appendChild(checkboxLabel);
    group.appendChild(header);

    // Controls (only shown if enabled)
    const config = parameterConfigs.get(paramKey);
    if (config) {
        const controls = document.createElement('div');
        controls.className = 'param-controls';

        // Start value
        const startControl = document.createElement('div');
        startControl.className = 'param-control';
        startControl.innerHTML = `
            <label>Start Value:</label>
            <input type="number" step="any" value="${config.start}"
                   data-param-key="${paramKey}" data-field="start">
        `;
        controls.appendChild(startControl);

        // Stop value
        const stopControl = document.createElement('div');
        stopControl.className = 'param-control';
        stopControl.innerHTML = `
            <label>Stop Value:</label>
            <input type="number" step="any" value="${config.stop}"
                   data-param-key="${paramKey}" data-field="stop">
        `;
        controls.appendChild(stopControl);

        // Interpolation type
        const interpControl = document.createElement('div');
        interpControl.className = 'param-control';
        interpControl.innerHTML = `
            <label>Interpolation:</label>
            <select data-param-key="${paramKey}" data-field="interpolation">
                <option value="linear" ${config.interpolation === 'linear' ? 'selected' : ''}>Linear</option>
                <option value="log" ${config.interpolation === 'log' ? 'selected' : ''}>Logarithmic</option>
            </select>
        `;
        controls.appendChild(interpControl);

        // Loop assignment
        const loopControl = document.createElement('div');
        loopControl.className = 'param-control';
        const numLoops = parseInt(document.getElementById('num-loops').value);
        let loopOptions = '';
        for (let i = 0; i < numLoops; i++) {
            loopOptions += `<option value="${i}" ${config.loop === i ? 'selected' : ''}>Loop ${i}</option>`;
        }
        loopControl.innerHTML = `
            <label>Loop:</label>
            <select data-param-key="${paramKey}" data-field="loop">
                ${loopOptions}
            </select>
        `;
        controls.appendChild(loopControl);

        // Add change listeners
        controls.querySelectorAll('input, select').forEach(input => {
            input.addEventListener('change', handleParameterConfigChange);
        });

        group.appendChild(controls);
    }

    return group;
}

/**
 * Handle parameter toggle
 */
function handleParameterToggle(isEnabled, paramKey, segmentData, param) {
    if (isEnabled) {
        // Add parameter configuration with default values
        parameterConfigs.set(paramKey, {
            segmentKey: `ch${segmentData.channelIdx}_seg${segmentData.segmentIdx}`,
            channelIdx: segmentData.channelIdx,
            segmentIdx: segmentData.segmentIdx,
            paramName: param.name,
            start: param.value || 0,
            stop: param.value || 1,
            interpolation: 'linear',
            loop: 0,
            segment: segmentData.segment  // Store the full segment data including actualName
        });
    } else {
        parameterConfigs.delete(paramKey);
    }

    // Update button state immediately after modifying parameterConfigs
    updateGenerateButton();

    // Then rebuild UI
    updateSweepConfig();
    updateTotalElements();
}

/**
 * Handle parameter configuration change
 */
function handleParameterConfigChange(e) {
    const paramKey = e.target.dataset.paramKey;
    const field = e.target.dataset.field;
    const value = e.target.type === 'number' ? parseFloat(e.target.value) : e.target.value;

    const config = parameterConfigs.get(paramKey);
    if (config) {
        config[field] = value;
        parameterConfigs.set(paramKey, config);
        updateTotalElements();
    }
}

/**
 * Initialize loop configuration
 */
function initializeLoopConfig() {
    updateLoopInputs();
    updateTotalElements();
}

/**
 * Update loop iteration inputs based on number of loops
 */
function updateLoopInputs() {
    const numLoops = parseInt(document.getElementById('num-loops').value);
    const container = document.getElementById('loop-config');

    container.innerHTML = '';

    for (let i = 0; i < numLoops; i++) {
        const loopItem = document.createElement('div');
        loopItem.className = 'loop-item';

        loopItem.innerHTML = `
            <label>Loop ${i}:</label>
            <input type="number" min="1" value="5" step="1"
                   class="loop-iterations" data-loop="${i}">
            <span class="small text-muted">iterations</span>
        `;

        const input = loopItem.querySelector('input');
        input.addEventListener('change', updateTotalElements);

        container.appendChild(loopItem);
    }

    // Update loop options in parameter configs
    updateSweepConfig();
}

/**
 * Calculate and update total elements display
 */
function updateTotalElements() {
    const loopInputs = document.querySelectorAll('.loop-iterations');
    let total = 1;

    loopInputs.forEach(input => {
        const value = parseInt(input.value) || 1;
        total *= value;
    });

    document.getElementById('total-elements').textContent = total;
}

/**
 * Update generate button state
 */
function updateGenerateButton() {
    const generateBtn = document.getElementById('generate-btn');

    const hasConfig = currentElement && parameterConfigs.size > 0;

    generateBtn.disabled = !hasConfig;
}

/**
 * Initialize global sequence element settings
 */
function initializeGlobalSettings() {
    // Trigger input default (Trigger A = 1)
    const triggerInput = document.getElementById('global-trigger-input');
    triggerInput.value = globalTriggerInput;
    triggerInput.addEventListener('change', (e) => {
        globalTriggerInput = parseInt(e.target.value);
    });

    // Repetitions default (1)
    const repetitions = document.getElementById('global-repetitions');
    repetitions.value = globalRepetitions;
    repetitions.addEventListener('change', (e) => {
        let value = parseInt(e.target.value);
        if (value < 1) value = 1;
        if (value > 65536) value = 65536;
        e.target.value = value;
        globalRepetitions = value;
    });
}

/**
 * Generate flags UI based on number of channels
 */
function generateGlobalFlags(numChannels) {
    const container = document.getElementById('global-flags-container');
    const flagsBody = document.getElementById('global-flags-body');

    if (!numChannels || numChannels === 0) {
        container.style.display = 'none';
        return;
    }

    // Show the flags container
    container.style.display = 'block';

    // Clear existing flags
    flagsBody.innerHTML = '';

    // Initialize globalFlags with default values (Flag A = Pulse (4), others = None (0))
    globalFlags = {};

    for (let channel = 1; channel <= numChannels; channel++) {
        const channelKey = `channel_${channel}`;
        // Default: Flag A = Pulse (4), Flags B, C, D = None (0)
        globalFlags[channelKey] = [4, 0, 0, 0];

        const channelGroup = document.createElement('div');
        channelGroup.className = 'flags-channel-group';

        const channelLabel = document.createElement('label');
        channelLabel.className = 'flags-channel-label';
        channelLabel.textContent = `Channel ${channel}`;
        channelGroup.appendChild(channelLabel);

        const flagsRow = document.createElement('div');
        flagsRow.className = 'flags-row';

        // Create flag dropdowns A, B, C, D
        const flagLabels = ['A', 'B', 'C', 'D'];
        flagLabels.forEach((flagLabel, flagIndex) => {
            const flagGroup = document.createElement('div');
            flagGroup.className = 'flag-group';

            const label = document.createElement('label');
            label.className = 'flag-label';
            label.textContent = flagLabel;
            label.htmlFor = `global-flag-ch${channel}-${flagLabel}`;
            flagGroup.appendChild(label);

            const select = document.createElement('select');
            select.id = `global-flag-ch${channel}-${flagLabel}`;
            select.className = 'flag-select';
            select.dataset.channel = channel;
            select.dataset.flagIndex = flagIndex;

            // Flag options
            const options = [
                { value: 0, label: 'None' },
                { value: 1, label: 'High' },
                { value: 2, label: 'Low' },
                { value: 3, label: 'Toggle' },
                { value: 4, label: 'Pulse' }
            ];

            options.forEach(opt => {
                const option = document.createElement('option');
                option.value = opt.value;
                option.textContent = opt.label;
                // Set default: Flag A = Pulse, others = None
                if (flagIndex === 0 && opt.value === 4) {
                    option.selected = true;
                } else if (flagIndex !== 0 && opt.value === 0) {
                    option.selected = true;
                }
                select.appendChild(option);
            });

            // Add change listener
            select.addEventListener('change', (e) => {
                const ch = parseInt(e.target.dataset.channel);
                const flagIdx = parseInt(e.target.dataset.flagIndex);
                const flagValue = parseInt(e.target.value);

                const chKey = `channel_${ch}`;
                if (!globalFlags[chKey]) {
                    globalFlags[chKey] = [0, 0, 0, 0];
                }
                globalFlags[chKey][flagIdx] = flagValue;
            });

            flagGroup.appendChild(select);
            flagsRow.appendChild(flagGroup);
        });

        channelGroup.appendChild(flagsRow);
        flagsBody.appendChild(channelGroup);
    }
}

/**
 * Attach event listeners
 */
function attachEventListeners() {
    // Number of loops selector
    document.getElementById('num-loops').addEventListener('change', function() {
        updateLoopInputs();
        updateTotalElements();
    });

    // Generate button
    document.getElementById('generate-btn').addEventListener('click', generateSequence);
}

/**
 * Generate and save the parametric sequence
 */
async function generateSequence() {
    // Show the modal to get sequence name and description
    showSaveSequenceModal();
}

/**
 * Show the save sequence modal
 */
function showSaveSequenceModal() {
    const modal = document.getElementById('save-sequence-modal');
    const nameInput = document.getElementById('modal-sequence-name');
    const descInput = document.getElementById('modal-sequence-description');
    const saveBtn = document.getElementById('save-modal-save');
    const cancelBtn = document.getElementById('save-modal-cancel');
    const backdrop = modal.querySelector('.custom-modal-backdrop');
    const nameError = document.getElementById('modal-name-error');

    // Clear previous input
    nameInput.value = '';
    descInput.value = '';
    nameInput.classList.remove('is-invalid');
    nameError.style.display = 'none';

    // Show modal
    modal.style.display = 'flex';

    // Focus name input
    setTimeout(() => nameInput.focus(), 100);

    // Handle save button click
    const handleSave = async () => {
        const name = nameInput.value.trim();

        if (!name) {
            nameInput.classList.add('is-invalid');
            nameError.style.display = 'block';
            nameInput.focus();
            return;
        }

        const config = gatherConfiguration();

        if (!config) {
            cleanup();
            return;
        }

        config.name = name;
        config.description = descInput.value.trim();

        // Close modal
        cleanup();

        try {
            showLoading('Generating sequence...');

            const response = await fetch('/api/parametric/generate/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(config)
            });

            const data = await response.json();
            hideLoading();

            if (data.success) {
                showStatus(`Sequence "${data.sequence_name}" created with ${data.num_elements} elements!`);
            } else {
                showError('Generation failed: ' + data.error);
            }
        } catch (error) {
            hideLoading();
            console.error('Error generating sequence:', error);
            showError('Failed to generate sequence');
        }
    };

    // Handle cancel
    const handleCancel = () => {
        cleanup();
    };

    // Cleanup function
    const cleanup = () => {
        modal.style.display = 'none';
        saveBtn.removeEventListener('click', handleSave);
        cancelBtn.removeEventListener('click', handleCancel);
        backdrop.removeEventListener('click', handleCancel);
        document.removeEventListener('keydown', handleEscape);
    };

    // Handle ESC key
    const handleEscape = (e) => {
        if (e.key === 'Escape') {
            handleCancel();
        } else if (e.key === 'Enter' && document.activeElement === nameInput) {
            handleSave();
        }
    };

    // Bind events
    saveBtn.addEventListener('click', handleSave);
    cancelBtn.addEventListener('click', handleCancel);
    backdrop.addEventListener('click', handleCancel);
    document.addEventListener('keydown', handleEscape);
}

/**
 * Gather current configuration for API call
 */
function gatherConfiguration() {
    if (!currentElement) {
        showError('No element selected');
        return null;
    }

    if (parameterConfigs.size === 0) {
        showError('No parameters configured');
        return null;
    }

    // Get loop iterations
    const loopInputs = document.querySelectorAll('.loop-iterations');
    const loopIterations = Array.from(loopInputs).map(input => parseInt(input.value) || 1);

    // Organize parameter configs by loop
    const paramsByLoop = {};

    parameterConfigs.forEach((config, paramKey) => {
        const loop = config.loop;

        if (!paramsByLoop[loop]) {
            paramsByLoop[loop] = [];
        }

        // Get the actual segment name from element_data
        // Use the stored segment data which includes actualName
        const segment = config.segment || currentElement.channels[config.channelIdx].segments[config.segmentIdx];
        const segmentName = segment.actualName || segment.name || `segment_${config.segmentIdx}`;

        paramsByLoop[loop].push({
            channel: config.channelIdx + 1,  // 1-indexed
            segment_name: segmentName,
            segment_index: config.segmentIdx,  // Include segment index for backend
            parameter: config.paramName,
            start: config.start,
            stop: config.stop,
            interpolation: config.interpolation,
            loop: config.loop
        });
    });

    return {
        element_id: currentElement.id,
        loop_iterations: loopIterations,
        parameters: paramsByLoop,
        trigger_input: globalTriggerInput,
        repetitions: globalRepetitions,
        flags: globalFlags
    };
}

/**
 * Show loading overlay
 */
function showLoading(message = 'Processing...') {
    const overlay = document.getElementById('loading-overlay');
    const messageEl = document.getElementById('loading-message');
    messageEl.textContent = message;
    overlay.style.display = 'flex';
}

/**
 * Hide loading overlay
 */
function hideLoading() {
    document.getElementById('loading-overlay').style.display = 'none';
}

/**
 * Show error message
 */
function showError(message) {
    CommonUtils.showError(message);
}

/**
 * Show status message
 */
function showStatus(message) {
    const statusSection = document.getElementById('status-section');
    const statusInfo = document.getElementById('status-info');

    statusInfo.innerHTML = `
        <div class="alert alert-success">
            <i class="fas fa-check-circle"></i> ${message}
        </div>
    `;

    statusSection.style.display = 'block';

    // Hide after 5 seconds
    setTimeout(() => {
        statusSection.style.display = 'none';
    }, 5000);
}
