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
      <svg class="${cls}" viewBox="0 0 260 400" xmlns="http://www.w3.org/2000/svg">
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

        ${compact ? "" : `<ellipse cx="130" cy="200" rx="115" ry="175" fill="url(#topAura)"/>`}

        <!-- Side thumb buttons (Forward / Backward) -->
        <path d="M51 142 C46 142 44 146 44 152 L44 178 C44 182 47 184 52 184 Z" fill="#2c2e35" stroke="#484b55" stroke-width="1"/>
        <path d="M51 190 C46 190 44 193 44 197 L44 224 C44 229 46 233 51 233 Z" fill="#2c2e35" stroke="#484b55" stroke-width="1"/>

        <!-- Main sculpted body silhouette -->
        <g filter="${compact ? "none" : "url(#softShadow)"}">
          <path d="M130 24 C84 24 62 42 56 80 L50 162 C47 210 53 262 62 308 C72 354 96 376 130 376 C164 376 188 354 198 308 C207 262 213 210 210 162 L204 80 C198 42 176 24 130 24 Z"
                fill="url(#bodyShell)" stroke="#4c505c" stroke-width="1.3"/>

          <!-- Split Left & Right click paddles -->
          <path d="M127 25 C86 26 65 44 59 80 L56 144 C82 149 105 151 127 151 Z"
                fill="url(#btnLeft)" stroke="#14151a" stroke-width="1.4"/>
          <path d="M133 25 C174 26 195 44 201 80 L204 144 C178 149 155 151 133 151 Z"
                fill="url(#btnRight)" stroke="#14151a" stroke-width="1.4"/>

          <!-- Subtle inner rim & palm contour -->
          <path d="M57 148 C82 154 106 156 130 156 C154 156 178 154 203 148"
                fill="none" stroke="#101116" stroke-width="2.2"/>
          <path d="M74 260 C84 316 104 344 130 344 C156 344 176 316 186 260"
                fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="1.4"/>

          <!-- Center scroll well & metallic wheel -->
          <rect x="118" y="42" width="24" height="72" rx="11" fill="#121318" stroke="#2c2e36" stroke-width="1.2"/>
          <rect x="122" y="48" width="16" height="58" rx="7" fill="url(#wheelMetal)" stroke="#686d7a" stroke-width="1"/>
          <g stroke="#2a2c34" stroke-width="1.3" opacity="0.7">
            <line x1="124" y1="56" x2="136" y2="56"/>
            <line x1="124" y1="62" x2="136" y2="62"/>
            <line x1="124" y1="68" x2="136" y2="68"/>
            <line x1="124" y1="74" x2="136" y2="74"/>
            <line x1="124" y1="80" x2="136" y2="80"/>
            <line x1="124" y1="86" x2="136" y2="86"/>
            <line x1="124" y1="92" x2="136" y2="92"/>
          </g>

          <!-- Front DPI / status LED diffuser -->
          <rect x="124" y="29" width="12" height="5" rx="2.5" fill="${ledColor}" opacity="0.95"/>
          <rect x="121" y="27" width="18" height="9" rx="4.5" fill="${ledColor}" opacity="0.28"/>

          <!-- Gold Dragonfly wing emblem -->
          <g transform="translate(130, 300)" fill="url(#goldWing)">
            <path d="M0 -8 C2 -14 14 -16 20 -13 C15 -8 8 -4 2 -3 L0 12 L-2 -3 C-8 -4 -15 -8 -20 -13 C-14 -16 -2 -14 0 -8 Z"/>
            <path d="M1 -1 C7 -2 14 -1 16 3 C11 5 5 4 1 2 Z" opacity="0.88"/>
            <path d="M-1 -1 C-7 -2 -14 -1 -16 3 C-11 5 -5 4 -1 2 Z" opacity="0.88"/>
            <circle cx="0" cy="-11" r="2.1"/>
          </g>
        </g>

        <!-- Interactive clickable hotspots for Key Binding view -->
        ${hot(0, 86, 86)}
        ${hot(2, 130, 77)}
        ${hot(1, 174, 86)}
        ${hot(3, 48, 163)}
        ${hot(4, 48, 211)}
        ${hot(5, 130, 224)}
      </svg>
    `;
  },

  renderBottom({ ledColor = "#ffff00" } = {}) {
    return `
      <svg class="mouse-svg-bottom" viewBox="0 0 240 380" xmlns="http://www.w3.org/2000/svg">
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
        <path d="M120 22 C76 22 56 42 50 82 L45 162 C43 210 49 260 58 304 C68 346 90 364 120 364 C150 364 172 346 182 304 C191 260 197 210 195 162 L190 82 C184 42 164 22 120 22 Z"
              fill="url(#bottomShell)" stroke="#4c505c" stroke-width="1.3"/>

        <!-- Top PTFE skate -->
        <path d="M74 44 C82 34 100 30 120 30 C140 30 158 34 166 44 C172 52 174 70 172 86 C164 92 152 94 120 94 C88 94 76 92 68 86 C66 70 68 52 74 44 Z"
              fill="url(#ptfe)" stroke="#b8becb" stroke-width="1"/>

        <!-- Bottom U PTFE skate -->
        <path d="M68 274 C76 318 94 344 120 344 C146 344 164 318 172 274 L160 272 C154 308 140 328 120 328 C100 328 86 308 80 272 Z"
              fill="url(#ptfe)" stroke="#b8becb" stroke-width="1"/>

        <!-- Live DPI Indicator LED dot -->
        <circle cx="96" cy="126" r="14" fill="url(#dpiGlow)"/>
        <circle cx="96" cy="126" r="4.5" fill="${ledColor}" stroke="#121318" stroke-width="1.2"/>

        <!-- DPI button (left) -->
        <rect x="78" y="156" width="16" height="28" rx="7" fill="#131419" stroke="#505562" stroke-width="1.1"/>
        <text x="86" y="198" fill="#8d92a3" font-size="8.5" text-anchor="middle" font-family="sans-serif">DPI</text>

        <!-- PAW3950 center sensor + PTFE ring -->
        <ellipse cx="120" cy="170" rx="18" ry="25" fill="url(#ptfe)" stroke="#b8becb" stroke-width="1"/>
        <ellipse cx="120" cy="170" rx="11" ry="16" fill="#14151a" stroke="#393c46" stroke-width="1"/>
        <circle cx="120" cy="170" r="4.5" fill="#090a0d" stroke="#5d6272" stroke-width="1"/>

        <!-- Mode switch (2.4G / OFF / BT or USB) -->
        <rect x="146" y="156" width="16" height="28" rx="7" fill="#131419" stroke="#505562" stroke-width="1.1"/>
        <rect x="149" y="160" width="10" height="10" rx="4" fill="#63697a"/>
        <text x="154" y="198" fill="#8d92a3" font-size="8.5" text-anchor="middle" font-family="sans-serif">MODE</text>

        <!-- Dongle storage bay outline -->
        <rect x="96" y="216" width="48" height="58" rx="8" fill="#1b1c22" stroke="#333640" stroke-width="1"/>
        <text x="120" y="249" fill="#666b7a" font-size="8" text-anchor="middle" font-family="sans-serif">PAW3950</text>
      </svg>
    `;
  },

  renderWireframe({ angle = 0 } = {}) {
    return `
      <svg class="mouse-svg-wire" viewBox="0 0 180 240" xmlns="http://www.w3.org/2000/svg">
        <line x1="90" y1="10" x2="90" y2="230" stroke="rgba(255,255,255,0.12)" stroke-dasharray="4 4"/>
        <line x1="15" y1="120" x2="165" y2="120" stroke="rgba(255,255,255,0.12)" stroke-dasharray="4 4"/>
        <g transform="rotate(${angle} 90 120)">
          <path d="M90 30 C64 30 51 43 47 68 L44 122 C42 152 46 184 53 204 C61 218 74 222 90 222 C106 222 119 218 127 204 C134 184 138 152 136 122 L133 68 C129 43 116 30 90 30 Z"
                fill="rgba(255,255,255,0.03)" stroke="rgba(244,243,248,0.68)" stroke-width="1.5"/>
          <path d="M47 94 C66 99 114 99 133 94" fill="none" stroke="rgba(244,243,248,0.45)" stroke-width="1.2"/>
          <line x1="90" y1="30" x2="90" y2="97" stroke="rgba(244,243,248,0.45)" stroke-width="1.2"/>
          <rect x="83" y="45" width="14" height="34" rx="6" fill="rgba(116,185,255,0.35)" stroke="#74b9ff" stroke-width="1.2"/>
          <path d="M90 14 L84 25 L96 25 Z" fill="#f7d06b"/>
        </g>
      </svg>
    `;
  },
};
