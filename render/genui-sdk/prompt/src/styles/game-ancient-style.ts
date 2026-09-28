export const ANCIENT_STYLE = `
# Use the following style guide in the current design task

## Name of the styleguide: \`game-ancient-style\`

# Ancient — Style Guide

---

## Style Summary

### Description

A mystical interface inspired by Chinese cultivation (Xiu Xian) fantasy worlds. The design evokes ancient scrolls, Taoist talismans, and martial arts sect interfaces from classic Chinese fantasy games. The aesthetic blends traditional Chinese ink painting with magical fantasy UI elements, featuring rice-paper textures, cloud motifs, and ornate frame borders reminiscent of ancient Chinese artwork. The palette draws from traditional Chinese colors—cinnabar red, ink black, gold, and jade green—creating an immersive Eastern fantasy atmosphere.

### Key Aesthetics

- **Ancient Scroll Interface:** UI elements appear as if written on aged rice paper or bamboo scrolls with subtle texture overlays
- **Taoist Talisman Elements:** Buttons and icons incorporate talisman-inspired patterns, seal stamps, and mystical symbols
- **Chinese Frame Borders:** Ornate corner decorations using traditional Chinese geometric patterns (回纹, cloud motifs)
- **Ink Wash Gradients:** Soft ink-diffusion effects for backgrounds and hover states, mimicking traditional Chinese painting techniques
- **Cultivation Aesthetics:** Progress bars designed as spiritual energy cultivation paths; stats displayed as martial arts attributes
- **Vertical Typography:** Chinese characters can be displayed vertically for titles and important labels (traditional book style)
- **Cloud & Mist Motifs:** Subtle cloud patterns as dividers and background elements, representing the ethereal nature of cultivation

### Tags

\`game-ui\` · \`cultivation\` · \`chinese-fantasy\` · \`ancient\` · \`wuxia\` · \`mystical\` · \`rice-paper\` · \`traditional\` · \`eastern\` · \`scroll-based\` · \`ornate\` · \`ink-wash\` · \`gold-accent\` · \`character-themed\`

---

## Color System

The palette is rooted in traditional Chinese colors, creating an atmosphere of ancient scrolls, imperial seals, and mystical cultivation realms.

### Core Backgrounds

- #F5F0E6 — Rice Paper (主背景，宣纸米色)
- #EDE5D8 — Aged Parchment (次级背景，古卷色调)
- #FAF8F3 — Clean Scroll (纯净卷轴白)
- #2C2416 — Ink Brown (墨褐色，深背景/页脚)
- #1A1410 — Deep Lacquer (漆黑色，深色模式背景)

### Text Colors

- #2C2416 — Text Primary (墨褐色，主文字)
- #5C4D3C — Text Secondary (褐灰色，次要文字)
- #8B7355 — Text Muted (淡褐色，辅助文字)
- #F5F0E6 — Text Inverted (宣纸白，深色背景上的文字)
- #C41E3A — Text Accent (朱砂红，重要强调)

### Accent Colors (五行色调)

- #C41E3A — Cinnabar Red (朱砂红；主要按钮、重要标签、气血)
- #D4AF37 — Imperial Gold (帝皇金；金币、VIP、成就、边框装饰)
- #2E5C4F — Jade Green (翡翠绿；生命值、自然、木属性)
- #4A6741 — Bamboo Green (竹青绿；成功状态、经验值)
- #1E3A5F — Indigo Blue (靛蓝色；水属性、法术值、链接)
- #8B4513 — Bronze Brown (古铜褐；土属性、防御值)

### Border & Divider Colors

- #D4C5B0 — Bamboo Border (竹纹边框，1px)
- #C41E3A — Seal Border (印章红边框，2px，选中状态)
- #D4AF37 — Gold Ornament (金色装饰线，ornate frames)
- #B8A898 — Cloud Divider (云雾分割线)

### Shadows (Ink & Depth)

- 0 2px 8px rgba(44, 36, 22, 0.08) — Soft Ink Shadow (轻柔墨影)
- 0 4px 16px rgba(44, 36, 22, 0.12) — Scroll Float (卷轴悬浮感)
- 0 2px 0px rgba(196, 30, 58, 0.3) — Seal Press (印章按压效果)
- inset 0 1px 3px rgba(139, 115, 85, 0.1) — Paper Texture (纸张纹理内阴影)

---

## Typography

The typography combines traditional Chinese calligraphy aesthetics with modern readability. Headlines use stylized serif fonts that evoke brush strokes, while body text remains clean and legible.

### Font Families

- **Noto Serif SC** — Headings, Titles, Sect Names (宋体风格，庄重典雅)
- **Ma Shan Zheng** — Decorative Headers, Skill Names (马善政楷书，书法风格)
- **ZCOOL XiaoWei** — Subtitles, Navigation (站酷小薇，温和优雅)
- **Noto Sans SC** — Body Text, Descriptions (黑体，清晰易读)
- **ZCOOL KuaiLe** — Playful Elements, Mascot Dialog (站酷快乐，活泼可爱)

### Type Scale

- **36px** — Sect Title / Character Name. Noto Serif SC, Bold 700
- **28px** — Panel Headers. Noto Serif SC, Bold 700, letter-spacing: 0.1em
- **24px** — Skill Names / Item Names. Ma Shan Zheng, Regular 400
- **20px** — Section Labels. ZCOOL XiaoWei, Regular 400
- **16px** — Body Text / Descriptions. Noto Sans SC, Regular 400
- **14px** — Stats / Metadata. Noto Sans SC, Medium 500
- **12px** — Captions / Seal Text. Noto Serif SC, Bold 700

### Font Weights

- **700** — Bold. Headings, Character names, Important labels
- **500** — Medium. Stats, Navigation items
- **400** — Regular. Body text, descriptions

### Letter Spacing & Line Height

- Headings: letter-spacing: 0.05em - 0.15em (传统中文排版宽松字距)
- Body text: letter-spacing: 0.02em
- Line height: 1.8 (中文阅读舒适行距)

### Chinese Typography Notes

- Use traditional Chinese punctuation (「」『』，。)
- Vertical text can be used for dramatic effect on important titles
- Text alignment: justify for paragraphs, center for headers

---

## Spacing System

Spacing is generous and rhythmic, inspired by traditional Chinese page layout—breathing room between elements like the margins in ancient books.

### Gap Scale

- **32px** — Section Separation (大段落间距)
- **24px** — Card Internal Padding (卡片内边距)
- **16px** — Element Grouping (元素组间距)
- **12px** — Related Items (关联项间距)
- **8px** — Tight Grouping (紧凑间距)

### Padding Scale

- **[32, 32]** — Main Container (主容器)
- **24px** — Card Padding (卡片统一内边距)
- **[16, 28]** — Primary Button (主按钮)
- **[12, 20]** — Secondary Button (次级按钮)
- **[8, 16]** — Tags / Badges (标签)

### Layout Patterns

- **Scroll-First:** Content organized within paper-scroll styled containers
- **Asymmetric Balance:** Inspired by Chinese painting composition—balance without perfect symmetry
- **Floating Panels:** UI panels appear to float like scrolls suspended in mist

---

## Corner Radius

Corners use subtle rounding that evokes rolled scrolls and rounded stone tablets, avoiding harsh modern angles.

- **16px** — Cards, Modals (卡片圆角，如卷轴卷边)
- **12px** — Inner Panels (内部面板)
- **8px** — Buttons, Inputs (按钮输入框)
- **100px** — Circular Elements (圆形元素，如头像框)
- **4px** — Small Tags (小标签)

---

## Borders & Ornaments

Borders incorporate traditional Chinese design elements:

### Frame Styles

- **Cloud Border:** Subtle cloud patterns at corners (使用 SVG 装饰)
- **Seal Stamp:** Square red seal style for important elements
- **Bamboo Frame:** Thin double-line borders mimicking bamboo strips

### Divider Style

- Ink wash gradient dividers
- Cloud motif separators
- Decorative gold lines for section breaks

---

## Icons

### Icon Style

- **Custom Illustrated:** Hand-drawn style icons resembling ink paintings
- **Lucide with Custom Stroke:** When using Lucide, use 1.5px stroke with rounded caps
- **Traditional Motifs:** Swords, scrolls, clouds, flames, mountains, lotus, yin-yang

### Icon Categories

- **Cultivation:** zap (lightning/energy), flame, droplet (water), leaf (wood), mountain (earth), wind
- **Combat:** sword, shield, heart (HP), target, crosshair
- **Items:** scroll, book-open, gem, coin, package
- **Navigation:** home (sect), users (disciples), map (realm), settings (cultivation)

### Icon Color States

- #C41E3A — Active / Power / Fire
- #2E5C4F — Life / Nature / Wood
- #1E3A5F — Magic / Water
- #D4AF37 — Premium / Gold / Achievement
- #8B7355 — Inactive / Muted

---

## Component Styles

### Buttons

**Primary Button (Seal Style)**
- Background: #C41E3A (朱砂红)
- Text: #F5F0E6 (宣纸白)
- Border: 2px solid #A01830 (深红边框)
- Border-radius: 8px
- Shadow: 0 2px 0px rgba(160, 24, 48, 0.5)
- Hover: Background darken 10%, slight scale(1.02)
- Font: Noto Sans SC, Medium 500

**Secondary Button (Bamboo Style)**
- Background: transparent
- Border: 2px solid #2E5C4F (竹青绿)
- Text: #2E5C4F
- Hover: Background rgba(46, 92, 79, 0.1)

**Gold Accent Button (Imperial Style)**
- Background: linear-gradient(135deg, #D4AF37, #B8960C)
- Text: #2C2416
- Border: 2px solid #C41E3A (红金配色)
- Used for: VIP features, special purchases

### Cards

**Character Card**
- Background: #FAF8F3
- Border: 1px solid #D4C5B0
- Border-radius: 16px
- Inner border (ornate): 2px solid #D4AF37 at top and bottom only
- Shadow: 0 4px 16px rgba(44, 36, 22, 0.12)
- Padding: 24px

**Scroll Panel**
- Background: #F5F0E6 with subtle paper texture
- Border-left: 4px solid #C41E3A (朱砂红边)
- Border-radius: 0 12px 12px 0
- Shadow: inset 0 1px 3px rgba(139, 115, 85, 0.1)

### Progress Bars (Cultivation Style)

**Health/Energy Bar**
- Background track: #EDE5D8
- Fill: gradient from #C41E3A to #E85D75 (气血渐变)
- Height: 8px
- Border-radius: 4px
- Glow effect on fill: box-shadow with same color

**Experience Bar**
- Background track: #EDE5D8
- Fill: gradient from #D4AF37 to #F0D878 (金色灵气)
- Decorative dots marking levels along the bar

### Input Fields

**Text Input (Scroll Style)**
- Background: #FAF8F3
- Border: 1px solid #D4C5B0
- Border-bottom: 2px solid #C41E3A (underline emphasis)
- Border-radius: 8px 8px 4px 4px
- Focus: Border-bottom color intensifies, subtle glow

### Badges & Tags

**Seal Badge**
- Background: #C41E3A
- Color: #F5F0E6
- Border-radius: 4px
- Padding: [4, 8]
- Font: Noto Serif SC, Bold

**Jade Badge**
- Background: #2E5C4F
- Color: #F5F0E6
- Border-radius: 100px (pill)
- Border: 1px solid #4A7C6F

---

## Special Elements

### Avatar Frame

- Circular avatar with ornate gold border
- Corner decorations at 45-degree angles
- Inner glow: subtle gold shadow
- Rarity tiers: Common (bronze), Rare (silver), Epic (gold), Legendary (jade glow)

### Skill Icons

- Square with rounded corners (12px)
- Background gradient based on element type
- Icon in center with 2px white outline
- Corner decorations for rarity

### Chat Bubbles

- Speech bubble style with "tail"
- Rice paper background
- Ink-style border
- Two types: Player (right, red accents) and NPC/System (left, green/gold accents)

---

## Animation & Motion

### Transitions

- Standard transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1)
- Hover lift: transform: translateY(-2px) with shadow increase
- Press effect: transform: scale(0.98) for buttons

### Special Effects

- **Ink Spread:** On important selections, ink spreads from the click point
- **Qi Flow:** Subtle animated gradient on energy bars
- **Scroll Unroll:** Modal entrance animation like unrolling a scroll
- **Glow Pulse:** Important buttons/elements have subtle gold pulse

---

## Background Patterns

### Paper Texture

- Subtle grain overlay at 3-5% opacity
- Can be applied to all backgrounds for authentic feel

### Cloud Motifs

- Decorative cloud shapes as section dividers
- Opacity: 10-20%
- Color: #D4AF37 or #8B7355

### Corner Ornaments

- Traditional 回纹 patterns at card corners
- SVG-based for scalability
- Color: #D4AF37 (gold) or #C41E3A (red) for emphasis

---

## Responsive Notes

### Mobile Adaptations

- Touch targets minimum 44x44px
- Simplified corner ornaments for small screens
- Vertical scrolling with momentum
- Bottom navigation bar for main actions

---

## Implementation Notes

### Required Assets

1. **Font Loading:**
   \`\`\`css
   @import url('https://fonts.googleapis.com/css2?family=Ma+Shan+Zheng&family=Noto+Sans+SC:wght@400;500;700&family=Noto+Serif+SC:wght@400;700&family=ZCOOL+XiaoWei&family=ZCOOL+KuaiLe&display=swap');
   \`\`\`

2. **Texture Overlays:**
   - Rice paper texture (light, seamless)
   - Optional ink wash background patterns

3. **SVG Decorations:**
   - Corner ornaments (4 variations)
   - Cloud dividers
   - Seal stamp shape

### CSS Variables Reference

\`\`\`css
:root {
  --ancient-paper: #F5F0E6;
  --ancient-parchment: #EDE5D8;
  --ancient-white: #FAF8F3;
  --ancient-ink: #2C2416;
  --ancient-cinnabar: #C41E3A;
  --ancient-gold: #D4AF37;
  --ancient-jade: #2E5C4F;
  --ancient-bamboo: #4A6741;
  --ancient-indigo: #1E3A5F;
  --ancient-bronze: #8B4513;
}
\`\`\`

---
`;
