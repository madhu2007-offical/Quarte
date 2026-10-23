# Carbon Design System Restyle

The Quarte Streamlit dashboard has been restyled to adhere to the **Carbon Design System** (the design language of the IBM Quantum Platform): clean, square, grid-based, data-dense, and calm.

---

## 1. Design Tokens & Palette

### Carbon White Theme (Default)
- **Page Background**: `#ffffff`
- **Tile / Layer Background**: `#f4f4f4`
- **Subtle Border**: `#e0e0e0`
- **Strong Border**: `#8d8d8d`
- **Text Primary**: `#161616`
- **Text Secondary**: `#525252`
- **Interactive Blue**: `#0f62fe` (hover `#0353e9`, active `#002d9c`)
- **Focus Ring**: `2px solid #0f62fe`
- **Header Bar**: `#161616` (height 48px, white text)
- **Status Colors**:
  - Success: `#198038`
  - Error: `#da1e28`
  - Warning: `#f1c21b`
  - Info: `#0043ce`

### Chart Palette (Sequential Carbon Order)
1. `#6929c4` (Purple)
2. `#1192e8` (Cyan)
3. `#005d5d` (Teal)
4. `#9f1853` (Magenta)
5. `#fa4d56` (Red)
6. `#002d9c` (Blue)
7. `#198038` (Green)

---

## 2. Typography & Offline Font Bundling

- **UI Typography**: IBM Plex Sans (weights 400 to 600, sentence case, no uppercase shouting, body 14px, helper 12px).
- **Code & Numbers**: IBM Plex Mono (job IDs, gate counts, deltas, code).
- **Offline Operation**: Font files are bundled directly in `dashboard/static/fonts/`:
  - `IBMPlexSans.ttf`
  - `IBMPlexMono-Regular.ttf`
  - `IBMPlexMono-SemiBold.ttf`
  Loaded locally via `@font-face` and Streamlit static serving (`enableStaticServing = true` in `.streamlit/config.toml`), with full system-ui fallbacks. Matplotlib fonts are registered via `matplotlib.font_manager.addfont()` to operate entirely offline without network access.

---

## 3. Component Styling

1. **Top Header Bar**: Fixed 48px `#161616` bar with product name `"Quarte"` on the left in white plain text, and tag `"Noisy simulation + saved hardware runs"` on the right.
2. **Side Navigation**: Left sidebar styled as side navigation (`Overview`, `Optimize`, `Benchmarks`, `Noisy simulation`, `Hardware runs`). Selected item features a `3px solid #0f62fe` left border and `#e8e8e8` background.
3. **Content Grid**: 0px border-radius, 1px `#e0e0e0` borders, `#f4f4f4` tile backgrounds, zero drop shadows.
4. **Square Buttons**: 48px tall, 0px border-radius, primary blue `#0f62fe` with hover/active transitions and visible keyboard focus rings.
5. **Metrics Tiles**: Large 32px light weight numbers with 12px secondary labels.
6. **Equivalence Notification**: Inline notification bar with 3px left border (`#198038` green PASS, `#da1e28` red FAIL).
7. **Jobs List Tables**: Hardware jobs tagged with green `"Completed"` pill; dry-run simulation jobs tagged with gray `"Simulation"` pill.
8. **Matplotlib Visualizations**: Styled with `style_carbon_ax` (no top/right spines, `#e0e0e0` gridlines, `#161616` error bars, direct labels, legends below plot).
9. **Circuit Drawings**: Native Qiskit Matplotlib drawer using `style="iqp"`.

---

## 4. Visual Verification Screenshots

- **Before Restyle**: `docs/dashboard_before.png`
- **After Restyle (Viewport)**: `docs/dashboard_carbon.png`
- **After Restyle (Full Page)**: `docs/dashboard_carbon_full.png`

---

## 5. Trademark & Attribution Disclaimer

Interface styled after the open-source Carbon Design System. Not affiliated with or endorsed by IBM. Hardware results come from jobs run on IBM Quantum through a user account.
