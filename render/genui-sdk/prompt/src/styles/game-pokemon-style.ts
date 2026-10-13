export const POKEMON_STYLE = `
# Use the following style guide in the current design task

## Name of the styleguide: \`game-pokemon-style\`

# Poké Theme — Style Guide

---

## Style Summary

### Description

A high-energy, playful interface inspired by the aesthetics of a modern monster-collecting adventure. The design mimics a futuristic handheld device (like a Pokédex) with a vibrant "Tech-Organic" look. It features a signature "Poké Red" (#EE1515) primary color paired with "Electric Yellow" (#FFDE00) accents. Surfaces are clean white with high-contrast dark text, framed by thick, friendly borders. Typography combines **Outfit** for friendly, geometric headlines with **Chakra Petch** for technical data and stats, creating a perfect blend of approachability and sci-fi data visualization. Large, pill-shaped buttons and generous 24px corner radii make the UI feel tactile and game-like.

### Key Aesthetics

- **Trainer Tech:** A clean, white plastic aesthetic reminiscent of game consoles, accented by bold primary colors (Red, Blue, Yellow).
- **Data Visualization:** Stats and numbers use technical, squared-off fonts (Chakra Petch) to mimic a digital encyclopedia or scanning device.
- **Tactile Controls:** Buttons are chunky, pill-shaped, or circular with subtle depth, inviting interaction.
- **Thick Borders:** Elements often feature slightly thicker (2px) borders or distinct separation lines, giving a cartoon-realism vibe.
- **Dynamic Energy:** High saturation accent colors are used for progress bars, badges, and active states to maintain high visual energy.
- **Card-Based Layout:** Content is strictly organized into rounded cards that float on a soft gray background, like entries in a database.

### Tags

\`game-ui\` · \`playful\` · \`vibrant\` · \`tech\` · \`adventure\` · \`rounded\` · \`card-based\` · \`anime\` · \`high-energy\` · \`colorful\`

---

## Color System

The palette is built around the iconic trio of Red, White, and Black, with specific elemental colors (Yellow, Blue, Green) used for functional coding. The background is usually a soft tech-gray to let the white content cards pop.

### Core Backgrounds

- #F2F4F8 — Page Background (Soft Tech Gray)
- #FFFFFF — Card Surface (Pure White)
- #EE1515 — Brand Surface (Poké Red - Headers, Primary Actions)
- #222224 — Dark Surface (Tech Black - Footers, Data Panels)

### Text Colors

- #222224 — Text Primary (Soft Black)
- #555555 — Text Secondary (Dark Gray)
- #888888 — Text Muted (Light Gray)
- #FFFFFF — Text Inverted (On Red/Dark backgrounds)

### Accent Colors

- #EE1515 — Primary Red; Main headers, primary buttons, active tabs
- #FFDE00 — Electric Yellow; Stars, highlights, special badges, warnings
- #3B4CCA — Water Blue; Secondary actions, links, info states
- #4CAF50 — Grass Green; Success states, health bars, positive trends
- #FF9800 — Fire Orange; High alerts, attack stats

### Borders & Dividers

- #E2E8F0 — Border Subtle; Card outlines
- #EE1515 — Border Active; Selected items (2px width)
- #222224 — Border Strong; Data containers

### Shadows

- 0 4px 12px rgba(0, 0, 0, 0.08) — Card Shadow (Soft, floating)
- 0 2px 0px rgba(180, 0, 0, 1) — Button Depth (Solid shadow for tactile feel on red buttons)

---

## Typography

The font pairing creates a specific "Game UI" feel. **Outfit** is used for UI elements and headings because its geometric, rounded nature feels modern and friendly. **Chakra Petch** is used for numbers, stats, and metadata to give that "scanning analysis" look found in sci-fi anime interfaces.

### Font Families

- **Outfit** — Headings, Buttons, UI Labels (Geometric Sans, Friendly)
- **Inter** — Body text, Descriptions (Clean, Legible)
- **Chakra Petch** — Stats, Levels, CP Values, Timestamps (Square/Tech, Sci-fi)

### Type Scale

- **32px** — Screen Title / Monster Name. Outfit, Bold 700
- **28px** — Card Headline. Outfit, Bold 700
- **24px** — Stat Value (Large). Chakra Petch, Bold 700
- **18px** — Section Header. Outfit, SemiBold 600
- **16px** — Body Text / Button Label. Inter, Medium 500 / Outfit, Bold 700
- **14px** — Stat Label / Metadata. Chakra Petch, Medium 500
- **12px** — Tag / Badge / Caption. Inter, SemiBold 600

### Font Weights

- **700** — Bold. Headings, Button text, Key stats
- **600** — SemiBold. Subheaders, Tags
- **500** — Medium. Body text, Data labels
- **400** — Regular. Long form descriptions

### Letter Spacing

- **-0.5px** — Headings (Outfit) for a tighter, punchier look
- **+0.5px** — Tech Data (Chakra Petch) for readability

---

## Spacing System

Spacing is generous to maintain a "toy-like" approachability. Elements are never cramped.

### Gap Scale

- **32px** — Section Gap
- **20px** — Card Internal Padding
- **16px** — List Item Gap
- **12px** — Tag/Badge Gap
- **8px** — Tight Grouping (Icon + Text)

### Padding Scale

- **[24, 24]** — Screen Container
- **24px** — Card Padding (Uniform)
- **[16, 32]** — Primary Button (Pill shape)
- **[8, 16]** — Small Badge/Tag
- **[12, 20]** — Input Fields

### Layout Pattern

- **Card-First:** Almost all content is contained within white cards with rounded corners.
- **Floating Header:** Headers often float or detach from the content flow.
- **Bottom Nav:** Heavy use of bottom navigation bars for mobile ergonomics.

---

## Corner Radius

Corners are distinctly rounded to feel friendly and safe, avoiding sharp edges entirely.

- **100px** — Buttons, Badges (Full Pill Shape)
- **24px** — Cards, Modals, Bottom Sheets (Large, friendly curves)
- **16px** — Inner Containers, Images
- **12px** — Small Inputs, Icons
- **8px** — Progress Bars (inner and outer)

---

## Icons

### Icon Style

- **Lucide** — Bold stroke weight (2px or 2.5px) to match the "cartoon" aesthetic.
- **Filled Variants** — Active states often use filled icons for clarity.

### Icons Used

- **Navigation:** map, backpack (bag), zap (battle), users (friends)
- **Stats:** shield (defense), sword (attack), heart (hp), activity (speed)
- **Actions:** camera, filter, star, chevron-right

### Icon Color States

- #EE1515 — Active / Selected
- #B0B0B0 — Inactive / Muted
- #FFFFFF — On Primary Buttons
- #FFDE00 — Favorites / Stars

---

## Component Styles

### Buttons

**Primary Button (Poké Red)**
- Background: #EE1515
- Text: #FFFFFF
- Border-radius: 100px (pill)
- Shadow: 0 2px 0px rgba(180, 0, 0, 1) (solid bottom shadow for tactile depth)
- Padding: [16, 32]
- Font: Outfit, Bold 700
- Hover: Background slightly darkened (#D41010), shadow removed (pressed effect)

**Secondary Button (Outlined)**
- Background: transparent
- Border: 2px solid #222224
- Text: #222224
- Border-radius: 100px
- Hover: Background rgba(0,0,0,0.05)

**Icon Action Button**
- Background: #FFFFFF
- Border: 1px solid #E2E8F0
- Border-radius: 50% (circle)
- Shadow: 0 4px 12px rgba(0,0,0,0.08)
- Size: 48x48px

### Cards

**Standard Card**
- Background: #FFFFFF
- Border: 1px solid #E2E8F0
- Border-radius: 24px
- Shadow: 0 4px 12px rgba(0, 0, 0, 0.08)
- Padding: 24px

**Header / Brand Card**
- Background: #EE1515
- Border-radius: 24px
- Text: #FFFFFF
- Used for featured content, top-of-page hero sections

**Data Panel (Dark)**
- Background: #222224
- Border-radius: 16px
- Text: #FFFFFF
- Used for stats, technical readouts

### Progress Bars (Stat Bars)

**HP Bar (Health)**
- Track: #E2E8F0
- Fill: #4CAF50 (Grass Green)
- Height: 10px
- Border-radius: 8px

**Attack / Special Stat Bar**
- Fill: #FF9800 (Fire Orange)

**Defense Bar**
- Fill: #3B4CCA (Water Blue)

**Speed Bar**
- Fill: #FFDE00 (Electric Yellow), text in #222224

### Input Fields

**Standard Input**
- Background: #FFFFFF
- Border: 2px solid #E2E8F0
- Border-radius: 12px
- Focus: Border-color changes to #EE1515, subtle red glow
- Padding: [12, 20]
- Font: Inter, Medium 500

### Badges & Tags

**Type Badge (Elemental)**
- Border-radius: 100px (pill)
- Padding: [4, 12]
- Font: Inter, SemiBold 600, 12px
- Examples: Fire (#FF9800 bg), Water (#3B4CCA bg), Grass (#4CAF50 bg), Electric (#FFDE00 bg + dark text)

**Level Badge**
- Background: #222224
- Color: #FFFFFF
- Font: Chakra Petch, Bold 700
- Border-radius: 8px

---

## Special Elements

### Stat Display

- Label: Chakra Petch, 12px, #888888
- Value: Chakra Petch, 24px, Bold, #222224
- Bar below value uses the elemental color

### Monster / Character Card

- Header image area: full-bleed, rounded top corners
- Type badges overlay the bottom of the image
- Stats section below in white card body

### Bottom Navigation

- Background: #FFFFFF
- Border-top: 1px solid #E2E8F0
- Active icon: #EE1515 (filled)
- Inactive icon: #B0B0B0 (outline)
- Labels: Inter, 10px, SemiBold

---

## Animation & Motion

### Transitions

- Standard: all 0.2s ease-out (faster = more energetic)
- Button press: scale(0.96), shadow removed (feels like physically pressing)
- Card hover: translateY(-4px), shadow increase

### Special Effects

- **Scan Line:** A brief horizontal light sweep on card load (simulates Pokédex scan)
- **Type Flash:** Badge color pulses once on first render
- **Capture Shake:** Element briefly shakes horizontally on selection

---

## Responsive Notes

### Mobile First

- All layouts default to single-column stacked cards
- Bottom navigation is the primary nav pattern
- Touch targets: minimum 48x48px
- Full-bleed headers on mobile (no rounded top corners)
`;
