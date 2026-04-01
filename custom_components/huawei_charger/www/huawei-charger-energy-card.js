class HuaweiChargerEnergyCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._lastEntityStates = {};
  }

  setConfig(config) {
    this.config = {
      show_cost: config?.show_cost ?? false,
      energy_cost: config?.energy_cost ?? 0.12, // per kWh
      currency: config?.currency ?? '€',
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

  _stateMap(hass = this._hass) {
    return hass?.states || {};
  }

  _renderSafely() {
    try {
      this.render();
    } catch (error) {
      console.error('Huawei charger energy card render failed:', error);
      if (!this.shadowRoot) {
        return;
      }
      this.shadowRoot.innerHTML = `
        <ha-card>
          <div class="card-content">
            <div class="error">
              <h3>Card temporarily unavailable</h3>
              <p>The Huawei Charger energy card hit a transient frontend state. Refresh the dashboard if this persists.</p>
            </div>
          </div>
        </ha-card>
      `;
    }
  }

  _candidateEntityIds(hass = this._hass) {
    const allEntityIds = Object.keys(this._stateMap(hass));
    const exactMatches = allEntityIds.filter((id) => id.includes('huawei_charger'));
    if (exactMatches.length > 0) {
      return exactMatches;
    }
    return allEntityIds.filter((id) => id.includes('charger') || id.includes('huawei'));
  }

  _trackedEntityIds(hass) {
    const tracked = new Set(
      this._candidateEntityIds(hass).filter(id =>
        (
          id.includes('session_energy') ||
          id.includes('session_duration') ||
          id.includes('total_energy') ||
          id.includes('rated_charging_power') ||
          id.includes('dynamic_power_limit')
        )
      )
    );

    [
      this.config.session_energy_entity,
      this.config.session_duration_entity,
      this.config.total_energy_entity,
      this.config.current_power_entity,
      this.config.dynamic_power_entity,
      this.config.rated_power_entity,
    ].forEach(entityId => {
      if (entityId && hass.states?.[entityId]) {
        tracked.add(entityId);
      }
    });

    return [...tracked];
  }

  _hasEntityStatesChanged(hass, oldHass) {
    if (!hass || !oldHass) return false;

    const trackedEntities = this._trackedEntityIds(hass);

    // Check if any relevant entity states changed by comparing with previous hass
    for (const entityId of trackedEntities) {
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

    // Auto-detect energy monitoring entities
    const huaweiEntities = this._candidateEntityIds();
    
    const sessionEnergyEntity = this._findEntityBySuffixes(
      huaweiEntities,
      ['session_energy'],
      this.config.session_energy_entity
    );
    const sessionDurationEntity = this._findEntityBySuffixes(
      huaweiEntities,
      ['session_duration'],
      this.config.session_duration_entity
    );
    const totalEnergyEntity = this._findEntityBySuffixes(
      huaweiEntities,
      ['total_energy_charged', 'total_energy'],
      this.config.total_energy_entity
    );
    const currentPowerEntity = this.config.current_power_entity
      ? this._findEntityBySuffixes(huaweiEntities, [], this.config.current_power_entity)
      : null;
    const dynamicLimitEntity = this._findEntityBySuffixes(
      huaweiEntities,
      ['dynamic_power_limit'],
      this.config.dynamic_power_entity
    );
    const ratedPowerEntity = this._findEntityBySuffixes(
      huaweiEntities,
      ['rated_charging_power', 'rated_power', 'max_power', 'fixed_max_power'],
      this.config.rated_power_entity
    );
    
    const hasAnyResolvedEntity = [
      sessionEnergyEntity,
      sessionDurationEntity,
      totalEnergyEntity,
      currentPowerEntity,
      dynamicLimitEntity,
      ratedPowerEntity,
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

    const safeParse = (value, fallback = 0) => {
      const parsed = parseFloat(value);
      return Number.isFinite(parsed) ? parsed : fallback;
    };

    const hasSessionEnergy = this._isEntityAvailable(sessionEnergyEntity);
    const hasSessionDuration = this._isEntityAvailable(sessionDurationEntity);
    const hasTotalEnergy = this._isEntityAvailable(totalEnergyEntity);
    const hasCurrentPower = this._isEntityAvailable(currentPowerEntity);

    if (!hasSessionEnergy && !hasSessionDuration && !hasTotalEnergy && !hasCurrentPower) {
      this.shadowRoot.innerHTML = `
        <ha-card>
          <div class="card-content">
            <div class="error">
              <h3>No compatible energy entities available</h3>
              <p>The card will render automatically when Huawei exposes power or energy data.</p>
            </div>
          </div>
        </ha-card>
      `;
      return;
    }

    const sessionEnergy = hasSessionEnergy ? safeParse(sessionEnergyEntity.state, 0) : 0;
    const sessionDuration = hasSessionDuration ? safeParse(sessionDurationEntity.state, 0) : 0;
    const totalEnergy = hasTotalEnergy ? safeParse(totalEnergyEntity.state, 0) : 0;
    const currentPower = hasCurrentPower ? safeParse(currentPowerEntity.state, 0) : 0;

    const configMax = safeParse(this.config?.max_session_energy, NaN);
    const dynamicMaxAttr = safeParse(dynamicLimitEntity?.attributes?.max, NaN);
    const ratedPower = safeParse(ratedPowerEntity?.state, NaN);
    const sessionCapacity = Number.isFinite(configMax) && configMax > 0 ? configMax : null;
    const powerCapacityCandidates = [dynamicMaxAttr, ratedPower, 7.4];
    const powerCapacity = powerCapacityCandidates.find(value => Number.isFinite(value) && value > 0) || 7.4;

    // Calculate session metrics
    const sessionCost = sessionEnergy * this.config.energy_cost;
    const averagePower = hasSessionEnergy && hasSessionDuration && sessionDuration > 0
      ? (sessionEnergy / (sessionDuration / 60))
      : 0;
    const sessionHours = Math.floor(sessionDuration / 60);
    const sessionMinutes = Math.floor(sessionDuration % 60);

    const remainingEnergy = sessionCapacity !== null
      ? Math.max(sessionCapacity - sessionEnergy, 0)
      : null;
    const estimatedTimeToFull = sessionCapacity !== null && currentPower > 0
      ? (remainingEnergy / currentPower) * 60
      : 0;
    const estHours = Math.floor(estimatedTimeToFull / 60);
    const estMinutes = Math.floor(estimatedTimeToFull % 60);

    const sessionProgress = sessionCapacity !== null && sessionCapacity > 0
      ? (sessionEnergy / sessionCapacity) * 100
      : 0;
    const powerUsagePercent = powerCapacity > 0 && currentPower > 0
      ? Math.min(Math.max((currentPower / powerCapacity) * 100, 0), 999)
      : 0;
    const energyItems = [];

    if (hasSessionEnergy) {
      energyItems.push(`
        <div class="energy-item">
          <ha-icon class="energy-icon" icon="mdi:battery-charging-outline"></ha-icon>
          <div class="energy-value">${sessionEnergy.toFixed(2)}</div>
          <div class="energy-label">Session kWh</div>
        </div>
      `);
    }

    if (hasSessionDuration) {
      energyItems.push(`
        <div class="energy-item">
          <ha-icon class="energy-icon" icon="mdi:clock-outline"></ha-icon>
          <div class="energy-value">${sessionHours}h ${sessionMinutes}m</div>
          <div class="energy-label">Duration</div>
        </div>
      `);
    }

    if (hasTotalEnergy) {
      energyItems.push(`
        <div class="energy-item">
          <ha-icon class="energy-icon" icon="mdi:sigma"></ha-icon>
          <div class="energy-value">${totalEnergy.toFixed(1)}</div>
          <div class="energy-label">Total kWh</div>
        </div>
      `);
    }

    if (hasSessionEnergy && hasSessionDuration) {
      energyItems.push(`
        <div class="energy-item">
          <ha-icon class="energy-icon" icon="mdi:speedometer"></ha-icon>
          <div class="energy-value">${averagePower.toFixed(1)}</div>
          <div class="energy-label">Avg Power</div>
        </div>
      `);
    } else if (hasCurrentPower) {
      energyItems.push(`
        <div class="energy-item">
          <ha-icon class="energy-icon" icon="mdi:flash"></ha-icon>
          <div class="energy-value">${currentPower.toFixed(1)}</div>
          <div class="energy-label">Current kW</div>
        </div>
      `);
    }

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
        .energy-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 12px;
          margin-bottom: 20px;
        }
        .energy-item {
          background: var(--secondary-background-color);
          border-radius: 12px;
          padding: 16px;
          text-align: center;
          transition: transform 0.2s ease;
        }
        .energy-item:hover {
          transform: translateY(-2px);
        }
        .energy-icon {
          --mdc-icon-size: 24px;
          color: var(--primary-color);
          margin-bottom: 8px;
        }
        .energy-value {
          font-size: 1.5em;
          font-weight: bold;
          color: var(--primary-text-color);
          margin-bottom: 4px;
        }
        .energy-label {
          font-size: 0.8em;
          opacity: 0.7;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }
        .session-details {
          background: linear-gradient(135deg, var(--primary-color) 20%, var(--secondary-background-color));
          border-radius: 12px;
          padding: 16px;
          margin-bottom: 16px;
        }
        .session-title {
          font-size: 1em;
          font-weight: 500;
          margin-bottom: 12px;
          display: flex;
          align-items: center;
        }
        .session-title ha-icon {
          margin-right: 8px;
          --mdc-icon-size: 18px;
        }
        .session-stats {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 12px;
        }
        .stat-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 8px 0;
          border-bottom: 1px solid var(--divider-color);
        }
        .stat-item:last-child {
          border-bottom: none;
        }
        .stat-label {
          font-size: 0.9em;
          opacity: 0.8;
        }
        .stat-value {
          font-weight: 500;
        }
        .power-trend {
          display: flex;
          align-items: center;
          justify-content: space-between;
          background: var(--secondary-background-color);
          border-radius: 8px;
          padding: 12px;
          margin-top: 16px;
        }
        .trend-item {
          text-align: center;
          flex: 1;
        }
        .trend-value {
          font-size: 1.2em;
          font-weight: bold;
          color: var(--primary-color);
        }
        .trend-label {
          font-size: 0.8em;
          opacity: 0.7;
          margin-top: 4px;
        }
        .error {
          color: var(--error-color);
          text-align: center;
          padding: 16px;
        }
        .cost-highlight {
          color: var(--accent-color);
          font-weight: bold;
        }
        .charging-indicator {
          display: inline-block;
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: #4CAF50;
          margin-left: 8px;
          animation: pulse 2s infinite;
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
      </style>
      
      <ha-card>
        <div class="card-content">
          <div class="card-header">
            <ha-icon icon="mdi:chart-line"></ha-icon>
            <h3 class="card-title">Energy Monitoring</h3>
            ${hasCurrentPower && currentPower > 0 ? '<span class="charging-indicator"></span>' : ''}
          </div>
          
          <div class="energy-grid">
            ${energyItems.join('')}
          </div>

          ${(hasCurrentPower || (this.config.show_cost && hasSessionEnergy) || (hasCurrentPower && estimatedTimeToFull > 0)) ? `
            <div class="session-details">
              <div class="session-title">
                <ha-icon icon="mdi:information-outline"></ha-icon>
                Current Session
              </div>
              <div class="session-stats">
                ${hasCurrentPower ? `
                  <div class="stat-item">
                    <span class="stat-label">Current Power:</span>
                    <span class="stat-value">${currentPower.toFixed(1)} kW</span>
                  </div>
                ` : ''}
                ${this.config.show_cost && hasSessionEnergy ? `
                  <div class="stat-item">
                    <span class="stat-label">Session Cost:</span>
                    <span class="stat-value cost-highlight">${this.config.currency}${sessionCost.toFixed(2)}</span>
                  </div>
                ` : ''}
                ${sessionCapacity !== null && hasCurrentPower && currentPower > 0 && estimatedTimeToFull > 0 ? `
                  <div class="stat-item">
                    <span class="stat-label">Est. Full Time:</span>
                    <span class="stat-value">${estHours}h ${estMinutes}m</span>
                  </div>
                ` : ''}
              </div>
            </div>
          ` : ''}

          ${(hasSessionEnergy || (hasSessionEnergy && hasSessionDuration) || hasCurrentPower) ? `
            <div class="power-trend">
              ${sessionCapacity !== null && hasSessionEnergy ? `
                <div class="trend-item">
                  <div class="trend-value">${sessionProgress.toFixed(0)}%</div>
                  <div class="trend-label">Battery Progress</div>
                </div>
              ` : ''}
              ${hasSessionEnergy && hasSessionDuration ? `
                <div class="trend-item">
                  <div class="trend-value">${averagePower.toFixed(1)}</div>
                  <div class="trend-label">Average Power (kW)</div>
                </div>
              ` : ''}
              ${hasCurrentPower ? `
                <div class="trend-item">
                  <div class="trend-value">${Math.round(powerUsagePercent)}%</div>
                  <div class="trend-label">Limit Usage</div>
                </div>
              ` : ''}
            </div>
          ` : ''}
        </div>
      </ha-card>
    `;
  }
}

if (!customElements.get('huawei-charger-energy-card')) {
  customElements.define('huawei-charger-energy-card', HuaweiChargerEnergyCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === 'huawei-charger-energy-card')) {
  window.customCards.push({
    type: 'huawei-charger-energy-card',
    name: 'Huawei Charger Energy Card',
    description: 'A custom card to monitor energy consumption and charging sessions'
  });
}
