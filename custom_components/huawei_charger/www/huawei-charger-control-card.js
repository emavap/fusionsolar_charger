class HuaweiChargerControlCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  setConfig(config) {
    this.config = {
      dynamic_power_entity: 'number.huawei_charger_dynamic_power_limit',
      fixed_power_entity: 'number.huawei_charger_fixed_max_charging_power',
      ...config
    };
  }

  set hass(hass) {
    this._hass = hass;
    this.render();
  }

  getCardSize() {
    return 4;
  }

  render() {
    if (!this._hass || !this.config) return;

    const dynamicEntity = this._hass.states[this.config.dynamic_power_entity];
    const fixedEntity = this._hass.states[this.config.fixed_power_entity];
    
    if (!dynamicEntity) {
      this.shadowRoot.innerHTML = `
        <ha-card>
          <div class="card-content">
            <div class="error">Entity ${this.config.dynamic_power_entity} not found</div>
          </div>
        </ha-card>
      `;
      return;
    }

    const dynamicValue = parseFloat(dynamicEntity.state) || 0;
    const fixedValue = parseFloat(fixedEntity?.state) || 0;
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
              >
              <div class="power-display">
                <span id="dynamic-display">${dynamicValue.toFixed(1)}</span>
                <span class="power-unit">kW</span>
              </div>
            </div>
            <div class="slider-labels">
              <span>${minValue}kW</span>
              <span>${maxValue}kW</span>
            </div>
          </div>

          <div class="preset-buttons">
            ${presets.map(preset => `
              <div class="preset-button ${Math.abs(dynamicValue - preset.value) < 0.1 ? 'active' : ''}" 
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
      this.setPowerLimit(value);
    });

    // Preset button clicks
    presetButtons.forEach(button => {
      button.addEventListener('click', () => {
        const value = parseFloat(button.dataset.value);
        slider.value = value;
        display.textContent = value.toFixed(1);
        this.updatePresetButtons(value);
        this.setPowerLimit(value);
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

  setPowerLimit(value) {
    if (!this._hass) return;
    
    this._hass.callService('number', 'set_value', {
      entity_id: this.config.dynamic_power_entity,
      value: value
    });
  }
}

customElements.define('huawei-charger-control-card', HuaweiChargerControlCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'huawei-charger-control-card',
  name: 'Huawei Charger Control Card',
  description: 'A custom card to control Huawei charger power limits with presets'
});