class HuaweiChargerInfoCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._lastEntityStates = {};
  }

  setConfig(config) {
    this.config = {
      show_diagnostic: config?.show_diagnostic !== false,
      ...config
    };
  }

  set hass(hass) {
    const oldHass = this._hass;
    this._hass = hass;
    
    // Always render on first load
    if (!oldHass) {
      this._renderSafely();
      return;
    }
    
    // Check if relevant entity states have changed
    if (this._hasEntityStatesChanged(hass, oldHass)) {
      this._renderSafely();
    }
  }

  getCardSize() {
    return this.config.show_diagnostic ? 5 : 3;
  }

  _normalizeStateValue(value) {
    return String(value ?? '').trim().toLowerCase();
  }

  _isEntityAvailable(entity) {
    if (!entity) return false;
    const state = this._normalizeStateValue(entity.state);
    return state !== '' && state !== 'unknown' && state !== 'unavailable' && state !== 'none';
  }

  _findEntityBySuffixes(huaweiEntities, suffixes, configuredEntityId = null) {
    if (configuredEntityId && this._hass.states?.[configuredEntityId]) {
      return this._hass.states[configuredEntityId];
    }

    for (const suffix of suffixes) {
      const found = huaweiEntities.find(
        (id) => id.endsWith(`_${suffix}`) || id.endsWith(`.${suffix}`)
      );
      if (found) {
        return this._hass.states[found];
      }
    }

    return null;
  }

  _stateMap(hass = this._hass) {
    return hass?.states || {};
  }

  _renderSafely() {
    try {
      this.render();
    } catch (error) {
      console.error('Huawei charger info card render failed:', error);
      if (!this.shadowRoot) {
        return;
      }
      this.shadowRoot.innerHTML = `
        <ha-card>
          <div class="card-content">
            <div class="error">
              <h3>Card temporarily unavailable</h3>
              <p>The Huawei Charger info card hit a transient frontend state. Refresh the dashboard if this persists.</p>
            </div>
          </div>
        </ha-card>
      `;
    }
  }

  _parseNumber(value) {
    const parsed = parseFloat(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  _candidateEntityIds(hass = this._hass) {
    const allEntityIds = Object.keys(this._stateMap(hass));
    const exactMatches = allEntityIds.filter((id) => id.includes('huawei_charger'));
    if (exactMatches.length > 0) {
      return exactMatches;
    }
    return allEntityIds.filter((id) => id.includes('charger') || id.includes('huawei'));
  }

  _hasEntityStatesChanged(hass, oldHass) {
    if (!hass || !oldHass) return false;
    
    // Get current device info entities
    const huaweiEntities = this._candidateEntityIds(hass).filter(id =>
      (
        id.includes('device_name') ||
        id.includes('alias') ||
        id.includes('esn') ||
        id.includes('serial_number') ||
        id.includes('software_version') ||
        id.includes('hardware_version') ||
        id.includes('device_model') ||
        id.includes('model') ||
        id.includes('rated_charging_power') ||
        id.includes('rated_power') ||
        id.includes('temperature') ||
        id.includes('lock_status') ||
        id.includes('error_code') ||
        id.includes('warning_code') ||
        id.includes('voltage') ||
        id.includes('network_mode') ||
        id.includes('grounding_system') ||
        id.includes('authentication_type') ||
        id.includes('encrypt_type')
      )
    );
    
    // Check if any relevant entity states changed by comparing with previous hass
    for (const entityId of huaweiEntities) {
      const currentState = this._stateMap(hass)[entityId];
      const previousState = this._stateMap(oldHass)[entityId];
      
      if (!currentState && !previousState) continue; // Both don't exist
      if (!currentState || !previousState) return true; // One exists, one doesn't
      
      // Compare state values (these are the main values we display)
      if (currentState.state !== previousState.state) {
        return true;
      }
    }
    
    return false;
  }

  render() {
    if (!this._hass) return;

    // Auto-detect device info entities
    const huaweiEntities = this._candidateEntityIds();
    
    // Get device info entities
    const deviceName = this._findEntityBySuffixes(huaweiEntities, ['device_name', 'alias']);
    const serialNumber = this._findEntityBySuffixes(huaweiEntities, ['esn', 'device_serial_number', 'serial_number']);
    const softwareVersion = this._findEntityBySuffixes(huaweiEntities, ['software_version']);
    const hardwareVersion = this._findEntityBySuffixes(huaweiEntities, ['hardware_version']);
    const deviceModel = this._findEntityBySuffixes(huaweiEntities, ['device_model', 'model']);
    const ratedPower = this._findEntityBySuffixes(huaweiEntities, ['rated_charging_power', 'rated_power']);
    const temperature = this._findEntityBySuffixes(huaweiEntities, ['temperature']);
    const lockStatus = this._findEntityBySuffixes(huaweiEntities, ['lock_status']);
    const errorCode = this._findEntityBySuffixes(huaweiEntities, ['error_code']);
    const warningCode = this._findEntityBySuffixes(huaweiEntities, ['warning_code']);
    const networkMode = this._findEntityBySuffixes(huaweiEntities, ['network_mode']);
    const groundingSystem = this._findEntityBySuffixes(huaweiEntities, ['grounding_system']);
    const authType = this._findEntityBySuffixes(huaweiEntities, ['authentication_type']);
    const encryptType = this._findEntityBySuffixes(huaweiEntities, ['encrypt_type']);
    
    // Get voltage sensors for diagnostic info
    const phaseAVoltage = this._findEntityBySuffixes(huaweiEntities, ['phase_a_voltage']);
    const phaseBVoltage = this._findEntityBySuffixes(huaweiEntities, ['phase_b_voltage']);
    const phaseCVoltage = this._findEntityBySuffixes(huaweiEntities, ['phase_c_voltage']);
    
    if (huaweiEntities.length === 0) {
      this.shadowRoot.innerHTML = `
        <ha-card>
          <div class="card-content">
            <div class="error">
              <h3>No Huawei Charger entities found</h3>
              <p>Make sure the Huawei Charger integration is installed and configured.</p>
            </div>
          </div>
        </ha-card>
      `;
      return;
    }

    const detailRows = [];
    const statusRows = [];
    const diagnosticRows = [];
    const hasTemperature = this._isEntityAvailable(temperature);
    const parsedTemperature = this._parseNumber(temperature?.state);
    const parsedPhaseAVoltage = this._parseNumber(phaseAVoltage?.state);
    const parsedPhaseBVoltage = this._parseNumber(phaseBVoltage?.state);
    const parsedPhaseCVoltage = this._parseNumber(phaseCVoltage?.state);

    if (this._isEntityAvailable(deviceName)) {
      detailRows.push({ label: 'Name', value: deviceName.state });
    }
    if (this._isEntityAvailable(deviceModel)) {
      detailRows.push({ label: 'Model', value: deviceModel.state });
    }
    if (this._isEntityAvailable(serialNumber)) {
      detailRows.push({ label: 'ESN', value: serialNumber.state });
    }
    if (this._isEntityAvailable(ratedPower)) {
      detailRows.push({ label: 'Rated Power', value: `${ratedPower.state} kW` });
    }

    if (this._isEntityAvailable(softwareVersion)) {
      statusRows.push({ label: 'Software', value: softwareVersion.state });
    }
    if (this._isEntityAvailable(hardwareVersion)) {
      statusRows.push({ label: 'Hardware', value: hardwareVersion.state });
    }
    if (hasTemperature && parsedTemperature !== null) {
      statusRows.push({ label: 'Temperature', value: `${parsedTemperature.toFixed(1)}°C` });
    }
    if (this._isEntityAvailable(lockStatus)) {
      const lockValue = this._normalizeStateValue(lockStatus.state);
      const lockLabel = lockValue === '1'
        ? 'Locked'
        : lockValue === '0'
          ? 'Unlocked'
          : lockStatus.state;
      statusRows.push({ label: 'Lock Status', value: lockLabel });
    }
    if (this._isEntityAvailable(networkMode)) {
      statusRows.push({ label: 'Network Mode', value: networkMode.state });
    }

    if (this._isEntityAvailable(groundingSystem)) {
      diagnosticRows.push({ label: 'Grounding System', value: groundingSystem.state });
    }
    if (this._isEntityAvailable(authType)) {
      diagnosticRows.push({ label: 'Authentication Type', value: authType.state });
    }
    if (this._isEntityAvailable(encryptType)) {
      diagnosticRows.push({ label: 'Encrypt Type', value: encryptType.state });
    }

    if (detailRows.length === 0 && statusRows.length === 0 && diagnosticRows.length === 0) {
      this.shadowRoot.innerHTML = `
        <ha-card>
          <div class="card-content">
            <div class="error">
              <h3>No compatible device information entities available</h3>
              <p>The card will render automatically when Huawei exposes model, version, or configuration metadata.</p>
            </div>
          </div>
        </ha-card>
      `;
      return;
    }

    // Determine device health status
    let healthStatus = 'Info';
    let healthColor = '#2196F3';
    let healthIcon = 'mdi:information';
    
    const errorCodeValue = Number.parseInt(errorCode?.state, 10) || 0;
    const warningCodeValue = Number.parseInt(warningCode?.state, 10) || 0;
    const temp = parsedTemperature ?? 0;
    
    if (errorCodeValue > 0) {
      healthStatus = 'Error';
      healthColor = '#F44336';
      healthIcon = 'mdi:alert-circle';
    } else if (warningCodeValue > 0 || temp > 60) {
      healthStatus = 'Warning';
      healthColor = '#FF9800';
      healthIcon = 'mdi:alert';
    } else if (detailRows.length > 0 || statusRows.length > 0) {
      healthStatus = 'Good';
      healthColor = '#4CAF50';
      healthIcon = 'mdi:check-circle';
    }

    this.shadowRoot.innerHTML = `
      <style>
        .card-content {
          padding: 16px;
        }
        .card-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 20px;
        }
        .header-left {
          display: flex;
          align-items: center;
        }
        .header-left ha-icon {
          margin-right: 8px;
          --mdc-icon-size: 20px;
        }
        .card-title {
          font-size: 1.1em;
          font-weight: 500;
          margin: 0;
        }
        .health-status {
          display: flex;
          align-items: center;
          padding: 4px 12px;
          border-radius: 16px;
          font-size: 0.8em;
          font-weight: 500;
          background: ${healthColor}20;
          color: ${healthColor};
        }
        .health-status ha-icon {
          --mdc-icon-size: 16px;
          margin-right: 4px;
        }
        .device-info {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
          gap: 16px;
          margin-bottom: 20px;
        }
        .info-section {
          background: var(--secondary-background-color);
          border-radius: 12px;
          padding: 16px;
        }
        .section-title {
          font-size: 0.9em;
          font-weight: 500;
          margin-bottom: 12px;
          display: flex;
          align-items: center;
          color: var(--primary-color);
        }
        .section-title ha-icon {
          margin-right: 8px;
          --mdc-icon-size: 16px;
        }
        .info-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 6px 0;
          border-bottom: 1px solid var(--divider-color);
        }
        .info-item:last-child {
          border-bottom: none;
        }
        .info-label {
          font-size: 0.85em;
          opacity: 0.8;
        }
        .info-value {
          font-weight: 500;
          text-align: right;
          max-width: 50%;
          word-break: break-word;
        }
        .diagnostic-section {
          margin-top: 16px;
        }
        .voltage-readings {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 12px;
          margin-top: 12px;
        }
        .voltage-item {
          text-align: center;
          padding: 12px;
          background: var(--card-background-color);
          border-radius: 8px;
          border: 1px solid var(--divider-color);
        }
        .voltage-phase {
          font-size: 0.8em;
          opacity: 0.7;
          margin-bottom: 4px;
        }
        .voltage-value {
          font-size: 1.1em;
          font-weight: bold;
          color: var(--primary-color);
        }
        .status-indicators {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 12px;
          margin-top: 16px;
        }
        .status-item {
          display: flex;
          align-items: center;
          padding: 12px;
          background: var(--secondary-background-color);
          border-radius: 8px;
        }
        .status-icon {
          --mdc-icon-size: 20px;
          margin-right: 8px;
        }
        .status-good { color: #4CAF50; }
        .status-warning { color: #FF9800; }
        .status-error { color: #F44336; }
        .error {
          color: var(--error-color);
          text-align: center;
          padding: 16px;
        }
        .expandable {
          cursor: pointer;
          user-select: none;
        }
        .expandable:hover {
          background: var(--secondary-background-color);
        }
        .collapsed {
          display: none;
        }
      </style>
      
      <ha-card>
        <div class="card-content">
          <div class="card-header">
            <div class="header-left">
              <ha-icon icon="mdi:information"></ha-icon>
              <h3 class="card-title">Device Information</h3>
            </div>
            <div class="health-status">
              <ha-icon icon="${healthIcon}"></ha-icon>
              ${healthStatus}
            </div>
          </div>
          
          <div class="device-info">
            ${detailRows.length > 0 ? `
              <div class="info-section">
                <div class="section-title">
                  <ha-icon icon="mdi:chip"></ha-icon>
                  Device Details
                </div>
                ${detailRows.map((row) => `
                  <div class="info-item">
                    <span class="info-label">${row.label}:</span>
                    <span class="info-value">${row.value}</span>
                  </div>
                `).join('')}
              </div>
            ` : ''}

            ${statusRows.length > 0 ? `
              <div class="info-section">
                <div class="section-title">
                  <ha-icon icon="mdi:cog"></ha-icon>
                  Firmware & Status
                </div>
                ${statusRows.map((row) => `
                  <div class="info-item">
                    <span class="info-label">${row.label}:</span>
                    <span class="info-value">${row.value}</span>
                  </div>
                `).join('')}
              </div>
            ` : ''}
          </div>

          ${this.config.show_diagnostic && (
            diagnosticRows.length > 0 ||
            parsedPhaseAVoltage !== null ||
            parsedPhaseBVoltage !== null ||
            parsedPhaseCVoltage !== null ||
            this._isEntityAvailable(errorCode) ||
            this._isEntityAvailable(warningCode)
          ) ? `
            <div class="diagnostic-section">
              <div class="info-section">
                <div class="section-title expandable">
                  <ha-icon icon="mdi:chart-line-variant"></ha-icon>
                  Diagnostic Information
                  <ha-icon icon="mdi:chevron-down" style="margin-left: auto;"></ha-icon>
                </div>
                <div class="diagnostic-content">
                  ${diagnosticRows.length > 0 ? diagnosticRows.map((row) => `
                    <div class="info-item">
                      <span class="info-label">${row.label}:</span>
                      <span class="info-value">${row.value}</span>
                    </div>
                  `).join('') : ''}

                  ${(parsedPhaseAVoltage !== null || parsedPhaseBVoltage !== null || parsedPhaseCVoltage !== null) ? `
                    <div class="voltage-readings">
                      ${parsedPhaseAVoltage !== null ? `
                        <div class="voltage-item">
                          <div class="voltage-phase">Phase A</div>
                          <div class="voltage-value">${parsedPhaseAVoltage.toFixed(1)}V</div>
                        </div>
                      ` : ''}
                      ${parsedPhaseBVoltage !== null ? `
                        <div class="voltage-item">
                          <div class="voltage-phase">Phase B</div>
                          <div class="voltage-value">${parsedPhaseBVoltage.toFixed(1)}V</div>
                        </div>
                      ` : ''}
                      ${parsedPhaseCVoltage !== null ? `
                        <div class="voltage-item">
                          <div class="voltage-phase">Phase C</div>
                          <div class="voltage-value">${parsedPhaseCVoltage.toFixed(1)}V</div>
                        </div>
                      ` : ''}
                    </div>
                  ` : ''}
                  
                  ${(this._isEntityAvailable(errorCode) || this._isEntityAvailable(warningCode)) ? `
                    <div class="status-indicators">
                      ${this._isEntityAvailable(errorCode) ? `
                        <div class="status-item">
                          <ha-icon class="status-icon ${errorCodeValue > 0 ? 'status-error' : 'status-good'}" 
                                   icon="${errorCodeValue > 0 ? 'mdi:alert-circle' : 'mdi:check-circle'}"></ha-icon>
                          <div>
                            <div style="font-weight: 500;">Error Code</div>
                            <div style="font-size: 0.8em; opacity: 0.7;">${errorCodeValue}</div>
                          </div>
                        </div>
                      ` : ''}
                      
                      ${this._isEntityAvailable(warningCode) ? `
                        <div class="status-item">
                          <ha-icon class="status-icon ${warningCodeValue > 0 ? 'status-warning' : 'status-good'}" 
                                   icon="${warningCodeValue > 0 ? 'mdi:alert' : 'mdi:check-circle'}"></ha-icon>
                          <div>
                            <div style="font-weight: 500;">Warning Code</div>
                            <div style="font-size: 0.8em; opacity: 0.7;">${warningCodeValue}</div>
                          </div>
                        </div>
                      ` : ''}
                    </div>
                  ` : ''}
                </div>
              </div>
            </div>
          ` : ''}
        </div>
      </ha-card>
    `;

    this._bindExpandableSections();
  }

  _bindExpandableSections() {
    const toggles = this.shadowRoot?.querySelectorAll('.section-title.expandable');
    toggles?.forEach((toggle) => {
      toggle.addEventListener('click', () => {
        const content = toggle.nextElementSibling;
        if (content) {
          content.classList.toggle('collapsed');
        }
      });
    });
  }
}

if (!customElements.get('huawei-charger-info-card')) {
  customElements.define('huawei-charger-info-card', HuaweiChargerInfoCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === 'huawei-charger-info-card')) {
  window.customCards.push({
    type: 'huawei-charger-info-card',
    name: 'Huawei Charger Info Card',
    description: 'A custom card to display device information and diagnostics'
  });
}
