/**
 * Waveform Upload & Capture JavaScript (Standalone Version)
 * Handles sequence selection and AWG/Scope operations using mock or real instruments
 * Updated to use separate AWG, Scope, and LUT configurations
 */

// Global state
let sequences = [];
let selectedSequenceId = null;
let sequencePreview = null;
let isSequenceUploaded = false;
let areInstrumentsConnected = false;

// Separate config arrays
let awgConfigs = [];
let scopeConfigs = [];
let lutConfigs = [];

// Selected config IDs
let selectedAwgConfigId = null;
let selectedScopeConfigId = null;
let selectedLutCh1Id = null;
let selectedLutCh2Id = null;

// Selected config objects
let selectedAwgConfig = null;
let selectedScopeConfig = null;

// DOM Elements
const sequenceLibrary = document.getElementById('sequence-library');
const selectedSequenceDisplay = document.getElementById('selected-sequence-display');
const uploadSequenceBtn = document.getElementById('upload-sequence-btn');
const triggerCaptureBtn = document.getElementById('trigger-capture-btn');
const jumpToBtn = document.getElementById('jump-to-btn');
const jumpToIndex = document.getElementById('jump-to-index');
const disconnectBtn = document.getElementById('disconnect-btn');
const operationStatus = document.getElementById('operation-status');
const operationMessage = document.getElementById('operation-message');
const captureStatus = document.getElementById('capture-status');
const scopeCapturePlot = document.getElementById('scope-capture-plot');
const captureStats = document.getElementById('capture-stats');
const refreshSequencesBtn = document.getElementById('refresh-sequences-btn');
const awgConfigSelect = document.getElementById('awg-config-select');
const scopeConfigSelect = document.getElementById('scope-config-select');
const lutCh1Select = document.getElementById('lut-ch1-select');
const lutCh2Select = document.getElementById('lut-ch2-select');
const instrumentConfigDetails = document.getElementById('instrument-config-details');

/**
 * Initialize the page
 */
document.addEventListener('DOMContentLoaded', () => {
    // Initialize sequence preview
    sequencePreview = new UploadSequencePreview();
    
    loadSequences();
    loadAllConfigs();
    
    // Event listeners
    refreshSequencesBtn.addEventListener('click', loadSequences);
    uploadSequenceBtn.addEventListener('click', handleUploadSequence);
    triggerCaptureBtn.addEventListener('click', handleTriggerAndCapture);
    jumpToBtn.addEventListener('click', handleJumpToSegment);
    disconnectBtn.addEventListener('click', handleDisconnectInstruments);
    
    awgConfigSelect.addEventListener('change', handleAwgConfigSelection);
    scopeConfigSelect.addEventListener('change', handleScopeConfigSelection);
    lutCh1Select.addEventListener('change', handleLutSelection);
    lutCh2Select.addEventListener('change', handleLutSelection);
    
    // Add beforeunload handler for automatic disconnect on page navigation
    window.addEventListener('beforeunload', handleBeforeUnload);
    
    // Intercept navigation links to disconnect before leaving
    setupNavigationInterception();
});

/**
 * Load all configurations from the server (AWG, Scope, LUT)
 */
async function loadAllConfigs() {
    try {
        const response = await fetch('/api/all-configs/');
        const data = await response.json();
        
        if (data.success) {
            awgConfigs = data.awg_configs || [];
            scopeConfigs = data.scope_configs || [];
            lutConfigs = data.lut_configs || [];
            
            renderConfigSelects();
        } else {
            console.error('Failed to load configs:', data.error);
            showError('Failed to load configurations');
        }
    } catch (error) {
        console.error('Error loading configs:', error);
        showError('Error loading configurations');
    }
}

/**
 * Render all configuration dropdowns
 */
function renderConfigSelects() {
    // AWG configs
    if (awgConfigs.length === 0) {
        awgConfigSelect.innerHTML = '<option value="">No AWG configs available</option>';
    } else {
        awgConfigSelect.innerHTML = `
            <option value="">Select AWG config...</option>
            ${awgConfigs.map(c => `<option value="${c.id}">${CommonUtils.escapeHtml(c.name)}</option>`).join('')}
        `;
    }
    
    // Scope configs
    if (scopeConfigs.length === 0) {
        scopeConfigSelect.innerHTML = '<option value="">No Scope configs available</option>';
    } else {
        scopeConfigSelect.innerHTML = `
            <option value="">Select Scope config...</option>
            ${scopeConfigs.map(c => `<option value="${c.id}">${CommonUtils.escapeHtml(c.name)}</option>`).join('')}
        `;
    }
    
    // LUT configs (for both channels)
    const lutOptions = `
        <option value="">None</option>
        ${lutConfigs.map(c => `<option value="${c.id}">${CommonUtils.escapeHtml(c.name)}</option>`).join('')}
    `;
    lutCh1Select.innerHTML = lutOptions;
    lutCh2Select.innerHTML = lutOptions;
    
    updateConfigDetails();
}

/**
 * Handle AWG configuration selection
 */
function handleAwgConfigSelection() {
    const configId = awgConfigSelect.value;
    
    if (!configId) {
        selectedAwgConfigId = null;
        selectedAwgConfig = null;
    } else {
        selectedAwgConfigId = parseInt(configId);
        selectedAwgConfig = awgConfigs.find(c => c.id === selectedAwgConfigId);
    }
    
    updateConfigDetails();
    updateButtonStates();
}

/**
 * Handle Scope configuration selection
 */
function handleScopeConfigSelection() {
    const configId = scopeConfigSelect.value;
    
    if (!configId) {
        selectedScopeConfigId = null;
        selectedScopeConfig = null;
    } else {
        selectedScopeConfigId = parseInt(configId);
        selectedScopeConfig = scopeConfigs.find(c => c.id === selectedScopeConfigId);
    }
    
    updateConfigDetails();
    updateButtonStates();
}

/**
 * Handle LUT selection change
 */
function handleLutSelection() {
    selectedLutCh1Id = lutCh1Select.value ? parseInt(lutCh1Select.value) : null;
    selectedLutCh2Id = lutCh2Select.value ? parseInt(lutCh2Select.value) : null;
}

/**
 * Get a display label for driver type
 */
function getDriverTypeLabel(driverType, instrumentType) {
    if (!driverType || driverType === 'mock') {
        return 'Mock';
    }
    // Extract the class name from the full driver path
    // e.g. "qcodes.instrument_drivers.tektronix.TektronixAWG70002A" -> "TektronixAWG70002A"
    const parts = driverType.split('.');
    return parts[parts.length - 1] || driverType;
}

/**
 * Extract IP from VISA address
 */
function extractIpFromAddress(address) {
    if (!address) return '-';
    const match = address.match(/TCPIP\d*::([^:]+)::/);
    return match ? match[1] : '-';
}

/**
 * Check if a config represents a mock instrument
 * is_mock is true for mock, false for real hardware
 */
function isConfigMock(config) {
    if (!config) return true;
    // is_mock field is set by backend based on driver_type
    // Check for both boolean and string representations
    // If is_mock is falsy (false, undefined, null, 0) AND driver_type is not 'mock', it's real hardware
    const isMockField = config.is_mock === true || config.is_mock === 'true' || config.is_mock === 'True';
    const isMockDriver = config.driver_type === 'mock';
    
    // Debug logging (can be removed after verification)
    console.log('isConfigMock check:', {
        configName: config.name,
        is_mock: config.is_mock,
        driver_type: config.driver_type,
        isMockField: isMockField,
        isMockDriver: isMockDriver,
        result: isMockField || isMockDriver
    });
    
    return isMockField || isMockDriver;
}

/**
 * Update the config details display
 */
function updateConfigDetails() {
    if (!selectedAwgConfig && !selectedScopeConfig) {
        instrumentConfigDetails.innerHTML = `
            <div class="text-muted small">
                <i class="fas fa-info-circle"></i> Select AWG and Scope configurations
            </div>
        `;
        return;
    }
    
    let html = '';
    
    if (selectedAwgConfig) {
        const awgType = getDriverTypeLabel(selectedAwgConfig.driver_type, 'awg');
        const awgIp = extractIpFromAddress(selectedAwgConfig.address);
        const awgIsMock = isConfigMock(selectedAwgConfig);
        
        html += `
            <div class="config-detail-row">
                <span class="config-detail-label">AWG:</span>
                <span class="config-detail-value">${awgType}${!awgIsMock ? ` (${awgIp})` : ''}</span>
            </div>
        `;
    }
    
    if (selectedScopeConfig) {
        const scopeType = getDriverTypeLabel(selectedScopeConfig.driver_type, 'scope');
        const scopeIp = extractIpFromAddress(selectedScopeConfig.address);
        const scopeIsMock = isConfigMock(selectedScopeConfig);
        
        html += `
            <div class="config-detail-row">
                <span class="config-detail-label">Scope:</span>
                <span class="config-detail-value">${scopeType}${!scopeIsMock ? ` (${scopeIp})` : ''}</span>
            </div>
        `;
    }
    
    // Determine overall mode - Real Hardware if either AWG or Scope is real
    const awgIsMock = isConfigMock(selectedAwgConfig);
    const scopeIsMock = isConfigMock(selectedScopeConfig);
    // Show "Real Hardware" if at least one instrument is selected and is real
    const hasRealInstrument = (selectedAwgConfig && !awgIsMock) || (selectedScopeConfig && !scopeIsMock);
    const isMock = !hasRealInstrument;
    const alertClass = isMock ? 'alert-info' : 'alert-success';
    const modeText = isMock ? 'Simulation Mode' : 'Real Hardware';
    const modeIcon = isMock ? 'fa-microchip' : 'fa-plug';
    
    html = `
        <div class="alert ${alertClass} mb-2 py-1 px-2">
            <i class="fas ${modeIcon}"></i> <small>${modeText}</small>
        </div>
    ` + html;
    
    instrumentConfigDetails.innerHTML = html;
}

/**
 * Load all sequences from the server
 */
async function loadSequences() {
    try {
        showLoadingOverlay();
        
        const response = await fetch('/api/sequences/');
        const data = await response.json();
        
        if (data.success) {
            sequences = data.sequences;
            renderSequenceLibrary();
        } else {
            showError('Failed to load sequences: ' + data.error);
        }
    } catch (error) {
        showError('Error loading sequences: ' + error.message);
    } finally {
        hideLoadingOverlay();
    }
}

/**
 * Render the sequence library cards
 */
function renderSequenceLibrary() {
    if (sequences.length === 0) {
        sequenceLibrary.innerHTML = `
            <div class="text-center text-muted p-4">
                <i class="fas fa-inbox fa-3x mb-3"></i>
                <p>No sequences found. Create sequences in the Sequencer.</p>
            </div>
        `;
        return;
    }
    
    sequenceLibrary.innerHTML = sequences.map(seq => `
        <div class="sequence-card ${seq.id === selectedSequenceId ? 'selected' : ''}" 
             data-sequence-id="${seq.id}">
            <div class="sequence-card-header">
                <div class="sequence-card-name">${CommonUtils.escapeHtml(seq.name)}</div>
                <a href="/api/sequences/${seq.id}/download/" 
                   class="sequence-download-btn" 
                   title="Download sequence data as JSON"
                   onclick="event.stopPropagation();">
                    <i class="fas fa-download"></i>
                </a>
            </div>
            <div class="sequence-card-info">
                <span>${seq.num_positions} positions</span>
                <span>${CommonUtils.formatDuration(seq.total_duration)}</span>
            </div>
            ${seq.description ? `<div class="sequence-card-description">${CommonUtils.escapeHtml(seq.description)}</div>` : ''}
        </div>
    `).join('');
    
    // Add click listeners to sequence cards
    document.querySelectorAll('.sequence-card').forEach(card => {
        card.addEventListener('click', () => {
            const sequenceId = parseInt(card.dataset.sequenceId);
            selectSequence(sequenceId);
        });
    });
}

/**
 * Select a sequence
 */
async function selectSequence(sequenceId) {
    // If selecting a different sequence and instruments are connected, disconnect first
    if (selectedSequenceId !== sequenceId && areInstrumentsConnected) {
        await disconnectInstrumentsSilently();
    }
    
    selectedSequenceId = sequenceId;
    isSequenceUploaded = false;
    areInstrumentsConnected = false;
    const sequence = sequences.find(s => s.id === sequenceId);
    
    if (sequence) {
        // Update UI
        renderSequenceLibrary();
        
        // Update selected sequence display
        selectedSequenceDisplay.classList.add('has-selection');
        selectedSequenceDisplay.innerHTML = `
            <div class="sequence-name">${CommonUtils.escapeHtml(sequence.name)}</div>
            <div class="sequence-details">
                ${sequence.num_positions} positions • ${CommonUtils.formatDuration(sequence.total_duration)}
            </div>
        `;
        
        // Update sequence preview
        if (sequencePreview) {
            sequencePreview.updatePreview(sequenceId);
        }
        
        // Update button state
        updateButtonStates();
    }
}

/**
 * Update the button enabled/disabled states
 */
function updateButtonStates() {
    // Upload button is enabled when sequence AND AWG config are selected
    uploadSequenceBtn.disabled = !selectedSequenceId || !selectedAwgConfigId;
    
    // Trigger button is only enabled when sequence is uploaded
    triggerCaptureBtn.disabled = !isSequenceUploaded;
    
    // Jump To button and input are enabled when sequence is uploaded
    jumpToBtn.disabled = !isSequenceUploaded;
    jumpToIndex.disabled = !isSequenceUploaded;
    
    // Disconnect button is enabled when instruments are connected
    disconnectBtn.disabled = !areInstrumentsConnected;
}

/**
 * Check if currently using mock instruments
 */
function isMockConfig() {
    // If either selected config is real (not mock), consider it real hardware mode
    const awgIsMock = isConfigMock(selectedAwgConfig);
    const scopeIsMock = isConfigMock(selectedScopeConfig);
    // Return true (mock mode) only if ALL selected instruments are mock
    return awgIsMock && scopeIsMock;
}

/**
 * Get the mode string (Mock/Real) based on current config
 */
function getModeString() {
    return isMockConfig() ? 'Mock' : 'Real';
}

/**
 * Handle sequence upload to AWG
 */
async function handleUploadSequence() {
    if (!selectedSequenceId || !selectedAwgConfigId) {
        return;
    }
    
    const modeStr = getModeString();
    
    try {
        // Disable buttons and show status
        uploadSequenceBtn.disabled = true;
        triggerCaptureBtn.disabled = true;
        disconnectBtn.disabled = true;
        showOperationStatus(`Uploading sequence to ${modeStr} AWG...`);
        
        // Build request body with separate config IDs
        const requestBody = {
            sequence_id: selectedSequenceId,
            awg_config_id: selectedAwgConfigId,
        };
        
        // Add scope config if selected
        if (selectedScopeConfigId) {
            requestBody.scope_config_id = selectedScopeConfigId;
        }
        
        // Add LUT config IDs if selected
        if (selectedLutCh1Id) {
            requestBody.lut_channel_1_id = selectedLutCh1Id;
        }
        if (selectedLutCh2Id) {
            requestBody.lut_channel_2_id = selectedLutCh2Id;
        }
        
        const response = await fetch('/api/upload-sequence/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody),
        });
        
        const data = await response.json();
        
        if (data.success) {
            showOperationStatus('Sequence uploaded successfully!', 'success');
            
            // Mark sequence as uploaded and instruments as connected
            isSequenceUploaded = true;
            areInstrumentsConnected = true;
            
            // Update button states
            updateButtonStates();
            
            // Hide status after delay
            setTimeout(() => {
                hideOperationStatus();
            }, 2000);
        } else {
            showOperationStatus('Upload failed: ' + data.error, 'danger');
            showError('Upload failed: ' + data.error);
        }
    } catch (error) {
        showOperationStatus('Upload error: ' + error.message, 'danger');
        showError('Upload error: ' + error.message);
    } finally {
        // Re-enable upload button
        uploadSequenceBtn.disabled = false;
        updateButtonStates();
    }
}

/**
 * Handle trigger and capture operation
 */
async function handleTriggerAndCapture() {
    if (!selectedSequenceId) {
        return;
    }
    
    try {
        // Disable button and show status
        triggerCaptureBtn.disabled = true;
        disconnectBtn.disabled = true;
        showOperationStatus('Triggering AWG and capturing...');
        updateCaptureStatus('Capturing...', 'warning');
        
        const response = await fetch('/api/trigger-and-capture/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                sequence_id: selectedSequenceId,
            }),
        });
        
        const data = await response.json();
        
        if (data.success) {
            showOperationStatus('Capture complete!', 'success');
            updateCaptureStatus('Captured', 'success');
            
            // Plot the captured waveforms
            plotCapturedWaveforms(data);
            
            // Update stats
            updateCaptureStats(data);
            
            // Hide status after delay
            setTimeout(() => {
                hideOperationStatus();
            }, 3000);
        } else {
            showOperationStatus('Capture failed: ' + data.error, 'danger');
            updateCaptureStatus('Error', 'danger');
            showError('Capture failed: ' + data.error);
        }
    } catch (error) {
        showOperationStatus('Capture error: ' + error.message, 'danger');
        updateCaptureStatus('Error', 'danger');
        showError('Capture error: ' + error.message);
    } finally {
        // Re-enable button after operation completes
        setTimeout(() => {
            triggerCaptureBtn.disabled = false;
            updateButtonStates();
        }, 1000);
    }
}

/**
 * Handle jump to specific segment
 */
async function handleJumpToSegment() {
    if (!selectedSequenceId) {
        return;
    }
    
    const segmentIndex = parseInt(jumpToIndex.value);
    if (!segmentIndex || segmentIndex < 1) {
        showError('Please enter a valid segment number (1 or greater)');
        return;
    }
    
    try {
        // Disable buttons and show status
        jumpToBtn.disabled = true;
        triggerCaptureBtn.disabled = true;
        disconnectBtn.disabled = true;
        showOperationStatus(`Jumping to segment ${segmentIndex} and capturing...`);
        updateCaptureStatus('Jumping and capturing...', 'warning');
        
        const response = await fetch('/api/jump-to-and-capture/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                segment_index: segmentIndex,
            }),
        });
        
        const data = await response.json();
        
        if (data.success) {
            showOperationStatus(`Jump to segment ${segmentIndex} complete!`, 'success');
            updateCaptureStatus('Captured', 'success');
            
            // Plot the captured waveforms
            plotCapturedWaveforms(data);
            
            // Update stats
            updateCaptureStats(data);
            
            // Hide status after delay
            setTimeout(() => {
                hideOperationStatus();
            }, 3000);
        } else {
            showOperationStatus('Jump and capture failed: ' + data.error, 'danger');
            updateCaptureStatus('Error', 'danger');
            showError('Jump and capture failed: ' + data.error);
        }
    } catch (error) {
        showOperationStatus('Jump and capture error: ' + error.message, 'danger');
        updateCaptureStatus('Error', 'danger');
        showError('Jump and capture error: ' + error.message);
    } finally {
        // Re-enable buttons after operation completes
        setTimeout(() => {
            updateButtonStates();
        }, 1000);
    }
}

/**
 * Handle instrument disconnection
 */
async function handleDisconnectInstruments() {
    try {
        // Disable buttons and show status
        uploadSequenceBtn.disabled = true;
        triggerCaptureBtn.disabled = true;
        disconnectBtn.disabled = true;
        showOperationStatus('Disconnecting instruments...');
        
        const response = await fetch('/api/disconnect-instruments/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
        });
        
        const data = await response.json();
        
        if (data.success) {
            showOperationStatus('Instruments disconnected successfully!', 'success');
            
            // Mark instruments as disconnected and sequence as not uploaded
            areInstrumentsConnected = false;
            isSequenceUploaded = false;
            
            // Clear capture display
            scopeCapturePlot.innerHTML = `
                <div class="plot-placeholder">
                    <i class="fas fa-wave-square"></i>
                    <p>Select a sequence, then click "Upload to AWG" to start</p>
                </div>
            `;
            updateCaptureStatus('No capture', 'secondary');
            captureStats.style.display = 'none';
            
            // Update button states
            updateButtonStates();
            
            // Hide status after delay
            setTimeout(() => {
                hideOperationStatus();
            }, 2000);
        } else {
            showOperationStatus('Disconnect failed: ' + data.error, 'danger');
            showError('Disconnect failed: ' + data.error);
        }
    } catch (error) {
        showOperationStatus('Disconnect error: ' + error.message, 'danger');
        showError('Disconnect error: ' + error.message);
    } finally {
        // Re-enable buttons based on current state
        setTimeout(() => {
            updateButtonStates();
        }, 1000);
    }
}

/**
 * Plot captured waveforms using Plotly
 */
function plotCapturedWaveforms(data) {
    const { time_axis, time_unit, channels } = data;
    
    // Create traces for each channel
    const traces = channels.map(channel => ({
        x: time_axis,
        y: channel.data,
        type: 'scatter',
        mode: 'lines',
        name: channel.name,
        line: {
            width: 2,
        },
    }));
    
    // Determine title based on config
    const modeStr = getModeString();
    
    // Layout configuration
    const layout = {
        title: `Scope Capture (${modeStr})`,
        xaxis: {
            title: `Time (${time_unit})`,
            showgrid: true,
            zeroline: true,
        },
        yaxis: {
            title: 'Amplitude (V)',
            showgrid: true,
            zeroline: true,
        },
        hovermode: 'x unified',
        showlegend: true,
        legend: {
            x: 1,
            xanchor: 'right',
            y: 1,
        },
        margin: {
            l: 60,
            r: 30,
            t: 50,
            b: 60,
        },
        autosize: true,
    };
    
    // Plot configuration
    const config = {
        responsive: true,
        displayModeBar: true,
        displaylogo: false,
        modeBarButtonsToRemove: ['lasso2d', 'select2d'],
    };
    
    // Clear placeholder if exists
    scopeCapturePlot.innerHTML = '';
    
    // Create the plot
    Plotly.newPlot(scopeCapturePlot, traces, layout, config).then(() => {
        setTimeout(() => {
            Plotly.Plots.resize(scopeCapturePlot);
        }, 100);
    });
    
    window.addEventListener('resize', () => {
        Plotly.Plots.resize(scopeCapturePlot);
    });
}

/**
 * Update capture statistics
 */
function updateCaptureStats(data) {
    const { time_unit, channels, time_axis } = data;
    
    document.getElementById('stat-time-unit').textContent = time_unit;
    document.getElementById('stat-channels').textContent = channels.map(ch => ch.name).join(', ');
    document.getElementById('stat-points').textContent = time_axis.length.toLocaleString();
    
    captureStats.style.display = 'grid';
}

/**
 * Update capture status badge
 */
function updateCaptureStatus(text, type) {
    captureStatus.textContent = text;
    captureStatus.className = 'badge';
    
    switch (type) {
        case 'success':
            captureStatus.classList.add('bg-success');
            break;
        case 'warning':
            captureStatus.classList.add('bg-warning');
            break;
        case 'danger':
            captureStatus.classList.add('bg-danger');
            break;
        default:
            captureStatus.classList.add('bg-secondary');
    }
}

/**
 * Show operation status message
 */
function showOperationStatus(message, type = 'info') {
    operationMessage.textContent = message;
    operationStatus.className = `alert alert-${type}`;
    operationStatus.style.display = 'block';
}

/**
 * Hide operation status message
 */
function hideOperationStatus() {
    operationStatus.style.display = 'none';
}

/**
 * Show loading overlay
 */
function showLoadingOverlay() {
    document.getElementById('loading-overlay').style.display = 'flex';
}

/**
 * Hide loading overlay
 */
function hideLoadingOverlay() {
    document.getElementById('loading-overlay').style.display = 'none';
}

/**
 * Show error message
 */
function showError(message) {
    if (window.CommonUtils && CommonUtils.showError) {
        CommonUtils.showError(message);
    }
    console.error('Error: ' + message);
}

/**
 * Disconnect instruments silently
 */
async function disconnectInstrumentsSilently() {
    if (!areInstrumentsConnected) {
        return;
    }
    
    try {
        const response = await fetch('/api/disconnect-instruments/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
        });
        
        const data = await response.json();
        
        if (data.success) {
            areInstrumentsConnected = false;
            isSequenceUploaded = false;
        }
    } catch (error) {
        console.error('Silent disconnect error:', error.message);
    }
}

/**
 * Handle page unload
 */
function handleBeforeUnload(event) {
    if (areInstrumentsConnected) {
        const data = JSON.stringify({});
        navigator.sendBeacon('/api/disconnect-instruments/', data);
    }
}

/**
 * Setup navigation interception
 */
function setupNavigationInterception() {
    const navLinks = document.querySelectorAll('.navbar-nav a.nav-link');
    
    navLinks.forEach(link => {
        link.addEventListener('click', async (event) => {
            if (areInstrumentsConnected) {
                event.preventDefault();
                await disconnectInstrumentsSilently();
                window.location.href = link.href;
            }
        });
    });
}