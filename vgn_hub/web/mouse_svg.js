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
      <svg class="mouse-svg-bottom" viewBox="0 0 270 380" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="bottomShell" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stop-color="#282a31"/>
            <stop offset="100%" stop-color="#17181d"/>
          </linearGradient>
          <linearGradient id="ptfe" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#f7f8fb"/>
            <stop offset="100%" stop-color="#d8dce5"/>
          </linearGradient>
          <radialGradient id="dpiGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stop-color="${ledColor}" stop-opacity="0.95"/>
            <stop offset="50%" stop-color="${ledColor}" stop-opacity="0.35"/>
            <stop offset="100%" stop-color="${ledColor}" stop-opacity="0"/>
          </radialGradient>
        </defs>

        <!-- Base housing matching full-shouldered, broad-bottomed Dragonfly 3 Ultra silhouette -->
        <path d="M135 18 C82 18 55 38 49 78 C46 112 46 146 47 180 C48 220 46 266 54 304 C64 344 92 362 135 362 C178 362 206 344 216 304 C224 266 222 220 223 180 C224 146 224 112 221 78 C215 38 188 18 135 18 Z"
              fill="url(#bottomShell)" stroke="#4c505c" stroke-width="1.3"/>

        <!-- Top PTFE skate -->
        <path d="M72 41 C84 30 104 27 135 27 C166 27 186 30 198 41 C207 50 209 69 206 84 C194 90 174 92 135 92 C96 92 76 90 64 84 C61 69 63 50 72 41 Z"
              fill="url(#ptfe)" stroke="#b8becb" stroke-width="1"/>

        <!-- Bottom U PTFE skate -->
        <path d="M62 274 C70 318 96 346 135 346 C174 346 200 318 208 274 L194 272 C186 308 164 328 135 328 C106 328 84 308 76 272 Z"
              fill="url(#ptfe)" stroke="#b8becb" stroke-width="1"/>

        <!-- Live DPI Indicator LED dot -->
        <circle cx="98" cy="124" r="14" fill="url(#dpiGlow)"/>
        <circle cx="98" cy="124" r="4.5" fill="${ledColor}" stroke="#121318" stroke-width="1.2"/>

        <!-- DPI button (left) -->
        <rect x="80" y="158" width="18" height="28" rx="8" fill="#131419" stroke="#505562" stroke-width="1.1"/>
        <text x="89" y="200" fill="#8d92a3" font-size="8.5" text-anchor="middle" font-family="sans-serif">DPI</text>

        <!-- PAW3950 center sensor + PTFE ring -->
        <ellipse cx="135" cy="172" rx="20" ry="26" fill="url(#ptfe)" stroke="#b8becb" stroke-width="1"/>
        <ellipse cx="135" cy="172" rx="12" ry="16" fill="#14151a" stroke="#393c46" stroke-width="1"/>
        <circle cx="135" cy="172" r="4.8" fill="#090a0d" stroke="#5d6272" stroke-width="1"/>

        <!-- Mode switch (2.4G / OFF / BT or USB) -->
        <rect x="172" y="158" width="18" height="28" rx="8" fill="#131419" stroke="#505562" stroke-width="1.1"/>
        <rect x="176" y="162" width="10" height="10" rx="4" fill="#63697a"/>
        <text x="181" y="200" fill="#8d92a3" font-size="8.5" text-anchor="middle" font-family="sans-serif">MODE</text>

        <!-- Dongle storage bay outline -->
        <rect x="104" y="216" width="62" height="58" rx="9" fill="#1b1c22" stroke="#333640" stroke-width="1"/>
        <text x="135" y="249" fill="#666b7a" font-size="8" text-anchor="middle" font-family="sans-serif">PAW3950</text>
      </svg>
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
