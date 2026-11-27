window.VgnMouseSvg = {
  renderTop({ ledColor = "#8ef6ff", activeSlot = null, interactive = false, compact = false } = {}) {
    const cls = compact ? "mouse-svg-compact" : "mouse-svg-top";
    const hot = (slot, cx, cy) =>
      interactive
        ? `<g class="mouse-hotspot ${activeSlot === slot ? "is-active" : ""}" data-slot="${slot}">
             <circle class="hotspot-ring" cx="${cx}" cy="${cy}" r="14"/>
             <circle class="hotspot-dot" cx="${cx}" cy="${cy}" r="5"/>
           </g>`
        : "";

    return `
      <svg class="${cls}" viewBox="0 0 280 390" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="bodyShell" x1="0.15" y1="0" x2="0.85" y2="1">
            <stop offset="0%" stop-color="#34363d"/>
            <stop offset="48%" stop-color="#22242a"/>
            <stop offset="100%" stop-color="#17181d"/>
          </linearGradient>
          <linearGradient id="btnLeft" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stop-color="#3c3f48"/>
            <stop offset="100%" stop-color="#25272e"/>
          </linearGradient>
          <linearGradient id="btnRight" x1="1" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#3c3f48"/>
            <stop offset="100%" stop-color="#25272e"/>
          </linearGradient>
          <linearGradient id="wheelMetal" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stop-color="#4e525d"/>
            <stop offset="50%" stop-color="#9aa0ae"/>
            <stop offset="100%" stop-color="#3a3d46"/>
          </linearGradient>
          <linearGradient id="goldWing" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stop-color="#f7da84"/>
            <stop offset="50%" stop-color="#d4a64a"/>
            <stop offset="100%" stop-color="#9e7424"/>
          </linearGradient>
          <radialGradient id="topAura" cx="50%" cy="45%" r="55%">
            <stop offset="0%" stop-color="${ledColor}" stop-opacity="0.22"/>
            <stop offset="100%" stop-color="${ledColor}" stop-opacity="0"/>
          </radialGradient>
          <filter id="softShadow" x="-25%" y="-15%" width="150%" height="140%">
            <feDropShadow dx="0" dy="14" stdDeviation="12" flood-color="#000000" flood-opacity="0.6"/>
          </filter>
        </defs>

        ${compact ? "" : `<ellipse cx="140" cy="195" rx="126" ry="175" fill="url(#topAura)"/>`}

        <!-- Side thumb buttons (Forward / Backward) -->
        <path d="M42 138 C36 138 33 142 33 148 L33 176 C33 181 36 184 41 184 Z" fill="#2c2e35" stroke="#484b55" stroke-width="1"/>
        <path d="M40 189 C35 189 33 192 33 197 L33 224 C33 230 35 234 41 234 Z" fill="#2c2e35" stroke="#484b55" stroke-width="1"/>

        <!-- Main sculpted body silhouette (plump Dragonfly proportions) -->
        <g filter="${compact ? "none" : "url(#softShadow)"}">
          <path d="M140 24 C84 24 54 44 47 84 L40 162 C37 212 43 266 56 312 C69 352 100 366 140 366 C180 366 211 352 224 312 C237 266 243 212 240 162 L233 84 C226 44 196 24 140 24 Z"
                fill="url(#bodyShell)" stroke="#4c505c" stroke-width="1.3"/>

          <!-- Split Left & Right click paddles -->
          <path d="M136 25 C86 26 58 46 51 84 L46 146 C78 152 106 154 136 154 Z"
                fill="url(#btnLeft)" stroke="#14151a" stroke-width="1.4"/>
          <path d="M144 25 C194 26 222 46 229 84 L234 146 C202 152 174 154 144 154 Z"
                fill="url(#btnRight)" stroke="#14151a" stroke-width="1.4"/>

          <!-- Subtle inner rim & palm contour -->
          <path d="M48 150 C80 157 110 159 140 159 C170 159 200 157 232 150"
                fill="none" stroke="#101116" stroke-width="2.2"/>
          <path d="M68 258 C82 316 106 340 140 340 C174 340 198 316 212 258"
                fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="1.4"/>

          <!-- Center scroll well & metallic wheel -->
          <rect x="125" y="42" width="30" height="74" rx="13" fill="#121318" stroke="#2c2e36" stroke-width="1.2"/>
          <rect x="130" y="48" width="20" height="60" rx="8" fill="url(#wheelMetal)" stroke="#686d7a" stroke-width="1"/>
          <g stroke="#2a2c34" stroke-width="1.3" opacity="0.7">
            <line x1="133" y1="56" x2="147" y2="56"/>
            <line x1="133" y1="62" x2="147" y2="62"/>
            <line x1="133" y1="68" x2="147" y2="68"/>
            <line x1="133" y1="74" x2="147" y2="74"/>
            <line x1="133" y1="80" x2="147" y2="80"/>
            <line x1="133" y1="86" x2="147" y2="86"/>
            <line x1="133" y1="92" x2="147" y2="92"/>
            <line x1="133" y1="98" x2="147" y2="98"/>
          </g>

          <!-- Front DPI / status LED diffuser -->
          <rect x="133" y="29" width="14" height="5" rx="2.5" fill="${ledColor}" opacity="0.95"/>
          <rect x="129" y="27" width="22" height="9" rx="4.5" fill="${ledColor}" opacity="0.28"/>

          <!-- Gold Dragonfly wing emblem -->
          <g transform="translate(140, 294) scale(1.12)" fill="url(#goldWing)">
            <path d="M0 -8 C2 -14 14 -16 20 -13 C15 -8 8 -4 2 -3 L0 12 L-2 -3 C-8 -4 -15 -8 -20 -13 C-14 -16 -2 -14 0 -8 Z"/>
            <path d="M1 -1 C7 -2 14 -1 16 3 C11 5 5 4 1 2 Z" opacity="0.88"/>
            <path d="M-1 -1 C-7 -2 -14 -1 -16 3 C-11 5 -5 4 -1 2 Z" opacity="0.88"/>
            <circle cx="0" cy="-11" r="2.1"/>
          </g>
        </g>

        <!-- Interactive clickable hotspots for Key Binding view -->
        ${hot(0, 88, 92)}
        ${hot(2, 140, 78)}
        ${hot(1, 192, 92)}
        ${hot(3, 39, 158)}
        ${hot(4, 39, 208)}
        ${hot(5, 140, 224)}
      </svg>
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

        <!-- Base housing -->
        <path d="M135 22 C80 22 52 42 45 82 L39 162 C36 210 42 260 54 304 C67 344 96 358 135 358 C174 358 203 344 216 304 C228 260 234 210 231 162 L225 82 C218 42 190 22 135 22 Z"
              fill="url(#bottomShell)" stroke="#4c505c" stroke-width="1.3"/>

        <!-- Top PTFE skate -->
        <path d="M68 44 C80 32 103 29 135 29 C167 29 190 32 202 44 C211 53 215 72 212 87 C198 93 177 95 135 95 C93 95 72 93 58 87 C55 72 59 53 68 44 Z"
              fill="url(#ptfe)" stroke="#b8becb" stroke-width="1"/>

        <!-- Bottom U PTFE skate -->
        <path d="M58 274 C69 320 96 344 135 344 C174 344 201 320 212 274 L197 272 C188 308 166 326 135 326 C104 326 82 308 73 272 Z"
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
          <path d="M100 32 C68 32 54 45 50 68 L48 122 C46 154 51 184 59 202 C68 212 82 214 100 214 C118 214 132 212 141 202 C149 184 154 154 152 122 L150 68 C146 45 132 32 100 32 Z"
                fill="rgba(255,255,255,0.03)" stroke="rgba(244,243,248,0.68)" stroke-width="1.5"/>
          <path d="M50 96 C74 101 126 101 150 96" fill="none" stroke="rgba(244,243,248,0.45)" stroke-width="1.2"/>
          <line x1="100" y1="32" x2="100" y2="99" stroke="rgba(244,243,248,0.45)" stroke-width="1.2"/>
          <rect x="92" y="47" width="16" height="34" rx="7" fill="rgba(116,185,255,0.35)" stroke="#74b9ff" stroke-width="1.2"/>
          <path d="M100 14 L94 25 L106 25 Z" fill="#f7d06b"/>
        </g>
      </svg>
    `;
  },
};
