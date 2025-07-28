class HuaweiChargerStatusCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error('You need to define an entity');
    }
    this.config = config;
  }

  set hass(hass) {
    this._hass = hass;
    this.render();
  }

  getCardSize() {
    return 3;
  }

  render() {
    if (!this._hass || !this.config) return;

    const entityId = this.config.entity;
    const entity = this._hass.states[entityId];
    
    if (!entity) {
      this.shadowRoot.innerHTML = `
        <ha-card>
          <div class="card-content">
            <div class="error">Entity ${entityId} not found</div>
          </div>
        </ha-card>
      `;
      return;
    }

    // Get related entities
    const baseName = entityId.replace('sensor.huawei_charger_', '').replace('_', ' ');
    const chargingStatus = this._hass.states[`sensor.huawei_charger_charging_status`];
    const currentPower = this._hass.states[`sensor.huawei_charger_current_power`];
    const sessionEnergy = this._hass.states[`sensor.huawei_charger_session_energy`];
    const pluggedIn = this._hass.states[`sensor.huawei_charger_plugged_in`];
    const dynamicPowerLimit = this._hass.states[`number.huawei_charger_dynamic_power_limit`];

    // Determine charging state and color
    const isCharging = chargingStatus?.state === '1' || chargingStatus?.state === 'Charging';
    const isPlugged = pluggedIn?.state === '1' || pluggedIn?.state === 'Connected';
    const power = parseFloat(currentPower?.state) || 0;
    const powerLimit = parseFloat(dynamicPowerLimit?.state) || 7.4;
    
    let statusText = 'Unknown';
    let statusColor = '#666';
    let statusIcon = 'mdi:help-circle';
    
    if (isCharging) {
      statusText = 'Charging';
      statusColor = '#4CAF50';
      statusIcon = 'mdi:battery-charging';
    } else if (isPlugged) {
      statusText = 'Connected';
      statusColor = '#2196F3';
      statusIcon = 'mdi:power-plug';
    } else {
      statusText = 'Idle';
      statusColor = '#9E9E9E';
      statusIcon = 'mdi:ev-station';
    }

    const powerPercent = Math.min((power / powerLimit) * 100, 100);

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
          
          <div class="power-display">
            <div>
              <span class="power-current">${power.toFixed(1)}</span>
              <span class="power-unit">kW</span>
            </div>
            <div class="power-limit">
              Limit: ${powerLimit}kW
            </div>
          </div>
          
          <div class="power-bar">
            <div class="power-fill"></div>
          </div>
          
          <div class="session-info">
            <div class="info-item">
              <div class="info-label">Session Energy</div>
              <div class="info-value">${sessionEnergy?.state || 0} kWh</div>
            </div>
            <div class="info-item">
              <div class="info-label">Connection</div>
              <div class="info-value">${isPlugged ? 'Connected' : 'Disconnected'}</div>
            </div>
          </div>
        </div>
      </ha-card>
    `;
  }
}

customElements.define('huawei-charger-status-card', HuaweiChargerStatusCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'huawei-charger-status-card',
  name: 'Huawei Charger Status Card',
  description: 'A custom card to display Huawei charger status and power information'
});