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

  rotationArcPath(cx, cy, r, sensorDeg) {
    const visDeg = sensorDeg * 1.5;
    if (Math.abs(visDeg) < 0.01) return "";
    const rad = ((visDeg - 90) * Math.PI) / 180;
    const ex = cx + r * Math.cos(rad);
    const ey = cy + r * Math.sin(rad);
    const sweep = visDeg > 0 ? 1 : 0;
    return `M ${cx.toFixed(2)} ${(cy - r).toFixed(2)} A ${r} ${r} 0 0 ${sweep} ${ex.toFixed(2)} ${ey.toFixed(2)}`;
  },

  renderRotationDial({ angle = 0 } = {}) {
    const cx = 148;
    const cy = 144;
    const R_OUTER = 104;
    const R_BAND = 88;
    const R_INNER = 74;
    const R_LABEL = 123;

    const polar = (r, visDeg) => {
      const rad = ((visDeg - 90) * Math.PI) / 180;
      return [cx + r * Math.cos(rad), cy + r * Math.sin(rad)];
    };

    const spanArc = (r) => {
      const [sx, sy] = polar(r, -135);
      const [ex, ey] = polar(r, 135);
      return `M ${sx.toFixed(2)} ${sy.toFixed(2)} A ${r} ${r} 0 1 1 ${ex.toFixed(2)} ${ey.toFixed(2)}`;
    };

    let ticks = "";
    let labels = "";
    for (let deg = -90; deg <= 90; deg += 5) {
      const visDeg = deg * 1.5;
      const isMajor = deg % 15 === 0;
      const rIn = isMajor ? 95 : 99;
      const [x1, y1] = polar(rIn, visDeg);
      const [x2, y2] = polar(R_OUTER, visDeg);
      const stroke = isMajor
        ? deg === 0
          ? "rgba(255,255,255,0.85)"
          : "rgba(255,255,255,0.48)"
        : "rgba(255,255,255,0.22)";
      const sw = isMajor ? (deg === 0 ? 1.5 : 1.2) : 1;
      ticks += `<line x1="${x1.toFixed(2)}" y1="${y1.toFixed(2)}" x2="${x2.toFixed(2)}" y2="${y2.toFixed(2)}" stroke="${stroke}" stroke-width="${sw}"/>`;

      if (isMajor) {
        const [lx, ly] = polar(R_LABEL, visDeg);
        labels += `<text class="dial-tick-label" x="${lx.toFixed(2)}" y="${ly.toFixed(2)}" text-anchor="middle" dominant-baseline="central">${deg}°</text>`;
      }
    }

    return `
      <svg class="rot-dial-svg" viewBox="0 0 296 254" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <filter id="rotNeedleGlow" x="-120%" y="-40%" width="340%" height="180%">
            <feGaussianBlur stdDeviation="2.6"/>
          </filter>
          <filter id="rotKnobShadow" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="7"/>
          </filter>
          <linearGradient id="rotKnobBevel" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#50535f"/>
            <stop offset="48%" stop-color="#292b34"/>
            <stop offset="100%" stop-color="#121318"/>
          </linearGradient>
          <radialGradient id="rotKnobFace" cx="35%" cy="25%" r="72%">
            <stop offset="0%" stop-color="#2b2d35"/>
            <stop offset="60%" stop-color="#1b1c22"/>
            <stop offset="100%" stop-color="#13141a"/>
          </radialGradient>
        </defs>

        <!-- Static 270deg radial track -->
        <path d="${spanArc(R_BAND)}" fill="none" stroke="rgba(255,255,255,0.065)" stroke-width="28"/>
        <path d="${spanArc(R_OUTER)}" fill="none" stroke="rgba(255,255,255,0.14)" stroke-width="1"/>
        <path d="${spanArc(R_INNER)}" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="1"/>

        <!-- Live active swept angle highlight -->
        <path id="rot-active-arc" d="${this.rotationArcPath(cx, cy, R_BAND, angle)}" fill="none" stroke="rgba(222,238,94,0.16)" stroke-width="28"/>
        <path id="rot-active-rim" d="${this.rotationArcPath(cx, cy, R_OUTER, angle)}" fill="none" stroke="#dce960" stroke-width="2" stroke-opacity="0.75"/>

        ${ticks}
        ${labels}

        <!-- Rotating pointer needle -->
        <g id="rot-needle-group" class="rot-needle-group" transform="rotate(${angle * 1.5} ${cx} ${cy})">
          <line x1="${cx}" y1="73" x2="${cx}" y2="41" stroke="#e2f064" stroke-width="6" stroke-linecap="round" opacity="0.32" filter="url(#rotNeedleGlow)"/>
          <line x1="${cx}" y1="73" x2="${cx}" y2="40" stroke="#e7f36e" stroke-width="2.6" stroke-linecap="round"/>
        </g>

        <!-- Sculpted 3D metallic knob -->
        <circle cx="${cx}" cy="152" r="71" fill="rgba(0,0,0,0.6)" filter="url(#rotKnobShadow)"/>
        <circle cx="${cx}" cy="${cy}" r="72" fill="url(#rotKnobBevel)" stroke="rgba(255,255,255,0.14)" stroke-width="1"/>
        <circle cx="${cx}" cy="${cy}" r="61" fill="url(#rotKnobFace)" stroke="rgba(0,0,0,0.45)" stroke-width="1.2"/>
        <text id="rot-val" class="dial-readout-svg" x="${cx}" y="145" text-anchor="middle" dominant-baseline="central">${angle}°</text>
      </svg>
    `;
  },

  renderWireframe({ angle = 0 } = {}) {
    return `
      <svg class="mouse-svg-wire" viewBox="0 0 210 250" xmlns="http://www.w3.org/2000/svg">
        <g id="wire-mouse-group" class="wire-mouse-group" transform="rotate(${angle} 105 125)">
          <path d="M105 26 C72 26 57 38 55 64 C54 88 55 112 56 132 C57 156 54 180 61 200 C69 218 85 224 105 224 C125 224 141 218 149 200 C156 180 153 156 154 132 C155 112 156 88 155 64 C153 38 138 26 105 26 Z"
                fill="rgba(255,255,255,0.02)" stroke="rgba(244,243,248,0.68)" stroke-width="1.25"/>
          <path d="M55 82 L52.5 84 L52.5 103 L55.3 105" fill="none" stroke="rgba(244,243,248,0.52)" stroke-width="1.1"/>
          <path d="M55.5 110 L53 112 L53 132 L56 134" fill="none" stroke="rgba(244,243,248,0.52)" stroke-width="1.1"/>
          <path d="M60 44 C59 64 59 84 60 100 C60.5 104 63 106 67 106 L143 106 C147 106 149.5 104 150 100 C151 84 151 64 150 44"
                fill="none" stroke="rgba(244,243,248,0.52)" stroke-width="1.1"/>
          <line x1="105" y1="26" x2="105" y2="43" stroke="rgba(244,243,248,0.52)" stroke-width="1.1"/>
          <line x1="105" y1="77" x2="105" y2="106" stroke="rgba(244,243,248,0.52)" stroke-width="1.1"/>
          <rect x="97.5" y="43" width="15" height="34" rx="5.5" fill="rgba(255,255,255,0.05)" stroke="rgba(244,243,248,0.55)" stroke-width="1"/>
          <rect x="99.5" y="45.5" width="11" height="29" rx="3.5" fill="rgba(232,232,242,0.72)" stroke="rgba(255,255,255,0.85)" stroke-width="0.75"/>
        </g>
      </svg>
    `;
  },
};
