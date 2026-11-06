/**
 * Properties Panel Component
 * Handles the properties inspector and segment list
 */

class PropertiesPanel {
    constructor() {
        this.selectedSegment = null;
        this.segmentLibrary = null;
        this.timeline = null;
        this.sampleRate = window.waveformDesignerSettings?.defaultSampleRate || 25e9; // Default from settings

        this.propertiesContent = document.getElementById('properties-content');
        this.sampleRateInput = document.getElementById('sample-rate');

        this.bindEvents();
        this.setupGlobalSettings();
    }

    setReferences(timeline, segmentLibrary) {
        this.timeline = timeline;
        this.segmentLibrary = segmentLibrary;
    }

    bindEvents() {
        // Listen for segment selection events with validation
        window.addEventListener('segmentSelected', (e) => {
            this.handleSegmentSelection(e.detail);
        });

        // Listen for segment updates
        window.addEventListener('segmentAdded', (e) => {
            // Segment list removed - no action needed
        });

        window.addEventListener('segmentRemoved', (e) => {
            if (this.selectedSegment && this.selectedSegment.id === e.detail.id) {
                this.selectSegment(null);
            }
        });

        window.addEventListener('segmentUpdated', (e) => {
            if (this.selectedSegment && this.selectedSegment.id === e.detail.id) {
                this.selectedSegment = e.detail;
                this.updateProperties();
            }
        });

        window.addEventListener('segmentsCleared', () => {
            this.selectSegment(null);
        });

        window.addEventListener('segmentsReordered', () => {
            // Segment list removed - no action needed
        });
    }

    setupGlobalSettings() {
        if (this.sampleRateInput) {
            // Set initial value
            this.sampleRateInput.value = this.sampleRate;

            // Bind event listeners for sample rate changes
            this.sampleRateInput.addEventListener('change', (e) => {
                this.updateGlobalSampleRate(e.target.value);
            });

            this.sampleRateInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.target.blur();
                    this.updateGlobalSampleRate(e.target.value);
                }
            });

            this.sampleRateInput.addEventListener('blur', (e) => {
                this.updateGlobalSampleRate(e.target.value);
            });
        }

        // Listen for time scale changes
        const timeScaleSelect = document.getElementById('time-units');
        if (timeScaleSelect) {
            timeScaleSelect.addEventListener('change', (e) => {
                this.currentTimeUnits = e.target.value;
                this.updateTimeUnits();
                // Re-render properties to update labels
                if (this.selectedSegment) {
                    this.renderProperties();
                }
            });
            // Set initial time units
            this.currentTimeUnits = timeScaleSelect.value;
        }


        // Update the global reference for cross-component access
        window.propertiesPanel = this;
    }

    updateGlobalSampleRate(value) {
        const parsedValue = parseFloat(value);
        if (isNaN(parsedValue) || parsedValue <= 0) return;

        this.sampleRate = parsedValue;

        // Notify other components about the sample rate change
        window.dispatchEvent(new CustomEvent('settingChanged', {
            detail: { setting: 'sampleRate', value: this.sampleRate }
        }));
    }

    getSampleRate() {
        return this.sampleRate;
    }

    getTimeUnits() {
        return this.currentTimeUnits || 'us';
    }

    getTimeScaleInfo() {
        // Map time unit values to display info
        const timeScales = {
            'ns': { unit: 'ns', factor: 1e9, symbol: 'ns' },
            'us': { unit: 'μs', factor: 1e6, symbol: 'μs' },
            'ms': { unit: 'ms', factor: 1e3, symbol: 'ms' },
            's': { unit: 's', factor: 1, symbol: 's' }
        };
        return timeScales[this.currentTimeUnits] || timeScales['us'];
    }


    updateTimeUnits() {
        // This method will be called when the time scale changes
        // The labels will be updated when properties are re-rendered
    }

    handleSegmentSelection(segment) {
        // Validate selection state and prevent conflicts during element loading
        const isLoadingElement = window.waveformDesigner?.isLoadingElement || false;

        // Queue selection events during bulk loading
        if (isLoadingElement) {
            this.pendingSelection = segment;
            return;
        }

        // Process any pending selection from bulk loading
        if (this.pendingSelection) {
            segment = this.pendingSelection;
            this.pendingSelection = null;
        }

        // Update selection
        this.selectSegment(segment);
    }

    selectSegment(segment) {
        this.selectedSegment = segment;
        this.renderProperties();
    }

    renderProperties() {
        if (!this.selectedSegment) {
            this.propertiesContent.innerHTML = '<p class="no-selection">Select a segment to edit its properties</p>';
            return;
        }

        const segmentType = this.segmentLibrary?.getSegmentType(this.selectedSegment.type);
        if (!segmentType) {
            this.propertiesContent.innerHTML = '<p class="no-selection">Invalid segment type</p>';
            return;
        }

        const form = this.createPropertyForm(this.selectedSegment, segmentType);
        this.propertiesContent.innerHTML = '';
        this.propertiesContent.appendChild(form);
    }

    createPropertyForm(segment, segmentType) {
        const form = document.createElement('div');
        form.className = 'property-form';

        // Segment info header
        const header = document.createElement('div');
        header.innerHTML = `
            <h5 style="margin: 0 0 15px 0; color: ${segment.color}; font-size: 0.9rem; font-weight: 500;">
                ${segmentType.name} Segment
            </h5>
        `;
        form.appendChild(header);

        // Name field - always shown first
        form.appendChild(this.createPropertyGroup('Name', 'name', segment.name, 'text'));

        // Common properties - Duration is shown for all segments except waituntil
        if (segment.type !== 'waituntil') {
            const durationConfig = this.getParameterConfig('duration');
            form.appendChild(this.createPropertyGroup(durationConfig.label, 'duration', segment.duration, durationConfig.type, durationConfig.unit, durationConfig.step));
        }

        // Only show amplitude for non-ramp, non-custom, and non-waituntil segments
        // (ramp uses start and stop, custom uses parameters, waituntil doesn't need amplitude)
        if (segment.type !== 'ramp' && segment.type !== 'custom' && segment.type !== 'waituntil') {
            const amplitudeConfig = this.getParameterConfig('amplitude');
            form.appendChild(this.createPropertyGroup(amplitudeConfig.label, 'amplitude', segment.amplitude, amplitudeConfig.type, amplitudeConfig.unit, amplitudeConfig.step));
        }

        // Segment-specific properties
        if (segment.type === 'custom') {
            // Custom segment: show expression and parameters JSON
            this.addCustomSegmentFields(form, segment);
        } else {
            // Regular segments: show standard parameters
            segmentType.parameters.forEach(param => {
                if (param !== 'duration' && param !== 'amplitude') {
                    const value = segment.parameters[param] ?? this.getDefaultParameterValue(param, segment.type);
                    const config = this.getParameterConfig(param);
                    form.appendChild(this.createPropertyGroup(config.label, param, value, config.type, config.unit, config.step));
                }
            });
        }

        // Markers section
        const markersSection = this.createMarkersSection(segment);
        form.appendChild(markersSection);

        // Delete button
        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'btn btn-sm';
        deleteBtn.style.cssText = 'background: #e74c3c; color: white; width: 100%; margin-top: 20px;';
        deleteBtn.textContent = 'Delete Segment';
        deleteBtn.onclick = () => this.deleteSegment();
        form.appendChild(deleteBtn);

        return form;
    }

    createPropertyGroup(label, property, value, type = 'number', unit = '', step = 0.001) {
        const group = document.createElement('div');
        group.className = 'property-group';

        const labelEl = document.createElement('label');
        labelEl.textContent = `${label}${unit ? ` (${unit})` : ''}:`;
        group.appendChild(labelEl);

        let input;
        if (type === 'select') {
            input = document.createElement('select');
            const config = this.getParameterConfig(property);

            // Add options based on property type
            if (property === 'type' && config.options) {
                // For exponential type dropdown
                config.options.forEach(option => {
                    const optionEl = document.createElement('option');
                    optionEl.value = option.value;
                    optionEl.textContent = option.label;
                    optionEl.selected = option.value === value;
                    input.appendChild(optionEl);
                });
            } else if (property === 'type') {
                // For general segment type dropdown (if needed)
                this.segmentLibrary?.getAllSegmentTypes().forEach(segType => {
                    const option = document.createElement('option');
                    option.value = segType.id;
                    option.textContent = segType.name;
                    option.selected = segType.id === value;
                    input.appendChild(option);
                });
            }
        } else {
            input = document.createElement('input');
            input.type = type;
            if (type === 'number') {
                input.step = step;
                input.value = this.formatNumberValue(value, property);
            } else {
                input.value = value;
            }
        }

        input.addEventListener('change', (e) => {
            this.updateSegmentProperty(property, e.target.value, type);
        });

        // Only update on Enter key for number inputs, not on every keystroke
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.target.blur(); // This will trigger the change event
                this.updateSegmentProperty(property, e.target.value, type);
            }
        });

        // Update when input loses focus (user clicks elsewhere)
        input.addEventListener('blur', (e) => {
            this.updateSegmentProperty(property, e.target.value, type);
        });

        group.appendChild(input);
        return group;
    }

    formatNumberValue(value, property) {
        // Format values for display based on property type and current scales
        if (property === 'duration' || property === 'rise_time' || property === 'fall_time' ||
            property === 'width' || property === 'center' || property === 'time_constant' ||
            property === 'absolute_time') {
            const timeInfo = this.getTimeScaleInfo();
            return (value * timeInfo.factor).toFixed(3); // Convert to current time scale
        } else if (property === 'amplitude' || property === 'start' || property === 'stop' || property === 'offset') {
            // Use fixed units (V) instead of dynamic amplitude scaling
            return value.toFixed(3);
        } else if (property === 'frequency') {
            return (value / 1e6).toFixed(3); // Convert to MHz
        }
        return value;
    }

    updateSegmentProperty(property, value, type) {
        if (!this.selectedSegment || !this.timeline) return;

        let parsedValue = value;

        if (type === 'number') {
            parsedValue = parseFloat(value);
            if (isNaN(parsedValue)) return;

            // Convert back to base units using current scales
            if (property === 'duration' || property === 'rise_time' || property === 'fall_time' ||
                property === 'width' || property === 'center' || property === 'time_constant' ||
                property === 'absolute_time' || property.endsWith('_delay') || property.endsWith('_duration')) {
                const timeInfo = this.getTimeScaleInfo();
                parsedValue = parsedValue / timeInfo.factor; // Convert from current time scale to seconds
            } else if (property === 'amplitude' || property === 'start' || property === 'stop' || property === 'offset') {
                // Use fixed units (V) - no conversion needed since input is already in V
                // parsedValue = parsedValue; // No conversion needed
            } else if (property === 'frequency') {
                parsedValue = parsedValue * 1e6; // Convert from MHz
            }

            // Validate minimum duration based on sample rate
            if (property === 'duration') {
                const minDuration = 1 / this.sampleRate;
                if (parsedValue < minDuration) {
                    const minDurationMicroseconds = minDuration * 1e6;
                    const inputDurationMicroseconds = parsedValue * 1e6;
                    const sampleRateGHz = this.sampleRate / 1e9;

                    // Show the Bootstrap modal instead of alert
                    this.showDurationWarningModal(
                        inputDurationMicroseconds,
                        minDurationMicroseconds,
                        sampleRateGHz,
                        event.target
                    );

                    parsedValue = minDuration;

                    // Update the input field to show the corrected value
                    const input = event.target;
                    if (input) {
                        input.value = minDurationMicroseconds.toFixed(3);
                    }
                }
            }

            // Validate marker properties to ensure they don't exceed segment duration
            if (property.startsWith('marker')) {
                const [markerName, markerProp] = property.split('_');
                const validatedValue = this.validateMarkerProperty(markerName, markerProp, parsedValue);
                if (validatedValue !== parsedValue) {
                    parsedValue = validatedValue;
                    // Update the input field to show the corrected value
                    const timeInfo = this.getTimeScaleInfo();
                    if (event && event.target) {
                        event.target.value = (parsedValue * timeInfo.factor).toFixed(3);
                    }
                }
            }
        }

        const updates = {};
        if (property === 'duration' || property === 'amplitude' || property === 'name') {
            updates[property] = parsedValue;
        } else if (property.startsWith('marker')) {
            // Handle marker property updates
            const [markerName, markerProp] = property.split('_');
            updates.markers = {
                ...this.selectedSegment.markers,
                [markerName]: {
                    ...this.selectedSegment.markers[markerName],
                    [markerProp]: parsedValue
                }
            };
        } else {
            updates.parameters = { ...this.selectedSegment.parameters, [property]: parsedValue };
        }

        this.timeline.updateSegment(this.selectedSegment.id, updates);
    }

    validateMarkerProperty(markerName, markerProp, value) {
        if (!this.selectedSegment) return value;

        const marker = this.selectedSegment.markers[markerName];
        const segmentDuration = this.selectedSegment.duration;

        // Get the other property value (delay or duration)
        const otherProp = markerProp === 'delay' ? 'duration' : 'delay';
        const otherValue = marker[otherProp];

        // Check if delay + duration would exceed segment duration
        const delay = markerProp === 'delay' ? value : otherValue;
        const duration = markerProp === 'duration' ? value : otherValue;

        if (delay + duration > segmentDuration) {
            const timeInfo = this.getTimeScaleInfo();
            const maxValue = Math.max(0, segmentDuration - otherValue);

            // Show warning and limit the value
            this.showMarkerWarningModal(
                markerName,
                markerProp,
                (value * timeInfo.factor).toFixed(3),
                (maxValue * timeInfo.factor).toFixed(3),
                timeInfo.symbol
            );

            return maxValue;
        }

        return value;
    }

    createMarkersSection(segment) {
        const section = document.createElement('div');
        section.className = 'markers-section';
        section.style.cssText = 'margin-top: 20px; padding-top: 15px; border-top: 1px solid #ecf0f1;';

        // Markers header
        const header = document.createElement('h6');
        header.textContent = 'Markers';
        header.style.cssText = 'margin: 0 0 15px 0; color: #2c3e50; font-size: 0.9rem; font-weight: 500;';
        section.appendChild(header);

        // Ensure markers exist (for backward compatibility)
        if (!segment.markers) {
            segment.markers = {
                marker1: { delay: 0, duration: 0 },
                marker2: { delay: 0, duration: 0 }
            };
        }

        // Create marker controls
        const timeInfo = this.getTimeScaleInfo();

        // Marker 1
        const marker1Group = this.createMarkerGroup('Marker 1', 'marker1', segment.markers.marker1, timeInfo);
        section.appendChild(marker1Group);

        // Marker 2
        const marker2Group = this.createMarkerGroup('Marker 2', 'marker2', segment.markers.marker2, timeInfo);
        section.appendChild(marker2Group);

        return section;
    }

    createMarkerGroup(label, markerName, markerData, timeInfo) {
        const group = document.createElement('div');
        group.className = 'marker-group';
        group.style.cssText = 'margin-bottom: 15px; padding: 10px; background: #f8f9fa; border-radius: 4px;';

        // Marker label
        const labelEl = document.createElement('div');
        labelEl.textContent = label;
        labelEl.style.cssText = 'font-weight: 500; margin-bottom: 8px; color: #495057; font-size: 0.85rem;';
        group.appendChild(labelEl);

        // Delay input
        const delayGroup = document.createElement('div');
        delayGroup.style.cssText = 'margin-bottom: 8px;';

        const delayLabel = document.createElement('label');
        delayLabel.textContent = `Delay (${timeInfo.symbol}):`;
        delayLabel.style.cssText = 'display: block; font-size: 0.8rem; color: #6c757d; margin-bottom: 3px;';

        const delayInput = document.createElement('input');
        delayInput.type = 'number';
        delayInput.step = 0.001;
        delayInput.value = (markerData.delay * timeInfo.factor).toFixed(3);
        delayInput.style.cssText = 'width: 100%; padding: 4px 8px; border: 1px solid #ced4da; border-radius: 3px; font-size: 0.8rem;';

        delayInput.addEventListener('change', (e) => {
            this.updateSegmentProperty(`${markerName}_delay`, e.target.value, 'number');
        });

        delayInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.target.blur();
            }
        });

        delayGroup.appendChild(delayLabel);
        delayGroup.appendChild(delayInput);

        // Duration input
        const durationGroup = document.createElement('div');

        const durationLabel = document.createElement('label');
        durationLabel.textContent = `Duration (${timeInfo.symbol}):`;
        durationLabel.style.cssText = 'display: block; font-size: 0.8rem; color: #6c757d; margin-bottom: 3px;';

        const durationInput = document.createElement('input');
        durationInput.type = 'number';
        durationInput.step = 0.001;
        durationInput.value = (markerData.duration * timeInfo.factor).toFixed(3);
        durationInput.style.cssText = 'width: 100%; padding: 4px 8px; border: 1px solid #ced4da; border-radius: 3px; font-size: 0.8rem;';

        durationInput.addEventListener('change', (e) => {
            this.updateSegmentProperty(`${markerName}_duration`, e.target.value, 'number');
        });

        durationInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.target.blur();
            }
        });

        durationGroup.appendChild(durationLabel);
        durationGroup.appendChild(durationInput);

        group.appendChild(delayGroup);
        group.appendChild(durationGroup);

        return group;
    }

    showMarkerWarningModal(markerName, property, inputValue, maxValue, timeUnit) {
        const message = `The ${property} value for ${markerName} would exceed the segment duration. The ${property} will be automatically set to the maximum allowed value.`;
        const details = {
            [`Maximum ${property}`]: `${maxValue} ${timeUnit}`,
            'Your Input': `${inputValue} ${timeUnit}`
        };
        ModalUtils.showWarning(message, 'Marker Value Too Large', details);
    }

    showExpressionErrorModal(title, message, explanation, example) {
        const fullMessage = `${message}\n\nRequired: ${explanation}\n\nPlease correct your expression and try again.`;
        ModalUtils.showAlert(fullMessage, title, 'error');
    }

    getParameterConfig(param) {
        // Get current time scale info for dynamic units
        const timeInfo = this.getTimeScaleInfo();

        const configs = {
            'start': { label: 'Start Amplitude', type: 'number', unit: 'V', step: 0.1 },
            'stop': { label: 'Stop Amplitude', type: 'number', unit: 'V', step: 0.1 },
            'frequency': { label: 'Frequency', type: 'number', unit: 'MHz', step: 0.1 },
            'phase': { label: 'Phase', type: 'number', unit: 'degrees', step: 1 },
            'offset': { label: 'Offset', type: 'number', unit: 'V', step: 0.1 },
            'duty_cycle': { label: 'Duty Cycle', type: 'number', unit: '%', step: 0.01 },
            'rise_time': { label: 'Rise Time', type: 'number', unit: timeInfo.symbol, step: 0.001 },
            'fall_time': { label: 'Fall Time', type: 'number', unit: timeInfo.symbol, step: 0.001 },
            'width': { label: 'Width', type: 'number', unit: timeInfo.symbol, step: 0.001 },
            'center': { label: 'Center', type: 'number', unit: timeInfo.symbol, step: 0.001 },
            'time_constant': { label: 'Time Constant', type: 'number', unit: timeInfo.symbol, step: 0.001 },
            'absolute_time': { label: 'Absolute Time', type: 'number', unit: timeInfo.symbol, step: 0.001 },
            'type': { label: 'Type', type: 'select', unit: '', step: 1, options: [
                { value: 'rise', label: 'Rise (1-exp(-t/T))' },
                { value: 'decay', label: 'Decay (exp(-t/T))' }
            ]},
            'expression': { label: 'Expression', type: 'text', unit: '', step: 1 }
        };

        // Also update duration to use dynamic time units
        if (param === 'duration') {
            return { label: 'Duration', type: 'number', unit: timeInfo.symbol, step: timeInfo.factor > 1e6 ? 0.001 : 0.01 };
        }

        // Use fixed amplitude units (V)
        if (param === 'amplitude') {
            return { label: 'Amplitude', type: 'number', unit: 'V', step: 0.001 };
        }

        return configs[param] || { label: param, type: 'number', unit: '', step: 0.001 };
    }

    addCustomSegmentFields(form, segment) {
        // Combined expression and parameters field
        const combinedGroup = document.createElement('div');
        combinedGroup.className = 'property-group';
        combinedGroup.style.marginBottom = '15px';

        const combinedLabel = document.createElement('label');
        combinedLabel.textContent = 'Custom Expression:';
        combinedLabel.style.fontWeight = '500';
        combinedGroup.appendChild(combinedLabel);

        const combinedHelp = document.createElement('div');
        combinedHelp.style.cssText = 'font-size: 0.75rem; color: #6c757d; margin: 5px 0;';
        combinedHelp.textContent = 'Format: t, param1, param2: expression, {"param1": value1, "param2": value2}';
        combinedGroup.appendChild(combinedHelp);

        // Construct combined value from separate fields
        const expression = segment.parameters?.expression || 't, amp, tau: amp * exp(-t / tau)';
        const paramsJson = segment.parameters?.params_json || '{"amp": 2, "tau": 0.33}';
        const combinedValue = `${expression}, ${paramsJson}`;

        const combinedTextarea = document.createElement('textarea');
        combinedTextarea.value = combinedValue;
        combinedTextarea.placeholder = 't, amp, tau: amp * exp(-t / tau), {"amp": 2, "tau": 0.33}';
        combinedTextarea.rows = 3;
        combinedTextarea.style.cssText = 'width: 100%; font-family: monospace; font-size: 0.85rem;';

        // Only validate on blur (losing focus)
        combinedTextarea.addEventListener('blur', (e) => {
            this.updateCombinedCustomField(e.target.value);
        });

        // Handle keyboard events
        combinedTextarea.addEventListener('keydown', (e) => {
            // Stop propagation for all keys to prevent global shortcuts from interfering
            e.stopPropagation();

            // Validate on Enter key (but not Shift+Enter for multi-line)
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault(); // Prevent newline
                e.target.blur(); // This will trigger the blur event which validates
            }
        });

        combinedGroup.appendChild(combinedTextarea);

        // Example button
        const exampleBtn = document.createElement('button');
        exampleBtn.type = 'button';
        exampleBtn.className = 'btn btn-sm';
        exampleBtn.textContent = 'Load Example';
        exampleBtn.style.cssText = 'margin-top: 10px; background: #3498db; color: white;';
        exampleBtn.onclick = () => {
            combinedTextarea.value = 't, amp, tau: amp * exp(-t / tau), {"amp": 2, "tau": 0.33}';
            this.updateCombinedCustomField(combinedTextarea.value);
        };

        form.appendChild(combinedGroup);
        form.appendChild(exampleBtn);
    }

    updateCombinedCustomField(value) {
        if (!this.selectedSegment || !this.timeline) return;

        // Split on the last comma that's outside any braces (to separate expression from JSON)
        // Find the position of the JSON object start
        const jsonStartIndex = value.lastIndexOf('{');
        if (jsonStartIndex === -1) {
            this.showExpressionErrorModal(
                'JSON Parameters Not Found',
                'Invalid format: JSON parameters not found.',
                'Use format: "t, param: expr, {"param": value}"',
                'Example: t, amp, tau: amp * exp(-t / tau), {"amp": 2, "tau": 0.33}'
            );
            return;
        }

        // Find the comma before the JSON object
        let splitIndex = -1;
        let braceCount = 0;
        for (let i = value.length - 1; i >= 0; i--) {
            if (value[i] === '}') braceCount++;
            else if (value[i] === '{') braceCount--;
            else if (value[i] === ',' && braceCount === 0) {
                splitIndex = i;
                break;
            }
        }

        if (splitIndex === -1) {
            this.showExpressionErrorModal(
                'Missing Separator',
                'Invalid format: Missing comma separator between expression and parameters.',
                'Use format: "t, param: expr, {"param": value}"',
                'Example: t, amp, tau: amp * exp(-t / tau), {"amp": 2, "tau": 0.33}'
            );
            return;
        }

        const expression = value.substring(0, splitIndex).trim();
        const paramsJson = value.substring(splitIndex + 1).trim();

        // Validate expression
        if (!expression.includes(':')) {
            this.showExpressionErrorModal(
                'Missing Colon Separator',
                'Expression must contain ":" separator between parameters and expression body.',
                'Format: parameters: expression',
                'Example: t, param1: param1*t'
            );
            return;
        }

        const [args, body] = expression.split(':', 2);
        const argsList = args.split(',').map(a => a.trim());
        if (!argsList.length || argsList[0] !== 't') {
            this.showExpressionErrorModal(
                'Invalid Parameters',
                'First parameter must be "t" (time variable).',
                'Format: t, param1, param2: expression',
                'Example: t, amp, tau: amp * exp(-t / tau)'
            );
            return;
        }

        // Validate JSON
        try {
            const params = JSON.parse(paramsJson);
            if (typeof params !== 'object' || Array.isArray(params)) {
                this.showExpressionErrorModal(
                    'Invalid Parameters Format',
                    'Parameters must be a JSON object.',
                    'Format: {"param1": value1, "param2": value2}',
                    'Example: {"amp": 2, "tau": 0.33}'
                );
                return;
            }

            // Validate that all parameters in expression are in JSON
            const paramNames = argsList.slice(1); // Skip 't'
            for (const paramName of paramNames) {
                if (!(paramName in params)) {
                    this.showExpressionErrorModal(
                        'Parameter Mismatch',
                        `Parameter "${paramName}" from expression not found in parameters JSON.`,
                        'All parameters in the expression must be defined in the JSON object.',
                        `Add "${paramName}" to your JSON: {"${paramName}": value, ...}`
                    );
                    return;
                }
            }
        } catch (e) {
            this.showExpressionErrorModal(
                'Invalid JSON Format',
                `JSON parsing error: ${e.message}`,
                'Check your JSON syntax for errors.',
                'Valid JSON: {"amp": 2, "tau": 0.33}'
            );
            return;
        }

        // Update the segment with both fields
        const updates = {
            parameters: {
                ...this.selectedSegment.parameters,
                expression: expression,
                params_json: paramsJson
            }
        };

        this.timeline.updateSegment(this.selectedSegment.id, updates);
    }

    getDefaultParameterValue(param, segmentType) {
        // Use centralized defaults from segment-library.js
        const defaults = window.SEGMENT_DEFAULTS || {};
        return defaults[segmentType]?.[param] || 0;
    }

    updateProperties() {
        if (this.selectedSegment) {
            this.renderProperties();
        }
    }

    async deleteSegment() {
        if (this.selectedSegment && this.timeline) {
            const confirmed = await ModalUtils.showConfirm(
                'Are you sure you want to delete this segment?',
                'Delete Segment'
            );
            if (confirmed) {
                this.timeline.removeSegment(this.selectedSegment.id);
            }
        }
    }


    // Public API
    getSelectedSegment() {
        return this.selectedSegment;
    }


    showDurationWarningModal(inputDuration, minDuration, sampleRate, inputElement) {
        const message = 'The duration you entered is too short for the current sample rate. The duration will be automatically set to the minimum value.';
        const details = {
            'Minimum Duration': `${minDuration.toFixed(3)} μs`,
            'Your Input': `${inputDuration.toFixed(3)} μs`,
            'Sample Rate': `${sampleRate.toFixed(1)} GHz`
        };
        ModalUtils.showWarning(message, 'Duration Too Short', details);
    }
}

// Export for use in main application
window.PropertiesPanel = PropertiesPanel;
