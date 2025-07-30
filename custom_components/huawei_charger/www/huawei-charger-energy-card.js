class HuaweiChargerEnergyCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._lastEntityStates = {};
  }

  setConfig(config) {
    this.config = {
      show_cost: config?.show_cost || false,
      energy_cost: config?.energy_cost || 0.12, // per kWh
      currency: config?.currency || '€',
      ...config
    };
  }

  set hass(hass) {
    const oldHass = this._hass;
    this._hass = hass;
    
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
    return 4;
  }

  _hasEntityStatesChanged(hass, oldHass) {
    if (!hass || !oldHass) return false;
    
    // Get current energy monitoring entities
    const huaweiEntities = Object.keys(hass.states).filter(id => 
      id.includes('huawei_charger') && (
        id.includes('session_energy') || 
        id.includes('session_duration') ||
        id.includes('total_energy') ||
        id.includes('current_power') ||
        id.includes('power')
      )
    );
    
    // Check if any relevant entity states changed by comparing with previous hass
    for (const entityId of huaweiEntities) {
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

    // Auto-detect energy monitoring entities
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
    
    const sessionEnergyEntity = findEntity(['session_energy']) || 
                               this._hass.states[this.config.session_energy_entity];
    const sessionDurationEntity = findEntity(['session_duration']) || 
                                 this._hass.states[this.config.session_duration_entity];
    const totalEnergyEntity = findEntity(['total_energy_charged', 'total_energy']) || 
                             this._hass.states[this.config.total_energy_entity];
    const currentPowerEntity = findEntity(['current_power', 'power']) || 
                              this._hass.states[this.config.current_power_entity];
    
    // If no energy entities found, show helpful message
    if (!sessionEnergyEntity && !totalEnergyEntity && !currentPowerEntity) {
      this.shadowRoot.innerHTML = `
        <ha-card>
          <div class="card-content">
            <div class="error">
              <h3>No energy monitoring entities found</h3>
              <p>Available Huawei Charger entities:</p>
              <ul style="text-align: left; margin: 8px 0;">
                ${huaweiEntities.slice(0, 10).map(id => `<li><code>${id}</code></li>`).join('')}
                ${huaweiEntities.length > 10 ? `<li>... and ${huaweiEntities.length - 10} more</li>` : ''}
              </ul>
              <p>Make sure the integration includes energy-related sensor entities.</p>
            </div>
          </div>
        </ha-card>
      `;
      return;
    }

    const sessionEnergy = parseFloat(sessionEnergyEntity.state) || 0;
    const sessionDuration = parseFloat(sessionDurationEntity?.state) || 0;
    const totalEnergy = parseFloat(totalEnergyEntity?.state) || 0;
    const currentPower = parseFloat(currentPowerEntity?.state) || 0;

    // Calculate session metrics
    const sessionCost = sessionEnergy * this.config.energy_cost;
    const averagePower = sessionDuration > 0 ? (sessionEnergy / (sessionDuration / 60)) : 0;
    const sessionHours = Math.floor(sessionDuration / 60);
    const sessionMinutes = Math.floor(sessionDuration % 60);

    // Estimate remaining time if charging
    const estimatedTimeToFull = currentPower > 0 ? ((7.4 - sessionEnergy) / currentPower) * 60 : 0;
    const estHours = Math.floor(estimatedTimeToFull / 60);
    const estMinutes = Math.floor(estimatedTimeToFull % 60);

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
          background: linear-gradient(135deg, var(--primary-color)20, var(--secondary-background-color));
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
            ${currentPower > 0 ? '<span class="charging-indicator"></span>' : ''}
          </div>
          
          <div class="energy-grid">
            <div class="energy-item">
              <ha-icon class="energy-icon" icon="mdi:battery-charging-outline"></ha-icon>
              <div class="energy-value">${sessionEnergy.toFixed(2)}</div>
              <div class="energy-label">Session kWh</div>
            </div>
            
            <div class="energy-item">
              <ha-icon class="energy-icon" icon="mdi:clock-outline"></ha-icon>
              <div class="energy-value">${sessionHours}h ${sessionMinutes}m</div>
              <div class="energy-label">Duration</div>
            </div>
            
            <div class="energy-item">
              <ha-icon class="energy-icon" icon="mdi:sigma"></ha-icon>
              <div class="energy-value">${totalEnergy.toFixed(1)}</div>
              <div class="energy-label">Total kWh</div>
            </div>
            
            <div class="energy-item">
              <ha-icon class="energy-icon" icon="mdi:speedometer"></ha-icon>
              <div class="energy-value">${averagePower.toFixed(1)}</div>
              <div class="energy-label">Avg Power</div>
            </div>
          </div>

          <div class="session-details">
            <div class="session-title">
              <ha-icon icon="mdi:information-outline"></ha-icon>
              Current Session
            </div>
            <div class="session-stats">
              <div class="stat-item">
                <span class="stat-label">Current Power:</span>
                <span class="stat-value">${currentPower.toFixed(1)} kW</span>
              </div>
              ${this.config.show_cost ? `
                <div class="stat-item">
                  <span class="stat-label">Session Cost:</span>
                  <span class="stat-value cost-highlight">${this.config.currency}${sessionCost.toFixed(2)}</span>
                </div>
              ` : ''}
              ${currentPower > 0 && estimatedTimeToFull > 0 ? `
                <div class="stat-item">
                  <span class="stat-label">Est. Full Time:</span>
                  <span class="stat-value">${estHours}h ${estMinutes}m</span>
                </div>
              ` : ''}
            </div>
          </div>

          <div class="power-trend">
            <div class="trend-item">
              <div class="trend-value">${(sessionEnergy * 100 / 7.4).toFixed(0)}%</div>
              <div class="trend-label">Battery Progress</div>
            </div>
            <div class="trend-item">
              <div class="trend-value">${sessionDuration > 0 ? (sessionEnergy / (sessionDuration / 3600)).toFixed(1) : '0.0'}</div>
              <div class="trend-label">kW/h Rate</div>
            </div>
            <div class="trend-item">
              <div class="trend-value">${currentPower > 0 ? Math.round((currentPower / 7.4) * 100) : 0}%</div>
              <div class="trend-label">Power Usage</div>
            </div>
          </div>
        </div>
      </ha-card>
    `;
  }
}

customElements.define('huawei-charger-energy-card', HuaweiChargerEnergyCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'huawei-charger-energy-card',
  name: 'Huawei Charger Energy Card',
  description: 'A custom card to monitor energy consumption and charging sessions'
});