class HuaweiChargerControlCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._lastEntityStates = {};
    this._isUpdating = false;
    this._pendingValue = null;
    this._ignoreUpdatesUntil = null;
  }

  setConfig(config) {
    this.config = config || {};
  }

  set hass(hass) {
    const oldHass = this._hass;
    this._hass = hass;
    
    // Always render on first load
    if (!oldHass) {
      this.render();
      return;
    }
    
    // Skip updates if we're in the ignore period after user input
    if (this._ignoreUpdatesUntil && Date.now() < this._ignoreUpdatesUntil) {
      // But still check if the value has changed to what we expect
      if (this._pendingValue !== null) {
        const huaweiEntities = Object.keys(hass.states).filter(id => 
          id.includes('huawei_charger') && id.includes('dynamic_power_limit')
        );
        const dynamicEntity = huaweiEntities.length > 0 ? hass.states[huaweiEntities[0]] : null;
        const currentValue = parseFloat(dynamicEntity?.state) || 0;
        
        if (Math.abs(currentValue - this._pendingValue) < 0.1) {
          // Value matches - clear optimistic state and allow normal updates
          this._pendingValue = null;
          this._ignoreUpdatesUntil = null;
          this._isUpdating = false;
          this.render();
          return;
        }
      }
      return;
    }
    
    // Check if relevant entity states have changed
    if (this._hasEntityStatesChanged(hass, oldHass)) {
      // Clear pending value if the real update matches what we expected
      if (this._pendingValue !== null) {
        const huaweiEntities = Object.keys(hass.states).filter(id => 
          id.includes('huawei_charger') && id.includes('dynamic_power_limit')
        );
        const dynamicEntity = huaweiEntities.length > 0 ? hass.states[huaweiEntities[0]] : null;
        const currentValue = parseFloat(dynamicEntity?.state) || 0;
        
        if (Math.abs(currentValue - this._pendingValue) < 0.1) {
          // Value matches what we expected - clear optimistic state immediately
          this._pendingValue = null;
          this._ignoreUpdatesUntil = null;
          this._isUpdating = false;
        }
      }
      
      this.render();
    }
  }

  getCardSize() {
    return 4;
  }

  _hasEntityStatesChanged(hass, oldHass) {
    if (!hass || !oldHass) return false;
    
    // Get current power control entities
    const huaweiEntities = Object.keys(hass.states).filter(id => 
      id.includes('huawei_charger') && (
        id.includes('dynamic_power_limit') || 
        id.includes('fixed_max_charging_power') || 
        id.includes('fixed_max_power') ||
        id.includes('plugged_in')
      )
    );
    
    // Check if any relevant entity states changed by comparing with previous hass
    for (const entityId of huaweiEntities) {
      const currentState = hass.states[entityId];
      const previousState = oldHass.states[entityId];
      
      if (!currentState && !previousState) continue; // Both don't exist
      if (!currentState || !previousState) return true; // One exists, one doesn't
      
      // Compare state values
      if (currentState.state !== previousState.state) {
        return true;
      }
      
      // Compare key attributes that affect the display
      const currentAttrs = currentState.attributes;
      const previousAttrs = previousState.attributes;
      
      if (currentAttrs.min !== previousAttrs.min ||
          currentAttrs.max !== previousAttrs.max ||
          currentAttrs.step !== previousAttrs.step) {
        return true;
      }
    }
    
    return false;
  }

  render() {
    if (!this._hass) return;

    // Auto-detect power control entities
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
    
    const dynamicEntity = findEntity(['dynamic_power_limit']) || 
                         this._hass.states[this.config.dynamic_power_entity];
    const fixedEntity = findEntity(['fixed_max_charging_power', 'fixed_max_power']) || 
                       this._hass.states[this.config.fixed_power_entity];
    const pluggedInEntity = findEntity(['plugged_in']) || 
                           this._hass.states[this.config.plugged_in_entity];
    
    // If no power control entities found, show helpful message
    if (!dynamicEntity) {
      this.shadowRoot.innerHTML = `
        <ha-card>
          <div class="card-content">
            <div class="error">
              <h3>No power control entities found</h3>
              <p>Available Huawei Charger entities:</p>
              <ul style="text-align: left; margin: 8px 0;">
                ${huaweiEntities.slice(0, 10).map(id => `<li><code>${id}</code></li>`).join('')}
                ${huaweiEntities.length > 10 ? `<li>... and ${huaweiEntities.length - 10} more</li>` : ''}
              </ul>
              <p>Make sure the integration includes number entities for power control.</p>
            </div>
          </div>
        </ha-card>
      `;
      return;
    }

    // Use pending value if we have one, otherwise use actual entity state
    const dynamicValue = this._pendingValue !== null ? this._pendingValue : (parseFloat(dynamicEntity.state) || 0);
    const fixedValue = parseFloat(fixedEntity?.state) || 0;
    const pluggedInValue = pluggedInEntity?.state;
    
    // Interpret plugged-in status values
    let cableStatus = 'Disconnected';
    let cableIcon = 'mdi:power-plug-off';
    let cableColor = 'disconnected';
    
    if (pluggedInValue === '1') {
      cableStatus = 'Connected';
      cableIcon = 'mdi:power-plug';
      cableColor = 'connected';
    } else if (pluggedInValue === '3') {
      cableStatus = 'Charging';
      cableIcon = 'mdi:battery-charging';
      cableColor = 'charging';
    } else if (pluggedInValue === '2') {
      cableStatus = 'Ready';
      cableIcon = 'mdi:power-plug';
      cableColor = 'ready';
    }
    const minValue = dynamicEntity.attributes.min || 1.6;
    const maxValue = dynamicEntity.attributes.max || 7.4;
    const step = dynamicEntity.attributes.step || 0.1;

    // Preset power levels
    const presets = [
      { label: 'Eco', value: Math.min(2.0, maxValue), icon: 'mdi:leaf' },
      { label: 'Normal', value: Math.min(3.7, maxValue), icon: 'mdi:flash' },
      { label: 'Fast', value: Math.min(7.4, maxValue), icon: 'mdi:lightning-bolt' },
      { label: 'Max', value: maxValue, icon: 'mdi:speedometer' }
    ];

    this.shadowRoot.innerHTML = `
      <style>
        .card-content {
          padding: 16px;
        }
        .card-header {
          display: flex;
          align-items: center;
          margin-bottom: 20px;
        }
        .card-header ha-icon {
          margin-right: 8px;
          --mdc-icon-size: 20px;
        }
        .card-title {
          font-size: 1.1em;
          font-weight: 500;
          margin: 0;
        }
        .power-section {
          margin-bottom: 24px;
        }
        .section-title {
          font-size: 0.9em;
          font-weight: 500;
          margin-bottom: 12px;
          color: var(--primary-text-color);
          opacity: 0.8;
        }
        .power-slider-container {
          display: flex;
          align-items: center;
          gap: 12px;
          margin: 16px 0;
        }
        .power-input {
          flex: 1;
          height: 40px;
        }
        .power-display {
          min-width: 60px;
          text-align: center;
          font-weight: 500;
          font-size: 1.1em;
          color: var(--primary-color);
        }
        .power-unit {
          font-size: 0.8em;
          opacity: 0.7;
        }
        .preset-buttons {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 8px;
          margin-top: 16px;
        }
        .preset-button {
          display: flex;
          flex-direction: column;
          align-items: center;
          padding: 12px 8px;
          border: 1px solid var(--divider-color);
          border-radius: 8px;
          background: var(--card-background-color);
          cursor: pointer;
          transition: all 0.2s ease;
          text-align: center;
        }
        .preset-button:hover {
          background: var(--secondary-background-color);
          border-color: var(--primary-color);
        }
        .preset-button.active {
          background: var(--primary-color);
          color: var(--text-primary-color);
          border-color: var(--primary-color);
        }
        .preset-icon {
          --mdc-icon-size: 20px;
          margin-bottom: 4px;
        }
        .preset-label {
          font-size: 0.8em;
          font-weight: 500;
        }
        .preset-value {
          font-size: 0.7em;
          opacity: 0.8;
        }
        .current-settings {
          background: var(--secondary-background-color);
          border-radius: 8px;
          padding: 12px;
          margin-top: 16px;
        }
        .setting-row {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin: 4px 0;
        }
        .setting-label {
          font-size: 0.9em;
          opacity: 0.8;
        }
        .setting-value {
          font-weight: 500;
        }
        .error {
          color: var(--error-color);
          text-align: center;
          padding: 16px;
        }
        .slider-labels {
          display: flex;
          justify-content: space-between;
          font-size: 0.8em;
          opacity: 0.6;
          margin-top: 4px;
        }
        .updating-indicator {
          margin-left: 8px;
          animation: spin 1s linear infinite;
          font-size: 0.9em;
          color: var(--primary-color);
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        .preset-button.disabled {
          opacity: 0.5;
          pointer-events: none;
        }
        input[disabled] {
          opacity: 0.6;
        }
        .cable-status {
          display: flex;
          align-items: center;
          gap: 4px;
        }
        .cable-status ha-icon {
          --mdc-icon-size: 16px;
        }
        .cable-status.connected {
          color: #2196F3;
        }
        .cable-status.ready {
          color: #FF9800;
        }
        .cable-status.charging {
          color: #4CAF50;
        }
        .cable-status.disconnected {
          color: #F44336;
        }
      </style>
      
      <ha-card>
        <div class="card-content">
          <div class="card-header">
            <ha-icon icon="mdi:tune"></ha-icon>
            <h3 class="card-title">Power Control</h3>
          </div>
          
          <div class="power-section">
            <div class="section-title">Dynamic Power Limit</div>
            <div class="power-slider-container">
              <input 
                type="range" 
                class="power-input" 
                min="${minValue}" 
                max="${maxValue}" 
                step="${step}" 
                value="${dynamicValue}"
                id="dynamic-slider"
                ${this._isUpdating ? 'disabled' : ''}
              >
              <div class="power-display">
                <span id="dynamic-display">${dynamicValue.toFixed(1)}</span>
                <span class="power-unit">kW</span>
                ${this._isUpdating ? '<span class="updating-indicator">⟳</span>' : ''}
              </div>
            </div>
            <div class="slider-labels">
              <span>${minValue}kW</span>
              <span>${maxValue}kW</span>
            </div>
          </div>

          <div class="preset-buttons">
            ${presets.map(preset => `
              <div class="preset-button ${Math.abs(dynamicValue - preset.value) < 0.1 ? 'active' : ''} ${this._isUpdating ? 'disabled' : ''}" 
                   data-value="${preset.value}">
                <ha-icon class="preset-icon" icon="${preset.icon}"></ha-icon>
                <div class="preset-label">${preset.label}</div>
                <div class="preset-value">${preset.value}kW</div>
              </div>
            `).join('')}
          </div>

          <div class="current-settings">
            <div class="setting-row">
              <span class="setting-label">Dynamic Limit:</span>
              <span class="setting-value">${dynamicValue.toFixed(1)} kW</span>
            </div>
            ${fixedEntity ? `
              <div class="setting-row">
                <span class="setting-label">Fixed Max Power:</span>
                <span class="setting-value">${fixedValue.toFixed(1)} kW</span>
              </div>
            ` : ''}
            <div class="setting-row">
              <span class="setting-label">Cable Status:</span>
              <span class="setting-value cable-status ${cableColor}">
                <ha-icon icon="${cableIcon}"></ha-icon>
                ${cableStatus}
              </span>
            </div>
          </div>
        </div>
      </ha-card>
    `;

    this.setupEventListeners();
  }

  setupEventListeners() {
    const slider = this.shadowRoot.getElementById('dynamic-slider');
    const display = this.shadowRoot.getElementById('dynamic-display');
    const presetButtons = this.shadowRoot.querySelectorAll('.preset-button');

    // Slider input event
    slider?.addEventListener('input', (e) => {
      const value = parseFloat(e.target.value);
      display.textContent = value.toFixed(1);
      this.updatePresetButtons(value);
    });

    // Slider change event (when user releases)
    slider?.addEventListener('change', (e) => {
      const value = parseFloat(e.target.value);
      this._setPowerLimitOptimistic(value);
    });

    // Preset button clicks
    presetButtons.forEach(button => {
      button.addEventListener('click', () => {
        if (this._isUpdating || button.classList.contains('disabled')) return;
        
        const value = parseFloat(button.dataset.value);
        this._setPowerLimitOptimistic(value);
      });
    });
  }

  updatePresetButtons(currentValue) {
    const buttons = this.shadowRoot.querySelectorAll('.preset-button');
    buttons.forEach(button => {
      const buttonValue = parseFloat(button.dataset.value);
      button.classList.toggle('active', Math.abs(currentValue - buttonValue) < 0.1);
    });
  }

  _setPowerLimitOptimistic(value) {
    // Set the pending value and ignore updates for a period
    this._pendingValue = value;
    this._ignoreUpdatesUntil = Date.now() + 15000; // 15 seconds
    
    // Update UI immediately
    this.render();
    
    // Actually set the power limit
    this.setPowerLimit(value);
  }

  async setPowerLimit(value) {
    if (!this._hass || this._isUpdating) return;
    
    // Find the dynamic power limit entity
    const huaweiEntities = Object.keys(this._hass.states).filter(id => 
      id.includes('huawei_charger')
    );
    const dynamicEntityId = huaweiEntities.find(id => id.includes('dynamic_power_limit')) || 
                           this.config.dynamic_power_entity;
    
    if (!dynamicEntityId) return;
    
    // Set updating state
    this._isUpdating = true;
    this.render();
    
    try {
      await this._hass.callService('number', 'set_value', {
        entity_id: dynamicEntityId,
        value: value
      });
      
      // Wait for the coordinator delay (as mentioned in CLAUDE.md)
      // Plus extra time for entity state to update
      setTimeout(() => {
        this._isUpdating = false;
        // Don't force re-render here, let the normal update cycle handle it
        // The pending value and ignore period will handle the transition
      }, 12000); // 12 seconds to account for 10s delay + propagation
      
    } catch (error) {
      console.error('Failed to set power limit:', error);
      this._isUpdating = false;
      // Clear pending value on error
      this._pendingValue = null;
      this._ignoreUpdatesUntil = null;
      this.render();
    }
  }
}

customElements.define('huawei-charger-control-card', HuaweiChargerControlCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'huawei-charger-control-card',
  name: 'Huawei Charger Control Card',
  description: 'A custom card to control Huawei charger power limits with presets'
});