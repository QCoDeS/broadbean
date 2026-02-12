/**
 * Preview Panel Component
 * Handles the Plotly-based waveform preview and statistics
 */

class PreviewPanel {
    constructor() {
        this.timeline = null;
        this.propertiesPanel = null;
        this.isUpdating = false;
        this.updateTimeout = null;
        this.sampleRate = window.waveformDesignerSettings?.defaultSampleRate || 25e9; // Default from settings
        
        this.plotDiv = document.getElementById('preview-plot');
        this.refreshBtn = document.getElementById('refresh-preview-btn');
        
        // Stats elements
        this.statDuration = document.getElementById('stat-duration');
        this.statPoints = document.getElementById('stat-points');
        this.statPeak = document.getElementById('stat-peak');
        this.sampleCountBadge = document.getElementById('sample-count-badge');
        
        this.bindEvents();
        this.initializePlot();
    }

    setReferences(timeline) {
        this.timeline = timeline;
    }

    bindEvents() {
        // Auto-update on timeline changes is DISABLED - user must click Refresh button
        // These event listeners are commented out to prevent automatic preview updates:
        // window.addEventListener('segmentAdded', () => this.scheduleUpdate());
        // window.addEventListener('segmentRemoved', () => this.scheduleUpdate());
        // window.addEventListener('segmentUpdated', () => this.scheduleUpdate());
        // window.addEventListener('segmentsReordered', () => this.scheduleUpdate());
        // window.addEventListener('segmentsCleared', () => this.scheduleUpdate());
        // window.addEventListener('channelAdded', () => this.scheduleUpdate());
        // window.addEventListener('channelRemoved', () => this.scheduleUpdate());

        // Listen for settings changes (sample rate) - still update the internal value
        // but don't auto-refresh the preview
        window.addEventListener('settingChanged', (e) => {
            const { setting, value } = e.detail;
            if (setting === 'sampleRate') {
                this.sampleRate = value;
                // Don't auto-update: this.scheduleUpdate();
            }
        });

        // Listen for global scale changes - don't auto-refresh
        // const timeUnitsSelect = document.getElementById('time-units');
        // timeUnitsSelect?.addEventListener('change', () => this.scheduleUpdate());

        // Preview controls - Refresh button is the only way to update the preview
        this.refreshBtn?.addEventListener('click', () => this.updatePreview(true));
    }

    initializePlot() {
        const layout = {
            xaxis: {
                title: 'Time (μs)',
                showgrid: true,
                zeroline: true
            },
            yaxis: {
                title: 'Amplitude (V)',
                showgrid: true,
                zeroline: true
            },
            showlegend: true,
            legend: {
                x: 1,
                y: 1,
                bgcolor: 'rgba(255,255,255,0.8)'
            },
            margin: { l: 50, r: 50, t: 30, b: 50 },
            paper_bgcolor: 'white',
            plot_bgcolor: '#f8f9fa'
        };

        const config = {
            responsive: true,
            displayModeBar: true,
            modeBarButtonsToRemove: ['pan2d', 'lasso2d', 'select2d'],
            displaylogo: false
        };

        Plotly.newPlot(this.plotDiv, [], layout, config);
        this.showEmptyState();
    }

    showEmptyState() {
        const layout = {
            xaxis: {
                title: 'Time (μs)',
                showgrid: true,
                zeroline: true,
                range: [0, 10]
            },
            yaxis: {
                title: 'Amplitude (V)',
                showgrid: true,
                zeroline: true,
                range: [-1, 1]
            },
            annotations: [{
                text: 'Add segments to see waveform preview',
                x: 5,
                y: 0,
                showarrow: false,
                font: { size: 16, color: '#95a5a6' }
            }],
            showlegend: false
        };

        Plotly.react(this.plotDiv, [], layout);
        this.updateStats(0, 0, 0);
    }

    scheduleUpdate() {
        if (this.updateTimeout) {
            clearTimeout(this.updateTimeout);
        }
        this.updateTimeout = setTimeout(() => this.updatePreview(), 100);
    }

    async updatePreview(forceRefresh = false) {
        if (this.isUpdating && !forceRefresh) return;
        if (!this.timeline) return;

        const segments = this.timeline.getSegments();
        if (segments.length === 0) {
            this.showEmptyState();
            return;
        }

        this.isUpdating = true;
        this.showLoading(true);

        try {
            // Get global scale settings from the properties panel
            const timeUnitsSelect = document.getElementById('time-units');
            
            const timeUnitsValue = timeUnitsSelect ? timeUnitsSelect.value : 'us';
            const amplitudeScaleValue = 'V'; // Fixed amplitude units
            
            // Check if we have multi-channel data
            const channels = this.timeline?.channels || [];
            let requestData;
            
            if (channels.length > 0 && channels.some(channel => channel.segments && channel.segments.length > 0)) {
                // Multi-channel data - send channel structure
                requestData = {
                    channels: channels.map(channel => ({
                        name: channel.name,
                        color: channel.color,
                        segments: channel.segments.map(seg => ({
                            type: seg.type,
                            name: seg.name,
                            duration: seg.duration,
                            amplitude: seg.amplitude,
                            parameters: seg.parameters || {},
                            markers: seg.markers || { marker1: { delay: 0, duration: 0 }, marker2: { delay: 0, duration: 0 } }
                        }))
                    })),
                    sample_rate: this.sampleRate,
                    time_units: timeUnitsValue,
                    amplitude_scale: amplitudeScaleValue
                };
            } else {
                // Legacy single-channel data
                requestData = {
                    segments: segments.map(seg => ({
                        type: seg.type,
                        name: seg.name,
                        duration: seg.duration,
                        amplitude: seg.amplitude,
                        parameters: seg.parameters || {},
                        markers: seg.markers || { marker1: { delay: 0, duration: 0 }, marker2: { delay: 0, duration: 0 } }
                    })),
                    sample_rate: this.sampleRate,
                    time_units: timeUnitsValue,
                    amplitude_scale: amplitudeScaleValue
                };
            }

            // Get waveform data from backend
            const response = await fetch('/api/waveform/preview/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestData)
            });

            const data = await response.json();
            
            if (data.success) {
                await this.renderPlot(data.plot, data.stats);
                this.updateStats(data.stats.total_duration, data.stats.points, data.stats.peak_amplitude);
            } else {
                // Check if this is a duration mismatch error
                if (data.error_type === 'duration_mismatch') {
                    this.showDurationMismatchError(data.error_message, data.channel_info);
                } else {
                    throw new Error(data.error || 'Unknown error');
                }
            }

        } catch (error) {
            console.error('Failed to update preview:', error);
            this.showError(error.message);
        } finally {
            this.isUpdating = false;
            this.showLoading(false);
        }
    }

    async renderPlot(plotJson, stats) {
        try {
            // Always use the backend-generated plot directly
            // The backend now handles both single-channel and multi-channel plotting
            const plotData = JSON.parse(plotJson);
            
            
            // Fix trace data format before rendering
            const fixedTraces = plotData.data.map(trace => {
                const fixedTrace = { ...trace };
                
                // Convert numpy array objects to JavaScript arrays
                if (trace.x && typeof trace.x === 'object' && trace.x.bdata && trace.x.dtype) {
                    try {
                        // Decode base64 binary data for numpy arrays
                        const binaryString = atob(trace.x.bdata);
                        const bytes = new Uint8Array(binaryString.length);
                        for (let i = 0; i < binaryString.length; i++) {
                            bytes[i] = binaryString.charCodeAt(i);
                        }
                        
                        // Convert bytes to float64 array
                        const float64Array = new Float64Array(bytes.buffer);
                        fixedTrace.x = Array.from(float64Array);
                        
                    } catch (error) {
                        console.error('Failed to decode x data:', error);
                        fixedTrace.x = [];
                    }
                }
                
                if (trace.y && typeof trace.y === 'object' && trace.y.bdata && trace.y.dtype) {
                    try {
                        // Decode base64 binary data for numpy arrays
                        const binaryString = atob(trace.y.bdata);
                        const bytes = new Uint8Array(binaryString.length);
                        for (let i = 0; i < binaryString.length; i++) {
                            bytes[i] = binaryString.charCodeAt(i);
                        }
                        
                        // Convert bytes to float64 array
                        const float64Array = new Float64Array(bytes.buffer);
                        fixedTrace.y = Array.from(float64Array);
                        
                    } catch (error) {
                        console.error('Failed to decode y data:', error);
                        fixedTrace.y = [];
                    }
                }
                
                return fixedTrace;
            });
            
            // Use the plot data directly from the backend (which includes subplots if multi-channel)
            await Plotly.react(this.plotDiv, fixedTraces, plotData.layout);
            
        } catch (error) {
            console.error('Failed to render plot:', error);
            this.showError('Failed to render waveform plot');
        }
    }

    updateStats(duration, points, peakAmplitude) {
        if (this.statDuration) {
            // Get current time units from properties panel
            const timeInfo = window.propertiesPanel?.getTimeScaleInfo() || { factor: 1e6, symbol: 'μs' };
            this.statDuration.textContent = `${(duration * timeInfo.factor).toFixed(2)} ${timeInfo.symbol}`;
        }
        if (this.statPoints) {
            this.statPoints.textContent = points.toLocaleString();
        }
        if (this.sampleCountBadge) {
            this.sampleCountBadge.textContent = `${points.toLocaleString()} samples`;
        }
        if (this.statPeak) {
            this.statPeak.textContent = `${(peakAmplitude).toFixed(3)} V`;
        }
    }

    showLoading(show) {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.style.display = show ? 'flex' : 'none';
        }
    }

    showError(message) {
        const annotation = {
            text: `Error: ${message}`,
            x: 0.5,
            y: 0.5,
            xref: 'paper',
            yref: 'paper',
            showarrow: false,
            font: { size: 14, color: '#e74c3c' },
            bgcolor: 'rgba(231, 76, 60, 0.1)',
            bordercolor: '#e74c3c',
            borderwidth: 1
        };

        Plotly.relayout(this.plotDiv, {
            annotations: [annotation]
        });
    }

    showDurationMismatchError(message, channelInfo) {
        // Build detailed channel information text with line breaks
        let channelDetails = '';
        if (channelInfo && channelInfo.length > 0) {
            channelDetails = '<br><br><b>Channel Details:</b><br>';
            channelInfo.forEach(info => {
                channelDetails += `Channel ${info.channel}: ${info.npts.toLocaleString()} points<br>`;
            });
        }

        // Split the message into shorter lines for better wrapping
        const wrappedMessage = message
            .replace('All channels within the waveform element must be the same length.', 
                     'All channels within the waveform element<br>must be the same length.')
            .replace('Please edit the duration or add additional segments to ensure all channels are the same length.', 
                     'Please edit the duration or add additional<br>segments to ensure all channels are<br>the same length.');

        const fullMessage = `<b>Plot not updated:</b><br><br>${wrappedMessage}${channelDetails}`;

        const annotation = {
            text: fullMessage,
            x: 0.5,
            y: 0.5,
            xref: 'paper',
            yref: 'paper',
            showarrow: false,
            font: { size: 11, color: '#721c24' },
            bgcolor: 'rgba(248, 215, 218, 0.95)',
            bordercolor: '#f5c6cb',
            borderwidth: 2,
            borderpad: 20,
            align: 'left'
        };

        // Clear the plot and show error message
        const layout = {
            xaxis: {
                title: 'Time (μs)',
                showgrid: true,
                zeroline: true,
                range: [0, 10]
            },
            yaxis: {
                title: 'Amplitude (V)',
                showgrid: true,
                zeroline: true,
                range: [-1, 1]
            },
            annotations: [annotation],
            showlegend: false,
            margin: { l: 50, r: 50, t: 30, b: 50 }
        };

        Plotly.react(this.plotDiv, [], layout);
        
        // Clear stats to indicate no valid data
        this.updateStats(0, 0, 0);
    }

    // Public API
    refresh() {
        this.updatePreview(true);
    }

    setSampleRate(rate) {
        this.sampleRate = rate;
        this.scheduleUpdate();
    }

    exportPlotData() {
        if (!this.timeline) return null;
        
        const segments = this.timeline.getSegments();
        return {
            segments: segments,
            sampleRate: this.sampleRate,
            plotElement: this.plotDiv
        };
    }

    async exportPlotImage(format = 'png') {
        try {
            const image = await Plotly.toImage(this.plotDiv, {
                format: format,
                width: 800,
                height: 600,
                scale: 2
            });
            return image;
        } catch (error) {
            console.error('Failed to export plot image:', error);
            return null;
        }
    }
}

// Export for use in main application
window.PreviewPanel = PreviewPanel;
