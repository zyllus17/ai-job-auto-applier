import os
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
ASSETS = REPO_ROOT / "assets"
ASSETS.mkdir(exist_ok=True)

WINDOWS_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="240" height="64" viewBox="0 0 240 64" fill="none">
  <defs>
    <linearGradient id="win-grad" x1="0" y1="0" x2="240" y2="64" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#0078D6" />
      <stop offset="100%" stop-color="#005A9E" />
    </linearGradient>
    <filter id="shadow" x="-4" y="-2" width="248" height="72" filterUnits="userSpaceOnUse">
      <feDropShadow dx="0" dy="4" stdDeviation="4" flood-color="#000000" flood-opacity="0.25" />
    </filter>
  </defs>
  <!-- Background Card -->
  <rect x="2" y="2" width="236" height="60" rx="12" fill="url(#win-grad)" stroke="#38A5FF" stroke-width="1.5" filter="url(#shadow)" />
  
  <!-- Windows Official 4-Tile Logo -->
  <g transform="translate(18, 18)">
    <rect x="0" y="0" width="13" height="13" fill="#FFFFFF" rx="1" />
    <rect x="15" y="0" width="13" height="13" fill="#FFFFFF" rx="1" />
    <rect x="0" y="15" width="13" height="13" fill="#FFFFFF" rx="1" />
    <rect x="15" y="15" width="13" height="13" fill="#FFFFFF" rx="1" />
  </g>

  <!-- Typography -->
  <text x="56" y="28" fill="#FFFFFF" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" font-size="14.5" font-weight="700">Download for Windows</text>
  <text x="56" y="46" fill="#D6ECFF" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" font-size="11" font-weight="500">Windows 10 / 11 • 64-bit EXE</text>

  <!-- Download Arrow Icon -->
  <g transform="translate(212, 24)" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M4 1v10" />
    <path d="M1 8l3 3 3-3" />
    <path d="M0 15h8" />
  </g>
</svg>"""

MAC_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="240" height="64" viewBox="0 0 240 64" fill="none">
  <defs>
    <linearGradient id="mac-grad" x1="0" y1="0" x2="240" y2="64" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#242426" />
      <stop offset="100%" stop-color="#141416" />
    </linearGradient>
    <filter id="mac-shadow" x="-4" y="-2" width="248" height="72" filterUnits="userSpaceOnUse">
      <feDropShadow dx="0" dy="4" stdDeviation="4" flood-color="#000000" flood-opacity="0.3" />
    </filter>
  </defs>
  <!-- Background Card -->
  <rect x="2" y="2" width="236" height="60" rx="12" fill="url(#mac-grad)" stroke="#4A4A4F" stroke-width="1.5" filter="url(#mac-shadow)" />

  <!-- Apple Official Logo -->
  <g transform="translate(20, 16)" fill="#FFFFFF">
    <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.81-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M15.97 6.42c.66-.82 1.11-1.96.99-3.1-.96.04-2.12.64-2.8 1.44-.61.71-1.15 1.87-1 2.98 1.07.08 2.15-.5 2.81-1.32z"/>
  </g>

  <!-- Typography -->
  <text x="56" y="28" fill="#FFFFFF" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" font-size="14.5" font-weight="700">Download for macOS</text>
  <text x="56" y="46" fill="#A1A1A6" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" font-size="11" font-weight="500">Apple Silicon &amp; Intel • DMG</text>

  <!-- Download Arrow Icon -->
  <g transform="translate(212, 24)" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M4 1v10" />
    <path d="M1 8l3 3 3-3" />
    <path d="M0 15h8" />
  </g>
</svg>"""

LINUX_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="240" height="64" viewBox="0 0 240 64" fill="none">
  <defs>
    <linearGradient id="linux-grad" x1="0" y1="0" x2="240" y2="64" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#21262D" />
      <stop offset="100%" stop-color="#161B22" />
    </linearGradient>
    <filter id="linux-shadow" x="-4" y="-2" width="248" height="72" filterUnits="userSpaceOnUse">
      <feDropShadow dx="0" dy="4" stdDeviation="4" flood-color="#000000" flood-opacity="0.3" />
    </filter>
  </defs>
  <!-- Background Card -->
  <rect x="2" y="2" width="236" height="60" rx="12" fill="url(#linux-grad)" stroke="#F5A623" stroke-width="1.5" filter="url(#linux-shadow)" />

  <!-- Linux Tux Logo -->
  <g transform="translate(18, 16)">
    <ellipse cx="14" cy="18" rx="10" ry="12" fill="#FFFFFF" />
    <ellipse cx="14" cy="17" rx="8" ry="10" fill="#161B22" />
    <ellipse cx="14" cy="19" rx="6" ry="7" fill="#FFFFFF" />
    <circle cx="11.5" cy="14" r="1.5" fill="#161B22" />
    <circle cx="16.5" cy="14" r="1.5" fill="#161B22" />
    <!-- Beak -->
    <polygon points="12,17 16,17 14,21" fill="#F5A623" />
    <!-- Feet -->
    <ellipse cx="9" cy="28" rx="4" ry="2" fill="#F5A623" />
    <ellipse cx="19" cy="28" rx="4" ry="2" fill="#F5A623" />
  </g>

  <!-- Typography -->
  <text x="56" y="28" fill="#FFFFFF" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" font-size="14.5" font-weight="700">Download for Linux</text>
  <text x="56" y="46" fill="#F5A623" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" font-size="11" font-weight="500">Universal AppImage &amp; DEB</text>

  <!-- Download Arrow Icon -->
  <g transform="translate(212, 24)" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M4 1v10" />
    <path d="M1 8l3 3 3-3" />
    <path d="M0 15h8" />
  </g>
</svg>"""

(ASSETS / "download_windows.svg").write_text(WINDOWS_SVG, encoding="utf-8")
(ASSETS / "download_mac.svg").write_text(MAC_SVG, encoding="utf-8")
(ASSETS / "download_linux.svg").write_text(LINUX_SVG, encoding="utf-8")
print("Saved SVGs in assets/")
