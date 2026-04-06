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
        const dynamicEntity = this._findDynamicPowerEntity(hass);
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
        const dynamicEntity = this._findDynamicPowerEntity(hass);
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

  _trackedEntityIds(hass) {
    const tracked = new Set(
      Object.keys(hass.states).filter(id =>
        id.includes('huawei_charger') && (
          id.includes('dynamic_power_limit') ||
          id.includes('fixed_max_charging_power') ||
          id.includes('fixed_max_power') ||
          id.includes('device_status') ||
          id.includes('charge_store') ||
          id.includes('plugged_in') ||
          id.includes('plugged')
        )
      )
    );

    [
      this.config.dynamic_power_entity,
      this.config.fixed_power_entity,
      this.config.current_power_entity,
      this.config.device_status_entity,
      this.config.charge_store_entity,
      this.config.plugged_in_entity,
    ].forEach(entityId => {
      if (entityId && hass.states?.[entityId]) {
        tracked.add(entityId);
      }
    });

    return [...tracked];
  }

  _getHuaweiEntities(hass = this._hass) {
    return Object.keys(hass?.states || {}).filter((id) => id.includes('huawei_charger'));
  }

  _findDynamicPowerEntity(hass = this._hass) {
    return this._findEntityBySuffixes(
      this._getHuaweiEntities(hass),
      ['dynamic_power_limit'],
      this.config.dynamic_power_entity
    );
  }

  _findDynamicPowerEntityId(hass = this._hass) {
    if (this.config.dynamic_power_entity && hass?.states?.[this.config.dynamic_power_entity]) {
      return this.config.dynamic_power_entity;
    }

    return this._getHuaweiEntities(hass).find((id) =>
      id.endsWith('_dynamic_power_limit') || id.endsWith('.dynamic_power_limit')
    ) || null;
  }

  _deriveCableStatus(currentPowerEntity, deviceStatusEntity, chargeStoreEntity, pluggedInEntity) {
    const currentPower = parseFloat(currentPowerEntity?.state);
    const deviceStatusValue = this._normalizeStateValue(deviceStatusEntity?.state);
    const chargeStoreValue = this._normalizeStateValue(chargeStoreEntity?.state);
    const pluggedInValue = this._normalizeStateValue(pluggedInEntity?.state);
    const statusValue = deviceStatusValue || chargeStoreValue || pluggedInValue;
    const chargingStates = ['3', 'charging', 'active'];
    const readyStates = ['2', 'ready'];
    const connectedStates = ['1', 'connected', 'plugged', 'true'];

    if (
      (Number.isFinite(currentPower) && currentPower > 0.1) ||
      chargingStates.includes(deviceStatusValue) ||
      chargingStates.includes(chargeStoreValue) ||
      chargingStates.includes(pluggedInValue)
    ) {
      return {
        status: 'Charging',
        icon: 'mdi:battery-charging',
        color: 'charging'
      };
    }

    if (readyStates.includes(statusValue)) {
      return {
        status: 'Ready',
        icon: 'mdi:power-plug',
        color: 'ready'
      };
    }

    if (connectedStates.includes(statusValue)) {
      return {
        status: 'Connected',
        icon: 'mdi:power-plug',
        color: 'connected'
      };
    }

    return {
      status: 'Unknown',
      icon: 'mdi:help-circle',
      color: 'disconnected'
    };
  }

  _hasEntityStatesChanged(hass, oldHass) {
    if (!hass || !oldHass) return false;

    const trackedEntities = this._trackedEntityIds(hass);

    // Check if any relevant entity states changed by comparing with previous hass
    for (const entityId of trackedEntities) {
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
    const huaweiEntities = this._getHuaweiEntities();
    
    const dynamicEntity = this._findDynamicPowerEntity();
    const fixedEntity = this._findEntityBySuffixes(
      huaweiEntities,
      ['fixed_max_charging_power', 'fixed_max_power'],
      this.config.fixed_power_entity
    );
    const currentPowerEntity = this.config.current_power_entity
      ? this._findEntityBySuffixes(huaweiEntities, [], this.config.current_power_entity)
      : null;
    const deviceStatusEntity = this._findEntityBySuffixes(
      huaweiEntities,
      ['device_status'],
      this.config.device_status_entity
    );
    const chargeStoreEntity = this._findEntityBySuffixes(
      huaweiEntities,
      ['charge_store'],
      this.config.charge_store_entity
    );
    const pluggedInEntity = this._findEntityBySuffixes(
      huaweiEntities,
      ['plugged_in', 'plugged'],
      this.config.plugged_in_entity
    );
    const hasAnyResolvedEntity = [
      dynamicEntity,
      fixedEntity,
      currentPowerEntity,
      deviceStatusEntity,
      chargeStoreEntity,
      pluggedInEntity,
    ].some((entity) => Boolean(entity));

    if (huaweiEntities.length === 0 && !hasAnyResolvedEntity) {
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

    const hasDynamic = this._isEntityAvailable(dynamicEntity);
    const hasFixed = this._isEntityAvailable(fixedEntity);
    const hasCurrentPower = this._isEntityAvailable(currentPowerEntity);
    const hasDeviceStatus = this._isEntityAvailable(deviceStatusEntity);
    const hasChargeStore = this._isEntityAvailable(chargeStoreEntity);
    const hasPluggedState = this._isEntityAvailable(pluggedInEntity);

    if (!hasDynamic && !hasFixed && !hasCurrentPower && !hasDeviceStatus && !hasChargeStore && !hasPluggedState) {
      this.shadowRoot.innerHTML = `
        <ha-card>
          <div class="card-content">
            <div class="error">
              <h3>No compatible charger control entities available</h3>
              <p>The card will render controls automatically when Huawei exposes writable limit signals.</p>
            </div>
          </div>
        </ha-card>
      `;
      return;
    }

    const toNumber = (value, fallback) => {
      const parsed = parseFloat(value);
      return Number.isFinite(parsed) ? parsed : fallback;
    };

    // Use pending value if we have one, otherwise use actual entity state
    const dynamicValue = hasDynamic
      ? (this._pendingValue !== null ? this._pendingValue : toNumber(dynamicEntity.state, 0))
      : null;
    const fixedValue = hasFixed ? toNumber(fixedEntity.state, 0) : null;
    const cableState = (hasCurrentPower || hasDeviceStatus || hasChargeStore || hasPluggedState)
      ? this._deriveCableStatus(currentPowerEntity, deviceStatusEntity, chargeStoreEntity, pluggedInEntity)
      : null;
    const minValue = hasDynamic ? toNumber(dynamicEntity.attributes.min, 1.6) : null;
    const maxValue = hasDynamic ? toNumber(dynamicEntity.attributes.max, 7.4) : null;
    const step = hasDynamic ? toNumber(dynamicEntity.attributes.step, 0.1) : null;

    // Preset power levels
    const presets = hasDynamic ? [
      { label: 'Eco', value: Math.min(2.0, maxValue), icon: 'mdi:leaf' },
      { label: 'Normal', value: Math.min(3.7, maxValue), icon: 'mdi:flash' },
      { label: 'Fast', value: Math.min(7.4, maxValue), icon: 'mdi:lightning-bolt' },
      { label: 'Max', value: maxValue, icon: 'mdi:speedometer' }
    ] : [];

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
          
          ${hasDynamic ? `
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
          ` : `
            <div class="current-settings" style="margin-top: 0;">
              <div class="setting-row">
                <span class="setting-label">Dynamic Limit:</span>
                <span class="setting-value">Not exposed by Huawei</span>
              </div>
            </div>
          `}

          <div class="current-settings">
            ${hasDynamic ? `
              <div class="setting-row">
                <span class="setting-label">Dynamic Limit:</span>
                <span class="setting-value">${dynamicValue.toFixed(1)} kW</span>
              </div>
            ` : ''}
            ${hasFixed ? `
              <div class="setting-row">
                <span class="setting-label">Fixed Max Power:</span>
                <span class="setting-value">${fixedValue.toFixed(1)} kW</span>
              </div>
            ` : ''}
            ${cableState ? `
              <div class="setting-row">
                <span class="setting-label">Status:</span>
                <span class="setting-value cable-status ${cableState.color}">
                  <ha-icon icon="${cableState.icon}"></ha-icon>
                  ${cableState.status}
                </span>
              </div>
            ` : ''}
          </div>
        </div>
      </ha-card>
    `;

    this.setupEventListeners();
  }

  setupEventListeners() {
    const slider = this.shadowRoot.getElementById('dynamic-slider');
    const presetButtons = this.shadowRoot.querySelectorAll('.preset-button');

    // Slider input event
    slider?.addEventListener('input', (e) => {
      const value = parseFloat(e.target.value);
      this._updateDisplay(value);
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
    if (!Number.isFinite(value)) {
      return;
    }
    this._pendingValue = value;
    this._ignoreUpdatesUntil = Date.now() + 15000;
    this._applyPendingValue(value);
    this.setPowerLimit(value);
  }

  _applyPendingValue(value) {
    const slider = this.shadowRoot?.getElementById('dynamic-slider');
    if (slider && slider.value !== String(value)) {
      slider.value = value;
    }
    this._updateDisplay(value);
  }

  _updateDisplay(value) {
    const display = this.shadowRoot?.getElementById('dynamic-display');
    if (display) {
      display.textContent = value.toFixed(1);
    }
    this.updatePresetButtons(value);
  }

  async setPowerLimit(value) {
    if (!this._hass || this._isUpdating) return;
    
    // Find the dynamic power limit entity
    const dynamicEntityId = this._findDynamicPowerEntityId();
    
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

if (!customElements.get('huawei-charger-control-card')) {
  customElements.define('huawei-charger-control-card', HuaweiChargerControlCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === 'huawei-charger-control-card')) {
  window.customCards.push({
    type: 'huawei-charger-control-card',
    name: 'Huawei Charger Control Card',
    description: 'A custom card to control Huawei charger power limits with presets'
  });
}
