window.VgnMouseSvg = {
  renderTop({ ledColor = "#8ef6ff", activeSlot = null, interactive = false, compact = false } = {}) {
    if (compact) {
      return `<img class="mouse-svg-compact" src="assets/dragonfly3-top.png" alt="Dragonfly 3 Ultra" draggable="false"/>`;
    }

    const hot = (slot, cx, cy) =>
      interactive
        ? `<g class="mouse-hotspot ${activeSlot === slot ? "is-active" : ""}" data-slot="${slot}">
             <circle class="hotspot-ring" cx="${cx}" cy="${cy}" r="18"/>
             <circle class="hotspot-dot" cx="${cx}" cy="${cy}" r="6.5"/>
           </g>`
        : "";

    return `
      <div class="mouse-photo-wrap">
        <img class="mouse-photo-img" src="assets/dragonfly3-top.png" alt="Dragonfly 3 Ultra" draggable="false"/>
        <svg class="mouse-photo-overlay" viewBox="0 0 266 488" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <filter id="ledBlur" x="-80%" y="-80%" width="260%" height="260%">
              <feGaussianBlur stdDeviation="3.5"/>
            </filter>
          </defs>
          <!-- Live DPI LED tint over the front indicator bar -->
          <rect x="125" y="33" width="16" height="10" rx="5" fill="${ledColor}" opacity="0.65" filter="url(#ledBlur)"/>
          <rect x="128" y="36" width="10" height="4" rx="2" fill="${ledColor}" opacity="0.72"/>

          ${hot(0, 76, 120)}
          ${hot(2, 133, 102)}
          ${hot(1, 190, 120)}
          ${hot(3, 18, 184)}
          ${hot(4, 19, 262)}
          ${hot(5, 133, 285)}
        </svg>
      </div>
    `;
  },

  renderBottom({ ledColor = "#ffff00" } = {}) {
    return `
      <div class="mouse-photo-wrap mouse-photo-bottom">
        <img class="mouse-photo-img" src="assets/dragonfly3-bottom.png" alt="Dragonfly 3 Ultra Bottom" draggable="false"/>
        <svg class="mouse-photo-overlay" viewBox="0 0 172 332" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <radialGradient id="dpiGlow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stop-color="${ledColor}" stop-opacity="1"/>
              <stop offset="32%" stop-color="${ledColor}" stop-opacity="0.72"/>
              <stop offset="68%" stop-color="${ledColor}" stop-opacity="0.22"/>
              <stop offset="100%" stop-color="${ledColor}" stop-opacity="0"/>
            </radialGradient>
          </defs>
          <!-- Live DPI indicator LED over the physical bottom LED aperture -->
          <circle cx="44.5" cy="127.5" r="11" fill="url(#dpiGlow)"/>
          <circle cx="44.5" cy="127.5" r="3.2" fill="${ledColor}" opacity="0.95"/>
          <circle cx="44.5" cy="127.5" r="1.4" fill="#ffffff" opacity="0.9"/>
        </svg>
      </div>
    `;
  },

  renderWireframe({ angle = 0 } = {}) {
    return `
      <svg class="mouse-svg-wire" viewBox="0 0 200 240" xmlns="http://www.w3.org/2000/svg">
        <line x1="100" y1="10" x2="100" y2="230" stroke="rgba(255,255,255,0.12)" stroke-dasharray="4 4"/>
        <line x1="14" y1="120" x2="186" y2="120" stroke="rgba(255,255,255,0.12)" stroke-dasharray="4 4"/>
        <g transform="rotate(${angle} 100 120)">
          <path d="M100 28 C70 28 56 39 53 62 C51 84 51 106 52 126 C53 150 51 174 56 194 C63 210 79 216 100 216 C121 216 137 210 144 194 C149 174 147 150 148 126 C149 106 149 84 147 62 C144 39 130 28 100 28 Z"
                fill="rgba(255,255,255,0.03)" stroke="rgba(244,243,248,0.68)" stroke-width="1.5"/>
          <path d="M52 104 L148 104" fill="none" stroke="rgba(244,243,248,0.45)" stroke-width="1.2"/>
          <line x1="100" y1="28" x2="100" y2="104" stroke="rgba(244,243,248,0.45)" stroke-width="1.2"/>
          <rect x="92" y="47" width="16" height="34" rx="7" fill="rgba(116,185,255,0.35)" stroke="#74b9ff" stroke-width="1.2"/>
          <path d="M100 14 L94 25 L106 25 Z" fill="#f7d06b"/>
        </g>
      </svg>
    `;
  },
};
