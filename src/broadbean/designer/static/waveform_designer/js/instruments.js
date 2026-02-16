/**
 * Instruments Configuration Page
 * Manages separate AWG, Scope, and LUT configuration creation, editing, and saving
 */

const InstrumentsManager = {
    // Current IDs for each config type
    currentAwgId: null,
    currentScopeId: null,
    currentLutId: null,

    // Track if current configs are mock (for export button state)
    currentAwgIsMock: true,
    currentScopeIsMock: true,

    // Cached configs lists
    awgConfigs: [],
    scopeConfigs: [],
    lutConfigs: [],

    // Current tab
    activeTab: 'awg',

    // Pending LUT data from file
    pendingLutData: null,

    // Cached instrument types from backend
    awgTypes: [],
    scopeTypes: [],

    /**
     * Initialize on page load
     */
    async init() {
        await this.loadInstrumentTypes();
        this.loadAllConfigs();
        this.bindEvents();
        this.resetAwgForm();
        this.resetScopeForm();
        this.resetLutForm();
    },

    /**
     * Load available instrument types from backend
     */
    async loadInstrumentTypes() {
        try {
            const response = await fetch('/api/instrument-types/');
            const data = await response.json();

            if (data.success) {
                this.awgTypes = data.awg_types || [];
                this.scopeTypes = data.scope_types || [];
                this.populateInstrumentTypeDropdowns();
            } else {
                console.error('Failed to load instrument types:', data.error);
            }
        } catch (error) {
            console.error('Error loading instrument types:', error);
        }
    },

    /**
     * Populate the AWG and Scope type dropdowns with values from backend
     */
    populateInstrumentTypeDropdowns() {
        // Populate AWG type dropdown
        const awgSelect = document.getElementById('awg-type');
        if (awgSelect) {
            awgSelect.innerHTML = '';
            this.awgTypes.forEach(type => {
                const option = document.createElement('option');
                option.value = type.value;
                option.textContent = type.label;
                awgSelect.appendChild(option);
            });
        }

        // Populate Scope type dropdown
        const scopeSelect = document.getElementById('scope-type');
        if (scopeSelect) {
            scopeSelect.innerHTML = '';
            this.scopeTypes.forEach(type => {
                const option = document.createElement('option');
                option.value = type.value;
                option.textContent = type.label;
                scopeSelect.appendChild(option);
            });
        }
    },

    /**
     * Bind event listeners
     */
    bindEvents() {
        // Save buttons
        document.getElementById('save-awg-btn')?.addEventListener('click', () => this.saveAwgConfig());
        document.getElementById('save-scope-btn')?.addEventListener('click', () => this.saveScopeConfig());
        document.getElementById('save-lut-btn')?.addEventListener('click', () => this.saveLutConfig());

        // Delete buttons
        document.getElementById('delete-awg-btn')?.addEventListener('click', () => this.showDeleteModal('awg'));
        document.getElementById('delete-scope-btn')?.addEventListener('click', () => this.showDeleteModal('scope'));
        document.getElementById('delete-lut-btn')?.addEventListener('click', () => this.showDeleteModal('lut'));

        // Test connection buttons
        document.getElementById('test-awg-btn')?.addEventListener('click', () => this.testConnection('awg'));
        document.getElementById('test-scope-btn')?.addEventListener('click', () => this.testConnection('scope'));

        // Export YAML buttons
        document.getElementById('export-awg-btn')?.addEventListener('click', () => this.exportStationYaml('awg'));
        document.getElementById('export-scope-btn')?.addEventListener('click', () => this.exportStationYaml('scope'));

        // Delete modal buttons
        document.getElementById('delete-modal-cancel')?.addEventListener('click', () => this.closeDeleteModal());
        document.getElementById('delete-modal-confirm')?.addEventListener('click', () => this.confirmDelete());
        document.querySelector('#delete-confirm-modal .custom-modal-backdrop')?.addEventListener('click', () => this.closeDeleteModal());

        // LUT file input change
        document.getElementById('lut-file')?.addEventListener('change', (e) => this.handleLutFileChange(e));
    },

    /**
     * Switch between tabs
     */
    switchTab(tab) {
        this.activeTab = tab;

        // Update tab buttons
        document.querySelectorAll('.config-tab').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tab);
        });

        // Update tab content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.toggle('active', content.id === `${tab}-tab`);
        });
    },

    /**
     * Create new config (called from sidebar buttons)
     */
    newConfig(type) {
        this.switchTab(type);

        if (type === 'awg') {
            this.currentAwgId = null;
            this.currentAwgIsMock = true;
            this.resetAwgForm();
            document.getElementById('delete-awg-btn').disabled = true;
            document.getElementById('export-awg-btn').disabled = true;
            document.getElementById('awg-config-name').focus();
            this.updateStatus('Creating new AWG configuration');
        } else if (type === 'scope') {
            this.currentScopeId = null;
            this.currentScopeIsMock = true;
            this.resetScopeForm();
            document.getElementById('delete-scope-btn').disabled = true;
            document.getElementById('export-scope-btn').disabled = true;
            document.getElementById('scope-config-name').focus();
            this.updateStatus('Creating new Scope configuration');
        } else if (type === 'lut') {
            this.currentLutId = null;
            this.resetLutForm();
            document.getElementById('delete-lut-btn').disabled = true;
            document.getElementById('lut-config-name').focus();
            this.updateStatus('Creating new LUT configuration');
        }

        this.updateConfigsLists();
    },

    /**
     * Load all configurations
     */
    async loadAllConfigs() {
        try {
            const response = await fetch('/api/all-configs/');
            const data = await response.json();

            if (data.success) {
                this.awgConfigs = data.awg_configs || [];
                this.scopeConfigs = data.scope_configs || [];
                this.lutConfigs = data.lut_configs || [];
                this.displayAllConfigs();
            } else {
                this.showError('Failed to load configurations: ' + data.error);
            }
        } catch (error) {
            console.error('Error loading configurations:', error);
            this.showError('Failed to load configurations');
        }
    },

    /**
     * Display all config lists in sidebar
     */
    displayAllConfigs() {
        this.displayAwgConfigs();
        this.displayScopeConfigs();
        this.displayLutConfigs();
    },

    /**
     * Get display label for AWG driver type
     */
    getAwgTypeLabel(driverType) {
        const type = this.awgTypes.find(t => t.value === driverType);
        return type ? type.label : (driverType === 'mock' ? 'Mock' : driverType);
    },

    /**
     * Get display label for Scope driver type
     */
    getScopeTypeLabel(driverType) {
        const type = this.scopeTypes.find(t => t.value === driverType);
        return type ? type.label : (driverType === 'mock' ? 'Mock' : driverType);
    },

    /**
     * Display AWG configs in sidebar
     */
    displayAwgConfigs() {
        const container = document.getElementById('awg-configs-list');

        if (this.awgConfigs.length === 0) {
            container.innerHTML = '<div class="empty-state small text-muted">No AWG configs</div>';
            return;
        }

        container.innerHTML = '';
        this.awgConfigs.forEach(config => {
            const item = document.createElement('div');
            item.className = 'config-item' + (config.id === this.currentAwgId ? ' selected' : '');
            item.dataset.configId = config.id;
            const typeLabel = this.getAwgTypeLabel(config.driver_type);
            item.innerHTML = `
                <div class="config-item-name">${CommonUtils.escapeHtml(config.name)}</div>
                <div class="config-item-type small text-muted">${typeLabel}</div>
            `;
            item.addEventListener('click', () => this.selectAwgConfig(config.id));
            container.appendChild(item);
        });
    },

    /**
     * Display Scope configs in sidebar
     */
    displayScopeConfigs() {
        const container = document.getElementById('scope-configs-list');

        if (this.scopeConfigs.length === 0) {
            container.innerHTML = '<div class="empty-state small text-muted">No Scope configs</div>';
            return;
        }

        container.innerHTML = '';
        this.scopeConfigs.forEach(config => {
            const item = document.createElement('div');
            item.className = 'config-item' + (config.id === this.currentScopeId ? ' selected' : '');
            item.dataset.configId = config.id;
            const typeLabel = this.getScopeTypeLabel(config.driver_type);
            item.innerHTML = `
                <div class="config-item-name">${CommonUtils.escapeHtml(config.name)}</div>
                <div class="config-item-type small text-muted">${typeLabel}</div>
            `;
            item.addEventListener('click', () => this.selectScopeConfig(config.id));
            container.appendChild(item);
        });
    },

    /**
     * Display LUT configs in sidebar
     */
    displayLutConfigs() {
        const container = document.getElementById('lut-configs-list');

        if (this.lutConfigs.length === 0) {
            container.innerHTML = '<div class="empty-state small text-muted">No LUT configs</div>';
            return;
        }

        container.innerHTML = '';
        this.lutConfigs.forEach(config => {
            const item = document.createElement('div');
            item.className = 'config-item' + (config.id === this.currentLutId ? ' selected' : '');
            item.dataset.configId = config.id;
            item.innerHTML = `
                <div class="config-item-name">${CommonUtils.escapeHtml(config.name)}</div>
                <div class="config-item-type small text-muted">${config.num_points || 0} points</div>
            `;
            item.addEventListener('click', () => this.selectLutConfig(config.id));
            container.appendChild(item);
        });
    },

    /**
     * Update config lists selection state
     */
    updateConfigsLists() {
        this.displayAllConfigs();
    },

    // ========================================================================
    // AWG Config Methods
    // ========================================================================

    async selectAwgConfig(configId) {
        try {
            this.showLoading('Loading AWG configuration...');

            const response = await fetch(`/api/awg-configs/${configId}/`);
            const data = await response.json();

            this.hideLoading();

            if (data.success) {
                this.currentAwgId = configId;
                this.currentAwgIsMock = data.config.is_mock;
                this.loadAwgIntoForm(data.config);
                this.switchTab('awg');
                this.updateConfigsLists();
                this.updateStatus(`Loaded AWG: ${data.config.name}`);
                document.getElementById('delete-awg-btn').disabled = false;
                // Enable export button only for non-mock configs
                document.getElementById('export-awg-btn').disabled = data.config.is_mock;
            } else {
                this.showError('Failed to load AWG configuration: ' + data.error);
            }
        } catch (error) {
            this.hideLoading();
            console.error('Error loading AWG configuration:', error);
            this.showError('Failed to load AWG configuration');
        }
    },

    loadAwgIntoForm(config) {
        document.getElementById('awg-config-name').value = config.name || '';
        document.getElementById('awg-config-description').value = config.description || '';

        // Use driver_type directly (set by backend)
        document.getElementById('awg-type').value = config.driver_type || 'mock';

        // Extract IP from VISA address if present
        const address = config.address || '';
        const ipMatch = address.match(/TCPIP\d*::([^:]+)::/);
        const ip = ipMatch ? ipMatch[1] : '192.168.0.2';
        document.getElementById('awg-ip').value = ip;

        // Extract parameters
        const params = config.parameters || {};
        document.getElementById('awg-sample-rate').value = params['sample_rate']?.initial_value || 25e9;
        document.getElementById('awg-timeout').value = config.visa_timeout || 60;
        document.getElementById('awg-flags').checked = config.use_flags || false;

        // Channel parameters
        document.getElementById('awg-ch1-resolution').value = params['ch1.resolution']?.initial_value || 8;
        document.getElementById('awg-ch1-amplitude').value = params['ch1.awg_amplitude']?.initial_value || 0.5;
        document.getElementById('awg-ch1-hold').value = params['ch1.hold']?.initial_value || 'FIRST';

        document.getElementById('awg-ch2-resolution').value = params['ch2.resolution']?.initial_value || 8;
        document.getElementById('awg-ch2-amplitude').value = params['ch2.awg_amplitude']?.initial_value || 0.5;
        document.getElementById('awg-ch2-hold').value = params['ch2.hold']?.initial_value || 'FIRST';
    },

    getAwgFromForm() {
        const ip = document.getElementById('awg-ip').value.trim();
        return {
            name: document.getElementById('awg-config-name').value.trim(),
            description: document.getElementById('awg-config-description').value.trim(),
            // Send driver_type directly (dropdown now has driver_type values)
            driver_type: document.getElementById('awg-type').value,
            address: `TCPIP0::${ip}::inst0::INSTR`,
            use_flags: document.getElementById('awg-flags').checked,
            visa_timeout: parseInt(document.getElementById('awg-timeout').value) || 60,
            parameters: {
                'sample_rate': { initial_value: parseFloat(document.getElementById('awg-sample-rate').value) },
                'ch1.resolution': { initial_value: parseInt(document.getElementById('awg-ch1-resolution').value) },
                'ch1.awg_amplitude': { initial_value: parseFloat(document.getElementById('awg-ch1-amplitude').value) },
                'ch1.hold': { initial_value: document.getElementById('awg-ch1-hold').value },
                'ch2.resolution': { initial_value: parseInt(document.getElementById('awg-ch2-resolution').value) },
                'ch2.awg_amplitude': { initial_value: parseFloat(document.getElementById('awg-ch2-amplitude').value) },
                'ch2.hold': { initial_value: document.getElementById('awg-ch2-hold').value }
            }
        };
    },

    resetAwgForm() {
        document.getElementById('awg-config-name').value = '';
        document.getElementById('awg-config-description').value = '';
        // Set to first available type (mock by default)
        const awgType = this.awgTypes.length > 0 ? this.awgTypes[0].value : 'mock';
        document.getElementById('awg-type').value = awgType;
        document.getElementById('awg-ip').value = '192.168.0.2';
        document.getElementById('awg-sample-rate').value = '25000000000';
        document.getElementById('awg-timeout').value = '60';
        document.getElementById('awg-flags').checked = false;

        ['1', '2'].forEach(ch => {
            document.getElementById(`awg-ch${ch}-resolution`).value = '8';
            document.getElementById(`awg-ch${ch}-amplitude`).value = '0.5';
            document.getElementById(`awg-ch${ch}-hold`).value = 'FIRST';
        });
    },

    async saveAwgConfig() {
        const config = this.getAwgFromForm();

        if (!config.name) {
            this.showError('Please enter a configuration name');
            document.getElementById('awg-config-name').focus();
            return;
        }

        try {
            this.showLoading('Saving AWG configuration...');

            let response;
            if (this.currentAwgId) {
                response = await fetch(`/api/awg-configs/${this.currentAwgId}/`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(config)
                });
            } else {
                response = await fetch('/api/awg-configs/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(config)
                });
            }

            const data = await response.json();
            this.hideLoading();

            if (data.success) {
                this.currentAwgId = data.config.id;
                this.currentAwgIsMock = data.config.is_mock;
                this.showSuccess(`AWG configuration "${config.name}" saved successfully`);
                await this.loadAllConfigs();
                this.updateStatus(`Saved AWG: ${config.name}`);
                document.getElementById('delete-awg-btn').disabled = false;
                // Enable export button only for non-mock configs
                document.getElementById('export-awg-btn').disabled = data.config.is_mock;
            } else {
                this.showError('Failed to save AWG configuration: ' + data.error);
            }
        } catch (error) {
            this.hideLoading();
            console.error('Error saving AWG configuration:', error);
            this.showError('Failed to save AWG configuration');
        }
    },

    // ========================================================================
    // Scope Config Methods
    // ========================================================================

    async selectScopeConfig(configId) {
        try {
            this.showLoading('Loading Scope configuration...');

            const response = await fetch(`/api/scope-configs/${configId}/`);
            const data = await response.json();

            this.hideLoading();

            if (data.success) {
                this.currentScopeId = configId;
                this.currentScopeIsMock = data.config.is_mock;
                this.loadScopeIntoForm(data.config);
                this.switchTab('scope');
                this.updateConfigsLists();
                this.updateStatus(`Loaded Scope: ${data.config.name}`);
                document.getElementById('delete-scope-btn').disabled = false;
                // Enable export button only for non-mock configs
                document.getElementById('export-scope-btn').disabled = data.config.is_mock;
            } else {
                this.showError('Failed to load Scope configuration: ' + data.error);
            }
        } catch (error) {
            this.hideLoading();
            console.error('Error loading Scope configuration:', error);
            this.showError('Failed to load Scope configuration');
        }
    },

    loadScopeIntoForm(config) {
        document.getElementById('scope-config-name').value = config.name || '';
        document.getElementById('scope-config-description').value = config.description || '';

        // Use driver_type directly (set by backend)
        document.getElementById('scope-type').value = config.driver_type || 'mock';

        // Extract IP from VISA address if present
        const address = config.address || '';
        const ipMatch = address.match(/TCPIP\d*::([^:]+)::/);
        const ip = ipMatch ? ipMatch[1] : '192.168.0.3';
        document.getElementById('scope-ip').value = ip;

        // Extract parameters
        const params = config.parameters || {};
        document.getElementById('scope-acq-mode').value = params['acquisition.mode']?.initial_value || 'sample';

        // Trigger settings - convert to uppercase for UI display (qcodes stores lowercase)
        const triggerTypeValue = (params['trigger.type']?.initial_value || 'edge').toUpperCase();
        document.getElementById('trigger-type').value = triggerTypeValue;
        document.getElementById('trigger-edge').value = 'RISE';  // Not stored
        document.getElementById('trigger-level').value = params['trigger.level']?.initial_value || 0.5;
        document.getElementById('trigger-source').value = params['trigger.source']?.initial_value || 'AUX';

        // Horizontal settings
        document.getElementById('horizontal-position').value = params['horizontal.position']?.initial_value || 0;
        document.getElementById('horizontal-scale').value = params['horizontal.scale']?.initial_value || 100e-9;
        document.getElementById('horizontal-record-length').value = 5000;  // Not stored
        document.getElementById('horizontal-sample-rate').value = params['horizontal.sample_rate']?.initial_value || 2.5e9;
        document.getElementById('horizontal-mode').value = params['horizontal.mode']?.initial_value || 'auto';

        // Timeout
        document.getElementById('scope-timeout').value = config.visa_timeout || 60;

        const channels = config.channels || [];
        for (let i = 0; i < 3; i++) {
            const ch = channels[i] || {};
            const chNum = i + 1;
            document.getElementById(`scope-ch${chNum}-enabled`).checked = ch.enabled === 'ON';
            document.getElementById(`scope-ch${chNum}-scale`).value = ch.scale || 0.1;
            document.getElementById(`scope-ch${chNum}-offset`).value = ch.offset || 0;
            document.getElementById(`scope-ch${chNum}-position`).value = ch.position || 0;
        }
    },

    getScopeFromForm() {
        const ip = document.getElementById('scope-ip').value.trim();
        // Convert trigger type to lowercase as qcodes expects lowercase values
        const triggerType = document.getElementById('trigger-type').value.toLowerCase();
        return {
            name: document.getElementById('scope-config-name').value.trim(),
            description: document.getElementById('scope-config-description').value.trim(),
            // Send driver_type directly (dropdown now has driver_type values)
            driver_type: document.getElementById('scope-type').value,
            address: `TCPIP0::${ip}::inst0::INSTR`,
            visa_timeout: parseInt(document.getElementById('scope-timeout').value) || 60,
            parameters: {
                'acquisition.mode': { initial_value: document.getElementById('scope-acq-mode').value },
                'trigger.type': { initial_value: triggerType },
                'trigger.source': { initial_value: document.getElementById('trigger-source').value },
                'trigger.level': { initial_value: parseFloat(document.getElementById('trigger-level').value) },
                'horizontal.mode': { initial_value: document.getElementById('horizontal-mode').value },
                'horizontal.position': { initial_value: parseFloat(document.getElementById('horizontal-position').value) },
                'horizontal.scale': { initial_value: parseFloat(document.getElementById('horizontal-scale').value) },
                'horizontal.sample_rate': { initial_value: parseFloat(document.getElementById('horizontal-sample-rate').value) }
            },
            channels: [
                {
                    source: 'CH1',
                    enabled: document.getElementById('scope-ch1-enabled').checked ? 'ON' : 'OFF',
                    scale: parseFloat(document.getElementById('scope-ch1-scale').value),
                    offset: parseFloat(document.getElementById('scope-ch1-offset').value),
                    position: parseFloat(document.getElementById('scope-ch1-position').value)
                },
                {
                    source: 'CH2',
                    enabled: document.getElementById('scope-ch2-enabled').checked ? 'ON' : 'OFF',
                    scale: parseFloat(document.getElementById('scope-ch2-scale').value),
                    offset: parseFloat(document.getElementById('scope-ch2-offset').value),
                    position: parseFloat(document.getElementById('scope-ch2-position').value)
                },
                {
                    source: 'CH3',
                    enabled: document.getElementById('scope-ch3-enabled').checked ? 'ON' : 'OFF',
                    scale: parseFloat(document.getElementById('scope-ch3-scale').value),
                    offset: parseFloat(document.getElementById('scope-ch3-offset').value),
                    position: parseFloat(document.getElementById('scope-ch3-position').value)
                }
            ]
        };
    },

    resetScopeForm() {
        document.getElementById('scope-config-name').value = '';
        document.getElementById('scope-config-description').value = '';
        // Set to first available type (mock by default)
        const scopeType = this.scopeTypes.length > 0 ? this.scopeTypes[0].value : 'mock';
        document.getElementById('scope-type').value = scopeType;
        document.getElementById('scope-ip').value = '192.168.0.3';
        document.getElementById('scope-acq-mode').value = 'sample';

        document.getElementById('trigger-type').value = 'EDGE';
        document.getElementById('trigger-edge').value = 'RISE';
        document.getElementById('trigger-level').value = '0.5';
        document.getElementById('trigger-source').value = 'AUX';

        document.getElementById('horizontal-position').value = '0';
        document.getElementById('horizontal-scale').value = '1';
        document.getElementById('horizontal-record-length').value = '5000';
        document.getElementById('horizontal-sample-rate').value = '25000000000';
        document.getElementById('horizontal-mode').value = 'manual';

        document.getElementById('scope-timeout').value = '60';

        ['1', '2', '3'].forEach(ch => {
            document.getElementById(`scope-ch${ch}-enabled`).checked = false;
            document.getElementById(`scope-ch${ch}-scale`).value = '0.1';
            document.getElementById(`scope-ch${ch}-offset`).value = '0';
            document.getElementById(`scope-ch${ch}-position`).value = '0';
        });
    },

    async saveScopeConfig() {
        const config = this.getScopeFromForm();

        if (!config.name) {
            this.showError('Please enter a configuration name');
            document.getElementById('scope-config-name').focus();
            return;
        }

        try {
            this.showLoading('Saving Scope configuration...');

            let response;
            if (this.currentScopeId) {
                response = await fetch(`/api/scope-configs/${this.currentScopeId}/`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(config)
                });
            } else {
                response = await fetch('/api/scope-configs/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(config)
                });
            }

            const data = await response.json();
            this.hideLoading();

            if (data.success) {
                this.currentScopeId = data.config.id;
                this.currentScopeIsMock = data.config.is_mock;
                this.showSuccess(`Scope configuration "${config.name}" saved successfully`);
                await this.loadAllConfigs();
                this.updateStatus(`Saved Scope: ${config.name}`);
                document.getElementById('delete-scope-btn').disabled = false;
                // Enable export button only for non-mock configs
                document.getElementById('export-scope-btn').disabled = data.config.is_mock;
            } else {
                this.showError('Failed to save Scope configuration: ' + data.error);
            }
        } catch (error) {
            this.hideLoading();
            console.error('Error saving Scope configuration:', error);
            this.showError('Failed to save Scope configuration');
        }
    },

    // ========================================================================
    // LUT Config Methods
    // ========================================================================

    async selectLutConfig(configId) {
        try {
            this.showLoading('Loading LUT configuration...');

            const response = await fetch(`/api/lut-configs/${configId}/`);
            const data = await response.json();

            this.hideLoading();

            if (data.success) {
                this.currentLutId = configId;
                this.loadLutIntoForm(data.config);
                this.switchTab('lut');
                this.updateConfigsLists();
                this.updateStatus(`Loaded LUT: ${data.config.name}`);
                document.getElementById('delete-lut-btn').disabled = false;
            } else {
                this.showError('Failed to load LUT configuration: ' + data.error);
            }
        } catch (error) {
            this.hideLoading();
            console.error('Error loading LUT configuration:', error);
            this.showError('Failed to load LUT configuration');
        }
    },

    loadLutIntoForm(config) {
        document.getElementById('lut-config-name').value = config.name || '';
        document.getElementById('lut-config-description').value = config.description || '';

        // Store current LUT data
        this.pendingLutData = {
            input_lut: config.input_lut || [],
            output_lut: config.output_lut || []
        };

        // Update preview
        this.updateLutPreview(this.pendingLutData);

        // Clear file input
        const fileInput = document.getElementById('lut-file');
        if (fileInput) fileInput.value = '';
    },

    resetLutForm() {
        document.getElementById('lut-config-name').value = '';
        document.getElementById('lut-config-description').value = '';
        this.pendingLutData = null;

        document.getElementById('lut-status').innerHTML = '<span class="badge bg-secondary">No LUT data loaded</span>';
        document.getElementById('lut-preview').style.display = 'none';

        const fileInput = document.getElementById('lut-file');
        if (fileInput) fileInput.value = '';
    },

    handleLutFileChange(event) {
        const file = event.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const content = e.target.result;
                const lines = content.split('\n');

                // Parse CSV
                const inputLut = [];
                const outputLut = [];

                // Find header row
                let headerIndex = -1;
                let inputCol = -1;
                let outputCol = -1;

                for (let i = 0; i < lines.length; i++) {
                    const line = lines[i].trim();
                    if (!line) continue;

                    const cols = line.split(',').map(c => c.trim().toLowerCase());

                    for (let j = 0; j < cols.length; j++) {
                        if (['input', 'in'].includes(cols[j])) inputCol = j;
                        if (['output', 'out'].includes(cols[j])) outputCol = j;
                    }

                    if (inputCol >= 0 && outputCol >= 0) {
                        headerIndex = i;
                        break;
                    }
                }

                if (headerIndex < 0) {
                    this.showError('CSV must have "input" and "output" columns');
                    return;
                }

                // Parse data rows
                for (let i = headerIndex + 1; i < lines.length; i++) {
                    const line = lines[i].trim();
                    if (!line) continue;

                    const cols = line.split(',');
                    const inputVal = parseFloat(cols[inputCol]);
                    const outputVal = parseFloat(cols[outputCol]);

                    if (!isNaN(inputVal) && !isNaN(outputVal)) {
                        inputLut.push(inputVal);
                        outputLut.push(outputVal);
                    }
                }

                if (inputLut.length < 2) {
                    this.showError('LUT must have at least 2 data points');
                    return;
                }

                this.pendingLutData = { input_lut: inputLut, output_lut: outputLut };
                this.updateLutPreview(this.pendingLutData);
                this.showSuccess(`Loaded ${inputLut.length} points from CSV`);

            } catch (error) {
                console.error('Error parsing CSV:', error);
                this.showError('Failed to parse CSV file');
            }
        };

        reader.readAsText(file);
    },

    updateLutPreview(lutData) {
        const statusDiv = document.getElementById('lut-status');
        const previewDiv = document.getElementById('lut-preview');

        if (lutData && lutData.input_lut && lutData.input_lut.length > 0) {
            const numPoints = lutData.input_lut.length;
            const inputMin = Math.min(...lutData.input_lut).toFixed(4);
            const inputMax = Math.max(...lutData.input_lut).toFixed(4);
            const outputMin = Math.min(...lutData.output_lut).toFixed(4);
            const outputMax = Math.max(...lutData.output_lut).toFixed(4);

            statusDiv.innerHTML = `<span class="badge bg-success"><i class="fas fa-check-circle"></i> ${numPoints} points loaded</span>`;

            document.getElementById('lut-num-points').textContent = numPoints;
            document.getElementById('lut-input-range').textContent = `${inputMin} to ${inputMax}`;
            document.getElementById('lut-output-range').textContent = `${outputMin} to ${outputMax}`;

            previewDiv.style.display = 'block';

            // Plot the LUT data
            this.plotLutData(lutData);
        } else {
            statusDiv.innerHTML = '<span class="badge bg-secondary">No LUT data loaded</span>';
            previewDiv.style.display = 'none';
        }
    },

    /**
     * Plot LUT data using Plotly
     */
    plotLutData(lutData) {
        const plotDiv = document.getElementById('lut-plot');
        if (!plotDiv) return;

        const trace = {
            x: lutData.input_lut,
            y: lutData.output_lut,
            type: 'scatter',
            mode: 'lines+markers',
            name: 'LUT Mapping',
            line: {
                color: '#0d6efd',
                width: 2
            },
            marker: {
                size: 8,
                color: '#0d6efd'
            }
        };

        const layout = {
            title: {
                text: 'LUT Transfer Function',
                font: { size: 14 }
            },
            xaxis: {
                title: 'Input',
                showgrid: true,
                zeroline: true,
                zerolinecolor: '#ccc'
            },
            yaxis: {
                title: 'Output',
                showgrid: true,
                zeroline: true,
                zerolinecolor: '#ccc'
            },
            margin: {
                l: 60,
                r: 30,
                t: 40,
                b: 50
            },
            autosize: true,
            showlegend: false
        };

        const config = {
            responsive: true,
            displayModeBar: true,
            displaylogo: false,
            modeBarButtonsToRemove: ['lasso2d', 'select2d']
        };

        Plotly.newPlot(plotDiv, [trace], layout, config);
    },

    async saveLutConfig() {
        const name = document.getElementById('lut-config-name').value.trim();
        const description = document.getElementById('lut-config-description').value.trim();

        if (!name) {
            this.showError('Please enter a configuration name');
            document.getElementById('lut-config-name').focus();
            return;
        }

        if (!this.pendingLutData || !this.pendingLutData.input_lut || this.pendingLutData.input_lut.length < 2) {
            this.showError('Please load LUT data from a CSV file');
            return;
        }

        const config = {
            name: name,
            description: description,
            input_lut: this.pendingLutData.input_lut,
            output_lut: this.pendingLutData.output_lut
        };

        try {
            this.showLoading('Saving LUT configuration...');

            let response;
            if (this.currentLutId) {
                response = await fetch(`/api/lut-configs/${this.currentLutId}/`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(config)
                });
            } else {
                response = await fetch('/api/lut-configs/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(config)
                });
            }

            const data = await response.json();
            this.hideLoading();

            if (data.success) {
                this.currentLutId = data.config.id;
                this.showSuccess(`LUT configuration "${name}" saved successfully`);
                await this.loadAllConfigs();
                this.updateStatus(`Saved LUT: ${name}`);
                document.getElementById('delete-lut-btn').disabled = false;
            } else {
                this.showError('Failed to save LUT configuration: ' + data.error);
            }
        } catch (error) {
            this.hideLoading();
            console.error('Error saving LUT configuration:', error);
            this.showError('Failed to save LUT configuration');
        }
    },

    // ========================================================================
    // Common Methods
    // ========================================================================

    async configureInstrument(instrumentType) {
        const resultsDiv = document.getElementById('test-results');

        // Always save first to capture any user edits, then configure
        let configId;
        if (instrumentType === 'awg') {
            // Save/update to capture current form values
            resultsDiv.innerHTML = `
                <div class="test-result-item">
                    <i class="fas fa-spinner fa-spin"></i>
                    <span>Saving AWG configuration...</span>
                </div>
            `;
            await this.saveAwgConfig();
            if (!this.currentAwgId) {
                // Save failed
                return;
            }
            configId = this.currentAwgId;
        } else {
            // Save/update to capture current form values
            resultsDiv.innerHTML = `
                <div class="test-result-item">
                    <i class="fas fa-spinner fa-spin"></i>
                    <span>Saving Scope configuration...</span>
                </div>
            `;
            await this.saveScopeConfig();
            if (!this.currentScopeId) {
                // Save failed
                return;
            }
            configId = this.currentScopeId;
        }

        try {
            resultsDiv.innerHTML = `
                <div class="test-result-item">
                    <i class="fas fa-spinner fa-spin"></i>
                    <span>Configuring ${instrumentType.toUpperCase()}...</span>
                </div>
            `;

            const response = await fetch('/api/instrument-configs/test/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    instrument_type: instrumentType,
                    config_id: configId
                })
            });

            const data = await response.json();

            if (data.success) {
                resultsDiv.innerHTML = `
                    <div class="test-result-item success">
                        <i class="fas fa-check-circle"></i>
                        <span>${instrumentType.toUpperCase()}: ${data.message}</span>
                    </div>
                `;
            } else {
                resultsDiv.innerHTML = `
                    <div class="test-result-item error">
                        <i class="fas fa-times-circle"></i>
                        <span>${instrumentType.toUpperCase()}: ${data.error}</span>
                    </div>
                `;
            }
        } catch (error) {
            console.error('Error configuring instrument:', error);
            resultsDiv.innerHTML = `
                <div class="test-result-item error">
                    <i class="fas fa-times-circle"></i>
                    <span>${instrumentType.toUpperCase()}: Configuration failed</span>
                </div>
            `;
        }
    },

    // Alias for backwards compatibility
    testConnection(instrumentType) {
        return this.configureInstrument(instrumentType);
    },

    pendingDeleteType: null,

    showDeleteModal(type) {
        this.pendingDeleteType = type;

        let name = '';
        if (type === 'awg') {
            const config = this.awgConfigs.find(c => c.id === this.currentAwgId);
            name = config?.name || '';
        } else if (type === 'scope') {
            const config = this.scopeConfigs.find(c => c.id === this.currentScopeId);
            name = config?.name || '';
        } else if (type === 'lut') {
            const config = this.lutConfigs.find(c => c.id === this.currentLutId);
            name = config?.name || '';
        }

        document.getElementById('delete-config-name').textContent = name;
        document.getElementById('delete-confirm-modal').style.display = 'flex';
    },

    closeDeleteModal() {
        document.getElementById('delete-confirm-modal').style.display = 'none';
        this.pendingDeleteType = null;
    },

    async confirmDelete() {
        const type = this.pendingDeleteType;
        this.closeDeleteModal();

        if (!type) return;

        let url, configId;
        if (type === 'awg') {
            configId = this.currentAwgId;
            url = `/api/awg-configs/${configId}/`;
        } else if (type === 'scope') {
            configId = this.currentScopeId;
            url = `/api/scope-configs/${configId}/`;
        } else if (type === 'lut') {
            configId = this.currentLutId;
            url = `/api/lut-configs/${configId}/`;
        }

        if (!configId) return;

        try {
            this.showLoading('Deleting configuration...');

            const response = await fetch(url, { method: 'DELETE' });
            const data = await response.json();

            this.hideLoading();

            if (data.success) {
                this.showSuccess('Configuration deleted successfully');

                if (type === 'awg') {
                    this.currentAwgId = null;
                    this.resetAwgForm();
                    document.getElementById('delete-awg-btn').disabled = true;
                } else if (type === 'scope') {
                    this.currentScopeId = null;
                    this.resetScopeForm();
                    document.getElementById('delete-scope-btn').disabled = true;
                } else if (type === 'lut') {
                    this.currentLutId = null;
                    this.resetLutForm();
                    document.getElementById('delete-lut-btn').disabled = true;
                }

                await this.loadAllConfigs();
                this.updateStatus('Configuration deleted');
            } else {
                this.showError('Failed to delete configuration: ' + data.error);
            }
        } catch (error) {
            this.hideLoading();
            console.error('Error deleting configuration:', error);
            this.showError('Failed to delete configuration');
        }
    },

    updateStatus(message) {
        const statusDiv = document.getElementById('config-status');
        statusDiv.innerHTML = `<p>${message}</p>`;
    },

    showLoading(message = 'Processing...') {
        const overlay = document.getElementById('loading-overlay');
        const messageEl = document.getElementById('loading-message');
        if (messageEl) messageEl.textContent = message;
        overlay.style.display = 'flex';
    },

    hideLoading() {
        document.getElementById('loading-overlay').style.display = 'none';
    },

    showError(message) {
        if (window.CommonUtils?.showToast) {
            CommonUtils.showToast(message, 'error');
        } else {
            alert('Error: ' + message);
        }
    },

    showSuccess(message) {
        if (window.CommonUtils?.showToast) {
            CommonUtils.showToast(message, 'success');
        } else {
            console.log('Success:', message);
        }
    },

    /**
     * Export Station YAML configuration for AWG or Scope
     */
    exportStationYaml(type) {
        if (type === 'awg') {
            if (!this.currentAwgId) {
                this.showError('Please save the AWG configuration first before exporting');
                return;
            }
            if (this.currentAwgIsMock) {
                this.showError('Cannot export YAML for mock configurations');
                return;
            }
            // Trigger download by navigating to the download endpoint
            window.location.href = `/api/awg-configs/${this.currentAwgId}/download/`;
        } else if (type === 'scope') {
            if (!this.currentScopeId) {
                this.showError('Please save the Scope configuration first before exporting');
                return;
            }
            if (this.currentScopeIsMock) {
                this.showError('Cannot export YAML for mock configurations');
                return;
            }
            // Trigger download by navigating to the download endpoint
            window.location.href = `/api/scope-configs/${this.currentScopeId}/download/`;
        }
    }
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => InstrumentsManager.init());
