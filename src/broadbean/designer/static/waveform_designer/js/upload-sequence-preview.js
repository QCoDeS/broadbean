/**
 * Simplified Sequence Preview for Upload Page
 * Displays preview of saved sequences using the preview_saved_sequence API
 */

class UploadSequencePreview {
    constructor() {
        this.plotDiv = document.getElementById('sequence-preview-plot');
        this.statusBadge = document.getElementById('preview-status');
        this.statsContainer = document.getElementById('preview-stats');
        this.currentSequenceId = null;
        
        this.bindEvents();
    }

    bindEvents() {
        // Max subsequences input - update preview on Enter key
        const maxSubsequencesInput = document.getElementById('max-subsequences');
        if (maxSubsequencesInput) {
            maxSubsequencesInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    if (this.currentSequenceId) {
                        this.updatePreview(this.currentSequenceId);
                    }
                }
            });
        }
    }

    /**
     * Update preview for a specific sequence ID
     */
    async updatePreview(sequenceId) {
        if (!sequenceId) {
            this.showEmptyState();
            return;
        }

        this.currentSequenceId = sequenceId;

        try {
            this.showLoading();

            // Get max_subsequences from input
            const maxSubsequencesInput = document.getElementById('max-subsequences');
            const maxSubsequences = maxSubsequencesInput ? parseInt(maxSubsequencesInput.value) || 10 : 10;

            // Call backend to generate preview for saved sequence
            const response = await fetch(`/api/sequences/${sequenceId}/preview/?max_subsequences=${maxSubsequences}`);
            const result = await response.json();

            if (!result.success) {
                // Check if this is a duration mismatch error
                if (result.error_type === 'duration_mismatch') {
                    this.showDurationMismatchError(result.error_message, result.channel_info);
                    return;
                }
                throw new Error(result.error || 'Failed to generate preview');
            }

            // Display the plot
            this.displayPlot(result.plot, result.stats, result.display_info);

        } catch (error) {
            console.error('Preview generation failed:', error);
            this.showError(error.message);
        }
    }

    showEmptyState() {
        this.plotDiv.innerHTML = `
            <div class="plot-placeholder">
                <i class="fas fa-chart-line"></i>
                <p>Select a sequence to preview the waveforms</p>
            </div>
        `;
        
        if (this.statusBadge) {
            this.statusBadge.textContent = 'No sequence';
            this.statusBadge.className = 'badge bg-secondary';
        }

        this.updateStats(null);
    }

    showLoading() {
        this.plotDiv.innerHTML = `
            <div class="plot-placeholder">
                <i class="fas fa-spinner fa-spin"></i>
                <p>Generating preview...</p>
            </div>
        `;

        if (this.statusBadge) {
            this.statusBadge.textContent = 'Generating...';
            this.statusBadge.className = 'badge bg-warning';
        }
    }

    showError(message) {
        this.plotDiv.innerHTML = `
            <div class="plot-placeholder">
                <i class="fas fa-exclamation-triangle"></i>
                <p style="color: #e74c3c; font-weight: 600;">Preview Error</p>
                <p style="font-size: 0.9rem;">${CommonUtils.escapeHtml(message)}</p>
            </div>
        `;

        if (this.statusBadge) {
            this.statusBadge.textContent = 'Error';
            this.statusBadge.className = 'badge bg-danger';
        }
    }

    showDurationMismatchError(message, channelInfo) {
        // Build detailed channel information text
        let channelDetails = '';
        if (channelInfo && channelInfo.length > 0) {
            channelDetails = '<div style="margin-top: 15px; text-align: left; max-width: 400px; margin-left: auto; margin-right: auto;">';
            channelDetails += '<strong>Channel Details:</strong><br>';
            channelInfo.forEach(info => {
                channelDetails += `Channel ${info.channel}: ${info.npts.toLocaleString()} points<br>`;
            });
            channelDetails += '</div>';
        }

        this.plotDiv.innerHTML = `
            <div class="plot-placeholder">
                <i class="fas fa-exclamation-circle" style="color: #856404;"></i>
                <p style="color: #856404; font-weight: 600;">Duration Mismatch</p>
                <p style="font-size: 0.9rem; color: #856404;">${CommonUtils.escapeHtml(message)}</p>
                ${channelDetails}
            </div>
        `;

        if (this.statusBadge) {
            this.statusBadge.textContent = 'Duration mismatch';
            this.statusBadge.className = 'badge bg-warning';
        }

        this.updateStats(null);
    }

    displayPlot(plotJson, stats, displayInfo) {
        try {
            // Parse and display Plotly plot
            const plotData = JSON.parse(plotJson);
            
            // Fix trace data format before rendering (decode numpy arrays)
            const fixedTraces = plotData.data.map(trace => {
                const fixedTrace = { ...trace };
                
                // Convert numpy array objects to JavaScript arrays
                if (trace.x && typeof trace.x === 'object' && trace.x.bdata && trace.x.dtype) {
                    try {
                        const binaryString = atob(trace.x.bdata);
                        const bytes = new Uint8Array(binaryString.length);
                        for (let i = 0; i < binaryString.length; i++) {
                            bytes[i] = binaryString.charCodeAt(i);
                        }
                        const float64Array = new Float64Array(bytes.buffer);
                        fixedTrace.x = Array.from(float64Array);
                    } catch (error) {
                        console.error('Failed to decode x data:', error);
                        fixedTrace.x = [];
                    }
                }
                
                if (trace.y && typeof trace.y === 'object' && trace.y.bdata && trace.y.dtype) {
                    try {
                        const binaryString = atob(trace.y.bdata);
                        const bytes = new Uint8Array(binaryString.length);
                        for (let i = 0; i < binaryString.length; i++) {
                            bytes[i] = binaryString.charCodeAt(i);
                        }
                        const float64Array = new Float64Array(bytes.buffer);
                        fixedTrace.y = Array.from(float64Array);
                    } catch (error) {
                        console.error('Failed to decode y data:', error);
                        fixedTrace.y = [];
                    }
                }
                
                return fixedTrace;
            });
            
            // Clear container
            this.plotDiv.innerHTML = '';

            // Create Plotly plot with fixed traces
            Plotly.newPlot(this.plotDiv, fixedTraces, plotData.layout, {
                responsive: true,
                displayModeBar: true,
                modeBarButtonsToRemove: ['toImage', 'sendDataToCloud'],
                displaylogo: false
            }).then(() => {
                // Single resize with minimal delay to ensure proper sizing
                setTimeout(() => {
                    Plotly.Plots.resize(this.plotDiv);
                }, 10);
            });

            // Update status with displayInfo if available
            if (this.statusBadge) {
                if (displayInfo) {
                    this.statusBadge.textContent = displayInfo;
                    this.statusBadge.className = 'badge bg-info';
                } else {
                    this.statusBadge.textContent = 'Preview ready';
                    this.statusBadge.className = 'badge bg-success';
                }
            }

            // Update stats
            this.updateStats(stats);

        } catch (error) {
            console.error('Failed to display plot:', error);
            this.showError('Failed to display plot');
        }
    }

    updateStats(stats) {
        if (!this.statsContainer) return;

        const positionsEl = document.getElementById('stat-preview-positions');
        const durationEl = document.getElementById('stat-preview-duration');
        const sampleRateEl = document.getElementById('stat-preview-rate');

        if (stats) {
            if (positionsEl) {
                positionsEl.textContent = stats.num_positions || 0;
            }

            if (durationEl) {
                durationEl.textContent = CommonUtils.formatDuration(stats.total_duration || 0);
            }

            if (sampleRateEl) {
                sampleRateEl.textContent = CommonUtils.formatSampleRate(stats.sample_rate || 0);
            }

            // Show stats container
            this.statsContainer.style.display = 'grid';
        } else {
            if (positionsEl) positionsEl.textContent = '0';
            if (durationEl) durationEl.textContent = '0 μs';
            if (sampleRateEl) sampleRateEl.textContent = '0 Hz';
            
            // Hide stats container
            this.statsContainer.style.display = 'none';
        }
    }

}
