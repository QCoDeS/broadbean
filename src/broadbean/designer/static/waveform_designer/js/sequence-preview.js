/**
 * Sequence Preview Component
 * Generates and displays waveform sequence preview using broadbean
 */

class SequencePreview {
    constructor() {
        this.plotDiv = document.getElementById('sequence-preview-plot');
        this.statusBadge = document.getElementById('preview-status');
        this.statsContainer = document.getElementById('sequence-stats');
        this.currentSequence = [];
        this.isPreviewStale = false;

        this.init();
    }

    init() {
        this.bindEvents();
        this.showEmptyState();
    }

    bindEvents() {
        // Listen for sequence changes
        window.addEventListener('sequenceChanged', (e) => {
            this.currentSequence = e.detail.elements;
            if (this.currentSequence.length > 0) {
                // Mark preview as outdated but don't auto-update
                this.isPreviewStale = true;
                this.showOutdatedState();
            } else {
                this.isPreviewStale = false;
                this.showEmptyState();
            }
        });

        // Manual refresh button
        const refreshBtn = document.getElementById('refresh-preview-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                if (this.currentSequence.length > 0) {
                    this.updatePreview();
                }
            });
        }

        // Max subsequences input - update preview on Enter key
        const maxSubsequencesInput = document.getElementById('max-subsequences');
        if (maxSubsequencesInput) {
            maxSubsequencesInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    if (this.currentSequence.length > 0) {
                        this.updatePreview();
                    }
                }
            });
        }
    }

    showEmptyState() {
        this.plotDiv.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-chart-line"></i>
                <p class="empty-state-title">No Sequence</p>
                <p class="empty-state-text">Add elements to the timeline to see the preview</p>
            </div>
        `;

        if (this.statusBadge) {
            this.statusBadge.textContent = 'No sequence';
            this.statusBadge.className = 'badge bg-secondary';
        }

        this.updateStats(null);
    }

    showOutdatedState() {
        // Keep the existing plot but indicate it's outdated
        if (this.statusBadge) {
            this.statusBadge.textContent = 'Click "Update Preview" to refresh';
            this.statusBadge.className = 'badge bg-warning';
        }

        // If no plot exists yet, show a placeholder
        if (!this.plotDiv.querySelector('.plotly') && !this.plotDiv.querySelector('.empty-state')) {
            this.plotDiv.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-sync-alt"></i>
                    <p class="empty-state-title">Preview Not Generated</p>
                    <p class="empty-state-text">Click "Update Preview" to generate the sequence preview</p>
                </div>
            `;
        }
    }

    showLoading() {
        this.plotDiv.innerHTML = `
            <div class="empty-state">
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
            <div class="empty-state">
                <i class="fas fa-exclamation-triangle"></i>
                <p class="empty-state-title">Preview Error</p>
                <p class="empty-state-text">${CommonUtils.escapeHtml(message)}</p>
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
            channelDetails = '<br><br><strong>Channel Details:</strong><br>';
            channelInfo.forEach(info => {
                channelDetails += `Channel ${info.channel}: ${info.npts.toLocaleString()} points<br>`;
            });
        }

        this.plotDiv.innerHTML = `
            <div class="empty-state" style="max-width: 90%; padding: 1.5rem;">
                <i class="fas fa-exclamation-circle" style="color: #856404; font-size: 3rem; margin-bottom: 1rem;"></i>
                <p class="empty-state-title" style="color: #856404; margin-bottom: 1rem;">Plot Not Updated</p>
                <div class="alert alert-warning" style="text-align: center; margin: 0 auto; max-width: 600px; word-wrap: break-word;">
                    <p style="margin-bottom: 0.5rem;"><strong>${CommonUtils.escapeHtml(message)}</strong></p>
                    ${channelDetails}
                </div>
            </div>
        `;

        if (this.statusBadge) {
            this.statusBadge.textContent = 'Duration mismatch';
            this.statusBadge.className = 'badge bg-warning';
        }

        this.updateStats(null);
    }

    async updatePreview() {
        if (this.currentSequence.length === 0) {
            this.showEmptyState();
            return;
        }

        try {
            this.showLoading();

            // Get max_subsequences from input
            const maxSubsequencesInput = document.getElementById('max-subsequences');
            const maxSubsequences = maxSubsequencesInput ? parseInt(maxSubsequencesInput.value) || 10 : 10;

            // Prepare sequence data for backend
            const sequenceData = {
                elements: this.currentSequence.map(elem => ({
                    element_id: elem.element_id,
                    position: elem.position,
                    trigger_input: elem.trigger_input,
                    repetitions: elem.repetitions,
                    goto: elem.goto
                })),
                max_subsequences: maxSubsequences
            };

            // Call backend to generate preview
            const response = await fetch('/api/sequence/preview/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(sequenceData)
            });

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

            // Clear container
            this.plotDiv.innerHTML = '';

            // Create Plotly plot with fixed traces
            Plotly.newPlot(this.plotDiv, fixedTraces, plotData.layout, {
                responsive: true,
                displayModeBar: true,
                modeBarButtonsToRemove: ['toImage', 'sendDataToCloud'],
                displaylogo: false
            });

            // Mark preview as up-to-date
            this.isPreviewStale = false;

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

        const positionsEl = document.getElementById('stat-positions');
        const durationEl = document.getElementById('stat-total-duration');
        const sampleRateEl = document.getElementById('stat-sample-rate');

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
        } else {
            if (positionsEl) positionsEl.textContent = '0';
            if (durationEl) durationEl.textContent = '0 μs';
            if (sampleRateEl) sampleRateEl.textContent = '0 Hz';
        }
    }

}
