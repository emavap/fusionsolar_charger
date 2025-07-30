class HuaweiChargerInfoCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._lastEntityStates = {};
  }

  setConfig(config) {
    this.config = {
      show_diagnostic: config.show_diagnostic !== false,
      ...config
    };
  }

  set hass(hass) {
    this._hass = hass;
    
    // Check if relevant entity states have changed
    if (this._hasEntityStatesChanged(hass)) {
      this.render();
    }
  }

  getCardSize() {
    return this.config.show_diagnostic ? 5 : 3;
  }

  _hasEntityStatesChanged(hass) {
    if (!hass) return false;
    
    // Get current device info entities
    const huaweiEntities = Object.keys(hass.states).filter(id => 
      id.includes('huawei_charger') && (
        id.includes('device_name') ||
        id.includes('serial_number') ||
        id.includes('software_version') ||
        id.includes('hardware_version') ||
        id.includes('device_model') ||
        id.includes('rated_power') ||
        id.includes('temperature') ||
        id.includes('lock_status') ||
        id.includes('error_code') ||
        id.includes('warning_code') ||
        id.includes('voltage')
      )
    );
    
    // Check if any relevant entity states changed
    let hasChanged = false;
    for (const entityId of huaweiEntities) {
      const currentState = hass.states[entityId];
      if (!currentState) continue; // Skip if entity doesn't exist
      
      const lastState = this._lastEntityStates[entityId];
      
      if (!lastState || 
          currentState.state !== lastState.state || 
          JSON.stringify(currentState.attributes) !== JSON.stringify(lastState.attributes)) {
        hasChanged = true;
      }
      
      // Update cached state
      this._lastEntityStates[entityId] = {
        state: currentState.state,
        attributes: { ...currentState.attributes }
      };
    }
    
    return hasChanged || Object.keys(this._lastEntityStates).length === 0;
  }

  render() {
    if (!this._hass) return;

    // Auto-detect device info entities
    const huaweiEntities = Object.keys(this._hass.states).filter(id => 
      id.includes('huawei_charger')
    );
    
    const findEntity = (patterns) => {
      for (const pattern of patterns) {
        const found = huaweiEntities.find(id => id.includes(pattern));
        if (found) return this._hass.states[found];
      }
      return null;
    };
    
    // Get device info entities
    const deviceName = findEntity(['device_name', 'name']);
    const serialNumber = findEntity(['device_serial_number', 'serial_number']);
    const softwareVersion = findEntity(['software_version']);
    const hardwareVersion = findEntity(['hardware_version']);
    const deviceModel = findEntity(['device_model', 'model']);
    const ratedPower = findEntity(['rated_power']);
    const temperature = findEntity(['temperature']);
    const lockStatus = findEntity(['lock_status']);
    const errorCode = findEntity(['error_code']);
    const warningCode = findEntity(['warning_code']);
    
    // Get voltage sensors for diagnostic info
    const phaseAVoltage = findEntity(['phase_a_voltage']);
    const phaseBVoltage = findEntity(['phase_b_voltage']);
    const phaseCVoltage = findEntity(['phase_c_voltage']);
    
    // If no device info entities found, show helpful message
    if (!deviceName && !serialNumber && !softwareVersion && !temperature) {
      this.shadowRoot.innerHTML = `
        <ha-card>
          <div class="card-content">
            <div class="error">
              <h3>No device information entities found</h3>
              <p>Available Huawei Charger entities:</p>
              <ul style="text-align: left; margin: 8px 0;">
                ${huaweiEntities.slice(0, 10).map(id => `<li><code>${id}</code></li>`).join('')}
                ${huaweiEntities.length > 10 ? `<li>... and ${huaweiEntities.length - 10} more</li>` : ''}
              </ul>
              <p>Make sure the integration includes device information sensor entities.</p>
            </div>
          </div>
        </ha-card>
      `;
      return;
    }

    // Determine device health status
    let healthStatus = 'Good';
    let healthColor = '#4CAF50';
    let healthIcon = 'mdi:check-circle';
    
    const errorCodeValue = parseInt(errorCode?.state) || 0;
    const warningCodeValue = parseInt(warningCode?.state) || 0;
    const temp = parseFloat(temperature?.state) || 0;
    
    if (errorCodeValue > 0) {
      healthStatus = 'Error';
      healthColor = '#F44336';
      healthIcon = 'mdi:alert-circle';
    } else if (warningCodeValue > 0 || temp > 60) {
      healthStatus = 'Warning';
      healthColor = '#FF9800';
      healthIcon = 'mdi:alert';
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
            <div class="info-section">
              <div class="section-title">
                <ha-icon icon="mdi:chip"></ha-icon>
                Device Details
              </div>
              <div class="info-item">
                <span class="info-label">Name:</span>
                <span class="info-value">${deviceName?.state || 'Unknown'}</span>
              </div>
              <div class="info-item">
                <span class="info-label">Model:</span>
                <span class="info-value">${deviceModel?.state || 'Unknown'}</span>
              </div>
              <div class="info-item">
                <span class="info-label">Serial Number:</span>
                <span class="info-value">${serialNumber?.state || 'Unknown'}</span>
              </div>
              <div class="info-item">
                <span class="info-label">Rated Power:</span>
                <span class="info-value">${ratedPower?.state || 'Unknown'} kW</span>
              </div>
            </div>

            <div class="info-section">
              <div class="section-title">
                <ha-icon icon="mdi:cog"></ha-icon>
                Firmware & Status
              </div>
              <div class="info-item">
                <span class="info-label">Software:</span>
                <span class="info-value">${softwareVersion?.state || 'Unknown'}</span>
              </div>
              <div class="info-item">
                <span class="info-label">Hardware:</span>
                <span class="info-value">${hardwareVersion?.state || 'Unknown'}</span>
              </div>
              <div class="info-item">
                <span class="info-label">Temperature:</span>
                <span class="info-value">${temp.toFixed(1)}°C</span>
              </div>
              <div class="info-item">
                <span class="info-label">Lock Status:</span>
                <span class="info-value">${lockStatus?.state === '1' ? 'Locked' : 'Unlocked'}</span>
              </div>
            </div>
          </div>

          ${this.config.show_diagnostic ? `
            <div class="diagnostic-section">
              <div class="info-section">
                <div class="section-title expandable" onclick="this.nextElementSibling.classList.toggle('collapsed')">
                  <ha-icon icon="mdi:chart-line-variant"></ha-icon>
                  Diagnostic Information
                  <ha-icon icon="mdi:chevron-down" style="margin-left: auto;"></ha-icon>
                </div>
                <div class="diagnostic-content">
                  <div class="voltage-readings">
                    <div class="voltage-item">
                      <div class="voltage-phase">Phase A</div>
                      <div class="voltage-value">${parseFloat(phaseAVoltage?.state || 0).toFixed(1)}V</div>
                    </div>
                    <div class="voltage-item">
                      <div class="voltage-phase">Phase B</div>
                      <div class="voltage-value">${parseFloat(phaseBVoltage?.state || 0).toFixed(1)}V</div>
                    </div>
                    <div class="voltage-item">
                      <div class="voltage-phase">Phase C</div>
                      <div class="voltage-value">${parseFloat(phaseCVoltage?.state || 0).toFixed(1)}V</div>
                    </div>
                  </div>
                  
                  <div class="status-indicators">
                    <div class="status-item">
                      <ha-icon class="status-icon ${errorCodeValue > 0 ? 'status-error' : 'status-good'}" 
                               icon="${errorCodeValue > 0 ? 'mdi:alert-circle' : 'mdi:check-circle'}"></ha-icon>
                      <div>
                        <div style="font-weight: 500;">Error Code</div>
                        <div style="font-size: 0.8em; opacity: 0.7;">${errorCodeValue}</div>
                      </div>
                    </div>
                    
                    <div class="status-item">
                      <ha-icon class="status-icon ${warningCodeValue > 0 ? 'status-warning' : 'status-good'}" 
                               icon="${warningCodeValue > 0 ? 'mdi:alert' : 'mdi:check-circle'}"></ha-icon>
                      <div>
                        <div style="font-weight: 500;">Warning Code</div>
                        <div style="font-size: 0.8em; opacity: 0.7;">${warningCodeValue}</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ` : ''}
        </div>
      </ha-card>
    `;
  }
}

customElements.define('huawei-charger-info-card', HuaweiChargerInfoCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'huawei-charger-info-card',
  name: 'Huawei Charger Info Card',
  description: 'A custom card to display device information and diagnostics'
});