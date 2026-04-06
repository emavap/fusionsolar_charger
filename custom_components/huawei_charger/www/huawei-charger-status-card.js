class HuaweiChargerStatusCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._lastEntityStates = {};
    this._lastChargingActivityAt = 0;
    this._chargingActivityTimer = null;
    this._chargingActivityWindowMs = 15 * 60 * 1000;
  }

  setConfig(config) {
    // Allow card to work without entity specification - will auto-detect
    this.config = config || {};
  }

  set hass(hass) {
    const oldHass = this._hass;
    this._hass = hass;

    if (oldHass) {
      this._recordChargingActivity(hass, oldHass);
    }
    
    // Always render on first load
    if (!oldHass) {
      this.render();
      return;
    }
    
    // Check if relevant entity states have changed
    if (this._hasEntityStatesChanged(hass, oldHass)) {
      this.render();
    }
  }

  getCardSize() {
    return 3;
  }

  disconnectedCallback() {
    if (this._chargingActivityTimer) {
      window.clearTimeout(this._chargingActivityTimer);
      this._chargingActivityTimer = null;
    }
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

  _parseNumericState(entity) {
    const parsed = parseFloat(entity?.state);
    return Number.isFinite(parsed) ? parsed : null;
  }

  _energyEntityIds(hass = this._hass) {
    const tracked = new Set(
      Object.keys(hass?.states || {}).filter(id =>
        id.includes('huawei_charger') && (
          id.includes('session_energy') ||
          id.includes('total_energy_charged') ||
          id.includes('total_energy')
        )
      )
    );

    if (this.config.session_energy_entity && hass?.states?.[this.config.session_energy_entity]) {
      tracked.add(this.config.session_energy_entity);
    }

    return [...tracked];
  }

  _scheduleChargingActivityExpiry() {
    if (this._chargingActivityTimer) {
      window.clearTimeout(this._chargingActivityTimer);
      this._chargingActivityTimer = null;
    }

    if (!this._lastChargingActivityAt) {
      return;
    }

    const remainingMs = this._chargingActivityWindowMs - (Date.now() - this._lastChargingActivityAt);
    if (remainingMs <= 0) {
      this._lastChargingActivityAt = 0;
      this.render();
      return;
    }

    this._chargingActivityTimer = window.setTimeout(() => {
      this._chargingActivityTimer = null;
      this.render();
    }, remainingMs + 250);
  }

  _recordChargingActivity(hass, oldHass) {
    for (const entityId of this._energyEntityIds(hass)) {
      const currentValue = this._parseNumericState(hass.states?.[entityId]);
      const previousValue = this._parseNumericState(oldHass.states?.[entityId]);

      if (currentValue === null || previousValue === null) {
        continue;
      }

      if (currentValue > previousValue + 0.001) {
        this._lastChargingActivityAt = Date.now();
        this._scheduleChargingActivityExpiry();
        return;
      }
    }
  }

  _hasRecentChargingActivity() {
    return this._lastChargingActivityAt > 0 &&
      (Date.now() - this._lastChargingActivityAt) <= this._chargingActivityWindowMs;
  }

  _trackedEntityIds(hass) {
    const tracked = new Set(
      Object.keys(hass.states).filter(id =>
        id.includes('huawei_charger') && (
          id.includes('session_energy') ||
          id.includes('total_energy_charged') ||
          id.includes('total_energy') ||
          id.includes('device_status') ||
          id.includes('charge_store') ||
          id.includes('plugged_in') ||
          id.includes('plugged') ||
          id.includes('dynamic_power_limit')
        )
      )
    );

    [
      this.config.current_power_entity,
      this.config.session_energy_entity,
      this.config.device_status_entity,
      this.config.charge_store_entity,
      this.config.plugged_in_entity,
      this.config.dynamic_power_entity,
    ].forEach(entityId => {
      if (entityId && hass.states?.[entityId]) {
        tracked.add(entityId);
      }
    });

    return [...tracked];
  }

  _connectedState(value) {
    const normalized = this._normalizeStateValue(value);
    if (['1', 'connected', 'plugged', 'plugged_in', 'true', 'on'].includes(normalized)) {
      return true;
    }
    if (['0', 'false', 'off', 'disconnected', 'unplugged', 'not_connected', 'idle', 'none'].includes(normalized)) {
      return false;
    }
    return null;
  }

  _deriveConnectionState(deviceStatus, chargeStore, pluggedIn, power, chargingActivityDetected) {
    const deviceStatusState = this._normalizeStateValue(deviceStatus?.state);
    const chargeStoreState = this._normalizeStateValue(chargeStore?.state);
    const pluggedState = this._normalizeStateValue(pluggedIn?.state);
    const pluggedConnectionState = this._connectedState(pluggedState);
    const deviceConnectionState = this._connectedState(deviceStatusState);
    const chargeStoreConnectionState = this._connectedState(chargeStoreState);
    const chargingStates = ['3', 'charging', 'active'];
    const readyStates = ['2', 'ready'];

    if (
      chargingActivityDetected ||
      chargingStates.includes(deviceStatusState) ||
      chargingStates.includes(chargeStoreState) ||
      chargingStates.includes(pluggedState) ||
      power > 0.1
    ) {
      return {
        isCharging: true,
        statusText: 'Charging',
        connectionText: 'Connected',
        statusColor: '#4CAF50',
        statusIcon: 'mdi:battery-charging'
      };
    }

    if (pluggedConnectionState === false) {
      return {
        isCharging: false,
        statusText: 'Idle',
        connectionText: 'Disconnected',
        statusColor: '#9E9E9E',
        statusIcon: 'mdi:ev-station'
      };
    }

    if (
      pluggedConnectionState === true &&
      (readyStates.includes(deviceStatusState) || readyStates.includes(chargeStoreState))
    ) {
      return {
        isCharging: false,
        statusText: 'Ready',
        connectionText: 'Connected',
        statusColor: '#FF9800',
        statusIcon: 'mdi:power-plug'
      };
    }

    if (
      pluggedConnectionState === true ||
      deviceConnectionState === true ||
      chargeStoreConnectionState === true
    ) {
      return {
        isCharging: false,
        statusText: 'Connected',
        connectionText: 'Connected',
        statusColor: '#2196F3',
        statusIcon: 'mdi:power-plug'
      };
    }

    return {
      isCharging: false,
      statusText: 'Idle',
      connectionText: 'Idle',
      statusColor: '#9E9E9E',
      statusIcon: 'mdi:ev-station'
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
      
      // Compare state values (these are the main values we display)
      if (currentState.state !== previousState.state) {
        return true;
      }
    }
    
    return false;
  }

  render() {
    if (!this._hass) return;

    // Auto-detect available entities by searching for Huawei Charger entities
    const huaweiEntities = Object.keys(this._hass.states).filter(id => 
      id.includes('huawei_charger')
    );
    
    const currentPower = this.config.current_power_entity
      ? this._findEntityBySuffixes(huaweiEntities, [], this.config.current_power_entity)
      : null;
    const sessionEnergy = this._findEntityBySuffixes(
      huaweiEntities,
      ['session_energy', 'total_energy_charged', 'total_energy'],
      this.config.session_energy_entity
    );
    const deviceStatus = this._findEntityBySuffixes(
      huaweiEntities,
      ['device_status'],
      this.config.device_status_entity
    );
    const chargeStore = this._findEntityBySuffixes(
      huaweiEntities,
      ['charge_store'],
      this.config.charge_store_entity
    );
    const pluggedIn = this._findEntityBySuffixes(
      huaweiEntities,
      ['plugged_in', 'plugged'],
      this.config.plugged_in_entity
    );
    const dynamicPowerLimit = this._findEntityBySuffixes(
      huaweiEntities,
      ['dynamic_power_limit', 'fixed_max_charging_power', 'fixed_max_power'],
      this.config.dynamic_power_entity
    );
    const hasAnyResolvedEntity = [
      currentPower,
      sessionEnergy,
      deviceStatus,
      chargeStore,
      pluggedIn,
      dynamicPowerLimit,
    ].some((entity) => Boolean(entity));
    
    // If no Huawei entities found, show helpful message with debugging info
    if (huaweiEntities.length === 0 && !hasAnyResolvedEntity) {
      // Show all entities for debugging
      const allEntities = Object.keys(this._hass.states).filter(id => 
        id.includes('charger') || id.includes('huawei')
      );
      
      this.shadowRoot.innerHTML = `
        <ha-card>
          <div class="card-content">
            <div class="error">
              <h3>No Huawei Charger entities found</h3>
              <p>Make sure the Huawei Charger integration is installed and configured.</p>
              <p>Check Settings → Devices & Services → Integrations</p>
              ${allEntities.length > 0 ? `
                <p><strong>Found these charger-related entities:</strong></p>
                <ul style="text-align: left; margin: 8px 0;">
                  ${allEntities.slice(0, 10).map(id => `<li><code>${id}</code></li>`).join('')}
                </ul>
              ` : '<p><em>No charger-related entities found at all.</em></p>'}
            </div>
          </div>
        </ha-card>
      `;
      return;
    }

    const hasCurrentPower = this._isEntityAvailable(currentPower);
    const hasSessionEnergy = this._isEntityAvailable(sessionEnergy);
    const hasPowerLimit = this._isEntityAvailable(dynamicPowerLimit);
    const hasDeviceStatus = this._isEntityAvailable(deviceStatus);
    const hasChargeStore = this._isEntityAvailable(chargeStore);
    const hasPluggedState = this._isEntityAvailable(pluggedIn);

    if (!hasCurrentPower && !hasSessionEnergy && !hasPowerLimit && !hasDeviceStatus && !hasChargeStore && !hasPluggedState) {
      this.shadowRoot.innerHTML = `
        <ha-card>
          <div class="card-content">
            <div class="error">
              <h3>No compatible charger status entities available</h3>
              <p>The card will render automatically when Huawei exposes charger status, energy, or limit data.</p>
            </div>
          </div>
        </ha-card>
      `;
      return;
    }

    const power = hasCurrentPower ? (parseFloat(currentPower.state) || 0) : null;
    const rawPowerLimit = hasPowerLimit ? parseFloat(dynamicPowerLimit.state) : NaN;
    const powerLimit = Number.isFinite(rawPowerLimit) && rawPowerLimit > 0 ? rawPowerLimit : null;
    const chargingActivityDetected = this._hasRecentChargingActivity();
    const connection = this._deriveConnectionState(
      deviceStatus,
      chargeStore,
      pluggedIn,
      power ?? 0,
      chargingActivityDetected
    );
    const isCharging = connection.isCharging;
    const statusText = connection.statusText;
    const statusColor = connection.statusColor;
    const statusIcon = connection.statusIcon;

    const safeLimit = powerLimit && powerLimit > 0 ? powerLimit : null;
    const powerPercent = safeLimit && power !== null
      ? Math.min(Math.max((power / safeLimit) * 100, 0), 100)
      : 0;
    const energyLabel = sessionEnergy?.entity_id?.includes('total_energy') ? 'Total Energy' : 'Energy';
    const infoItems = [];

    if (hasSessionEnergy) {
      infoItems.push(`
        <div class="info-item">
          <div class="info-label">${energyLabel}</div>
          <div class="info-value">${sessionEnergy.state} kWh</div>
        </div>
      `);
    }

    if (powerLimit !== null) {
      infoItems.push(`
        <div class="info-item">
          <div class="info-label">Limit</div>
          <div class="info-value">${powerLimit.toFixed(1)} kW</div>
        </div>
      `);
    }

    if (hasCurrentPower || hasDeviceStatus || hasChargeStore || hasPluggedState || chargingActivityDetected) {
      infoItems.push(`
        <div class="info-item">
          <div class="info-label">Status</div>
          <div class="info-value">${statusText}</div>
        </div>
      `);
    }

    this.shadowRoot.innerHTML = `
      <style>
        .card-content {
          padding: 16px;
        }
        .charger-header {
          display: flex;
          align-items: center;
          margin-bottom: 16px;
        }
        .charger-icon {
          width: 48px;
          height: 48px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          margin-right: 16px;
          transition: all 0.3s ease;
        }
        .charger-icon ha-icon {
          --mdc-icon-size: 24px;
          color: white;
        }
        .charger-info h2 {
          margin: 0;
          font-size: 1.2em;
          font-weight: 500;
        }
        .charger-status {
          margin: 0;
          font-size: 0.9em;
          opacity: 0.7;
        }
        .power-display {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin: 16px 0;
          padding: 12px;
          background: var(--secondary-background-color);
          border-radius: 8px;
        }
        .power-current {
          font-size: 2em;
          font-weight: bold;
          color: ${statusColor};
        }
        .power-unit {
          font-size: 0.8em;
          opacity: 0.7;
        }
        .power-limit {
          font-size: 0.9em;
          opacity: 0.7;
        }
        .power-bar {
          width: 100%;
          height: 8px;
          background: var(--divider-color);
          border-radius: 4px;
          overflow: hidden;
          margin: 8px 0;
        }
        .power-fill {
          height: 100%;
          background: linear-gradient(90deg, ${statusColor}, ${statusColor}aa);
          width: ${powerPercent}%;
          transition: width 0.3s ease;
        }
        .session-info {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 12px;
          margin-top: 16px;
        }
        .info-item {
          text-align: center;
          padding: 8px;
          background: var(--secondary-background-color);
          border-radius: 6px;
        }
        .info-label {
          font-size: 0.8em;
          opacity: 0.7;
          margin-bottom: 4px;
        }
        .info-value {
          font-weight: 500;
        }
        .error {
          color: var(--error-color);
          text-align: center;
          padding: 16px;
        }
        @keyframes charging-pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.7; }
        }
        .charging .charger-icon {
          animation: charging-pulse 2s infinite;
        }
      </style>
      
      <ha-card>
        <div class="card-content">
          <div class="charger-header">
            <div class="charger-icon ${isCharging ? 'charging' : ''}" style="background-color: ${statusColor}">
              <ha-icon icon="${statusIcon}"></ha-icon>
            </div>
            <div class="charger-info">
              <h2>Huawei Charger</h2>
              <p class="charger-status">${statusText}</p>
            </div>
          </div>
          
          ${(hasCurrentPower || hasPowerLimit) ? `
            <div class="power-display">
              ${hasCurrentPower ? `
                <div>
                  <span class="power-current">${power.toFixed(1)}</span>
                  <span class="power-unit">kW</span>
                </div>
              ` : '<div><span class="power-current">-</span><span class="power-unit">kW</span></div>'}
              ${hasPowerLimit ? `
                <div class="power-limit">
                  Limit: ${powerLimit.toFixed(1)}kW
                </div>
              ` : ''}
            </div>
          ` : ''}
          
          ${safeLimit && power !== null ? `
            <div class="power-bar">
              <div class="power-fill"></div>
            </div>
          ` : ''}
          
          ${infoItems.length > 0 ? `
            <div class="session-info">
              ${infoItems.join('')}
            </div>
          ` : ''}
        </div>
      </ha-card>
    `;
  }
}

if (!customElements.get('huawei-charger-status-card')) {
  customElements.define('huawei-charger-status-card', HuaweiChargerStatusCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === 'huawei-charger-status-card')) {
  window.customCards.push({
    type: 'huawei-charger-status-card',
    name: 'Huawei Charger Status Card',
    description: 'A custom card to display Huawei charger status and power information'
  });
}
