/* global React */

/**
 * Claw Widget v15 design-system runtime.
 *
 * Public components intentionally preserve the class names and DOM hierarchy
 * from design_system.html. The CSS remains the geometry/visual source of truth;
 * these functions define the stable JSX and props contract used by generated
 * cards, the catalog bridge, and good-case JSX files.
 */
(function attachClawWidgetDesignSystem(global) {
  "use strict";

  const RUNTIME_STYLE_ID = "claw-widget-design-system-runtime-styles";
  const RUNTIME_STYLES = String.raw`
/* ── Design Tokens ────────────────────────────────── */
:root {
  /* ── HarmonyOS HMOS Design Tokens ─────────────────
     Neutrals: Snow Gray → Night Black
     Brand Blue anchor: #0A59F7 (HarmonyOS emphasize)
     Functional: connected #64BB5C · alert #ED6F21 · warning #E84026 */
  /* ═══ HarmonyOS Design Tokens ═══
     色值来源：HarmonyOS Component Library.sketch · sharedSwatches
     · 文本 / 边框 / 蒙层采用 black-alpha / white-alpha 叠加
     · 语义色 anchor 取自 ohos_id_color_* 与 palette 色板
  */
  --gray-0:#fff; --gray-25:#fafafa; --gray-50:#f5f5f5; --gray-75:#f0f0f0; --gray-100:#ebebeb;
  --gray-150:#e0e0e0; --gray-200:#d4d4d4; --gray-250:#c7c7c7; --gray-300:#b3b3b3;
  --gray-350:#a0a0a0; --gray-400:#8c8c8c; --gray-450:#787878; --gray-500:#666666;
  --gray-550:#545454; --gray-600:#454545; --gray-650:#383838; --gray-700:#2d2d2d;
  --gray-750:#242424; --gray-800:#1d1d1d; --gray-850:#181818; --gray-900:#141414;
  --gray-950:#0f0f0f; --gray-975:#0a0a0a; --gray-1000:#000;

  /* emphasize 品牌色 · anchor #0A59F7 (ohos_id_color_emphasize / palette8) */
  --blue-25:#f4f7ff; --blue-50:#e8efff; --blue-75:#d1dfff; --blue-100:#a9c1ff;
  --blue-200:#7a9fff; --blue-300:#4b7dff; --blue-400:#0a59f7; --blue-500:#0847cc;
  --blue-600:#0637a3; --blue-700:#052b80; --blue-800:#04205e; --blue-900:#03173f;

  /* connected 确认色 · anchor #64BB5C (ohos_id_color_connected / palette4) */
  --green-25:#f1faef; --green-50:#e0f4dd; --green-75:#c2e7bd; --green-100:#a0d79a;
  --green-200:#87cc80; --green-300:#73c16b; --green-400:#64bb5c; --green-500:#4ea047;
  --green-600:#3c8336; --green-700:#2d6628; --green-800:#1e481b; --green-900:#122e10;

  /* warning 一级警示色 · anchor #E84026 (ohos_id_color_warning / ohos_id_color_handup) */
  --red-25:#fef3f1; --red-50:#fde4e0; --red-75:#fbc9c1; --red-100:#f7a096;
  --red-200:#f27a6b; --red-300:#ed5a46; --red-400:#e84026; --red-500:#c4321c;
  --red-600:#a02614; --red-700:#7c1c0e; --red-800:#581308; --red-900:#380b04;

  /* alert 二级警示色 · anchor #ED6F21 (ohos_id_color_alert / palette9) */
  --orange-25:#fff6ef; --orange-50:#ffebd9; --orange-75:#ffd4ae; --orange-100:#ffba7d;
  --orange-200:#fb9e51; --orange-300:#f48533; --orange-400:#ed6f21; --orange-500:#c85a19;
  --orange-600:#a24712; --orange-700:#7c360c; --orange-800:#562507; --orange-900:#371704;

  /* yellow · anchor #F7CE00 (palette11) */
  --yellow-25:#fffef0; --yellow-50:#fffbd0; --yellow-75:#fff6a0; --yellow-100:#ffed6e;
  --yellow-200:#ffe344; --yellow-300:#fcd824; --yellow-400:#f7ce00; --yellow-500:#cca900;
  --yellow-600:#a38500; --yellow-700:#7a6300; --yellow-800:#524200; --yellow-900:#342900;

  /* purple · anchor #AC49F5 (palette6) */
  --purple-25:#faf2ff; --purple-50:#f3e0ff; --purple-75:#e4c2fe; --purple-100:#d39dfa;
  --purple-200:#c276f6; --purple-300:#b85ff5; --purple-400:#ac49f5; --purple-500:#8c3bcc;
  --purple-600:#702fa3; --purple-700:#54247b; --purple-800:#3a1957; --purple-900:#230f36;

  /* pink · anchor #E64566 (palette7) */
  --pink-25:#fef3f5; --pink-50:#fde1e7; --pink-75:#fac2cf; --pink-100:#f59ab0;
  --pink-200:#ef7690; --pink-300:#eb5c7b; --pink-400:#e64566; --pink-500:#c0374f;
  --pink-600:#9a2c3f; --pink-700:#75212f; --pink-800:#52161f; --pink-900:#330c12;

  /* cyan · anchor #61CFBE (palette3) */
  --cyan-25:#edfbf9; --cyan-50:#d7f5f1; --cyan-75:#b1ecde; --cyan-100:#8adfd3;
  --cyan-200:#74d5c8; --cyan-300:#6bd2c3; --cyan-400:#61cfbe; --cyan-500:#4fac9e;
  --cyan-600:#3f897e; --cyan-700:#306860; --cyan-800:#214944; --cyan-900:#142e2a;

  --white:#fff;

  /* ── 1.3.1 背景模板：v15 单色纯色 + 融球 ── */
  --card-bg-solid-white:#FFFFFF;
  --card-bg-solid-blue:#E5EDFE;
  --card-bg-solid-orange:#FFF3E6;
  --card-bg-solid-green:#F0FFE6;
  --card-bg-solid-cyan:#E6FDFF;
  --card-bg-solid-purple:#EDE6FF;
  --card-bg-solid-white-content:#000000;
  --card-bg-solid-blue-content:#1f4799;
  --card-bg-solid-orange-content:#99661f;
  --card-bg-solid-green-content:#52991f;
  --card-bg-solid-cyan-content:#1f8f99;
  --card-bg-solid-purple-content:#401f99;

  /* 融球背景·四组配色 */
  --card-bg-orb-orange-right-bottom-color:#FAA89E;
  --card-bg-orb-orange-left-bottom-color:#FF8E3E;
  --card-bg-orb-orange-top-color:#BF3F26;
  --card-bg-orb-blue-right-bottom-color:rgba(82,204,204,1);
  --card-bg-orb-blue-left-bottom-color:rgba(143,162,217,1);
  --card-bg-orb-blue-top-color:rgba(18,30,89,1);
  --card-bg-orb-purple-right-bottom-color:rgba(179,152,217,1);
  --card-bg-orb-purple-left-bottom-color:rgba(87,97,217,1);
  --card-bg-orb-purple-top-color:rgba(27,18,89,1);
  --card-bg-orb-green-right-bottom-color:rgba(96,191,152,1);
  --card-bg-orb-green-left-bottom-color:rgba(38,191,166,1);
  --card-bg-orb-green-top-color:rgba(23,115,76,1);

  /* 融球几何 — 相对宿主卡片尺寸，圆角随卡片 */
  --card-bg-orb-right-bottom-size:62.5%;
  --card-bg-orb-right-bottom-x:60%;
  --card-bg-orb-right-bottom-y:50%;
  --card-bg-orb-left-bottom-size:100%;
  --card-bg-orb-left-bottom-x:-25%;
  --card-bg-orb-left-bottom-y:43.75%;
  --card-bg-orb-top-size:131.25%;
  --card-bg-orb-top-x:-15.625%;
  --card-bg-orb-top-y:-56.25%;
  --card-bg-orb-backplate:rgba(255,255,255,.05);
  --card-bg-orb-blur:50px;

  --radius-2xs:.125rem; --radius-xs:.25rem; --radius-sm:.375rem; --radius-md:.5rem; --radius-lg:.625rem;
  --radius-xl:.75rem; --radius-2xl:1rem; --radius-3xl:1.25rem; --radius-4xl:1.5rem; --radius-full:9999px;

  /* ── HarmonyOS semantic tokens (Light) ──
     text/border 采用 black-alpha，对应 ohos_id_color_text_* / list_separator / component_normal
     surface 对应 ohos_id_color_background / sub_background / card_bg */
  --surface:#fff;         /* ohos_id_color_card_bg / background */
  --surface-2:#f1f3f5;    /* ohos_id_color_sub_background / panel_bg */
  --surface-3:#f1f3f5;    /* ohos_id_color_sub_background */
  --text:rgba(0,0,0,.902);     /* ohos_id_color_text_primary */
  --text-2:rgba(0,0,0,.6);     /* ohos_id_color_text_secondary / text_hint */
  --text-3:rgba(0,0,0,.4);     /* ohos_id_color_text_tertiary */
  --border:rgba(0,0,0,.05);       /* ohos_id_color_list_separator */
  --border-strong:rgba(0,0,0,.102); /* ohos_id_color_component_normal */
  --sh1:0 1px 2px -1px rgba(0,0,0,.08);
  --sh2:0 2px 4px -1px rgba(0,0,0,.08);
  --sh3:0 4px 8px -2px rgba(0,0,0,.10);
  --sh4:0 8px 16px -4px rgba(0,0,0,.12);
  --font:"HarmonyOS Sans SC","HarmonyOS Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,"PingFang SC","Microsoft YaHei",sans-serif;
  --mono:ui-monospace,"SF Mono","Menlo",monospace;

  /* ── Typography Scale Tokens ── */
  --fs-dl:3.5rem; --fw-dl:300; /* Display_L · 56px · Light */
  --fs-dm:3rem;   --fw-dm:300; /* Display_M · 48px · Light */
  --fs-ds:2.375rem;--fw-ds:300;/* Display_S · 38px · Light */
  --fs-tl:1.875rem;--fw-tl:700;/* Title_L   · 30px · Bold */
  --fs-tm:1.5rem;  --fw-tm:700;/* Title_M   · 24px · Bold */
  --fs-ts:1.25rem; --fw-ts:700;/* Title_S   · 20px · Bold */
  --fs-stl:1.125rem;--fw-stl:500;/* Subtitle_L· 18px · Medium */
  --fs-stm:1rem;   --fw-stm:500;/* Subtitle_M· 16px · Medium */
  --fs-sts:.875rem;--fw-sts:500;/* Subtitle_S· 14px · Medium */
  --fs-bl:1rem;    --fw-bl:400; /* Body_L    · 16px · Regular */
  --fs-bm:.875rem; --fw-bm:400; /* Body_M    · 14px · Regular */
  --fs-bs:.75rem;  --fw-bs:400; /* Body_S    · 12px · Regular */
  --fs-cl:.75rem;  --fw-cl:500; /* Caption_L · 12px · Medium（组件可覆写 Regular） */
  --fs-cm:.625rem; --fw-cm:500; /* Caption_M · 10px · Medium（组件可覆写 Regular） */
  --fs-cs:.5rem;   --fw-cs:500; /* Caption_S · 8px  · Medium */

  /* ── Font Color Tokens ── */
  --font-primary:#000000;
  --font-secondary:rgba(0,0,0,.6);
  --font-tertiary:rgba(0,0,0,.4);
  --graphic-primary:#000000;
  --graphic-secondary:rgba(0,0,0,.60);
  --graphic-tertiary:rgba(0,0,0,.20);
  --top-text-bottom-value-divider:rgba(0,0,0,.2);

  /* ── Backplate Color Tokens · Light Mode ── */
  --comp_background_primary:#ffffff;
  --comp_background_secondary:rgba(0,0,0,.20);
  --comp_background_tertiary:rgba(0,0,0,.10);

  /* ── Progress Circle Tokens ── */
  --pc-track:rgba(0,0,0,.10);
  --pc-bar:#64bb5c;
  --pc-sm:44px; --pc-sm-sw:6px;
  --pc-md:96px; --pc-md-sw:6px;
}

[data-theme="dark"] {
  /* HarmonyOS dark palette — inverted Night Black scale */
  --gray-0:#000; --gray-25:#0a0a0a; --gray-50:#0f0f0f; --gray-75:#141414; --gray-100:#181818;
  --gray-150:#1d1d1d; --gray-200:#242424; --gray-250:#2d2d2d; --gray-300:#383838;
  --gray-350:#454545; --gray-400:#545454; --gray-450:#666666; --gray-500:#787878;
  --gray-550:#8c8c8c; --gray-600:#a0a0a0; --gray-650:#b3b3b3; --gray-700:#c7c7c7;
  --gray-750:#d4d4d4; --gray-800:#e0e0e0; --gray-850:#ebebeb; --gray-900:#f0f0f0;
  --gray-950:#f5f5f5; --gray-975:#fafafa; --gray-1000:#fff;
  /* HarmonyOS dark-mode anchor overrides (palette dark values) */
  --blue-400:#317af7;     /* palette8 dark */
  --green-400:#5ba854;    /* palette4 dark */
  --red-400:#d94838;      /* ohos warning dark */
  --orange-400:#db6b42;   /* palette9 dark */
  --yellow-400:#d1a738;   /* palette11 dark */
  --purple-400:#8c55c2;   /* palette6 dark */
  --pink-400:#d64966;     /* palette7 dark */
  --cyan-400:#5aada0;     /* palette3 dark */
  /* ── HarmonyOS semantic tokens (Dark) ── */
  --surface:#2e3033;      /* ohos_id_color_card_bg dark */
  --surface-2:#000;       /* ohos_id_color_background / sub_background dark */
  --surface-3:#202224;    /* ohos_id_color_panel_bg / dialog_bg dark */
  --text:rgba(255,255,255,.8588);  /* ohos_id_color_text_primary dark */
  --text-2:rgba(255,255,255,.6);   /* ohos_id_color_text_secondary dark */
  --text-3:rgba(255,255,255,.4);   /* ohos_id_color_text_tertiary dark */
  --border:rgba(255,255,255,.051);    /* ohos_id_color_list_separator dark */
  --border-strong:rgba(255,255,255,.102); /* ohos_id_color_component_normal dark */
  --sh1:0 1px 2px -1px rgba(0,0,0,.24); --sh2:0 2px 4px -1px rgba(0,0,0,.24);
  --sh3:0 4px 8px -2px rgba(0,0,0,.36); --sh4:0 8px 16px -4px rgba(0,0,0,.32);
  /* ── Font Color Tokens (Dark) ── */
  --font-primary:#ffffff;
  --font-secondary:rgba(255,255,255,.6);
  --font-tertiary:rgba(255,255,255,.4);
  --top-text-bottom-value-divider:rgba(255,255,255,.2);
  /* ── Graphic Element Color Tokens (Dark) ── */
  --graphic-primary:#ffffff;
  --graphic-secondary:rgba(255,255,255,.60);
  --graphic-tertiary:rgba(255,255,255,.20);
  /* ── Backplate Color Tokens (Dark) ── */
  --comp_background_primary:#ffffff;
  --comp_background_secondary:rgba(255,255,255,.20);
  --comp_background_tertiary:rgba(255,255,255,.10);
  /* ── Progress Circle Tokens (Dark) ── */
  --pc-track:rgba(255,255,255,.10);
}

/* 局部暗色模式：用于融球卡片，不依赖页面主题 */
[data-color-mode="dark"] {
  --font-primary:#ffffff;
  --font-secondary:rgba(255,255,255,.60);
  --font-tertiary:rgba(255,255,255,.40);
  --graphic-primary:#ffffff;
  --graphic-secondary:rgba(255,255,255,.60);
  --graphic-tertiary:rgba(255,255,255,.20);
  --comp_background_primary:#ffffff;
  --comp_background_secondary:rgba(255,255,255,.20);
  --comp_background_tertiary:rgba(255,255,255,.10);}

/* 单色模式：宿主背景模板必须提供 --background-content-color */
[data-color-mode="monochrome"] {
  --font-primary:var(--background-content-color);
  --font-secondary:color-mix(in srgb,var(--background-content-color) 60%,transparent);
  --font-tertiary:color-mix(in srgb,var(--background-content-color) 40%,transparent);
  --graphic-primary:var(--background-content-color);
  --graphic-secondary:color-mix(in srgb,var(--background-content-color) 60%,transparent);
  --graphic-tertiary:color-mix(in srgb,var(--background-content-color) 20%,transparent);
  --comp_background_primary:var(--background-content-color);
  --comp_background_secondary:color-mix(in srgb,var(--background-content-color) 20%,transparent);
  --comp_background_tertiary:color-mix(in srgb,var(--background-content-color) 10%,transparent);}

/* ── Button ──────────────────────────────────────── */
.ring-wrap{position:relative;flex-shrink:0}
.ring-center{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;pointer-events:none;gap:5px}

.btn {
  position: relative;
  display: inline-block;
  flex-shrink: 0;
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
  color: var(--btn-text);
  border: none;
  background: transparent;
  transition: color .12s;}
.pill-btn {
  width: 136px;
  height: 36px;
  padding: 0 12px;
  border-radius: 30px;
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;
  font-size: 14px;
  font-weight: 500;
  line-height: 19px;}
.circle-btn {
  width: 40px;
  min-width: 40px;
  height: 40px;
  padding: 0;
  border-radius: 50%;}
.btn::before {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background-color: var(--btn-bg);
  transition: background-color .12s;}
.btn::after {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: inherit;
  pointer-events: none;}
.btn:focus { outline: none;}
.btn:focus-visible::after {
  outline: 2px solid var(--blue-400);
  outline-offset: 2px;}
.btn:hover:not(:disabled)::before { background-color: var(--btn-bg-hover);}
.btn:active:not(:disabled)::before { background-color: var(--btn-bg-active);}
.btn:disabled { opacity: .4; cursor: not-allowed; pointer-events: none;}
.btn-inner {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;}
.btn-icon {
  position: relative;
  z-index: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink:0;}
.pill-btn .btn-inner{gap:8px;align-items:center;justify-content:center}
.pill-btn .btn-icon{
  flex-basis:20px;width:20px;height:20px;
  font-size:18px;line-height:20px;}
.circle-btn .btn-icon{
  flex-basis:20px;width:20px;height:20px;
  font-size:20px;line-height:20px;}
.btn-label {
  position: relative;
  z-index: 1;
  font: inherit;}
.button-card-position-demo{
  position:relative;width:160px;height:160px;border-radius:20px;
  background:var(--card-bg-solid-blue);
  --background-content-color:var(--card-bg-solid-blue-content);
  border:1px solid rgba(0,0,0,.06);overflow:hidden;}
.button-card-position-demo .pill-btn{
  position:absolute;left:12px;bottom:12px;
  --btn-bg:var(--comp_background_tertiary);--btn-bg-hover:var(--comp_background_tertiary);--btn-bg-active:var(--comp_background_tertiary);--btn-text:var(--font-primary)}
.button-card-position-demo .circle-btn{
  position:absolute;right:12px;bottom:12px;
  --btn-bg:var(--comp_background_tertiary);--btn-bg-hover:var(--comp_background_tertiary);--btn-bg-active:var(--comp_background_tertiary);--btn-text:var(--graphic-primary)}
#pillbutton .pill-btn{
  --btn-bg:var(--comp_background_tertiary);--btn-bg-hover:var(--comp_background_tertiary);--btn-bg-active:var(--comp_background_tertiary);--btn-text:var(--font-primary);}
#circlebutton .circle-btn{
  --btn-bg:var(--comp_background_tertiary);--btn-bg-hover:var(--comp_background_tertiary);--btn-bg-active:var(--comp_background_tertiary);--btn-text:var(--graphic-primary);}

/* ── CardButton · 2×4 Layout Pattern action ─────── */
.card-action-btn{
  box-sizing:border-box;
  display:block;
  width:100%;
  min-width:0;
  height:100%;
  min-height:48px;
  max-height:64px;
  padding:7px 12px;
  border:0;
  border-radius:16px;
  background:var(--comp_background_tertiary);
  color:var(--font-primary);
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;
  font-size:var(--fs-bm);
  font-weight:700;
  line-height:20px;
  cursor:pointer;}
.card-action-btn:focus{outline:none;}
.card-action-btn:focus-visible{outline:2px solid var(--blue-400);outline-offset:2px;}
.card-action-btn:disabled{opacity:.4;cursor:not-allowed;pointer-events:none;}
.card-action-btn__content{
  display:flex;
  flex-direction:row;
  align-items:center;
  justify-content:space-between;
  width:100%;
  height:100%;
  gap:8px;}
.card-action-btn__icon{
  display:block;
  order:2;
  flex:0 0 24px;
  width:24px;
  height:24px;
  color:inherit;
  background:currentColor;
  -webkit-mask:var(--card-button-icon-url) no-repeat center/contain;
  mask:var(--card-button-icon-url) no-repeat center/contain;}
.card-action-btn__icon-placeholder{
  display:block;
  order:2;
  flex:0 0 24px;
  width:24px;
  height:24px;
  border-radius:50%;
  background:currentColor;
  opacity:.20;}
.card-action-btn__label{
  order:1;
  flex:1 1 auto;
  min-width:0;
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap;
  text-align:left;}
.generated-card-frame[data-tone="dark"] .card-action-btn{
  background:var(--comp_background_tertiary);
  color:var(--font-primary);}

/* ── Icon media library ─────────────────────────── */
.icon-media-grid{
  display:grid;grid-template-columns:repeat(auto-fill,minmax(112px,1fr));gap:8px;}
.icon-media-item{
  min-width:0;border:1px solid var(--border);border-radius:12px;
  background:var(--surface);overflow:hidden;}
.icon-media-preview{
  height:72px;display:flex;align-items:center;justify-content:center;
  background-color:#f7f7f7;
  background-image:linear-gradient(45deg,#ededed 25%,transparent 25%),linear-gradient(-45deg,#ededed 25%,transparent 25%),linear-gradient(45deg,transparent 75%,#ededed 75%),linear-gradient(-45deg,transparent 75%,#ededed 75%);
  background-size:16px 16px;background-position:0 0,0 8px,8px -8px,-8px 0;}
.icon-media-preview img{display:block;width:32px;height:32px;object-fit:contain}
.icon-media-name{
  min-height:42px;padding:8px;font-family:var(--mono);font-size:.625rem;
  line-height:.8125rem;color:var(--text-2);text-align:center;overflow-wrap:anywhere;}
/* ── App Icon ───────────────────────────────────── */
.app-icon{
  display:block;width:20px;height:20px;flex:0 0 20px;
  border-radius:4px;object-fit:cover;overflow:hidden;}
.app-icon-library .icon-media-preview img{
  display:block;width:20px;height:20px;border-radius:4px;object-fit:cover;}
.app-icon-library .icon-media-name{
  min-height:32px;display:flex;align-items:center;justify-content:center;
  font-family:var(--font-sans);font-size:12px;line-height:16px;color:var(--text-2);}
.app-icon-demo-card{
  box-sizing:border-box;width:160px;height:160px;padding:12px;border-radius:24px;
  background:var(--card-bg-solid-blue);
  border:1px solid rgba(0,0,0,.06);}
.app-icon-title-row{
  display:flex;align-items:flex-start;justify-content:space-between;
  width:136px;min-height:20px;gap:4px;}
.app-icon-demo-title{
  min-width:0;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
  font-family:var(--font-sans);font-size:12px;font-weight:400;line-height:18px;
  color:rgba(0,0,0,.6);text-align:left;}
.icon-subsection-heading{
  scroll-margin-top:90px;margin:0 0 16px;font-size:14px;font-weight:600;
  line-height:20px;color:var(--text);}
.icon-subsection-heading.has-divider{
  margin-top:32px;padding-top:24px;border-top:1px solid var(--border);}
.weather-icon-library{grid-template-columns:repeat(auto-fill,112px);}
.weather-icon-library .icon-media-preview img{
  width:20px;height:20px;border-radius:4px;object-fit:contain;}
/* 天气组合示例的多椭圆深色背景。design_system.html 仅加载 runtime CSS，
   因此这里必须保留与设计源一致的背景几何，不能只保留天气卡内容样式。 */
.card-bg-dark__canvas{
  position:absolute;inset:0;display:block;width:100%;height:100%;
  overflow:hidden;border-radius:inherit;}
.card-bg-dark__ellipse{position:absolute;border-radius:50%;}
.card-bg-dark__ellipse--right-bottom{
  left:var(--card-bg-orb-right-bottom-x);top:var(--card-bg-orb-right-bottom-y);
  width:var(--card-bg-orb-right-bottom-size);
  aspect-ratio:1/1;background:var(--card-bg-orb-blue-right-bottom-color);}
.card-bg-dark__ellipse--left-bottom{
  left:var(--card-bg-orb-left-bottom-x);top:var(--card-bg-orb-left-bottom-y);
  width:var(--card-bg-orb-left-bottom-size);
  aspect-ratio:1/1;background:var(--card-bg-orb-blue-left-bottom-color);}
.card-bg-dark__ellipse--top{
  left:var(--card-bg-orb-top-x);top:var(--card-bg-orb-top-y);
  width:var(--card-bg-orb-top-size);
  aspect-ratio:1/1;background:var(--card-bg-orb-blue-top-color);}
.card-bg-dark__backplate{
  position:absolute;inset:0;width:100%;height:100%;
  border-radius:inherit;background:var(--card-bg-orb-backplate);
  -webkit-backdrop-filter:blur(var(--card-bg-orb-blur));
  backdrop-filter:blur(var(--card-bg-orb-blur));}
.card-bg-dark--rain{
  background:var(--card-bg-orb-blue-top-color);}
.card-bg-dark--cloudy{
  background:var(--card-bg-orb-blue-top-color);}
.weather-icon-demo-card{
  position:relative;isolation:isolate;contain:paint;overflow:hidden;
  box-sizing:border-box;width:160px;height:160px;padding:12px;border-radius:24px;
  background:transparent;border:0;}
.weather-icon-demo-card[data-weather="sunny"]{
  background:var(--card-bg-orb-blue-top-color);}
.weather-icon-demo-bg{
  z-index:0;pointer-events:none;}
.weather-icon-demo-content{
  position:relative;z-index:1;width:100%;height:100%;
  display:flex;flex-direction:column;align-items:flex-start;}
.weather-icon-demo-title{
  font-family:var(--font-sans);font-size:12px;font-weight:400;line-height:18px;
  color:rgba(255,255,255,.60);}
.weather-icon-demo-title-row{
  display:flex;align-items:flex-start;justify-content:space-between;
  width:136px;min-height:20px;gap:4px;}
.weather-icon-demo-reading{display:flex;align-items:center;gap:8px;margin-top:4px;}
.weather-icon-demo-temp{
  font-family:var(--font-sans);font-size:38px;font-weight:700;line-height:46px;
  color:#fff;font-variant-numeric:tabular-nums;}
.weather-icon-demo-glyph{
  display:block;width:20px;height:20px;border-radius:4px;object-fit:contain;}
.weather-icon-demo-meta{
  margin-top:auto;font-family:var(--font-sans);font-size:12px;font-weight:400;
  line-height:18px;color:rgba(255,255,255,.60);}
/* ── ProgressLine1 · 轨道 + Bar + 双标签 ─────────── */
.pb {
  display: flex;
  flex-direction: column;
  width: 116px;
  --pb-range: var(--blue-400); /* default: blue */}
.pb[data-color="orange"] { --pb-range: var(--orange-400);}
.pb[data-color="yellow"] { --pb-range: var(--yellow-400);}
.pb[data-color="purple"] { --pb-range: var(--purple-400);}
.pb[data-color="red"]    { --pb-range: var(--red-400);}
.pb[data-color="green"]  { --pb-range: var(--green-400);}
.pb[data-color="pink"]   { --pb-range: var(--pink-400);}
.pb-label-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  width: 116px;
  margin-top: 4px;}
.pb-label-left,
.pb-label-right {
  margin: 0;
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;
  font-size: 10px;
  line-height: 13px;
  color: var(--text);
  white-space: nowrap;}
.pb-label-left { text-align: left; font-weight: 400;}
.pb-label-right { text-align: right; font-weight: 400;}
.pb-track {
  position: relative;
  width: 116px;
  height: 8px;
  border-radius: var(--radius-full);
  overflow: hidden;
  background: var(--gray-150); /* light: gray-150 */}
[data-theme="dark"] .pb-track { background: var(--gray-400);} /* dark: gray-400 */
.pb-range {
  position: absolute;
  top: 0; left: 0;
  height: 8px;
  width: calc(var(--pb-current, 0) / var(--pb-total, 100) * 100%);
  border-radius: inherit;
  background: var(--pb-range);
  transition: width .3s cubic-bezier(.65,0,.35,1);}

/* ── ProgressLine2 · EmphasizedData + Bar ───────── */
.pl2{
  display:flex;
  flex-direction:column;
  align-items:stretch;
  gap:6px;
  box-sizing:border-box;
  padding-bottom:4px;
  width:100%;
  min-width:0;
  --pl2-bar:var(--graphic-primary,var(--blue-400));}
.pl2[data-mode="dark"]{--pl2-bar:#fff;}
.pl2 .ed{
  min-height:0;
  align-items:baseline;
  transform:translateY(3px);}
.pl2 .ed-val{line-height:1;}
.pl2 .ed-unit{line-height:1;}
.content-zone > [data-component="progress-line2"]{
  width:100%;
  min-width:0;}
.pl2-track{
  position:relative;
  width:100%;
  height:8px;
  overflow:hidden;
  border-radius:var(--radius-full);
  background:var(--graphic-tertiary);}
.pl2[data-mode="dark"] .pl2-track{background:var(--graphic-tertiary);}
.pl2-bar{
  position:absolute;
  inset:0 auto 0 0;
  width:calc(var(--pl2-current, 0) / var(--pl2-total, 100) * 100%);
  height:8px;
  border-radius:inherit;
  background:var(--pl2-bar);}

/* ── Gauge · 94×94 正圆 + 80 水平裁切 + 环内数值与标签 ── */
.gauge{
  position:relative;
  box-sizing:border-box;
  width:94px;
  height:80px;
  overflow:hidden;
  display:block;
  container-type:inline-size;
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;}
.gauge-arc{
  position:absolute;
  top:0;
  left:0;
  width:94px;
  height:94px;}
.gauge-arc svg{
  display:block;
  width:94px;
  height:94px;}
.gauge-track,
.gauge-bar{
  fill:none;
  stroke-width:10;
  stroke-linecap:round;}
.gauge-track{
  stroke:var(--graphic-tertiary);}
.gauge-bar{
  stroke:var(--graphic-primary);
  stroke-dasharray:var(--gauge-percent,0) 100;}
.gauge-copy{
  position:absolute;
  inset:0;
  width:100%;
  height:100%;
  z-index:1;
  display:flex;
  flex-direction:column;
  align-items:center;
  justify-content:center;
  gap:0;
  padding:4px 14px 8px;
  box-sizing:border-box;
  min-width:0;
  text-align:center;}
.gauge-value{
  margin:0;
  overflow:hidden;
  max-width:100%;
  font-size:var(--fs-tm);
  font-weight:var(--fw-tm);
  line-height:24px;
  color:var(--font-primary);
  font-variant-numeric:tabular-nums;
  text-align:center;
  text-overflow:ellipsis;
  white-space:nowrap;}
.gauge-meta{
  display:flex;
  max-width:100%;
  overflow:hidden;
  align-items:center;
  justify-content:center;
  gap:2px;
  margin-top:0;
  font-size:var(--fs-cm);
  font-weight:400;
  line-height:16px;
  color:var(--font-secondary);
  text-align:center;
  text-overflow:ellipsis;
  white-space:nowrap;}
[data-theme="dark"] .gauge:not([data-mode="light"]) .gauge-track,
.gauge[data-mode="dark"] .gauge-track{stroke:rgba(255,255,255,.20);}
[data-theme="dark"] .gauge:not([data-mode="light"]) .gauge-bar,
.gauge[data-mode="dark"] .gauge-bar{stroke:#fff;}
.gauge[data-mode="dark"] .gauge-value{color:#fff;}
.gauge[data-mode="dark"] .gauge-meta{color:rgba(255,255,255,.60);}
.pl2-demo-grid{display:flex;flex-wrap:wrap;gap:16px;}
.pl2-demo-case{display:flex;flex-direction:column;gap:6px;}
.pl2-demo-label{font-size:10px;font-weight:500;line-height:14px;color:var(--text-3);}
.pl2-demo-card{
  display:flex;
  flex-direction:column;
  align-items:stretch;
  justify-content:flex-end;
  gap:4px;
  box-sizing:border-box;
  width:160px;
  height:160px;
  padding:12px;
  border-radius:20px;}
.pl2-demo-card[data-card-size="2x4"]{width:320px;}
.pl2-demo-card[data-layout="type10a"],
.pl2-demo-card[data-layout="type2"]{
  justify-content:flex-start;
  gap:8px;}
.pl2-layout-title{
  flex:0 0 12px;
  height:12px;
  overflow:hidden;
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;
  font-size:12px;
  font-weight:400;
  line-height:12px;
  color:var(--font-secondary);
  white-space:nowrap;
  text-overflow:ellipsis;}
.pl2-layout-content{
  display:flex;
  flex:1;
  min-height:0;
  flex-direction:column;
  align-items:stretch;
  justify-content:flex-start;}
.pl2-layout-action{
  flex:0 0 36px;
  height:36px;}
.pl2-layout-action .pill-btn{width:100%;}
.pl2-layout-detail{
  display:flex;
  flex:1;
  min-height:0;
  align-items:flex-start;}
.pl2-demo-card[data-mode="light"]{
  background:var(--card-bg-orb-blue-top-color);}
.pl2-demo-card[data-mode="light"] .ed-val,
.pl2-demo-card[data-mode="light"] .ed-unit{color:#fff;}
.pl2-demo-card[data-mode="light"] .single-line-title{color:rgba(255,255,255,.60);}
.pl2-demo-card[data-mode="light"] .pl2-layout-title{color:rgba(255,255,255,.60);}
.pl2-demo-card[data-mode="dark"]{
  background:var(--card-bg-solid-blue);}
.pl2-demo-card[data-mode="light"] .pill-btn{
  --btn-bg:var(--comp_background_tertiary);--btn-bg-hover:var(--comp_background_tertiary);--btn-bg-active:var(--comp_background_tertiary);--btn-text:var(--font-primary);}
.pl2-demo-card[data-mode="dark"] .pill-btn{
  --btn-bg:var(--comp_background_tertiary);--btn-bg-hover:var(--comp_background_tertiary);--btn-bg-active:var(--comp_background_tertiary);--btn-text:var(--font-primary);}

/* ── Progress Circle · Icon + 环外数值 ──────────── */
.pr {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;}
.pr-wrap { position: relative;}
.pc-component{display:inline-flex;flex-direction:column;align-items:center;gap:2px}
.pc-external-value{
  margin:0;text-align:center;white-space:nowrap;
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;
  font-size:var(--fs-cm);font-weight:var(--fw-cm);line-height:14px;color:var(--font-primary);}
.pc-center-icon{display:flex;align-items:center;justify-content:center;color:var(--card-progress-icon,var(--font-secondary))}
.pc-center-icon img{display:block}
.pc-center-icon img{filter:brightness(0);opacity:.6}
.pc-center-icon[data-size="sm"] img{width:20px;height:20px}
.pc-center-icon[data-size="md"] img{width:20px;height:20px}
.pc-center-icon[data-size="single"] img{width:20px;height:20px}
.pc-dark-surface{
  width:140px;height:140px;border-radius:24px;
  display:flex;align-items:center;justify-content:center;
  background:var(--card-bg-orb-purple-top-color);}
.pc-dark-surface .pc-external-value{color:#fff}
.pc-family-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
.pc-family-rule{padding:14px;border:1px solid var(--line);border-radius:12px;background:var(--surface-2)}
.pc-family-rule strong{display:block;margin-bottom:4px;font-size:13px;color:var(--text-1)}
.pc-family-rule span{font-size:12px;line-height:1.6;color:var(--text-3)}
.pc-single-combo{display:inline-flex;flex:0 0 auto;align-items:center;gap:8px;min-width:max-content}
.pc-single-demo{display:flex;flex-wrap:wrap;gap:24px;align-items:flex-start;justify-content:flex-start;width:100%;text-align:left}
.pc-layout-demo{display:flex;flex-wrap:wrap;gap:20px;align-items:flex-start}
.pc-layout-case{display:flex;flex-direction:column;gap:8px}
.pc-layout-label{font-size:10px;font-weight:500;line-height:14px;color:var(--text-3)}
.pc-demo-card{
  box-sizing:border-box;width:160px;padding:12px;border-radius:20px;
  background:var(--card-bg-solid-blue);color:var(--font-primary);overflow:hidden}
.pc-demo-title{
  height:12px;line-height:12px;font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;
  font-size:12px;font-weight:400;color:rgba(0,0,0,.6);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pc-type12-card{height:160px}
.pc-type12-main{height:92px;display:grid;grid-template-columns:64px 64px;gap:8px}
.pc-type12-zone{width:64px;height:92px;display:flex;align-items:center;justify-content:center;min-width:0}
.pc-type12-button{
  width:136px;height:36px;margin-top:8px;border:0;border-radius:30px;
  display:flex;align-items:center;justify-content:center;gap:8px;
  background:var(--comp_background_tertiary);color:var(--font-primary);font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;
  font-size:14px;font-weight:500;line-height:19px;}
.pc-type6-card{height:160px}
.pc-type6-grid{width:136px;height:136px;display:grid;grid-template-columns:64px 64px;grid-template-rows:64px 64px;gap:8px}
.pc-type6-cell{width:64px;height:64px;display:flex;align-items:center;justify-content:center;min-width:0}

/* ── SemiRingBar 半圆进度条 ──────────────────────── */
.srb{display:inline-flex;flex-direction:column;align-items:center;--srb-color:var(--blue-400);}
.srb[data-color="orange"]{--srb-color:var(--orange-400);}
.srb[data-color="green"] {--srb-color:var(--green-400);}
.srb[data-color="red"]   {--srb-color:var(--red-400);}
.srb[data-color="purple"]{--srb-color:var(--purple-400);}
.srb-wrap{position:relative;}
.srb-svg{display:block;}
.srb-track{fill:none;stroke:var(--gray-150);stroke-linecap:round;}
[data-theme="dark"] .srb-track{stroke:var(--gray-400);}
.srb-range{fill:none;stroke:var(--srb-color);stroke-linecap:round;transition:stroke-dashoffset .3s cubic-bezier(.65,0,.35,1);}
.srb-center{
  position:absolute;left:0;right:0;
  bottom:14%;text-align:center;
  font-weight:700;color:var(--text);
  font-size:1.75rem;line-height:1;letter-spacing:-.01em;
}
.srb-scale{
  display:flex;justify-content:space-between;width:100%;
  margin-top:2px;font-size:.875rem;line-height:1.25rem;color:var(--text-3);font-weight:400;
  font-variant-numeric:tabular-nums;
}

/* ── EmphasizedData · 统一数值组件 ──────────────── */
.ed{
  display:inline-flex;
  /* Align the text baselines, not the bottoms of their different line boxes.
     A wrapping unit keeps its first baseline beside the number and expands
     downwards in normal flow. Do not clip it to the numeric line's height. */
  align-items:baseline;
  gap:2px;
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;}
.ed-val{
  font-size:var(--fs-ds);
  font-weight:700;
  line-height:1;
  color:var(--font-primary);
  font-variant-numeric:tabular-nums;}
.ed-unit{
  font-size:var(--fs-cl);
  font-weight:400;
  line-height:1.5;
  color:var(--font-secondary);}
/* ── 强调文本 · 主文本 + 次文本 ─────────────────── */
.emphasis-text{
  display:inline-flex;
  flex-direction:column;
  align-items:flex-start;
  gap:2px;
  min-width:0;
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;
  text-align:left;}
.emphasis-text-main{
  margin:0;
  font-size:var(--fs-ts);
  font-weight:700;
  line-height:20px;
  color:var(--font-primary);}
.emphasis-text-secondary{
  margin:0;
  font-size:var(--fs-bs);
  font-weight:400;
  line-height:16px;
  color:var(--font-secondary);}
.secondary-body{
  margin:0;
  min-width:0;
  max-width:100%;
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;
  font-size:var(--fs-bm);
  font-weight:400;
  line-height:19px;
  color:var(--font-secondary);
  text-align:left;
  white-space:normal;
  overflow-wrap:anywhere;}
.secondary-body[data-multiline="true"]{
  font-size:var(--fs-bs);
  line-height:16px;}
.secondary-body[data-segmented="true"]{
  display:flex;
  flex-direction:column;
  align-items:flex-start;
  row-gap:2px;
  width:100%;}
.secondary-body-row{
  display:flex;
  align-items:baseline;
  width:100%;
  min-width:0;}
.secondary-body-field{
  min-width:0;
  max-width:100%;
  white-space:nowrap;
  overflow-wrap:normal;}
.secondary-body-field[data-wrap="true"]{
  white-space:normal;
  overflow-wrap:anywhere;}
.secondary-body-separator{
  flex:0 0 auto;
  white-space:pre;}
.secondary-body-card{
  box-sizing:border-box;
  display:flex;
  flex-direction:column;
  align-items:stretch;
  width:140px;
  height:140px;
  padding:12px;
  border-radius:24px;
  background:var(--gray-25);
  box-shadow:inset 0 0 0 1px var(--border-strong);}
.secondary-body-card-top,
.secondary-body-card-bottom{
  display:flex;
  flex-direction:column;
  align-items:flex-start;
  gap:2px;}
.secondary-body-card-bottom{margin-top:auto;}

/* ── Title · SingleLineTitle / DoubleLineTitle ───── */
.single-line-title,
.double-line-title-main,
.double-line-title-sub{
  margin:0;
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;
  text-align:left;}
.single-line-title{
  min-width:0;
  width:100%;
  max-width:100%;
  overflow:hidden;
  font-size:var(--fs-bs);
  font-weight:var(--fw-bs);
  line-height:18px;
  color:var(--font-secondary);
  white-space:nowrap;
  text-overflow:ellipsis;}
.single-line-title-layout{
  display:flex;
  flex-direction:column;
  align-items:flex-start;
  min-width:0;
  flex:1;
  gap:2px;}
.double-line-title{
  display:flex;
  flex-direction:column;
  align-items:flex-start;
  min-width:0;
  flex:1;
  gap:4px;}
.double-line-title-main{
  width:100%;
  overflow:hidden;
  font-size:var(--fs-bs);
  font-weight:700;
  line-height:18px;
  color:var(--font-primary);
  white-space:nowrap;
  text-overflow:ellipsis;}
.double-line-title-sub{
  display:-webkit-box;
  width:100%;
  overflow:hidden;
  font-size:var(--fs-bs);
  font-weight:500;
  line-height:18px;
  color:var(--font-secondary);
  -webkit-box-orient:vertical;
  -webkit-line-clamp:2;
  line-clamp:2;}
.title-example-grid{
  display:flex;
  flex-wrap:wrap;
  gap:12px;}
.title-demo-case{
  display:flex;
  flex-direction:column;
  gap:6px;}
.title-demo-case-label{
  font-size:10px;
  font-weight:500;
  line-height:14px;
  color:var(--text-3);}
.title-demo-row{
  display:flex;
  align-items:flex-start;
  width:100%;
  gap:4px;}
.title-position-demo{
  box-sizing:border-box;
  width:276px;
  min-height:80px;
  padding:12px;
  border:1px dashed var(--border-strong);
  border-radius:var(--radius-xl);
  background:var(--card-bg-solid-blue);}
/* ── DataDisplay · 标签 + 数值 + 单位／辅助信息 ──── */
.data-display{
  display:inline-flex;
  flex-direction:column;
  align-items:center;
  justify-content:center;
  gap:8px;
  min-width:0;
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;
  text-align:center;}
.data-display-label,
.data-display-value,
.data-display-supporting{
  margin:0;
  max-width:100%;}
.data-display-label{
  font-size:var(--fs-bs);
  font-weight:500;
  line-height:18px;
  color:var(--font-secondary);}
.data-display-value{
  font-size:var(--fs-dl);
  font-weight:700;
  line-height:60px;
  color:var(--font-primary);
  font-variant-numeric:tabular-nums;}
.data-display-supporting{
  font-size:var(--fs-bm);
  font-weight:400;
  line-height:20px;
  color:var(--font-secondary);}

/* ── InfoBlock · 主副文本 + Icon／ProgressCircle ── */
.info-block{
  box-sizing:border-box;
  width:100%;
  height:64px;
  flex:0 0 64px;
  padding:0 8px;
  border-radius:16px;
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:4px;
  overflow:hidden;
  background:var(--comp_background_tertiary);
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;}
.info-block-copy{
  display:flex;
  flex:1 1 auto;
  min-width:0;
  flex-direction:column;
  align-items:flex-start;
  gap:0;}
.info-block-primary{
  margin:0;
  display:flex;
  align-items:baseline;
  max-width:100%;
  gap:2px;
  font-size:var(--fs-sts);
  font-weight:700;
  line-height:20px;
  color:var(--font-primary);}
.info-block-primary-value{
  min-width:0;
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap;}
.info-block-unit{
  flex:0 0 auto;
  font-size:var(--fs-cm);
  font-weight:500;
  line-height:16px;
  color:var(--font-secondary);}
.info-block-secondary{
  margin:0;
  max-width:100%;
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap;
  font-size:var(--fs-cl);
  font-weight:var(--fw-cl);
  line-height:18px;
  color:var(--font-secondary);}
.info-block-visual{
  flex:0 0 24px;
  width:24px;
  height:24px;
  display:flex;
  align-items:center;
  justify-content:center;}
.info-block-icon{
  display:block;
  width:24px;
  height:24px;
  object-fit:contain;
  filter:none;}
.info-block-icon[data-color="native"]{filter:none;}
.info-block-icon-mask{
  display:block;
  width:24px;
  height:24px;
  color:var(--graphic-primary);}
.info-block-progress{
  position:relative;
  flex:0 0 44px;
  width:44px;
  height:44px;}
.info-block-progress svg{
  display:block;
  width:44px;
  height:44px;
  transform:rotate(-90deg);}
.info-block-progress-track,
.info-block-progress-bar{
  fill:none;
  stroke-width:6;}
.info-block-progress-track{stroke:var(--graphic-tertiary);}
.info-block-progress-bar{
  stroke:var(--graphic-primary);
  stroke-linecap:round;}
.info-block-progress-inner{
  position:absolute;
  inset:0;
  display:flex;
  align-items:center;
  justify-content:center;}
.info-block-progress-icon{
  display:block;
  width:20px;
  height:20px;
  color:var(--graphic-secondary);
}

/* ── TopTextBottomValue · 2×4 多组上文下数 ─────── */
.top-text-bottom-value{
  position:relative;
  display:flex;
  width:100%;
  min-width:0;
  align-items:center;
  justify-content:space-around;
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;}
.top-text-bottom-value-divider{
  position:absolute;
  top:50%;
  width:1px;
  height:62px;
  background:var(--top-text-bottom-value-divider);
  transform:translate(-50%,-50%);
  pointer-events:none;}
.top-text-bottom-value-item{
  display:flex;
  flex:0 0 auto;
  width:max-content;
  min-width:0;
  flex-direction:column;
  align-items:center;
  justify-content:center;
  gap:0;
  text-align:center;}
.top-text-bottom-value-label,
.top-text-bottom-value-number,
.top-text-bottom-value-unit{
  max-width:none;
  margin:0;
  overflow:visible;
  text-overflow:clip;
  white-space:nowrap;}
.top-text-bottom-value-label{
  font-size:var(--fs-bs);
  font-weight:500;
  line-height:18px;
  color:var(--font-primary);}
.top-text-bottom-value-number{
  font-size:var(--fs-tm);
  font-weight:700;
  line-height:32px;
  color:var(--font-primary);
  font-variant-numeric:tabular-nums;}
.top-text-bottom-value-unit{
  font-size:var(--fs-bs);
  font-weight:400;
  line-height:18px;
  color:var(--font-secondary);}

/* ── TableText · 左标签 + 右参数 · 至少两组 ────── */
.table-text{
  display:flex;
  width:100%;
  height:100%;
  min-width:0;
  flex-direction:column;
  justify-content:flex-start;
  gap:2px;
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;}
.table-text[data-spacing="adaptive"]{
  justify-content:space-between;}
.table-text-item{
  display:flex;
  flex:0 0 auto;
  width:100%;
  min-width:0;
  align-items:flex-end;
  justify-content:space-between;
  gap:8px;}
.table-text-label,
.table-text-parameter{
  margin:0;
  overflow:hidden;
  font-size:var(--fs-cm);
  font-weight:500;
  line-height:16px;
  text-overflow:ellipsis;
  white-space:nowrap;}
.table-text-label{
  flex:1 1 auto;
  min-width:0;
  text-align:left;
  color:var(--font-secondary);}
.table-text-parameter{
  flex:0 1 auto;
  max-width:70%;
  text-align:right;
  color:var(--font-primary);
  font-variant-numeric:tabular-nums;}

/* ── TextBlock · 2×4 自然宽背板文本组 · 至少两组 ────── */
.text-block{
  display:flex;
  flex:1 1 64px;
  width:100%;
  height:auto;
  min-height:48px;
  max-height:64px;
  min-width:0;
  align-items:stretch;
  gap:8px;
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;}
.text-block-item{
  box-sizing:border-box;
  display:flex;
  flex:1 1 0;
  width:0;
  min-width:64px;
  height:100%;
  min-height:0;
  padding:0 8px;
  align-items:center;
  justify-content:center;
  border-radius:16px;
  background:var(--comp_background_tertiary);}
.text-block-copy{
  display:flex;
  width:100%;
  min-width:0;
  flex-direction:column;
  align-items:flex-start;
  justify-content:center;
  gap:2px;}
.text-block-label,
.text-block-parameter{
  max-width:100%;
  margin:0;
  overflow:hidden;
  text-align:left;
  text-overflow:ellipsis;
  white-space:nowrap;}
.text-block-label{
  font-size:var(--fs-cl);
  font-weight:700;
  line-height:18px;
  color:var(--font-primary);}
.text-block-parameter{
  font-size:var(--fs-cm);
  font-weight:500;
  line-height:16px;
  color:var(--font-primary);
  font-variant-numeric:tabular-nums;}

/* ── Props Spec (Props × Values visualizer) ──────── */
.ps{
  display:flex;flex-direction:column;gap:0;
  background:var(--surface-2);border:1px solid var(--border);
  border-radius:var(--radius-lg);
  margin-bottom:20px;overflow:hidden;}
.ps-row{
  display:grid;grid-template-columns:150px 1fr;gap:16px;
  padding:12px 16px;
  border-bottom:1px solid var(--border);
  align-items:center;min-height:44px;}
.ps-row:last-child{border-bottom:none}
.ps-name{
  display:flex;flex-direction:column;gap:1px;}
.ps-name-key{font-size:.75rem;font-weight:600;color:var(--text);font-family:var(--mono);line-height:1.2}
.ps-name-type{font-size:.5625rem;color:var(--text-3);font-family:var(--mono);letter-spacing:.02em}
.ps-values{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center}
.ps-chip{
  font-size:.6875rem;font-weight:500;color:var(--text-2);
  padding:3px 9px;border-radius:var(--radius-full);
  background:var(--surface);border:1px solid var(--border);
  font-family:var(--mono);white-space:nowrap;}
.ps-chip[data-default]{
  background:var(--blue-25);border-color:var(--blue-100);color:var(--blue-500);}
[data-theme="dark"] .ps-chip[data-default]{background:color-mix(in srgb,var(--blue-400) 20%,transparent);border-color:var(--blue-400);color:var(--blue-200)}
.ps-item{
  display:inline-flex;align-items:center;gap:6px;
  padding:2px 2px 2px 0;}
.ps-item-label{font-size:.625rem;color:var(--text-3);font-family:var(--mono);line-height:1}
.ps-header{
  font-size:.625rem;font-weight:700;color:var(--text-3);
  text-transform:uppercase;letter-spacing:.08em;
  padding:8px 16px;background:var(--surface-3);
  border-bottom:1px solid var(--border);}

/* ── EventCard ─────────────────────────────────── */
.ec{
  display:grid;
  grid-template-columns:8px minmax(0,1fr);
  column-gap:7px;
  align-items:stretch;
  width:100%;
  max-width:116px;
  min-width:0;}
.generated-card-frame[data-card-size="2x4"] .ec{
  max-width:none;}
.ec-rail{
  display:flex;
  flex-direction:column;
  align-items:center;
  align-self:stretch;
  box-sizing:border-box;
  padding-top:5px;
  min-height:0;}
.ec-dot{
  box-sizing:border-box;
  flex:0 0 8px;
  width:8px;
  height:8px;
  border:1.5px solid var(--graphic-primary);
  background:transparent;
  border-radius:50%;}
.ec-line{
  flex:1;
  width:1px;
  min-height:0;
  margin-top:5px;
  background:var(--graphic-secondary);}
.ec-content{
  display:flex;
  flex-direction:column;
  gap:0;
  min-height:max-content;
  min-width:0;
  width:auto;}
.ec-title{
  flex:0 0 auto;
  display:-webkit-box;
  overflow:hidden;
  -webkit-box-orient:vertical;
  -webkit-line-clamp:2;
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;
  font-size:14px;
  font-weight:500;
  line-height:18px;
  color:rgba(0,0,0,1);
  text-overflow:ellipsis;
  margin-bottom:0;}
.ec-location,.ec-time{
  flex:0 0 16px;
  overflow:hidden;
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;
  font-size:12px;
  font-weight:400;
  line-height:16px;
  color:rgba(0,0,0,.6);
  text-overflow:ellipsis;
  white-space:nowrap;}
.ec-meta{
  display:flex;
  align-items:center;
  width:100%;
  min-width:0;
  height:14px;
  gap:4px;
  overflow:hidden;}
.ec-meta-separator{
  flex:0 0 auto;
  font-size:10px;
  font-weight:400;
  line-height:14px;
  color:rgba(0,0,0,.6);}
.ec[data-density="compact"] .ec-rail{padding-top:4px;}
.ec[data-density="compact"] .ec-content{
  gap:2px;
  min-height:32px;}
.ec[data-density="compact"] .ec-title{
  display:block;
  overflow:hidden;
  margin-bottom:0;
  font-size:12px;
  line-height:16px;
  white-space:nowrap;
  text-overflow:ellipsis;}
.ec[data-density="compact"] .ec-time,
.ec[data-density="compact"] .ec-location{
  flex:0 1 auto;
  min-width:0;
  height:14px;
  font-size:10px;
  line-height:14px;}
.ec[data-density="compact"] .ec-time{flex-shrink:0;}
.ec[data-density="compact"] .ec-location{flex:1 1 auto;}

/* ── ChecklistItem ────────────────────────────────── */
.cli{
  box-sizing:border-box;
  display:flex;
  align-items:center;
  width:100%;
  min-width:0;
  height:48px;
  padding:4px 8px;
  border-radius:12px;
  background:var(--checklist-bg,rgba(255,255,255,.1));}
.cli-row{
  display:flex;align-items:center;gap:8px;width:100%;height:40px;}
.cli-checkbox{
  box-sizing:border-box;
  width:16px;height:16px;border-radius:50%;
  flex:0 0 16px;display:flex;align-items:center;justify-content:center;
  background:var(--checklist-checkbox-bg,rgba(255,255,255,.2));}
.cli-checkbox[data-done="true"]{
  background:var(--checklist-checkbox-bg,rgba(255,255,255,.2));}
.cli-check-icon{
  display:block;width:16px;height:16px;
  color:var(--checklist-check-color,#fff);font-size:12px;font-weight:700;line-height:16px;text-align:center;}
.cli-checkbox[data-done="false"]{
  background:var(--checklist-checkbox-bg,rgba(255,255,255,.2));
  border:1px solid var(--checklist-checkbox-border,rgba(255,255,255,.4));}
.cli-content{
  display:flex;flex-direction:column;gap:2px;min-width:0;flex:1;align-items:flex-start;}
.cli-title{
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;
  font-size:14px;font-weight:700;color:var(--card-primary,rgba(255,255,255,1));line-height:19px;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:100%;}
.cli-meta{
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;
  font-size:14px;font-weight:400;color:var(--card-secondary,rgba(255,255,255,.6));line-height:19px;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:100%;}
.cli-demo-stage{
  display:flex;flex-direction:column;align-items:flex-start;gap:4px;padding:16px;
  border-radius:16px;background:var(--card-bg-orb-blue-top-color);}

/* ── Badge ────────────────────────────────────────── */
.badge{
  box-sizing:border-box;
  flex:0 0 auto;
  align-self:flex-start;
  width:max-content;
  max-width:100%;
  height:16px;border-radius:8px;
  display:inline-flex;align-items:center;justify-content:center;
  padding:0 6px;
  white-space:nowrap;
  font-size:.625rem;font-weight:500;
  background:var(--comp_background_secondary);
  color:var(--font-primary);}
.badge[data-color="orange"]{--badge-color:var(--orange-400)}
.badge[data-color="green"] {--badge-color:var(--green-400)}
.badge[data-color="red"]   {--badge-color:var(--red-400)}
.badge[data-color="purple"]{--badge-color:var(--purple-400)}
.badge[data-color="yellow"]{--badge-color:var(--yellow-400)}
.badge[data-color="cyan"]  {--badge-color:var(--cyan-400)}
.badge[data-color="pink"]  {--badge-color:var(--pink-400)}

/* ════════════════════════════════════════════════════
   v10 组件扩展
   · 沿用用户既有规则(源自 v7)：EventCard / ChecklistItem / Badge
   · v12：移除 Reminder（与 EventCard 重复）
   ════════════════════════════════════════════════════ */

/* ── 单环右侧文本组 ───────────────────────────────
   单环内部规格：Label 在上、Value + Unit 在下 */
.pc-stat-text{
  display:inline-flex;
  flex-direction:column;
  align-items:flex-start;
  min-width:0;
  gap:0;
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;}
.pc-stat-value{
  margin:0;
  font-size:var(--fs-bs);
  font-weight:500;
  line-height:18px;
  color:var(--font-secondary);
  font-variant-numeric:tabular-nums;}
.pc-stat-label{
  margin:0;
  font-size:var(--fs-bm);
  font-weight:700;
  line-height:20px;
  color:var(--font-primary);}
.pc-stat-text[data-lines="3"]{gap:0;}
.pc-stat-text[data-lines="3"] .pc-stat-detail{
  display:inline-flex;
  flex-direction:column;
  align-items:flex-start;
  gap:0;
  min-width:0;
  white-space:nowrap;}
.pc-stat-text[data-lines="3"] .pc-stat-value,
.pc-stat-text[data-lines="3"] .pc-stat-label-secondary{
  font-size:var(--fs-cm);
  font-weight:400;
  line-height:16px;
  color:var(--font-secondary);}
.pc-single-combo[data-size="compact"] .pc-stat-label{line-height:18px;}
.pc-single-combo[data-size="compact"] .pc-stat-value{line-height:16px;}
.pc-single-combo[data-size="compact"] .pc-stat-text[data-lines="3"] .pc-stat-value,
.pc-single-combo[data-size="compact"] .pc-stat-text[data-lines="3"] .pc-stat-label-secondary{line-height:14px;}

/* ── 数值占比 · Icon + 数值 ─────────────────────── */
.numeric-ratio{
  display:inline-flex;
  align-items:center;
  gap:4px;
  min-width:0;
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;}
.numeric-ratio-icon{
  display:flex;
  align-items:center;
  justify-content:center;
  flex:0 0 16px;
  width:16px;
  height:16px;}
.numeric-ratio-icon img{
  display:block;
  width:12px;
  height:12px;
  object-fit:contain;
  filter:brightness(0);
  opacity:1;}
.numeric-ratio-value{
  margin:0;
  font-size:var(--fs-cm);
  font-weight:400;
  line-height:16px;
  color:var(--font-secondary);
  white-space:nowrap;}
.numeric-ratio-stack{
  display:inline-flex;
  flex-direction:column;
  align-items:flex-start;
  gap:4px;}

/* ── H_BarChart · 水平柱状图 · 文本标签 + 数值单位 + Track + Bar ── */
.bar-chart{
  display:flex;
  width:100%;
  min-width:0;
  flex-direction:column;
  align-items:flex-start;
  gap:11px;
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;}
.bar-chart-item{
  display:flex;
  width:100%;
  min-width:0;
  flex-direction:column;
  align-items:flex-start;
  gap:4px;}
.bar-chart-meta{
  display:flex;
  width:100%;
  min-width:0;
  align-items:flex-end;
  justify-content:space-between;
  gap:8px;}
.bar-chart-label{
  flex:1 1 auto;
  min-width:0;
  margin:0;
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap;
  font-size:var(--fs-bm);
  font-weight:700;
  line-height:20px;
  color:var(--font-secondary);}
.bar-chart-value-unit{
  flex:0 0 auto;
  margin:0;
  font-size:var(--fs-bm);
  font-weight:700;
  line-height:20px;
  color:var(--font-secondary);
  white-space:nowrap;
  text-align:right;
  font-variant-numeric:tabular-nums;}
.bar-chart-track{
  width:100%;
  height:6px;
  min-height:6px;
  max-height:6px;
  flex:0 0 6px;
  overflow:hidden;
  border-radius:32px;
  background:var(--graphic-tertiary);}
.bar-chart-bar{
  width:clamp(0%,calc(var(--bar-chart-percent,0) * 1%),100%);
  height:100%;
  min-height:6px;
  max-height:6px;
  border-radius:2px;
  background:var(--graphic-primary);}
[data-theme="dark"] .bar-chart:not([data-mode="light"]) .bar-chart-label,
.bar-chart[data-mode="dark"] .bar-chart-label{color:var(--font-secondary);}
[data-theme="dark"] .bar-chart:not([data-mode="light"]) .bar-chart-value-unit,
.bar-chart[data-mode="dark"] .bar-chart-value-unit{color:var(--font-secondary);}
[data-theme="dark"] .bar-chart:not([data-mode="light"]) .bar-chart-track,
.bar-chart[data-mode="dark"] .bar-chart-track{background:var(--graphic-tertiary);}
[data-theme="dark"] .bar-chart:not([data-mode="light"]) .bar-chart-bar,
.bar-chart[data-mode="dark"] .bar-chart-bar{background:var(--graphic-primary);}

/* BEGIN V15_REFERENCE_STYLES · generated by scripts/sync-v15-runtime-styles.js */
/* ── Tokens ─────────────────────────────────────── */
:root {
  /* ── HarmonyOS HMOS Design Tokens ─────────────────
     Neutrals: Snow Gray → Night Black
     Brand Blue anchor: #0A59F7 (HarmonyOS emphasize)
     Functional: connected #64BB5C · alert #ED6F21 · warning #E84026 */
  /* ═══ HarmonyOS Design Tokens ═══
     色值来源：HarmonyOS Component Library.sketch · sharedSwatches
     · 文本 / 边框 / 蒙层采用 black-alpha / white-alpha 叠加
     · 语义色 anchor 取自 ohos_id_color_* 与 palette 色板
  */
  --gray-0:#fff; --gray-25:#fafafa; --gray-50:#f5f5f5; --gray-75:#f0f0f0; --gray-100:#ebebeb;
  --gray-150:#e0e0e0; --gray-200:#d4d4d4; --gray-250:#c7c7c7; --gray-300:#b3b3b3;
  --gray-350:#a0a0a0; --gray-400:#8c8c8c; --gray-450:#787878; --gray-500:#666666;
  --gray-550:#545454; --gray-600:#454545; --gray-650:#383838; --gray-700:#2d2d2d;
  --gray-750:#242424; --gray-800:#1d1d1d; --gray-850:#181818; --gray-900:#141414;
  --gray-950:#0f0f0f; --gray-975:#0a0a0a; --gray-1000:#000;

  /* emphasize 品牌色 · anchor #0A59F7 (ohos_id_color_emphasize / palette8) */
  --blue-25:#f4f7ff; --blue-50:#e8efff; --blue-75:#d1dfff; --blue-100:#a9c1ff;
  --blue-200:#7a9fff; --blue-300:#4b7dff; --blue-400:#0a59f7; --blue-500:#0847cc;
  --blue-600:#0637a3; --blue-700:#052b80; --blue-800:#04205e; --blue-900:#03173f;

  /* connected 确认色 · anchor #64BB5C (ohos_id_color_connected / palette4) */
  --green-25:#f1faef; --green-50:#e0f4dd; --green-75:#c2e7bd; --green-100:#a0d79a;
  --green-200:#87cc80; --green-300:#73c16b; --green-400:#64bb5c; --green-500:#4ea047;
  --green-600:#3c8336; --green-700:#2d6628; --green-800:#1e481b; --green-900:#122e10;

  /* warning 一级警示色 · anchor #E84026 (ohos_id_color_warning / ohos_id_color_handup) */
  --red-25:#fef3f1; --red-50:#fde4e0; --red-75:#fbc9c1; --red-100:#f7a096;
  --red-200:#f27a6b; --red-300:#ed5a46; --red-400:#e84026; --red-500:#c4321c;
  --red-600:#a02614; --red-700:#7c1c0e; --red-800:#581308; --red-900:#380b04;

  /* alert 二级警示色 · anchor #ED6F21 (ohos_id_color_alert / palette9) */
  --orange-25:#fff6ef; --orange-50:#ffebd9; --orange-75:#ffd4ae; --orange-100:#ffba7d;
  --orange-200:#fb9e51; --orange-300:#f48533; --orange-400:#ed6f21; --orange-500:#c85a19;
  --orange-600:#a24712; --orange-700:#7c360c; --orange-800:#562507; --orange-900:#371704;

  /* yellow · anchor #F7CE00 (palette11) */
  --yellow-25:#fffef0; --yellow-50:#fffbd0; --yellow-75:#fff6a0; --yellow-100:#ffed6e;
  --yellow-200:#ffe344; --yellow-300:#fcd824; --yellow-400:#f7ce00; --yellow-500:#cca900;
  --yellow-600:#a38500; --yellow-700:#7a6300; --yellow-800:#524200; --yellow-900:#342900;

  /* purple · anchor #AC49F5 (palette6) */
  --purple-25:#faf2ff; --purple-50:#f3e0ff; --purple-75:#e4c2fe; --purple-100:#d39dfa;
  --purple-200:#c276f6; --purple-300:#b85ff5; --purple-400:#ac49f5; --purple-500:#8c3bcc;
  --purple-600:#702fa3; --purple-700:#54247b; --purple-800:#3a1957; --purple-900:#230f36;

  /* pink · anchor #E64566 (palette7) */
  --pink-25:#fef3f5; --pink-50:#fde1e7; --pink-75:#fac2cf; --pink-100:#f59ab0;
  --pink-200:#ef7690; --pink-300:#eb5c7b; --pink-400:#e64566; --pink-500:#c0374f;
  --pink-600:#9a2c3f; --pink-700:#75212f; --pink-800:#52161f; --pink-900:#330c12;

  /* cyan · anchor #61CFBE (palette3) */
  --cyan-25:#edfbf9; --cyan-50:#d7f5f1; --cyan-75:#b1ecde; --cyan-100:#8adfd3;
  --cyan-200:#74d5c8; --cyan-300:#6bd2c3; --cyan-400:#61cfbe; --cyan-500:#4fac9e;
  --cyan-600:#3f897e; --cyan-700:#306860; --cyan-800:#214944; --cyan-900:#142e2a;

  --white:#fff;

  /* ── 1.3.1 背景模板：所有示例卡片只能引用以下规范 Token ── */
  --card-bg-solid-blue:#E5EDFE;
  --card-bg-solid-orange:#FFF3E6;
  --card-bg-solid-green:#F0FFE6;
  --card-bg-solid-cyan:#E6FDFF;
  --card-bg-solid-purple:#EDE6FF;
  --card-bg-solid-blue-content:#1f4799;
  --card-bg-solid-orange-content:#99661f;
  --card-bg-solid-green-content:#52991f;
  --card-bg-solid-cyan-content:#1f8f99;
  --card-bg-solid-purple-content:#401f99;

  /* 融球背景·四组配色 */
  --card-bg-orb-orange-right-bottom-color:#FAA89E;
  --card-bg-orb-orange-left-bottom-color:#FF8E3E;
  --card-bg-orb-orange-top-color:#BF3F26;
  --card-bg-orb-blue-right-bottom-color:rgba(82,204,204,1);
  --card-bg-orb-blue-left-bottom-color:rgba(143,162,217,1);
  --card-bg-orb-blue-top-color:rgba(18,30,89,1);
  --card-bg-orb-purple-right-bottom-color:rgba(179,152,217,1);
  --card-bg-orb-purple-left-bottom-color:rgba(87,97,217,1);
  --card-bg-orb-purple-top-color:rgba(27,18,89,1);
  --card-bg-orb-green-right-bottom-color:rgba(96,191,152,1);
  --card-bg-orb-green-left-bottom-color:rgba(38,191,166,1);
  --card-bg-orb-green-top-color:rgba(23,115,76,1);

  /* 融球几何 — 相对宿主卡片尺寸，圆角随卡片 */
  --card-bg-orb-right-bottom-size:62.5%;
  --card-bg-orb-right-bottom-x:60%;
  --card-bg-orb-right-bottom-y:50%;
  --card-bg-orb-left-bottom-size:100%;
  --card-bg-orb-left-bottom-x:-25%;
  --card-bg-orb-left-bottom-y:43.75%;
  --card-bg-orb-top-size:131.25%;
  --card-bg-orb-top-x:-15.625%;
  --card-bg-orb-top-y:-56.25%;
  --card-bg-orb-backplate:rgba(255,255,255,.05);
  --card-bg-orb-blur:50px;

  /* ── 按背景类型映射的按钮示例色 ── */
  --button-light-blue-bg:rgba(10,89,247,.10);
  --button-light-blue-content:#0A59F7;
  --button-dark-bg:#FFFFFF;

  /* 展示层内部圆角值（不作为 Design Token 对外展示） */
  --radius-2xs:2px; --radius-xs:4px; --radius-sm:6px;
  --radius-md:8px; --radius-lg:10px; --radius-xl:12px;
  --radius-2xl:16px; --radius-3xl:20px; --radius-4xl:24px; --radius-full:9999px;

  /* ── HarmonyOS semantic tokens (Light) ──
     text/border 采用 black-alpha，对应 ohos_id_color_text_* / list_separator / component_normal
     surface 对应 ohos_id_color_background / sub_background / card_bg */
  --surface:#fff;         /* ohos_id_color_card_bg / background */
  --surface-2:#f1f3f5;    /* ohos_id_color_sub_background / panel_bg */
  --surface-3:#f1f3f5;    /* ohos_id_color_sub_background */
  --text:rgba(0,0,0,.902);     /* ohos_id_color_text_primary */
  --text-2:rgba(0,0,0,.6);     /* ohos_id_color_text_secondary / text_hint */
  --text-3:rgba(0,0,0,.4);     /* ohos_id_color_text_tertiary */
  --border:rgba(0,0,0,.05);       /* ohos_id_color_list_separator */
  --border-strong:rgba(0,0,0,.102); /* ohos_id_color_component_normal */
  --sh1:0 1px 2px -1px rgba(0,0,0,.08);
  --sh2:0 2px 4px -1px rgba(0,0,0,.08);
  --sh3:0 4px 8px -2px rgba(0,0,0,.10);
  --sh4:0 8px 16px -4px rgba(0,0,0,.12);
  --font:"HarmonyOS Sans SC","HarmonyOS Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,"PingFang SC","Microsoft YaHei",sans-serif;
  --mono:ui-monospace,"SF Mono","Menlo",monospace;

  /* ── Typography Scale Tokens ── */
  --fs-dl:3.5rem; --fw-dl:300; /* Display_L · 56px · Light */
  --fs-dm:3rem;   --fw-dm:300; /* Display_M · 48px · Light */
  --fs-ds:2.375rem;--fw-ds:300;/* Display_S · 38px · Light */
  --fs-tl:1.875rem;--fw-tl:700;/* Title_L   · 30px · Bold */
  --fs-tm:1.5rem;  --fw-tm:700;/* Title_M   · 24px · Bold */
  --fs-ts:1.25rem; --fw-ts:700;/* Title_S   · 20px · Bold */
  --fs-stl:1.125rem;--fw-stl:500;/* Subtitle_L· 18px · Medium */
  --fs-stm:1rem;   --fw-stm:500;/* Subtitle_M· 16px · Medium */
  --fs-sts:.875rem;--fw-sts:500;/* Subtitle_S· 14px · Medium */
  --fs-bl:1rem;    --fw-bl:400; /* Body_L    · 16px · Regular */
  --fs-bm:.875rem; --fw-bm:400; /* Body_M    · 14px · Regular */
  --fs-bs:.75rem;  --fw-bs:400; /* Body_S    · 12px · Regular */
  --fs-cl:.75rem;  --fw-cl:500; /* Caption_L · 12px · Medium（组件可覆写 Regular） */
  --fs-cm:.625rem; --fw-cm:500; /* Caption_M · 10px · Medium（组件可覆写 Regular） */
  --fs-cs:.5rem;   --fw-cs:500; /* Caption_S · 8px  · Medium */

  /* ── Font Color Tokens · Light Mode ── */
  --font-primary:#000000;
  --font-secondary:rgba(0,0,0,.6);
  --font-tertiary:rgba(0,0,0,.4);
  --top-text-bottom-value-divider:rgba(0,0,0,.2);

  /* ── Backplate Color Tokens · Light Mode ── */
  --comp_background_primary:#ffffff;
  --comp_background_secondary:rgba(0,0,0,.20);
  --comp_background_tertiary:rgba(0,0,0,.10);

  /* ── Progress Circle Tokens ── */
  --pc-track:rgba(0,0,0,.10);
  --pc-bar:#64bb5c;
  --pc-sm:44px; --pc-sm-sw:6px;
  --pc-md:96px; --pc-md-sw:6px;

}
[data-theme="dark"] {
  /* HarmonyOS dark palette — inverted Night Black scale */
  --gray-0:#000; --gray-25:#0a0a0a; --gray-50:#0f0f0f; --gray-75:#141414; --gray-100:#181818;
  --gray-150:#1d1d1d; --gray-200:#242424; --gray-250:#2d2d2d; --gray-300:#383838;
  --gray-350:#454545; --gray-400:#545454; --gray-450:#666666; --gray-500:#787878;
  --gray-550:#8c8c8c; --gray-600:#a0a0a0; --gray-650:#b3b3b3; --gray-700:#c7c7c7;
  --gray-750:#d4d4d4; --gray-800:#e0e0e0; --gray-850:#ebebeb; --gray-900:#f0f0f0;
  --gray-950:#f5f5f5; --gray-975:#fafafa; --gray-1000:#fff;
  /* HarmonyOS dark-mode anchor overrides (palette dark values) */
  --blue-400:#317af7;     /* palette8 dark */
  --green-400:#5ba854;    /* palette4 dark */
  --red-400:#d94838;      /* ohos warning dark */
  --orange-400:#db6b42;   /* palette9 dark */
  --yellow-400:#d1a738;   /* palette11 dark */
  --purple-400:#8c55c2;   /* palette6 dark */
  --pink-400:#d64966;     /* palette7 dark */
  --cyan-400:#5aada0;     /* palette3 dark */
  /* ── HarmonyOS semantic tokens (Dark) ── */
  --surface:#2e3033;      /* ohos_id_color_card_bg dark */
  --surface-2:#000;       /* ohos_id_color_background / sub_background dark */
  --surface-3:#202224;    /* ohos_id_color_panel_bg / dialog_bg dark */
  --text:rgba(255,255,255,.8588);  /* ohos_id_color_text_primary dark */
  --text-2:rgba(255,255,255,.6);   /* ohos_id_color_text_secondary dark */
  --text-3:rgba(255,255,255,.4);   /* ohos_id_color_text_tertiary dark */
  --border:rgba(255,255,255,.051);    /* ohos_id_color_list_separator dark */
  --border-strong:rgba(255,255,255,.102); /* ohos_id_color_component_normal dark */
  --sh1:0 1px 2px -1px rgba(0,0,0,.24); --sh2:0 2px 4px -1px rgba(0,0,0,.24);
  --sh3:0 4px 8px -2px rgba(0,0,0,.36); --sh4:0 8px 16px -4px rgba(0,0,0,.32);
  /* ── Font Color Tokens (Dark) ── */
  --font-primary:#ffffff;
  --font-secondary:rgba(255,255,255,.6);
  --font-tertiary:rgba(255,255,255,.4);
  --top-text-bottom-value-divider:rgba(255,255,255,.2);
  /* ── Graphic Element Color Tokens (Dark) ── */
  --graphic-primary:#ffffff;
  --graphic-secondary:rgba(255,255,255,.60);
  --graphic-tertiary:rgba(255,255,255,.20);
  /* ── Backplate Color Tokens (Dark) ── */
  --comp_background_primary:#ffffff;
  --comp_background_secondary:rgba(255,255,255,.20);
  --comp_background_tertiary:rgba(255,255,255,.10);
  /* ── Progress Circle Tokens (Dark) ── */
  --pc-track:rgba(255,255,255,.10);}

/* 局部暗色模式：用于暗色卡片背景，不依赖页面主题 */
[data-color-mode="dark"] {
  --font-primary:#ffffff;
  --font-secondary:rgba(255,255,255,.60);
  --font-tertiary:rgba(255,255,255,.40);
  --top-text-bottom-value-divider:rgba(255,255,255,.20);
  --graphic-primary:#ffffff;
  --graphic-secondary:rgba(255,255,255,.60);
  --graphic-tertiary:rgba(255,255,255,.20);
  --comp_background_primary:#ffffff;
  --comp_background_secondary:rgba(255,255,255,.20);
  --comp_background_tertiary:rgba(255,255,255,.10);}

/* 单色模式：宿主背景模板必须提供 --background-content-color */
[data-color-mode="monochrome"] {
  --font-primary:var(--background-content-color);
  --font-secondary:color-mix(in srgb,var(--background-content-color) 60%,transparent);
  --font-tertiary:color-mix(in srgb,var(--background-content-color) 40%,transparent);
  --graphic-primary:var(--background-content-color);
  --graphic-secondary:color-mix(in srgb,var(--background-content-color) 60%,transparent);
  --graphic-tertiary:color-mix(in srgb,var(--background-content-color) 20%,transparent);
  --comp_background_primary:var(--background-content-color);
  --comp_background_secondary:color-mix(in srgb,var(--background-content-color) 20%,transparent);
  --comp_background_tertiary:color-mix(in srgb,var(--background-content-color) 10%,transparent);}

/* ── Design Token Showcase ────────────────────── */
/* Typography */
.dt-type-item{display:flex;align-items:baseline;gap:16px;padding:5px 0;border-bottom:1px solid var(--border)}
.dt-type-item:last-child{border-bottom:none}
.dt-type-token{font-size:.5625rem;color:var(--text-3);width:88px;flex-shrink:0;font-family:var(--mono);white-space:nowrap}
.dt-type-spec{font-size:.5625rem;color:var(--text-3);width:88px;flex-shrink:0;white-space:nowrap}

/* ── Typography Table ── */
.tt{width:100%;border-collapse:collapse}
.tt thead tr{background:var(--surface-3)}
.tt th{font-size:.5rem;font-weight:700;color:var(--text-3);text-transform:uppercase;letter-spacing:.07em;padding:8px 12px;border-bottom:1px solid var(--border-strong);text-align:left}
.tt td{padding:8px 12px;border-bottom:1px solid var(--border);vertical-align:middle}
.tt tr:last-child td{border-bottom:none}
.tt tr:nth-child(even) td{background:rgba(0,0,0,.012)}
.tt-tok{font-family:var(--mono);color:var(--blue-500);font-weight:600;font-size:.625rem}
.tt-val{font-family:var(--mono);color:var(--text-2);font-size:.5625rem}
/* ── Font Color Grid ── */
.fc-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.fc-item{display:flex;flex-direction:column;gap:6px}
.fc-sw{height:32px;border-radius:var(--radius-md);border:1px solid rgba(0,0,0,.08)}
.fc-tk{font-size:.5625rem;font-weight:700;color:var(--text);font-family:var(--mono)}
.fc-val{font-size:.5rem;color:var(--text-3);font-family:var(--mono)}
/* Dark row container */
.fc-dark-row{background:#1a1a1a;border-radius:var(--radius-lg);padding:16px 16px 12px;margin-top:12px}
.fc-dark-row .fc-grid{gap:8px}
.fc-dark-row .fc-sw{border-color:rgba(255,255,255,.12)}
.fc-dark-row .fc-tk{color:rgba(255,255,255,.85)}
.fc-dark-row .fc-val{color:rgba(255,255,255,.4)}
.fc-dark-row .fc-lbl{font-size:.5rem;font-weight:600;color:rgba(255,255,255,.4);text-transform:uppercase;letter-spacing:.06em;margin-bottom:10px}
.fc-mono-row{background:var(--card-bg-solid-blue);border-radius:var(--radius-lg);padding:16px 16px 12px;margin-top:12px}
.fc-mono-row .fc-grid{gap:8px}
.fc-mono-row .fc-sw{border-color:color-mix(in srgb,var(--background-content-color) 18%,transparent)}
.fc-mono-row .fc-tk{color:var(--background-content-color)}
.fc-mono-row .fc-val{color:color-mix(in srgb,var(--background-content-color) 70%,transparent)}
.fc-mono-row .fc-lbl{font-size:.5rem;font-weight:600;color:color-mix(in srgb,var(--background-content-color) 70%,transparent);text-transform:uppercase;letter-spacing:.06em;margin-bottom:10px}
/* ── Scene / Rule Lists ── */
.scene-list{display:flex;flex-direction:column;gap:7px}
.scene-item{display:flex;gap:9px;align-items:flex-start;font-size:.8125rem;color:var(--text-2);line-height:1.5}
.sc-icon{width:16px;height:16px;border-radius:50%;background:var(--blue-25);color:var(--blue-500);font-size:.4375rem;font-weight:700;flex-shrink:0;margin-top:2px;display:flex;align-items:center;justify-content:center}
.sc-no{background:rgba(0,0,0,.05);color:var(--text-3)}
.rule-list{display:flex;flex-direction:column}
.rule-item{display:flex;gap:10px;align-items:flex-start;font-size:.8125rem;color:var(--text-2);line-height:1.5;padding:7px 0;border-bottom:1px solid var(--border)}
.rule-item:last-child{border-bottom:none}
.rk{font-size:.625rem;font-weight:700;color:var(--text);font-family:var(--mono);flex-shrink:0;min-width:76px;padding-top:2px}
/* ── Ring Demos ── */
.ring-row{display:flex;flex-wrap:wrap;gap:20px;align-items:flex-start}
.ring-cell{display:flex;flex-direction:column;align-items:center;gap:8px;flex-shrink:0}
.ring-wrap{position:relative;flex-shrink:0}
.ring-center{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;pointer-events:none;gap:5px}
.rn-spec{font-size:.6875rem;font-weight:600;color:var(--text);font-family:var(--mono);text-align:center}
.ri-spec{font-size:.4375rem;color:var(--text-3);font-family:var(--mono);margin-top:1px;text-align:center;line-height:1.6}
.ri-b{color:var(--blue-500)!important}
/* ── Center Text Spec ── */
.ct-spec-cell{padding:10px 12px;background:var(--surface-2);border:1px solid var(--border);border-radius:var(--radius-lg)}
.ct-spec-head{font-size:.625rem;font-weight:700;color:var(--blue-500);font-family:var(--mono);margin-bottom:8px}
.ct-spec-body{font-size:.6875rem;color:var(--text-2);line-height:1.8}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:20px}

/* ── Background color templates ─────────────────── */
.color-guide-stack{display:flex;flex-direction:column;gap:8px}
.bg-template-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(218px,1fr));gap:10px}
.bg-template{
  min-width:0;overflow:hidden;border:1px solid var(--border);border-radius:var(--radius-xl);
  background:var(--surface);}
.bg-template-preview{
  position:relative;width:140px;height:140px;margin:12px auto 0;border:0;
  border-radius:24px;background:var(--bg-preview,#fff);overflow:hidden;
  display:flex;align-items:flex-start;padding:12px;color:rgba(0,0,0,.6);}
.bg-template-preview::after{
  content:"";position:absolute;inset:0;border-radius:inherit;
  box-shadow:none;pointer-events:none;}
.bg-template-preview[data-tone="dark"]{color:rgba(255,255,255,.9)}
.bg-template-body{display:flex;flex-direction:column;gap:5px;padding:10px 12px 12px}
.bg-template-spec{font-size:.6875rem;line-height:1.125rem;color:var(--text-2)}
.bg-template-apps{font-size:.625rem;line-height:1rem;color:var(--text-3)}
.bg-code{font-family:var(--mono);font-size:.625rem;color:var(--blue-500);white-space:nowrap}

/* 融球背景模板
   几何（ellipse 的 x / y / 尺寸）全部为宿主卡片尺寸的百分比，
   模板铺满宿主卡片，圆角随宿主卡片。 */
.card-bg-orb{
  position:relative;padding:0;isolation:isolate;overflow:hidden;background:transparent;}
.card-bg-orb__canvas{
  position:absolute;inset:0;display:block;width:100%;height:100%;
  overflow:hidden;pointer-events:none;}
.card-bg-orb__ellipse{position:absolute;border-radius:50%;}
.card-bg-orb__ellipse--right-bottom{
  left:var(--card-bg-orb-right-bottom-x);top:var(--card-bg-orb-right-bottom-y);
  width:var(--card-bg-orb-right-bottom-size);aspect-ratio:1/1;
  background:var(--card-bg-orb-right-bottom-color);}
.card-bg-orb__ellipse--left-bottom{
  left:var(--card-bg-orb-left-bottom-x);top:var(--card-bg-orb-left-bottom-y);
  width:var(--card-bg-orb-left-bottom-size);aspect-ratio:1/1;
  background:var(--card-bg-orb-left-bottom-color);}
.card-bg-orb__ellipse--top{
  left:var(--card-bg-orb-top-x);top:var(--card-bg-orb-top-y);
  width:var(--card-bg-orb-top-size);aspect-ratio:1/1;
  background:var(--card-bg-orb-top-color);}
.card-bg-orb__backplate{
  position:absolute;inset:0;width:100%;height:100%;background:var(--card-bg-orb-backplate);
  -webkit-backdrop-filter:blur(var(--card-bg-orb-blur));
  backdrop-filter:blur(var(--card-bg-orb-blur));}

/* 融球配色修饰类 */
.card-bg-orb--orange{
  --card-bg-orb-right-bottom-color:var(--card-bg-orb-orange-right-bottom-color);
  --card-bg-orb-left-bottom-color:var(--card-bg-orb-orange-left-bottom-color);
  --card-bg-orb-top-color:var(--card-bg-orb-orange-top-color);}
.card-bg-orb--blue{
  --card-bg-orb-right-bottom-color:var(--card-bg-orb-blue-right-bottom-color);
  --card-bg-orb-left-bottom-color:var(--card-bg-orb-blue-left-bottom-color);
  --card-bg-orb-top-color:var(--card-bg-orb-blue-top-color);}
.card-bg-orb--purple{
  --card-bg-orb-right-bottom-color:var(--card-bg-orb-purple-right-bottom-color);
  --card-bg-orb-left-bottom-color:var(--card-bg-orb-purple-left-bottom-color);
  --card-bg-orb-top-color:var(--card-bg-orb-purple-top-color);}
.card-bg-orb--green{
  --card-bg-orb-right-bottom-color:var(--card-bg-orb-green-right-bottom-color);
  --card-bg-orb-left-bottom-color:var(--card-bg-orb-green-left-bottom-color);
  --card-bg-orb-top-color:var(--card-bg-orb-green-top-color);}

.bg-template--orb .bg-template-body{gap:4px}


/* ── Reset ───────────────────────────────────────── */
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:var(--font);background:var(--surface-2);color:var(--text);line-height:1.5;font-size:16px}
button{font-family:var(--font);cursor:pointer}
a{text-decoration:none}

/* ── Layout ──────────────────────────────────────── */
.header{
  background:var(--surface);border-bottom:1px solid var(--border);
  padding:16px 40px;display:flex;align-items:center;justify-content:space-between;
  position:sticky;top:0;z-index:100;box-shadow:var(--sh1);}
.header-title{font-size:1rem;font-weight:600}
.header-meta{font-size:.8125rem;color:var(--text-2);margin-top:2px}
.theme-btn{
  display:flex;align-items:center;gap:6px;font-size:.8125rem;color:var(--text-2);
  background:var(--surface-3);border:1px solid var(--border);border-radius:var(--radius-full);
  padding:5px 14px;transition:background .12s;}
.theme-btn:hover{background:var(--gray-100)}

.main{max-width:1100px;margin:0 auto;padding:32px 40px 80px}

/* TOC */
.toc{
  background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-2xl);
  padding:20px 24px;margin-bottom:36px;box-shadow:var(--sh1);}
.toc{display:flex;flex-direction:column;gap:14px}
.toc-group{display:flex;flex-direction:column;gap:8px}
.toc-title{font-size:.6875rem;font-weight:600;color:var(--text-2);text-transform:uppercase;letter-spacing:.06em}
.toc-sep{height:1px;background:var(--border)}
.toc-links{display:flex;flex-wrap:wrap;gap:6px}
.toc-link{
  font-size:.8125rem;color:var(--blue-500);
  padding:3px 10px;border-radius:var(--radius-full);
  border:1px solid var(--blue-100);background:var(--blue-25);
  font-weight:500;transition:all .12s;}
.toc-link:hover{background:var(--blue-50)}
.toc-link--token{
  color:var(--purple-500,#5f24ad);
  border-color:var(--purple-100,#c39cfa);
  background:var(--purple-25,#f8f2ff);}
.toc-link--token:hover{background:var(--purple-50,#eee0ff)}
.toc-subgroup{display:flex;flex-wrap:wrap;gap:6px;width:100%;padding-left:18px}
.toc-subgroup .toc-link{font-size:.75rem;font-weight:400}

/* Section */
.section{margin-bottom:48px}
.section-head{margin-bottom:16px}
.section-title{font-size:1rem;font-weight:600;margin-bottom:2px}
.section-desc{font-size:.8125rem;color:var(--text-2)}
.category-divider{display:flex;align-items:center;gap:16px;margin:48px 0 24px;scroll-margin-top:24px}
.category-divider::before,.category-divider::after{content:"";flex:1;height:1px;background:var(--border)}
.category-divider-label{font-size:.8125rem;font-weight:600;color:var(--text-2);letter-spacing:.04em;padding:0 4px}

.card{
  background:var(--surface);border:1px solid var(--border);
  border-radius:var(--radius-2xl);padding:28px;box-shadow:var(--sh1);}
.sub{margin-bottom:24px}
.sub:last-child{margin-bottom:0}
.lbl{font-size:.6875rem;font-weight:600;color:var(--text-2);text-transform:uppercase;letter-spacing:.06em;margin-bottom:10px}
.row{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
.col{display:flex;flex-direction:column;gap:10px}
.divider{height:1px;background:var(--border);margin:20px 0}

/* ── Button ──────────────────────────────────────── */
.btn {
  position: relative;
  display: inline-block;
  flex-shrink: 0;
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
  color: inherit;
  border: none;
  background: transparent;
  transition: color .12s;}
.pill-btn {
  --btn-bg:var(--comp_background_tertiary);
  --btn-bg-hover:var(--comp_background_tertiary);
  --btn-bg-active:var(--comp_background_tertiary);
  --btn-label-color:var(--font-primary);
  --btn-icon-color:var(--graphic-primary,var(--font-primary));
  width: 136px;
  height: 36px;
  padding: 0 12px;
  border-radius: 30px;
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;
  font-size: 14px;
  font-weight: 500;
  line-height: 19px;}
.circle-btn {
  --btn-bg:var(--comp_background_tertiary);
  --btn-bg-hover:var(--comp_background_tertiary);
  --btn-bg-active:var(--comp_background_tertiary);
  --btn-icon-color:var(--graphic-primary,var(--font-primary));
  width: 40px;
  min-width: 40px;
  height: 40px;
  padding: 0;
  border-radius: 50%;}
.circle-btn--even-grid{
  width:44px;
  min-width:44px;
  height:44px;}
.btn::before {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background-color: var(--btn-bg);
  transition: background-color .12s;}
.btn::after {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: inherit;
  pointer-events: none;}
.btn:focus { outline: none;}
.btn:focus-visible::after {
  outline: 2px solid var(--blue-400);
  outline-offset: 2px;}
.btn:hover:not(:disabled)::before { background-color: var(--btn-bg-hover);}
.btn:active:not(:disabled)::before { background-color: var(--btn-bg-active);}
.btn:disabled { opacity: .4; cursor: not-allowed; pointer-events: none;}
.btn-inner {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;}
.btn-icon {
  position: relative;
  z-index: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink:0;
  color:var(--btn-icon-color,var(--graphic-primary,var(--font-primary)));}
.btn-icon svg{display:block;width:20px;height:20px;fill:currentColor}
.btn-icon-mask{
  display:block;width:100%;height:100%;background:currentColor;
  -webkit-mask:var(--button-icon-url) no-repeat center/contain;
  mask:var(--button-icon-url) no-repeat center/contain;}
.pill-btn .btn-inner{gap:8px;align-items:center;justify-content:center}
.pill-btn .btn-icon{
  flex-basis:20px;width:20px;height:20px;
  font-size:18px;line-height:20px;}
.circle-btn .btn-icon{
  flex-basis:20px;width:20px;height:20px;
  font-size:20px;line-height:20px;}
.btn-label {
  position: relative;
  z-index: 1;
  font: inherit;
  color:var(--btn-label-color,var(--font-primary));}
.button-card-position-demo{
  position:relative;width:160px;height:160px;border-radius:20px;
  background:var(--card-bg-solid-blue);
  border:0;overflow:hidden;}
.button-card-position-demo .pill-btn{
  position:absolute;left:12px;bottom:12px;}
.button-card-position-demo .circle-btn{
  position:absolute;right:12px;bottom:12px;}

/* ── CardButton ─────────────────────────────────── */
.card-action-btn{
  box-sizing:border-box;
  width:var(--card-button-width,100%);
  height:var(--card-button-height,100%);
  padding:7px 12px;
  border:0;
  border-radius:16px;
  background:var(--comp_background_tertiary);
  color:var(--font-primary);
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;
  font-size:var(--fs-bm);
  font-weight:700;
  line-height:20px;
  cursor:pointer;
}
.card-action-btn__content{
  display:flex;
  flex-direction:row;
  align-items:center;
  justify-content:space-between;
  width:100%;
  height:100%;
  gap:8px;
}
.card-action-btn__icon{
  display:block;
  order:2;
  flex:0 0 24px;
  width:24px;
  height:24px;
  color:var(--graphic-primary,var(--font-primary));
}
.card-action-btn__icon--asset{
  background-color:currentColor;
  -webkit-mask:var(--card-action-icon-image) center / contain no-repeat;
  mask:var(--card-action-icon-image) center / contain no-repeat;}
.card-action-btn__icon--calendar{--card-action-icon-image:url("resources/base/media/calendar_fill.svg");}
.card-action-btn__icon--power{--card-action-icon-image:url("resources/base/media/battery_leaf_fill.svg");}
.card-action-btn__icon--exercise{--card-action-icon-image:url("resources/base/media/figure_run.svg");}
.card-action-btn__icon--music{--card-action-icon-image:url("resources/base/media/music_fill.svg");}
.card-action-btn__label{
  order:1;
  flex:1 1 auto;
  min-width:0;
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap;
  text-align:left;
  color:var(--font-primary);
}
.card-button-demo-grid{
  display:flex;
  flex-wrap:wrap;
  gap:20px;
  align-items:flex-end;
}
.card-button-demo-item{
  display:flex;
  flex-direction:column;
  gap:8px;
  align-items:flex-start;
}
.card-button-demo-item[hidden]{display:none;}
.card-button-type14-demo-card{
  box-sizing:border-box;
  display:grid;
  grid-template-columns:144px 144px;
  grid-template-rows:64px 64px;
  gap:8px;
  width:320px;
  height:160px;
  padding:12px;
  border-radius:20px;}
.card-button-type14-demo-card .card-action-btn{
  --card-button-width:144px;
  --card-button-height:64px;}

/* ── Icon media library ─────────────────────────── */
.icon-media-grid{
  display:grid;grid-template-columns:repeat(auto-fill,minmax(112px,1fr));gap:8px;}
.icon-media-item{
  min-width:0;border:1px solid var(--border);border-radius:12px;
  background:var(--surface);overflow:hidden;}
.icon-media-preview{
  height:72px;display:flex;align-items:center;justify-content:center;
  background-color:#f7f7f7;
  background-image:linear-gradient(45deg,#ededed 25%,transparent 25%),linear-gradient(-45deg,#ededed 25%,transparent 25%),linear-gradient(45deg,transparent 75%,#ededed 75%),linear-gradient(-45deg,transparent 75%,#ededed 75%);
  background-size:16px 16px;background-position:0 0,0 8px,8px -8px,-8px 0;}
.icon-media-preview img{display:block;width:32px;height:32px;object-fit:contain}
.icon-media-name{
  min-height:42px;padding:8px;font-family:var(--mono);font-size:.625rem;
  line-height:.8125rem;color:var(--text-2);text-align:center;overflow-wrap:anywhere;}
/* ── App Icon ───────────────────────────────────── */
.app-icon{
  display:block;width:20px;height:20px;flex:0 0 20px;
  border-radius:4px;object-fit:cover;overflow:hidden;}
.app-icon-library .icon-media-preview img{
  display:block;width:20px;height:20px;border-radius:4px;object-fit:cover;}
.app-icon-library .icon-media-name{
  min-height:32px;display:flex;align-items:center;justify-content:center;
  font-family:var(--font-sans);font-size:12px;line-height:16px;color:var(--text-2);}
.app-icon-demo-card{
  box-sizing:border-box;width:160px;height:160px;padding:12px;border-radius:24px;
  background:var(--card-bg-solid-blue);
  border:0;}
.app-icon-title-row{
  display:flex;align-items:flex-start;justify-content:space-between;
  width:136px;min-height:20px;gap:4px;}
.app-icon-demo-title{
  min-width:0;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
  font-family:var(--font-sans);font-size:12px;font-weight:400;line-height:18px;
  color:var(--font-secondary);text-align:left;}
.icon-subsection-heading{
  scroll-margin-top:90px;margin:0 0 16px;font-size:14px;font-weight:600;
  line-height:20px;color:var(--text);}
.icon-subsection-heading.has-divider{
  margin-top:32px;padding-top:24px;border-top:1px solid var(--border);}
.weather-icon-library{grid-template-columns:repeat(auto-fill,112px);}
.weather-icon-library .icon-media-preview img{
  width:20px;height:20px;border-radius:4px;object-fit:contain;}
.weather-icon-demo-card{
  position:relative;isolation:isolate;contain:paint;overflow:hidden;
  box-sizing:border-box;width:160px;height:160px;padding:12px;border-radius:24px;
  background:transparent;border:0;}
.weather-icon-demo-bg{
  z-index:0;pointer-events:none;}
.weather-icon-demo-content{
  position:relative;z-index:1;width:100%;height:100%;
  display:flex;flex-direction:column;align-items:flex-start;}
.weather-icon-demo-title{
  font-family:var(--font-sans);font-size:12px;font-weight:400;line-height:18px;
  color:var(--font-secondary);}
.weather-icon-demo-title-row{
  display:flex;align-items:flex-start;justify-content:space-between;
  width:136px;min-height:20px;gap:4px;}
.weather-icon-demo-reading{display:flex;align-items:center;gap:8px;margin-top:4px;}
.weather-icon-demo-temp{
  font-family:var(--font-sans);font-size:38px;font-weight:700;line-height:46px;
  color:var(--font-primary);font-variant-numeric:tabular-nums;}
.weather-icon-demo-glyph{
  display:block;width:20px;height:20px;border-radius:4px;object-fit:contain;}
.weather-icon-demo-meta{
  margin-top:auto;font-family:var(--font-sans);font-size:12px;font-weight:400;
  line-height:18px;color:var(--font-secondary);}
/* ── Button 配色由卡片背景上下文统一注入 ── */

/* ── ProgressLine2 · EmphasizedData + Bar ───────── */
.pl2{
  display:flex;
  flex-direction:column;
  align-items:stretch;
  gap:6px;
  box-sizing:border-box;
  padding-bottom:4px;
  width:100%;
  min-width:0;}
.pl2 .ed{
  min-height:0;
  align-items:baseline;
  transform:translateY(3px);}
.pl2 .ed-val{line-height:1;}
.pl2 .ed-unit{line-height:1;}
/* ProgressLine2 中间包裹层必须占满所在内容区：flex 行容器下默认按内容收缩，会导致 Track 变短 */
.content-zone > [data-component="progress-line2"]{
  width:100%;
  min-width:0;}
.pl2-track{
  position:relative;
  width:100%;
  height:8px;
  overflow:hidden;
  border-radius:var(--radius-full);
  background:var(--graphic-tertiary,rgba(0,0,0,.10));}
.pl2-bar{
  position:absolute;
  inset:0 auto 0 0;
  width:calc(var(--pl2-current, 0) / var(--pl2-total, 100) * 100%);
  height:8px;
  border-radius:inherit;
  background:var(--graphic-primary,var(--blue-400));}
.pl2-demo-grid{display:flex;flex-wrap:wrap;gap:16px;}
.pl2-demo-case{display:flex;flex-direction:column;gap:6px;}
.pl2-demo-label{font-size:10px;font-weight:500;line-height:14px;color:var(--text-3);}
.pl2-demo-card{
  display:flex;
  flex-direction:column;
  align-items:stretch;
  justify-content:flex-end;
  gap:4px;
  box-sizing:border-box;
  width:160px;
  height:160px;
  padding:12px;
  border-radius:20px;}
.pl2-demo-card > :not(.card-bg-orb__canvas){position:relative;z-index:1;}
.pl2-demo-card[data-card-size="2x4"]{width:320px;}
.pl2-demo-card[data-layout="type10a"],
.pl2-demo-card[data-layout="type10b"],
.pl2-demo-card[data-layout="type2"]{
  justify-content:flex-start;
  gap:8px;}
.pl2-layout-title{
  flex:0 0 12px;
  height:12px;
  overflow:hidden;
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;
  font-size:12px;
  font-weight:400;
  line-height:12px;
  color:var(--font-secondary);
  white-space:nowrap;
  text-overflow:ellipsis;}
.pl2-demo-card[data-layout="type10b"] .pl2-layout-title{
  flex:0 0 auto;
  height:auto;
  min-height:0;}
.pl2-layout-content{
  display:flex;
  flex:1;
  min-height:0;
  flex-direction:column;
  align-items:stretch;
  justify-content:flex-start;}
.pl2-layout-content--type10b{
  align-items:flex-start;
  gap:2px;}
.pl2-layout-content--type10b > *{flex:0 0 auto;}
.pl2-layout-action{
  flex:0 0 36px;
  height:36px;}
.pl2-layout-action .pill-btn{width:100%;}
.pl2-layout-detail{
  display:flex;
  flex:1;
  min-height:0;
  align-items:flex-start;}
/* 示例宿主通过 data-intent-bg 与 data-color-mode 统一注入背景及语义色。 */

/* ── Progress Circle · Icon + 环外数值 ──────────── */
.pr {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;}
.pr-wrap { position: relative;}
.pc-component{display:inline-flex;flex-direction:column;align-items:center;gap:2px}
.pc-external-value{
  margin:0;text-align:center;white-space:nowrap;
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;
  font-size:var(--fs-cm);font-weight:var(--fw-cm);line-height:14px;color:var(--font-primary);}
.pc-center-icon{
  display:flex;align-items:center;justify-content:center;
  width:20px;height:20px;
  color:var(--graphic-secondary,var(--font-secondary));}
.pc-center-icon:has(> img){
  background-color:currentColor;
  -webkit-mask:var(--pc-icon-image) center / contain no-repeat;
  mask:var(--pc-icon-image) center / contain no-repeat;}
.pc-center-icon:has(img[src$="externaldrive_fill.svg"]){--pc-icon-image:url("resources/base/media/externaldrive_fill.svg");}
.pc-center-icon:has(img[src$="music_fill.svg"]){--pc-icon-image:url("resources/base/media/music_fill.svg");}
.pc-center-icon:has(img[src$="phone_fill.svg"]){--pc-icon-image:url("resources/base/media/phone_fill.svg");}
.pc-center-icon:has(img[src$="icon_phone.svg"]){--pc-icon-image:url("resources/base/media/icon_phone.svg");}
.pc-center-icon:has(img[src$="l_circle_fill.svg"]){--pc-icon-image:url("resources/base/media/l_circle_fill.svg");}
.pc-center-icon:has(img[src$="r_circle_fill.svg"]){--pc-icon-image:url("resources/base/media/r_circle_fill.svg");}
.pc-center-icon:has(img[src$="earphone_case_16644.svg"]){--pc-icon-image:url("resources/base/media/earphone_case_16644.svg");}
.pc-center-icon:has(img[src$="battery_leaf_fill.svg"]){--pc-icon-image:url("resources/base/media/battery_leaf_fill.svg");}
.pc-center-icon:has(img[src$="icon_charge.svg"]){--pc-icon-image:url("resources/base/media/icon_charge.svg");}
.pc-center-icon img{display:none;}
.pc-single-combo svg circle:first-of-type,
.pc-component svg circle:first-of-type{stroke:var(--graphic-tertiary,var(--pc-track));}
.pc-single-combo svg circle:nth-of-type(2),
.pc-component svg circle:nth-of-type(2){stroke:var(--graphic-primary,var(--pc-bar));}
.pc-dark-surface{
  width:140px;height:140px;border-radius:24px;
  display:flex;align-items:center;justify-content:center;}
.pc-dark-surface .pc-external-value{color:var(--font-primary)}
.pc-family-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
.pc-family-rule{padding:14px;border:1px solid var(--line);border-radius:12px;background:var(--surface-2)}
.pc-family-rule strong{display:block;margin-bottom:4px;font-size:13px;color:var(--text-1)}
.pc-family-rule span{font-size:12px;line-height:1.6;color:var(--text-3)}
.pc-single-combo{display:inline-flex;align-items:center;gap:8px;min-width:0}
.pc-single-type10a-content{
  align-items:flex-start;
  justify-content:center;}
.pc-single-type11a-card{
  box-sizing:border-box;
  position:relative;
  isolation:isolate;
  overflow:hidden;
  width:160px;
  height:160px;
  padding:12px;
  border-radius:20px;}
.pc-single-type11a-title{
  position:absolute;
  top:12px;
  right:12px;
  left:12px;
  height:18px;}
.pc-single-type11a-hero{
  position:absolute;
  top:38px;
  right:12px;
  left:12px;
  height:52px;}
.pc-single-type11a-secondary{
  position:absolute;
  bottom:12px;
  left:12px;
  width:88px;}
.pc-single-type11a-action{
  position:absolute;
  right:12px;
  bottom:12px;
  width:40px;
  height:40px;}
.pc-single-demo{display:flex;flex-wrap:wrap;gap:24px;align-items:flex-start;justify-content:flex-start;width:100%;text-align:left}
.pc-layout-demo{display:flex;flex-wrap:wrap;gap:20px;align-items:flex-start}
.pc-layout-case{display:flex;flex-direction:column;gap:8px}
.pc-layout-label{font-size:10px;font-weight:500;line-height:14px;color:var(--text-3)}
.pc-demo-card{
  box-sizing:border-box;width:160px;padding:12px;border-radius:20px;
  background:var(--card-bg-solid-blue);color:var(--font-primary);overflow:hidden}
.pc-type12-card{height:160px}
.pc-type12-main{height:92px;display:grid;grid-template-columns:64px 64px;gap:8px}
.pc-type12-zone{width:64px;height:92px;display:flex;align-items:center;justify-content:center;min-width:0}
.pc-type12-button{
  width:136px;height:36px;margin-top:8px;border:0;border-radius:30px;
  display:flex;align-items:center;justify-content:center;gap:8px;
  background:var(--comp_background_tertiary);color:var(--font-primary);font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;
  font-size:14px;font-weight:500;line-height:19px;}
.pillbutton-type12-demo-card > .pill-btn{margin-top:8px;}
.pc-type6-card{height:160px}
.pc-type6-grid{width:136px;height:136px;display:grid;grid-template-columns:64px 64px;grid-template-rows:64px 64px;gap:8px}
.pc-type6-cell{width:64px;height:64px;display:flex;align-items:center;justify-content:center;min-width:0}

/* ── SemiRingBar 半圆进度条 ──────────────────────── */
.srb{display:inline-flex;flex-direction:column;align-items:center;--srb-color:var(--blue-400);}
.srb[data-color="orange"]{--srb-color:var(--orange-400);}
.srb[data-color="green"] {--srb-color:var(--green-400);}
.srb[data-color="red"]   {--srb-color:var(--red-400);}
.srb[data-color="purple"]{--srb-color:var(--purple-400);}
.srb-wrap{position:relative;}
.srb-svg{display:block;}
.srb-track{fill:none;stroke:var(--gray-150);stroke-linecap:round;}
[data-theme="dark"] .srb-track{stroke:var(--gray-400);}
.srb-range{fill:none;stroke:var(--srb-color);stroke-linecap:round;transition:stroke-dashoffset .3s cubic-bezier(.65,0,.35,1);}
.srb-center{
  position:absolute;left:0;right:0;
  bottom:14%;text-align:center;
  font-weight:700;color:var(--text);
  font-size:1.75rem;line-height:1;letter-spacing:-.01em;
}
.srb-scale{
  display:flex;justify-content:space-between;width:100%;
  margin-top:2px;font-size:.875rem;line-height:1.25rem;color:var(--text-3);font-weight:400;
  font-variant-numeric:tabular-nums;
}

/* ── EmphasizedData · 统一数值组件 ──────────────── */
.ed{
  display:inline-flex;
  align-items:baseline;
  gap:2px;
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;}
.ed-val{
  font-size:var(--fs-ds);
  font-weight:700;
  line-height:38px;
  color:var(--font-primary);
  font-variant-numeric:tabular-nums;}
.ed-unit{
  font-size:var(--fs-cl);
  font-weight:400;
  line-height:1.5;
  color:var(--font-secondary);}
/* ── 强调文本 · 主文本 + 次文本 ─────────────────── */
.emphasis-text{
  display:inline-flex;
  flex-direction:column;
  align-items:flex-start;
  gap:2px;
  min-width:0;
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;
  text-align:left;}
.emphasis-text-main{
  margin:0;
  font-size:var(--fs-ts);
  font-weight:700;
  line-height:20px;
  color:var(--font-primary);}
.emphasis-text-secondary{
  margin:0;
  font-size:var(--fs-bs);
  font-weight:400;
  line-height:16px;
  color:var(--font-secondary);}
.secondary-body{
  margin:0;
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;
  font-size:var(--fs-bm);
  font-weight:500;
  line-height:20px;
  color:var(--font-secondary);
  text-align:left;
  white-space:nowrap;}
.secondary-body-group[data-lines="multiple"] .secondary-body{
  font-size:var(--fs-bs);
  line-height:18px;}
.secondary-body-card{
  box-sizing:border-box;
  display:flex;
  flex-direction:column;
  align-items:stretch;
  width:160px;
  height:160px;
  padding:12px;
  gap:8px;
  border-radius:20px;
  background:var(--card-bg-solid-blue);
  box-shadow:none;}
.secondary-body-card-title{
  display:flex;
  flex:0 0 auto;
  min-width:0;
  align-items:flex-start;}
.secondary-body-card-core,
.secondary-body-card-detail{
  display:flex;
  flex:1 1 0;
  min-width:0;
  min-height:0;}
.secondary-body-card-core{
  align-items:flex-start;
  justify-content:flex-start;}
.secondary-body-card-detail{
  flex-direction:column;
  align-items:flex-start;
  justify-content:flex-end;
  gap:2px;}

/* ── Title · SingleLineTitle / DoubleLineTitle ───── */
.single-line-title,
.double-line-title-main,
.double-line-title-sub{
  margin:0;
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;
  text-align:left;}
.single-line-title{
  min-width:0;
  width:100%;
  max-width:100%;
  overflow:hidden;
  font-size:var(--fs-bs);
  font-weight:var(--fw-bs);
  line-height:18px;
  color:var(--font-secondary);
  white-space:nowrap;
  text-overflow:ellipsis;}
.single-line-title-layout{
  display:flex;
  flex-direction:column;
  align-items:flex-start;
  min-width:0;
  flex:1;
  gap:2px;}
.double-line-title{
  display:flex;
  flex-direction:column;
  align-items:flex-start;
  min-width:0;
  flex:1;
  gap:4px;}
.double-line-title-main{
  width:100%;
  overflow:hidden;
  font-size:var(--fs-bs);
  font-weight:700;
  line-height:18px;
  color:var(--font-primary);
  white-space:nowrap;
  text-overflow:ellipsis;}
.double-line-title-sub{
  display:-webkit-box;
  width:100%;
  overflow:hidden;
  font-size:var(--fs-bs);
  font-weight:500;
  line-height:18px;
  color:var(--font-secondary);
  -webkit-box-orient:vertical;
  -webkit-line-clamp:2;
  line-clamp:2;}
.double-title-ratio-demo-card{
  box-sizing:border-box;
  display:flex;
  flex-direction:column;
  align-items:stretch;
  width:160px;
  height:160px;
  padding:12px;
  gap:8px;
  border-radius:20px;}
.double-title-ratio-demo-title{
  flex:0 0 auto;
  min-width:0;}
.double-title-ratio-demo-content{
  display:flex;
  flex:1 1 auto;
  min-height:0;
  align-items:flex-end;
  justify-content:flex-start;}
.title-example-grid{
  display:flex;
  flex-wrap:wrap;
  gap:12px;}
.title-demo-case{
  display:flex;
  flex-direction:column;
  gap:6px;}
.title-demo-case-label{
  font-size:10px;
  font-weight:500;
  line-height:14px;
  color:var(--text-3);}
.title-demo-row{
  display:flex;
  align-items:flex-start;
  width:100%;
  gap:4px;}
.title-area-icon{
  display:block;
  flex:0 0 20px;
  width:20px;
  height:20px;}
.title-position-demo{
  box-sizing:border-box;
  width:276px;
  min-height:80px;
  padding:12px;
  border:0;
  border-radius:var(--radius-xl);
  background:var(--card-bg-solid-blue);}
/* ── DataDisplay · 标签 + 数值 + 单位／辅助信息 ──── */
.data-display{
  display:inline-flex;
  flex-direction:column;
  align-items:center;
  justify-content:center;
  gap:8px;
  min-width:0;
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;
  text-align:center;}
.data-display-label,
.data-display-value,
.data-display-supporting{margin:0;max-width:100%;}
.data-display-label{
  font-size:var(--fs-bs);
  font-weight:500;
  line-height:18px;
  color:var(--font-secondary);}
.data-display-value{
  font-size:var(--fs-dl);
  font-weight:700;
  line-height:60px;
  color:var(--font-primary);
  font-variant-numeric:tabular-nums;}
.data-display-supporting{
  font-size:var(--fs-bm);
  font-weight:400;
  line-height:20px;
  color:var(--font-secondary);}
.data-display-demo-grid{
  display:flex;
  flex-wrap:wrap;
  gap:24px;
  align-items:flex-start;}
.data-display-demo-card{
  box-sizing:border-box;
  width:160px;
  height:160px;
  padding:12px;
  border-radius:20px;
  background:var(--card-bg-solid-blue);
  overflow:hidden;}
.data-display-demo-card.card-bg-orb--orange{
  background:transparent;}
.data-display-type0-module{
  position:relative;
  z-index:1;
  width:136px;
  height:136px;
  display:flex;
  align-items:center;
  justify-content:center;}

/* ── 上文下数 · 三组标签 / 数值 / 单位 ───────────── */
.top-text-bottom-value{
  display:flex;
  width:100%;
  min-width:0;
  align-items:center;
  justify-content:space-around;
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;}
.top-text-bottom-value-item{
  display:flex;
  flex:0 1 auto;
  width:max-content;
  min-width:0;
  flex-direction:column;
  align-items:center;
  justify-content:center;
  gap:0;
  text-align:center;}
.top-text-bottom-value-label,
.top-text-bottom-value-number,
.top-text-bottom-value-unit{
  max-width:100%;
  margin:0;
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap;}
.top-text-bottom-value-number{font-variant-numeric:tabular-nums;}
.top-text-bottom-value[data-parent-width="136"] .top-text-bottom-value-label{
  font-size:var(--fs-cm);
  font-weight:500;
  line-height:16px;
  color:var(--font-primary);}
.top-text-bottom-value[data-parent-width="136"] .top-text-bottom-value-number{
  font-size:var(--fs-bm);
  font-weight:700;
  line-height:20px;
  color:var(--font-primary);}
.top-text-bottom-value[data-parent-width="136"] .top-text-bottom-value-unit{
  font-size:var(--fs-cm);
  font-weight:400;
  line-height:16px;
  color:var(--font-secondary);}
.top-text-bottom-value[data-parent-width="296"] .top-text-bottom-value-label{
  font-size:var(--fs-bs);
  font-weight:500;
  line-height:18px;
  color:var(--font-primary);}
.top-text-bottom-value[data-parent-width="296"] .top-text-bottom-value-number{
  font-size:var(--fs-tm);
  font-weight:700;
  line-height:32px;
  color:var(--font-primary);}
.top-text-bottom-value[data-parent-width="296"] .top-text-bottom-value-unit{
  font-size:var(--fs-bs);
  font-weight:400;
  line-height:18px;
  color:var(--font-secondary);}
.top-text-bottom-value[data-parent-width="296"]{
  position:relative;}
.top-text-bottom-value[data-parent-width="296"]::before,
.top-text-bottom-value[data-parent-width="296"]::after{
  content:"";
  position:absolute;
  top:50%;
  width:1px;
  height:62px;
  background:var(--top-text-bottom-value-divider);
  transform:translate(-50%,-50%);
  pointer-events:none;}
.top-text-bottom-value[data-parent-width="296"]::before{left:33.333%;}
.top-text-bottom-value[data-parent-width="296"]::after{left:66.667%;}
.top-text-bottom-value-demo-grid{
  display:flex;
  flex-wrap:wrap;
  align-items:flex-start;
  gap:24px;}
.top-text-bottom-value-demo-case{
  display:flex;
  flex-direction:column;
  gap:6px;}
.top-text-bottom-value-demo-label{
  font-size:var(--fs-cm);
  font-weight:500;
  line-height:16px;
  color:var(--text-3);}
.top-text-bottom-value-demo-card{
  box-sizing:border-box;
  height:160px;
  padding:12px;
  border-radius:20px;
  display:flex;
  flex-direction:column;
  overflow:hidden;
  position:relative;
  isolation:isolate;
  background:transparent;}
.top-text-bottom-value-demo-card[data-card-size="2x2"]{width:160px;}
.top-text-bottom-value-demo-card[data-card-size="2x4"]{width:320px;}
.top-text-bottom-value-demo-title{
  flex:0 0 auto;
  margin:0;
  overflow:hidden;
  font-size:var(--fs-bs);
  font-weight:400;
  line-height:18px;
  color:var(--font-secondary);
  text-overflow:ellipsis;
  white-space:nowrap;}
.top-text-bottom-value-demo-content{
  display:flex;
  flex:1 1 auto;
  min-height:0;
  width:100%;
  align-items:center;
  justify-content:center;}
.top-text-bottom-value-demo-card[data-layout="type1"] .top-text-bottom-value-demo-content{
  align-items:flex-end;}
.top-text-bottom-value-demo-card > :not(.card-bg-orb__canvas){position:relative;z-index:1;}

/* ── 表格文本 · 左标签 + 右参数 · 至少两组 ─────── */
.table-text{
  display:flex;
  width:100%;
  height:100%;
  min-width:0;
  min-height:0;
  flex-direction:column;
  justify-content:flex-start;
  gap:2px;
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;}
.table-text[data-spacing="adaptive"]{
  justify-content:space-between;}
.table-text-item{
  display:flex;
  flex:0 0 auto;
  width:100%;
  min-width:0;
  min-height:18px;
  align-items:center;
  justify-content:space-between;
  gap:8px;}
.table-text-label,
.table-text-parameter{
  margin:0;
  overflow:hidden;
  font-size:var(--fs-bs);
  font-weight:500;
  line-height:18px;
  text-overflow:ellipsis;
  white-space:nowrap;}
.table-text-label{
  flex:1 1 auto;
  min-width:0;
  text-align:left;
  color:var(--font-secondary);}
.table-text-parameter{
  flex:0 1 auto;
  max-width:70%;
  text-align:right;
  color:var(--font-primary);
  font-variant-numeric:tabular-nums;}
.table-text-demo-card{
  box-sizing:border-box;
  width:160px;
  height:160px;
  padding:12px;
  border-radius:20px;
  display:flex;
  flex-direction:column;
  align-items:stretch;
  position:relative;
  isolation:isolate;
  overflow:hidden;
  background:transparent;}
.table-text-demo-title{
  flex:0 0 auto;
  margin:0;
  overflow:hidden;
  font-size:var(--fs-bs);
  font-weight:400;
  line-height:18px;
  color:var(--font-secondary);
  text-overflow:ellipsis;
  white-space:nowrap;}
.table-text-demo-content{
  display:flex;
  flex:1 1 auto;
  width:100%;
  min-height:0;
  align-items:center;}
.table-text-demo-card[data-layout="type1"] .table-text-demo-content{align-items:flex-end;}
.table-text-demo-card > :not(.card-bg-orb__canvas){position:relative;z-index:1;}

/* ── 文本块 · 自然宽文本组 + 背板 · 横向等距 ────── */
.text-block{
  display:flex;
  flex:1 1 64px;
  width:100%;
  height:auto;
  min-height:48px;
  max-height:64px;
  min-width:0;
  align-items:stretch;
  gap:8px;
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;}
.text-block-item{
  box-sizing:border-box;
  display:flex;
  flex:1 1 0;
  width:0;
  min-width:64px;
  height:100%;
  min-height:0;
  padding:0 8px;
  align-items:center;
  justify-content:center;
  border-radius:16px;
  background:var(--comp_background_tertiary);}
.text-block-copy{
  display:flex;
  width:100%;
  min-width:0;
  flex-direction:column;
  align-items:flex-start;
  justify-content:center;
  gap:2px;}
.text-block-label,
.text-block-parameter{
  max-width:100%;
  margin:0;
  overflow:hidden;
  text-align:left;
  text-overflow:ellipsis;
  white-space:nowrap;}
.text-block-label{
  font-size:var(--fs-cl);
  font-weight:700;
  line-height:18px;
  color:var(--font-primary);}
.text-block-parameter{
  font-size:var(--fs-cm);
  font-weight:500;
  line-height:16px;
  color:var(--font-primary);
  font-variant-numeric:tabular-nums;}
/* ── InfoTile · 核心信息 + 解释文本 + 尾部视觉 ───── */
.info-tile{
  --info-tile-color:var(--info-tile-theme-color,var(--card-bg-solid-blue-content));
  box-sizing:border-box;
  width:136px;
  height:64px;
  padding:0 8px;
  border-radius:16px;
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:4px;
  background:var(--comp_background_tertiary);
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;}
.info-tile[data-card-size="2x2"]{width:136px;}
.info-tile[data-card-size="2x4"]{width:144px;}
.info-tile-copy{
  display:flex;
  flex:1 1 auto;
  min-width:0;
  flex-direction:column;
  align-items:flex-start;
  gap:0;}
.info-tile-primary{
  margin:0;
  display:flex;
  align-items:baseline;
  max-width:100%;
  gap:2px;
  font-size:var(--fs-bl);
  font-weight:700;
  line-height:22px;
  color:var(--font-primary);}
.info-tile-primary-value{
  min-width:0;
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap;}
.info-tile-unit{
  flex:0 0 auto;
  font-size:var(--fs-cm);
  font-weight:500;
  line-height:16px;
  color:var(--font-secondary);}
.info-tile-secondary{
  margin:0;
  max-width:100%;
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap;
  font-size:var(--fs-cm);
  font-weight:var(--fw-cm);
  line-height:16px;
  color:var(--font-secondary);}
.info-tile-visual{
  flex:0 0 24px;
  width:24px;
  height:24px;
  display:flex;
  align-items:center;
  justify-content:center;}
.info-tile-icon{
  display:block;
  width:24px;
  height:24px;
  background-color:var(--graphic-primary,var(--info-tile-color));
  -webkit-mask:var(--info-tile-icon) center / contain no-repeat;
  mask:var(--info-tile-icon) center / contain no-repeat;}
.info-tile-progress{
  position:relative;
  flex:0 0 44px;
  width:44px;
  height:44px;}
.info-tile-progress svg{display:block;width:44px;height:44px;transform:rotate(-90deg)}
.info-tile-progress-track,
.info-tile-progress-bar{
  fill:none;
  stroke-width:6;}
.info-tile-progress-track{stroke:var(--graphic-tertiary,color-mix(in srgb,var(--info-tile-color) 20%,transparent))}
.info-tile-progress-bar{
  stroke:var(--graphic-primary,var(--info-tile-color));
  stroke-linecap:round;}
.info-tile-progress-inner{
  position:absolute;
  inset:0;
  display:flex;
  align-items:center;
  justify-content:center;}
.info-tile-progress-inner-icon{
  display:block;
  width:20px;
  height:20px;
  background-color:var(--graphic-secondary,color-mix(in srgb,var(--info-tile-color) 60%,transparent));
  -webkit-mask:var(--info-tile-icon) center / contain no-repeat;
  mask:var(--info-tile-icon) center / contain no-repeat;}
.info-tile-demo-grid{
  display:flex;
  flex-wrap:wrap;
  gap:24px;
  align-items:flex-start;}
.info-tile-demo-card{
  position:relative;
  isolation:isolate;
  box-sizing:border-box;
  width:160px;
  height:160px;
  padding:12px;
  border-radius:20px;
  display:flex;
  align-items:center;
  justify-content:center;
  overflow:hidden;}
.info-tile-demo-card[data-layout="type3"]{
  flex-direction:column;
  align-items:stretch;
  justify-content:flex-start;
  gap:8px;}
.info-tile-demo-card > .info-tile{position:relative;z-index:1}

/* ── Props Spec (Props × Values visualizer) ──────── */
.ps{
  display:flex;flex-direction:column;gap:0;
  background:var(--surface-2);border:1px solid var(--border);
  border-radius:var(--radius-lg);
  margin-bottom:20px;overflow:hidden;}
.ps-row{
  display:grid;grid-template-columns:150px 1fr;gap:16px;
  padding:12px 16px;
  border-bottom:1px solid var(--border);
  align-items:center;min-height:44px;}
.ps-row:last-child{border-bottom:none}
.ps-name{
  display:flex;flex-direction:column;gap:1px;}
.ps-name-key{font-size:.75rem;font-weight:600;color:var(--text);font-family:var(--mono);line-height:1.2}
.ps-name-type{font-size:.5625rem;color:var(--text-3);font-family:var(--mono);letter-spacing:.02em}
.ps-values{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center}
.ps-chip{
  font-size:.6875rem;font-weight:500;color:var(--text-2);
  padding:3px 9px;border-radius:var(--radius-full);
  background:var(--surface);border:1px solid var(--border);
  font-family:var(--mono);white-space:nowrap;}
.ps-chip[data-default]{
  background:var(--blue-25);border-color:var(--blue-100);color:var(--blue-500);}
[data-theme="dark"] .ps-chip[data-default]{background:color-mix(in srgb,var(--blue-400) 20%,transparent);border-color:var(--blue-400);color:var(--blue-200)}
.ps-item{
  display:inline-flex;align-items:center;gap:6px;
  padding:2px 2px 2px 0;}
.ps-item-label{font-size:.625rem;color:var(--text-3);font-family:var(--mono);line-height:1}
.ps-header{
  font-size:.625rem;font-weight:700;color:var(--text-3);
  text-transform:uppercase;letter-spacing:.08em;
  padding:8px 16px;background:var(--surface-3);
  border-bottom:1px solid var(--border);}

/* ── EventCard ─────────────────────────────────── */
.ec{
  display:grid;
  grid-template-columns:8px minmax(0,1fr);
  column-gap:8px;
  align-items:stretch;
  width:100%;
  min-width:0;}
.ec-rail{
  display:flex;
  flex-direction:column;
  align-items:center;
  align-self:stretch;
  box-sizing:border-box;
  padding-top:6px;
  min-height:0;}
.ec-dot{
  box-sizing:border-box;
  flex:0 0 8px;
  width:8px;
  height:8px;
  border:1.5px solid var(--graphic-primary,var(--font-primary));
  background:transparent;
  border-radius:50%;}
.ec-line{
  flex:1;
  width:1px;
  min-height:0;
  margin-top:4px;
  background:var(--graphic-secondary,var(--font-secondary));}
.ec-content{
  display:flex;
  flex-direction:column;
  gap:0;
  min-width:0;
  width:100%;}
.ec-title{
  display:-webkit-box;
  width:100%;
  max-width:100%;
  overflow:hidden;
  -webkit-box-orient:vertical;
  -webkit-line-clamp:2;
  line-clamp:2;
  overflow-wrap:break-word;
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;
  font-size:var(--fs-bm);
  font-weight:700;
  line-height:18px;
  color:var(--font-primary);
  text-overflow:ellipsis;
  margin-bottom:0;}
.ec-location,.ec-time{
  display:block;
  width:100%;
  max-width:100%;
  overflow:hidden;
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;
  font-size:var(--fs-cm);
  font-weight:400;
  line-height:16px;
  color:var(--font-secondary);
  text-overflow:ellipsis;
  white-space:nowrap;}
.ec-location{margin-top:0;}
.ec-meta{
  display:flex;
  align-items:center;
  width:100%;
  min-width:0;
  height:14px;
  gap:4px;
  overflow:hidden;}
.ec-meta-separator{
  flex:0 0 auto;
  font-size:10px;
  font-weight:400;
  line-height:14px;
  color:var(--font-secondary);}
.ec[data-density="compact"] .ec-rail{padding-top:4px;}
.ec[data-density="compact"] .ec-content{
  gap:2px;
  min-height:32px;}
.ec[data-density="compact"] .ec-title{
  display:block;
  overflow:hidden;
  margin-bottom:0;
  font-size:12px;
  line-height:16px;
  white-space:nowrap;
  text-overflow:ellipsis;}
.ec[data-density="compact"] .ec-time,
.ec[data-density="compact"] .ec-location{
  min-width:0;
  width:auto;
  max-width:none;
  height:14px;
  margin-top:0;
  font-size:10px;
  line-height:14px;}
.ec[data-density="compact"] .ec-time{flex:0 0 auto;}
.ec[data-density="compact"] .ec-location{flex:1 1 0;}
.event-card-demo-card{
  box-sizing:border-box;
  width:160px;
  height:160px;
  padding:12px;
  border-radius:20px;
  display:flex;
  flex-direction:column;
  align-items:stretch;
  gap:8px;
  overflow:hidden;
  background:var(--card-bg-solid-blue);}
.event-card-demo-title{
  flex:0 0 auto;
  margin:0;
  overflow:hidden;
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;
  font-size:var(--fs-bs);
  font-weight:400;
  line-height:18px;
  color:var(--font-secondary);
  text-overflow:ellipsis;
  white-space:nowrap;}
.event-card-demo-content{
  display:flex;
  flex:1 1 auto;
  min-height:0;
  align-items:flex-start;}
.event-card-demo-card[data-layout="type1"] .event-card-demo-content{
  align-items:flex-end;}


/* ── Badge ────────────────────────────────────────── */
.badge{
  height:16px;border-radius:8px;
  display:inline-flex;align-items:center;justify-content:center;
  padding:0 6px;
  font-size:.625rem;font-weight:500;
  background:var(--comp_background_secondary);
  color:var(--font-primary);}

/* ════════════════════════════════════════════════════
   v10 组件扩展
   · 沿用用户既有规则(源自 v7)：EventCard / Badge
   · v12：移除 Reminder（与 EventCard 重复）
   ════════════════════════════════════════════════════ */

/* ── 单环右侧文本组 ───────────────────────────────
   单环内部规格：Label 文本组在上、Value + Unit 在下 */
.pc-stat-text{
  display:inline-flex;
  flex-direction:column;
  align-items:flex-start;
  min-width:0;
  gap:0;
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;}
.pc-stat-value{
  margin:0;
  font-size:var(--fs-bs);
  font-weight:500;
  line-height:18px;
  color:var(--font-secondary);
  font-variant-numeric:tabular-nums;}
.pc-stat-label{
  margin:0;
  font-size:var(--fs-bm);
  font-weight:700;
  line-height:20px;
  color:var(--font-primary);}
.pc-stat-text[data-lines="3"]{
  gap:0;}
.pc-stat-text[data-lines="3"] .pc-stat-detail{
  display:inline-flex;
  flex-direction:column;
  align-items:flex-start;
  gap:0;
  min-width:0;
  white-space:nowrap;}
.pc-stat-text[data-lines="3"] .pc-stat-value,
.pc-stat-text[data-lines="3"] .pc-stat-label-secondary{
  font-size:var(--fs-cm);
  font-weight:400;
  line-height:16px;
  color:var(--font-secondary);}

/* ── 数值占比 · Icon + 数值 ─────────────────────── */
.numeric-ratio{
  display:inline-flex;
  align-items:center;
  gap:4px;
  min-width:0;
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;}
.numeric-ratio-icon{
  display:flex;
  align-items:center;
  justify-content:center;
  flex:0 0 16px;
  width:16px;
  height:16px;}
.numeric-ratio-value{
  margin:0;
  font-size:var(--fs-cm);
  font-weight:400;
  line-height:16px;
  color:var(--font-secondary);
  white-space:nowrap;}
.numeric-ratio-stack{
  display:inline-flex;
  flex-direction:column;
  align-items:flex-start;
  gap:4px;}
.numeric-ratio-type11a-card{
  box-sizing:border-box;
  position:relative;
  isolation:isolate;
  overflow:hidden;
  width:160px;
  height:160px;
  padding:12px;
  border-radius:20px;}
.numeric-ratio-type11a-title{
  position:absolute;
  top:12px;
  right:12px;
  left:12px;
  height:18px;}
.numeric-ratio-type11a-hero{
  position:absolute;
  top:38px;
  right:12px;
  left:12px;}
.numeric-ratio-type11a-secondary{
  position:absolute;
  bottom:12px;
  left:12px;
  width:88px;
  height:auto;}
.numeric-ratio-type11a-action{
  position:absolute;
  right:12px;
  bottom:12px;
  width:40px;
  height:40px;}
.emphasized-data-type11a-card{
  box-sizing:border-box;
  position:relative;
  isolation:isolate;
  overflow:hidden;
  width:160px;
  height:160px;
  padding:12px;
  border-radius:20px;}
.emphasized-data-type11a-card > :not(.card-bg-orb__canvas){z-index:1;}
.emphasized-data-type11a-title{
  position:absolute;
  top:12px;
  right:12px;
  left:12px;
  height:18px;}
.emphasized-data-type11a-hero{
  position:absolute;
  top:38px;
  right:12px;
  left:12px;}
.emphasized-data-type11a-secondary{
  position:absolute;
  bottom:12px;
  left:12px;
  width:88px;
  display:flex;
  flex-direction:column;
  align-items:flex-start;
  gap:2px;}
.emphasized-data-type11a-secondary .secondary-body{
  font-size:var(--fs-bs);
  line-height:16px;}
.emphasized-data-type11a-action{
  position:absolute;
  right:12px;
  bottom:12px;
  width:40px;
  height:40px;}

/* ── 柱状图 · 文本标签 + 数值单位 + Track + Bar ──────── */
.bar-chart{
  display:flex;
  width:100%;
  min-width:0;
  flex-direction:column;
  align-items:flex-start;
  gap:11px;
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;}
.bar-chart-item{
  display:flex;
  width:100%;
  min-width:0;
  flex-direction:column;
  align-items:flex-start;
  gap:4px;}
.bar-chart-meta{
  display:flex;
  width:100%;
  min-width:0;
  align-items:flex-end;
  justify-content:space-between;
  gap:8px;}
.bar-chart-label{
  flex:1 1 auto;
  min-width:0;
  margin:0;
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap;
  font-size:var(--fs-bm);
  font-weight:700;
  line-height:20px;
  color:var(--font-secondary);}
.bar-chart-value-unit{
  flex:0 0 auto;
  margin:0;
  font-size:var(--fs-bm);
  font-weight:700;
  line-height:20px;
  color:var(--font-secondary);
  white-space:nowrap;
  text-align:right;
  font-variant-numeric:tabular-nums;}
.bar-chart-track{
  width:100%;
  height:6px;
  min-height:6px;
  max-height:6px;
  flex:0 0 6px;
  overflow:hidden;
  border-radius:32px;
  background:var(--graphic-tertiary,rgba(0,0,0,.20));}
.bar-chart-bar{
  width:clamp(0%,calc(var(--bar-chart-percent,0) * 1%),100%);
  height:100%;
  min-height:6px;
  max-height:6px;
  border-radius:2px;
  background:var(--graphic-primary,var(--button-light-blue-content));}
.bar-chart-demo-card{
  box-sizing:border-box;
  width:160px;
  height:160px;
  padding:12px;
  border-radius:20px;
  display:flex;
  flex-direction:column;
  align-items:stretch;
  background:var(--card-bg-solid-blue);}
.bar-chart-demo-grid{display:flex;flex-wrap:wrap;align-items:flex-start;gap:24px;}
.bar-chart-demo-case{display:flex;flex-direction:column;gap:6px;}
.bar-chart-demo-label{font-size:var(--fs-cm);font-weight:500;line-height:16px;color:var(--text-3);}
.text-block-demo-card{
  box-sizing:border-box;
  width:320px;
  height:160px;
  padding:12px;
  border-radius:20px;
  display:flex;
  flex-direction:column;
  align-items:stretch;
  gap:8px;
  background:var(--card-bg-solid-blue);}
.text-block-demo-zone{
  display:flex;
  flex:1 1 0;
  width:100%;
  min-width:0;
  min-height:0;
  flex-direction:column;
  align-items:stretch;}
.text-block-demo-zone:first-child{justify-content:flex-start;}
.text-block-demo-zone:last-child{justify-content:flex-end;}
.bar-chart-demo-title{
  flex:0 0 auto;
  margin:0;
  overflow:hidden;
  font-size:var(--fs-bs);
  font-weight:400;
  line-height:18px;
  color:var(--font-secondary);
  text-overflow:ellipsis;
  white-space:nowrap;}
.bar-chart-demo-content{
  display:flex;
  flex:1 1 auto;
  width:100%;
  min-height:0;
  align-items:center;}

/* ── 示例背景意图映射 ───────────────────────────── */
.intent-example-card{
  box-sizing:border-box;
  width:160px;
  height:160px;
  padding:12px;
  border-radius:20px;
  position:relative;
  isolation:isolate;
  overflow:hidden;
  display:flex;
  align-items:center;
  justify-content:center;}
.intent-example-card > :not(.card-bg-orb__canvas){position:relative;z-index:1;}
.badge-demo-content{display:flex;align-items:center;gap:8px;}
.badge-demo-title{font-size:18px;font-weight:700;color:var(--font-primary);}
.single-title-type10a-card .pl2-layout-title{
  flex-basis:18px;
  height:18px;
  line-height:18px;}
.badge-type1-demo-card{
  flex-direction:column;
  align-items:stretch;
  justify-content:flex-start;
  gap:8px;}
.badge-type1-title-row{
  display:flex;
  flex:0 0 18px;
  align-items:center;
  min-width:0;
  gap:8px;}
.badge-type1-title-row .single-line-title{
  flex:0 1 auto;
  width:auto;}
.badge-type1-title-row .badge{flex:0 0 auto;}
.badge-type1-content{
  display:flex;
  flex:1 1 auto;
  min-height:0;
  align-items:flex-end;}
/* 所有示例卡片外层统一不使用描边或阴影。 */
[class*="demo-card"],
.intent-example-card,
.secondary-body-card,
.title-position-demo,
.button-card-position-demo,
.bg-template-preview,
.numeric-ratio-type11a-card,
.emphasized-data-type11a-card{
  border:0;
  box-shadow:none;}
.bg-template-preview::after{box-shadow:none;}
[data-intent-bg="solid-blue"]{
  --background-content-color:var(--card-bg-solid-blue-content);
  background:var(--card-bg-solid-blue);}
[data-intent-bg="solid-orange"]{
  --background-content-color:var(--card-bg-solid-orange-content);
  background:var(--card-bg-solid-orange);}
[data-intent-bg="solid-green"]{
  --background-content-color:var(--card-bg-solid-green-content);
  background:var(--card-bg-solid-green);}
[data-intent-bg="solid-cyan"]{
  --background-content-color:var(--card-bg-solid-cyan-content);
  background:var(--card-bg-solid-cyan);}
[data-intent-bg="solid-purple"]{
  --background-content-color:var(--card-bg-solid-purple-content);
  background:var(--card-bg-solid-purple);}
[data-intent-bg="orb-orange"],
[data-intent-bg="orb-blue"],
[data-intent-bg="orb-purple"],
[data-intent-bg="orb-green"]{background:transparent;}
/* END V15_REFERENCE_STYLES */

/* ── Generated Card mode · v15 ─────────────────────
   Component geometry and palettes stay here; card composition is expressed
   declaratively with Card, Stack, and Grid props. */
.generated-card-background{
  position:absolute;inset:0;z-index:0;display:block;width:100%;height:100%;
  overflow:hidden;border-radius:inherit;pointer-events:none;
  -webkit-clip-path:inset(0 round 20px);clip-path:inset(0 round 20px);}
.generated-card-frame:has(> .generated-card-background) > :not(.generated-card-background){position:relative;z-index:1;}
.generated-card-background__ellipse{position:absolute;display:block;border-radius:50%;}
.generated-card-background__ellipse[data-position="right-bottom"]{
  left:var(--card-bg-orb-right-bottom-x);top:var(--card-bg-orb-right-bottom-y);width:var(--card-bg-orb-right-bottom-size);aspect-ratio:1/1;
  background:var(--card-bg-ellipse-right-bottom);}
.generated-card-background__ellipse[data-position="left-bottom"]{
  left:var(--card-bg-orb-left-bottom-x);top:var(--card-bg-orb-left-bottom-y);width:var(--card-bg-orb-left-bottom-size);aspect-ratio:1/1;
  background:var(--card-bg-ellipse-left-bottom);}
.generated-card-background__ellipse[data-position="top"]{
  left:var(--card-bg-orb-top-x);top:var(--card-bg-orb-top-y);width:var(--card-bg-orb-top-size);aspect-ratio:1/1;
  background:var(--card-bg-ellipse-top);}
.generated-card-background__backplate{
  position:absolute;inset:0;display:block;width:100%;height:100%;
  border-radius:inherit;background:var(--card-bg-orb-backplate);
  -webkit-backdrop-filter:blur(var(--card-bg-orb-blur));backdrop-filter:blur(var(--card-bg-orb-blur));}
.generated-card-background[data-appearance="orb-orange"],
.generated-card-background[data-appearance="orange-gradient"],
.generated-card-background[data-appearance="type0-gradient"]{
  background:transparent;
  --card-bg-ellipse-right-bottom:var(--card-bg-orb-orange-right-bottom-color);
  --card-bg-ellipse-left-bottom:var(--card-bg-orb-orange-left-bottom-color);
  --card-bg-ellipse-top:var(--card-bg-orb-orange-top-color);}
.generated-card-background[data-appearance="orb-blue"],
.generated-card-background[data-appearance="sunny-gradient"],
.generated-card-background[data-appearance="cloudy-gradient"],
.generated-card-background[data-appearance="slate-gradient"]{
  background:transparent;
  --card-bg-ellipse-right-bottom:var(--card-bg-orb-blue-right-bottom-color);
  --card-bg-ellipse-left-bottom:var(--card-bg-orb-blue-left-bottom-color);
  --card-bg-ellipse-top:var(--card-bg-orb-blue-top-color);}
.generated-card-background[data-appearance="orb-purple"],
.generated-card-background[data-appearance="purple-gradient"]{
  background:transparent;
  --card-bg-ellipse-right-bottom:var(--card-bg-orb-purple-right-bottom-color);
  --card-bg-ellipse-left-bottom:var(--card-bg-orb-purple-left-bottom-color);
  --card-bg-ellipse-top:var(--card-bg-orb-purple-top-color);}
.generated-card-background[data-appearance="orb-green"]{
  background:transparent;
  --card-bg-ellipse-right-bottom:var(--card-bg-orb-green-right-bottom-color);
  --card-bg-ellipse-left-bottom:var(--card-bg-orb-green-left-bottom-color);
  --card-bg-ellipse-top:var(--card-bg-orb-green-top-color);}
.generated-card-frame{
  --font-primary:var(--card-primary);
  --font-secondary:var(--card-secondary);
  --font-tertiary:var(--card-tertiary);
  --graphic-primary:var(--card-graphic-primary);
  --graphic-secondary:var(--card-graphic-secondary);
  --graphic-tertiary:var(--card-graphic-tertiary);
  --comp_background_primary:var(--card-comp-primary);
  --comp_background_secondary:var(--card-comp-secondary);
  --comp_background_tertiary:var(--card-comp-tertiary);
  --card-progress-track:var(--graphic-tertiary);
  --card-progress-bar:var(--graphic-primary);
  --card-progress-icon:var(--graphic-secondary);
  --top-text-bottom-value-divider:rgba(0,0,0,.20);
  --checklist-bg:rgba(0,0,0,.05);
  --checklist-checkbox-bg:rgba(0,0,0,.10);
  --checklist-checkbox-border:rgba(0,0,0,.20);
  --checklist-check-color:var(--card-primary);
  font-family:"HarmonyOS Sans SC","HarmonyOS Sans",-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;}
.generated-card-frame[data-tone="dark"]{
  --card-progress-track:var(--graphic-tertiary);
  --card-progress-bar:var(--graphic-primary);
  --card-progress-icon:var(--graphic-secondary);
  --top-text-bottom-value-divider:rgba(255,255,255,.20);
  --checklist-bg:rgba(255,255,255,.10);
  --checklist-checkbox-bg:rgba(255,255,255,.20);
  --checklist-checkbox-border:rgba(255,255,255,.40);
  --checklist-check-color:#FFFFFF;}
.generated-card-frame[data-tone="dark"] .info-block-icon-mask{color:var(--graphic-primary);}
.generated-card-frame[data-tone="dark"] .info-block-progress-icon{color:var(--graphic-secondary);}
.generated-card-frame [data-surface="backplate"]{
  box-sizing:border-box;
  padding:6px;
  border-radius:16px;
  overflow:hidden;}
.generated-card-frame[data-tone="light"] [data-surface="backplate"]{
  background:var(--comp_background_tertiary);}
.generated-card-frame[data-tone="dark"] [data-surface="backplate"]{
  background:var(--comp_background_tertiary);}
.generated-card-frame .single-line-title,
.generated-card-frame .double-line-title-main,
.generated-card-frame .double-line-title-sub,
.generated-card-frame .ed,
.generated-card-frame .emphasis-text,
.generated-card-frame .secondary-body,
.generated-card-frame .data-display,
.generated-card-frame .pc-external-value,
.generated-card-frame .pc-stat-text,
.generated-card-frame .numeric-ratio,
.generated-card-frame .ec-title,
.generated-card-frame .ec-time,
.generated-card-frame .ec-location,
.generated-card-frame .ec-meta-separator,
.generated-card-frame .pill-btn{font-family:inherit;}
.generated-card-frame .title-demo-row{position:relative;width:100%;min-height:12px;height:auto;gap:4px;align-items:flex-start;}
.generated-card-frame .single-line-title-row{flex:0 1 auto;width:fit-content;max-width:100%;min-width:0;}
.generated-card-frame .single-line-title-layout{
  box-sizing:border-box;width:100%;min-height:12px;height:auto;padding-right:0;}
.generated-card-frame .single-line-title{
  font-size:12px;font-weight:400;line-height:18px;color:var(--card-secondary);}
.generated-card-frame .ec-title{
  color:var(--card-primary);}
.generated-card-frame .ec-time,
.generated-card-frame .ec-location,
.generated-card-frame .ec-meta-separator{
  color:var(--card-secondary);}
.generated-card-frame .double-line-title{
  box-sizing:border-box;width:100%;min-height:28px;height:auto;padding-right:0;gap:4px;}
.generated-card-frame .double-line-title-main{
  font-size:12px;font-weight:700;line-height:18px;color:var(--card-primary);}
.generated-card-frame .double-line-title-sub{
  font-size:12px;font-weight:500;line-height:18px;color:var(--card-secondary);}
.generated-card-frame .ed-val{
  font-size:38px;font-weight:700;line-height:1;color:var(--card-primary);}
.generated-card-frame .pl2 .ed-val{line-height:1;}
.generated-card-frame .ed-unit{
  font-size:12px;font-weight:400;line-height:1.5;color:var(--card-secondary);}
.generated-card-frame .pl2 .ed-unit{line-height:1;}
.generated-card-frame .emphasis-text-main{
  font-size:20px;font-weight:700;line-height:20px;color:var(--card-primary);}
.generated-card-frame .emphasis-text-secondary{
  font-size:12px;font-weight:400;line-height:16px;color:var(--card-secondary);}
.generated-card-frame .secondary-body{
  font-size:14px;font-weight:400;line-height:19px;color:var(--font-secondary);}
.generated-card-frame .secondary-body[data-multiline="true"]{
  font-size:12px;line-height:16px;}
.generated-card-frame .pc-external-value{
  font-size:10px;font-weight:500;line-height:14px;color:var(--card-primary);}
.generated-card-frame .generated-card-mask{
  display:block;flex:0 0 auto;background-color:currentColor;
  -webkit-mask:var(--generated-card-icon-url) no-repeat center/contain;
  mask:var(--generated-card-icon-url) no-repeat center/contain;}
.generated-card-frame .pc-center-icon .generated-card-mask[data-size="sm"],
.generated-card-frame .pc-center-icon .generated-card-mask[data-size="md"],
.generated-card-frame .pc-center-icon .generated-card-mask[data-size="single"]{width:20px;height:20px;}
.generated-card-frame .numeric-ratio-icon .generated-card-mask{width:12px;height:12px;color:var(--graphic-primary);}
.generated-card-frame .pc-stat-label{
  font-size:14px;font-weight:700;line-height:20px;color:var(--card-primary);white-space:nowrap;}
.generated-card-frame .pc-stat-value{
  font-size:12px;font-weight:500;line-height:18px;color:var(--card-secondary);white-space:nowrap;}
.generated-card-frame .pc-stat-text[data-lines="3"] .pc-stat-value,
.generated-card-frame .pc-stat-text[data-lines="3"] .pc-stat-label-secondary{
  font-size:10px;font-weight:400;line-height:16px;color:var(--card-secondary);white-space:nowrap;}
.generated-card-frame .numeric-ratio-value{
  font-size:10px;font-weight:400;line-height:16px;color:var(--card-secondary);}

.generated-card-frame .btn[data-appearance="card"]{
  --btn-bg:var(--comp_background_tertiary);
  --btn-bg-hover:var(--comp_background_tertiary);
  --btn-bg-active:var(--comp_background_tertiary);
  --btn-text:var(--font-primary);
  background:var(--comp_background_tertiary);}
.generated-card-frame .btn[data-appearance="card"]::before{display:none;}
.generated-card-frame .pill-btn[data-appearance="card"]{
  box-sizing:border-box;display:inline-flex;width:136px;min-width:136px;height:36px;padding:0;border-radius:30px;flex:none;}
.generated-card-frame [data-surface="backplate"] .pill-btn[data-appearance="card"]{
  width:120px;min-width:120px;max-width:120px;align-self:center;}
.generated-card-frame[data-card-size="2x4"] [data-surface="backplate"] .pill-btn[data-appearance="card"]{
  width:118px;min-width:118px;max-width:118px;border-radius:18px;}
.generated-card-frame .circle-btn[data-appearance="card"]{
  /* Generation contract: 36vp button inside the optional 40vp action slot. */
  --btn-bg:var(--comp_background_tertiary);
  --btn-bg-hover:var(--comp_background_tertiary);
  --btn-bg-active:var(--comp_background_tertiary);
  --btn-text:var(--graphic-primary);
  position:relative;display:inline-flex;width:36px;min-width:36px;height:36px;padding:0;border-radius:50%;
  background:var(--comp_background_tertiary);}
.generated-card-frame .btn-icon-mask{
  display:block;width:100%;height:100%;background:var(--graphic-primary);
  -webkit-mask:var(--button-icon-url) no-repeat center/contain;
  mask:var(--button-icon-url) no-repeat center/contain;}
.generated-card-frame .circle-btn[data-appearance="card"] .btn-icon-mask{
  background:var(--graphic-primary);}

`;

  function ensureRuntimeStyles() {
    if (
      typeof document === "undefined"
      || document.documentElement?.dataset.catalogSourceStyles === "true"
      || document.getElementById(RUNTIME_STYLE_ID)
    ) return;
    const styleElement = document.createElement("style");
    styleElement.id = RUNTIME_STYLE_ID;
    styleElement.dataset.owner = "ClawWidgetDesignSystem";
    const begin = "/* BEGIN V15_REFERENCE_STYLES · generated by scripts/sync-v15-runtime-styles.js */";
    const end = "/* END V15_REFERENCE_STYLES */";
    const start = RUNTIME_STYLES.indexOf(begin);
    const finish = RUNTIME_STYLES.indexOf(end, start + begin.length);
    if (start < 0 || finish < 0) throw new Error("missing v15 catalog styles in design-system runtime");
    if (document.documentElement?.dataset.catalogRuntimeStyles === "true") {
      styleElement.textContent = RUNTIME_STYLES.slice(start + begin.length, finish).trim();
    } else {
      // Catalog examples have independent sizing; never cascade them over
      // generated Cards whose geometry is shared with the A2UI converters.
      styleElement.textContent = RUNTIME_STYLES.slice(0, start) + RUNTIME_STYLES.slice(finish + end.length);
    }
    document.head.appendChild(styleElement);
  }

  ensureRuntimeStyles();

  const ASSET_ROOT = "resources/base/media/";

  function monochromeAppearance(background, contentColor) {
    return {
      background,
      boxShadow: "none",
      "--background-content-color": contentColor,
      "--card-primary": contentColor,
      "--card-secondary": `color-mix(in srgb,${contentColor} 60%,transparent)`,
      "--card-tertiary": `color-mix(in srgb,${contentColor} 40%,transparent)`,
      "--card-graphic-primary": contentColor,
      "--card-graphic-secondary": `color-mix(in srgb,${contentColor} 60%,transparent)`,
      "--card-graphic-tertiary": `color-mix(in srgb,${contentColor} 20%,transparent)`,
      "--card-comp-primary": contentColor,
      "--card-comp-secondary": `color-mix(in srgb,${contentColor} 20%,transparent)`,
      "--card-comp-tertiary": `color-mix(in srgb,${contentColor} 10%,transparent)`,
    };
  }

  function darkAppearance(background) {
    return {
      background,
      boxShadow: "none",
      "--card-primary": "#FFFFFF",
      "--card-secondary": "rgba(255,255,255,.60)",
      "--card-tertiary": "rgba(255,255,255,.40)",
      "--card-graphic-primary": "#FFFFFF",
      "--card-graphic-secondary": "rgba(255,255,255,.60)",
      "--card-graphic-tertiary": "rgba(255,255,255,.20)",
      "--card-comp-primary": "#FFFFFF",
      "--card-comp-secondary": "rgba(255,255,255,.20)",
      "--card-comp-tertiary": "rgba(255,255,255,.10)",
    };
  }

  const solidWhite = monochromeAppearance("#FFFFFF", "#000000");
  const solidBlue = monochromeAppearance("#E5EDFE", "#1f4799");
  const solidOrange = monochromeAppearance("#FFF3E6", "#99661f");
  const solidGreen = monochromeAppearance("#F0FFE6", "#52991f");
  const solidCyan = monochromeAppearance("#E6FDFF", "#1f8f99");
  const solidPurple = monochromeAppearance("#EDE6FF", "#401f99");
  // JSX preserves the authored orb layers. The A2UI adapter owns its fallback.
  const orbOrange = darkAppearance("#BF3F26");
  const orbBlue = darkAppearance("rgb(18,30,89)");
  const orbPurple = darkAppearance("rgb(27,18,89)");
  const orbGreen = darkAppearance("rgb(23,115,76)");

  const CARD_APPEARANCES = Object.freeze({
    "solid-white": solidWhite,
    "solid-blue": solidBlue,
    "solid-orange": solidOrange,
    "solid-green": solidGreen,
    "solid-cyan": solidCyan,
    "solid-purple": solidPurple,
    "orb-orange": orbOrange,
    "orb-blue": orbBlue,
    "orb-purple": orbPurple,
    "orb-green": orbGreen,

    /* 旧示例兼容别名：统一降落到 v15 的正式背景模板。 */
    "neutral-soft": solidWhite,
    "blue-soft": solidBlue,
    "pink-soft": solidOrange,
    "yellow-soft": solidOrange,
    "green-soft": solidGreen,
    "cyan-soft": solidCyan,
    "sunny-gradient": orbBlue,
    "cloudy-gradient": orbBlue,
    "slate-gradient": orbBlue,
    "purple-gradient": orbPurple,
    "orange-gradient": orbOrange,
    "type0-gradient": orbOrange,
  });

  const DARK_CARD_APPEARANCES = new Set([
    "orb-orange",
    "orb-blue",
    "orb-purple",
    "orb-green",
    "sunny-gradient",
    "cloudy-gradient",
    "slate-gradient",
    "purple-gradient",
    "orange-gradient",
    "type0-gradient",
  ]);

  /* 融球只用于 2×2。兼容历史 2×4 JSX 时降级到同色系单色背景。 */
  const TWO_BY_FOUR_APPEARANCE_FALLBACKS = Object.freeze({
    "orb-orange": "solid-orange",
    "orb-blue": "solid-blue",
    "orb-purple": "solid-purple",
    "orb-green": "solid-green",
    "sunny-gradient": "solid-blue",
    "cloudy-gradient": "solid-blue",
    "slate-gradient": "solid-blue",
    "purple-gradient": "solid-purple",
    "orange-gradient": "solid-orange",
    "type0-gradient": "solid-orange",
  });

  function cx(...values) {
    return values.filter(Boolean).join(" ");
  }

  function clamp(value, min = 0, max = 100) {
    const number = Number(value);
    if (!Number.isFinite(number)) return min;
    return Math.min(max, Math.max(min, number));
  }

  const FORMATTED_PERCENTAGE_PATTERN = /^\s*\d+(?:\.\d+)?\s*[%％]\s*$/;

  function isFormattedPercentage(value) {
    return typeof value === "string" && FORMATTED_PERCENTAGE_PATTERN.test(value);
  }

  function progressPercentage(value) {
    if (isFormattedPercentage(value)) {
      return clamp(Number.parseFloat(value));
    }
    if (typeof value === "string" && /^\s*[+-]?\d+(?:\.\d+)?\s*％?\s*$/.test(value)) {
      return clamp(Number.parseFloat(value));
    }
    return clamp(value);
  }

  function percentageFrom(currentValue, totalValue = 100) {
    const total = Number(totalValue);
    if (!Number.isFinite(total) || total <= 0) return 0;
    return clamp((Number(currentValue) / total) * 100);
  }

  function visiblePercentage(value) {
    return Math.trunc(clamp(value));
  }

  function formatPercentage(value) {
    return `${visiblePercentage(value)}%`;
  }

  function formatProgressCircleText(value) {
    if (isFormattedPercentage(value)) return value.trim();
    return formatPercentage(progressPercentage(value));
  }

  function assetUrl(value) {
    if (!value) return "";
    if (/^(?:[a-z]+:|\/|\.|data:)/i.test(value) || value.includes("/")) return value;
    return `${ASSET_ROOT}${value.includes(".") ? value : `${value}.svg`}`;
  }

  function GeneratedCardMask({ src, size, className }) {
    return (
      <span
        className={cx("generated-card-mask", className)}
        data-size={size}
        style={{ "--generated-card-icon-url": `url("${assetUrl(src)}")` }}
        aria-hidden="true"
      />
    );
  }

  function CardBackground({ appearance, size }) {
    if (size !== "2x2" || !DARK_CARD_APPEARANCES.has(appearance)) return null;
    return (
      <span
        className="generated-card-background"
        data-appearance={appearance}
        data-card-size={size}
        aria-hidden="true"
      >
        <span className="generated-card-background__ellipse" data-position="right-bottom" />
        <span className="generated-card-background__ellipse" data-position="left-bottom" />
        <span className="generated-card-background__ellipse" data-position="top" />
        <span className="generated-card-background__backplate" />
      </span>
    );
  }

  function resolveJustify(value) {
    return ({ start: "flex-start", center: "center", end: "flex-end", between: "space-between" })[value] || value;
  }

  function resolveFlex(flex, basis) {
    if (basis != null) return `0 0 ${typeof basis === "number" ? `${basis}px` : basis}`;
    if (flex === 1) return "1 1 0";
    if (flex === 0) return "0 0 auto";
    return flex;
  }

  const CARD_SIZE_PRESETS = Object.freeze({
    "2x2": Object.freeze({ width: 160, height: 160 }),
    "2x4": Object.freeze({ width: 320, height: 160 }),
  });

  function resolveCardDimensions(size) {
    const preset = CARD_SIZE_PRESETS[size];
    if (preset) return preset;
    if (typeof size === "number" && Number.isFinite(size) && size > 0) {
      const dimension = `${size}px`;
      return { width: dimension, height: dimension };
    }
    throw new Error('Card.size must be "2x2", "2x4", or a positive legacy number');
  }

  function Card({ children, size = "2x2", appearance, background, padding = 12, direction = "column", gap = 0, align, justify, className, style, ...rest }) {
    const dimensions = resolveCardDimensions(size);
    const semanticSize = CARD_SIZE_PRESETS[size] ? size : undefined;
    const resolvedAppearance = size === "2x4"
      ? (TWO_BY_FOUR_APPEARANCE_FALLBACKS[appearance] || appearance)
      : appearance;
    const cardAppearance = CARD_APPEARANCES[resolvedAppearance];
    let cardTone;
    if (cardAppearance) cardTone = DARK_CARD_APPEARANCES.has(resolvedAppearance) ? "dark" : "light";
    let cardColorMode;
    if (cardTone === "dark") cardColorMode = "dark";
    else if (cardAppearance) cardColorMode = "monochrome";
    return (
      <div
        className={cx("ds-frame", cardAppearance && "generated-card-frame", className)}
        data-appearance={resolvedAppearance}
        data-card-size={semanticSize}
        data-tone={cardTone}
        data-color-mode={cardColorMode}
        style={{
          boxSizing: "border-box",
          position: "relative",
          width: dimensions.width,
          height: dimensions.height,
          padding,
          borderRadius: cardAppearance ? 20 : 24,
          overflow: "hidden",
          display: "flex",
          flexDirection: direction === "row" ? "row" : "column",
          gap,
          alignItems: align,
          justifyContent: resolveJustify(justify),
          ...(cardAppearance || null),
          background: background || cardAppearance?.background || "var(--surface)",
          ...style,
        }}
        {...rest}
      >
        {cardAppearance && !background && <CardBackground appearance={resolvedAppearance} size={semanticSize} />}
        {children}
      </div>
    );
  }

  function Stack({
    children,
    direction = "column",
    gap = 0,
    align = "stretch",
    justify = "start",
    wrap = false,
    flex,
    basis,
    width,
    minWidth = 0,
    height,
    minHeight,
    mt,
    mb,
    ml,
    mr,
    position,
    top,
    right,
    bottom,
    left,
    alignSelf,
    surface,
    className,
    style,
    ...rest
  }) {
    const inferredMinHeight = React.Children.toArray(children).reduce((value, child) => {
      if (value !== undefined || !React.isValidElement(child)) return value;
      return child.type?.__clawStackMinHeight;
    }, undefined);
    const resolvedMinHeight = minHeight ?? inferredMinHeight ?? (flex === 1 ? 0 : undefined);
    return (
      <div
        className={className}
        data-surface={surface}
        style={{
          display: "flex",
          flexDirection: direction === "row" ? "row" : "column",
          gap,
          alignItems: align,
          justifyContent: resolveJustify(justify),
          flexWrap: wrap ? "wrap" : "nowrap",
          flex: resolveFlex(flex, basis),
          width: width === "full" ? "100%" : width,
          minWidth,
          height: height === "full" ? "100%" : height,
          minHeight: resolvedMinHeight,
          marginTop: mt,
          marginBottom: mb,
          marginLeft: ml,
          marginRight: mr,
          position,
          top,
          right,
          bottom,
          left,
          alignSelf,
          ...style,
        }}
        {...rest}
      >
        {children}
      </div>
    );
  }

  function Grid({ children, columns = 2, rows, gap = 0, rowGap, columnGap, flex, basis, width, minWidth = 0, height, minHeight, align, justify, mt, mb, className, style, ...rest }) {
    const resolvedMinHeight = minHeight ?? (flex === 1 ? 0 : undefined);
    return (
      <div
        className={className}
        style={{
          display: "grid",
          gridTemplateColumns: typeof columns === "number" ? `repeat(${columns}, minmax(0, 1fr))` : columns,
          gridTemplateRows: rows,
          gap,
          rowGap: rowGap ?? gap,
          columnGap: columnGap ?? gap,
          flex: resolveFlex(flex, basis),
          width: width === "full" ? "100%" : width,
          minWidth,
          height: height === "full" ? "100%" : height,
          minHeight: resolvedMinHeight,
          alignItems: align,
          justifyItems: justify,
          marginTop: mt,
          marginBottom: mb,
          ...style,
        }}
        {...rest}
      >
        {children}
      </div>
    );
  }

  function Icon({ name, src, size, alt = "", decorative = true, className, style, ...rest }) {
    let dimension;
    if (size != null) dimension = typeof size === "number" ? `${size}px` : size;
    return (
      <img
        className={className}
        src={assetUrl(src || name)}
        alt={decorative ? "" : alt}
        aria-hidden={decorative ? "true" : undefined}
        style={{ width: dimension, height: dimension, ...style }}
        {...rest}
      />
    );
  }

  function AppIcon({ name, src, alt = "", className, ...rest }) {
    return <Icon name={name} src={src} alt={alt} decorative={!alt} className={cx("app-icon", className)} {...rest} />;
  }

  function WeatherIcon({ name, src, alt = "", className, ...rest }) {
    return <Icon name={name} src={src} alt={alt} decorative={!alt} className={cx("weather-icon-demo-glyph", className)} {...rest} />;
  }

  function SingleLineTitle({ title, icon: _legacyIcon, iconAlt: _legacyIconAlt, iconFit: _legacyIconFit, invertIcon: _legacyInvertIcon, dataIds, className, ...rest }) {
    return (
      <div className={cx("title-demo-row", "single-line-title-row", className)} {...rest}>
        <div className="single-line-title-layout"><p className="single-line-title">{title}</p></div>
      </div>
    );
  }

  function DoubleLineTitle({ title, secondaryInfo, icon: _legacyIcon, iconAlt: _legacyIconAlt, iconFit: _legacyIconFit, invertIcon: _legacyInvertIcon, dataIds, className, ...rest }) {
    return (
      <div className={cx("title-demo-row", className)} {...rest}>
        <div className="double-line-title">
          <p className="double-line-title-main">{title}</p>
          <p className="double-line-title-sub">{secondaryInfo}</p>
        </div>
      </div>
    );
  }

  function Badge({ value, children, color = "blue", dataIds, className, ...rest }) {
    return <span className={cx("badge", className)} data-color={color} {...rest}>{children ?? value}</span>;
  }

  const emphasizedUnitPattern = new RegExp(
    String.raw`\s*([+-]?\d+(?:\.\d+)?)\s*`
      + String.raw`(次[/／]分钟|次[/／]分|bpm|公里/小时|千米/小时|毫秒|分钟|小时|千卡|公里|千米|`
      + String.raw`GB可用|TB|GB|MB|KB|mA|mV|A|V|W|秒|分|天|步|米|克|升|元|次|个|级|%|％)`,
    "gi",
  );
  const emphasizedCelsiusPattern = /^\s*([+-]?\d+(?:\.\d+)?)\s*(?:℃|°\s*C|摄氏度)\s*$/i;

  function normalizeEmphasizedItem(item) {
    if (item.dataIds?.unit) return [item];
    const numeric = typeof item.value === 'number'
      || (typeof item.value === 'string' && /^[+-]?\d+(?:\.\d+)?$/.test(item.value.trim()));
    if (numeric && ['℃', '°C', '摄氏度'].includes(item.unit)) {
      return [{...item, value: `${String(item.value).trim()}°`, unit: undefined}];
    }
    if (numeric && typeof item.value === 'string' && item.unit) {
      return [{...item, value: item.value.trim()}];
    }
    if (typeof item.value !== "string") return [item];

    const celsius = emphasizedCelsiusPattern.exec(item.value);
    if (celsius) return [{ ...item, value: `${celsius[1]}°`, unit: undefined }];

    const parts = [];
    let position = 0;
    emphasizedUnitPattern.lastIndex = 0;
    let match;
    while ((match = emphasizedUnitPattern.exec(item.value)) != null) {
      if (match.index !== position) return [item];
      parts.push({
        value: match[1],
        unit: match[2],
      });
      position = emphasizedUnitPattern.lastIndex;
    }
    return parts.length > 0 && item.value.slice(position).trim() === "" ? parts : [item];
  }

  function EmphasizedData({ value, unit, items, dataIds, className, ...rest }) {
    const normalized = (items || [{ value, unit, dataIds }]).flatMap(normalizeEmphasizedItem);
    return (
      <div className={cx("ed", className)} {...rest}>
        {normalized.map((item, index) => (
          <React.Fragment key={item.key ?? index}>
            <span className="ed-val">{item.value}</span>
            {item.unit != null && <span className="ed-unit">{item.unit}</span>}
          </React.Fragment>
        ))}
      </div>
    );
  }

  function EmphasisText({ mainText, secondaryText, dataIds, className, ...rest }) {
    return (
      <div className={cx("emphasis-text", className)} {...rest}>
        <p className="emphasis-text-main">{mainText}</p>
        {secondaryText != null && <p className="emphasis-text-secondary">{secondaryText}</p>}
      </div>
    );
  }

  function defaultSecondaryBodyRowSizes(itemCount) {
    const rowSizes = [];
    for (let index = 0; index < itemCount; index += 2) {
      rowSizes.push(Math.min(2, itemCount - index));
    }
    return rowSizes;
  }

  function resolvedSecondaryBodyRowSizes(itemCount, rowSizes) {
    if (
      !Array.isArray(rowSizes)
      || rowSizes.some((size) => size !== 1 && size !== 2)
      || rowSizes.reduce((total, size) => total + size, 0) !== itemCount
    ) {
      return defaultSecondaryBodyRowSizes(itemCount);
    }
    return rowSizes;
  }

  function renderSecondaryBodyItems(items, separator, layout) {
    const rows = [];
    const rowSizes = resolvedSecondaryBodyRowSizes(items.length, layout?.rowSizes);
    const wrappingIndexes = new Set(layout?.wrappingIndexes || []);
    let itemOffset = 0;
    for (let rowIndex = 0; rowIndex < rowSizes.length; rowIndex += 1) {
      const rowSize = rowSizes[rowIndex];
      const rowStart = itemOffset;
      const rowItems = items.slice(rowStart, rowStart + rowSize);
      itemOffset += rowSize;
      rows.push(
        <span className="secondary-body-row" key={rowItems[0]?.key ?? rowStart}>
          {rowItems.map((item, itemIndexInRow) => {
            const itemIndex = rowStart + itemIndexInRow;
            return (
              <React.Fragment key={item.key ?? itemIndex}>
                {itemIndexInRow > 0 && <span className="secondary-body-separator" aria-hidden="true">{separator}</span>}
                <span
                  className="secondary-body-field"
                  data-wrap={wrappingIndexes.has(itemIndex) ? "true" : undefined}
                >
                  {item.label != null && item.label !== "" && <span>{item.label}</span>}
                  <span>{item.value}</span>
                </span>
              </React.Fragment>
            );
          })}
        </span>
      );
    }
    return rows;
  }

  function measureSecondaryBodyLayout(element, itemCount, separator) {
    if (!element || !global.document?.body || itemCount <= 0) return null;
    const availableWidth = element.clientWidth || element.getBoundingClientRect().width;
    const fields = Array.from(element.querySelectorAll(":scope > .secondary-body-row > .secondary-body-field"));
    if (!(availableWidth > 0) || fields.length !== itemCount) return null;

    const measurement = element.cloneNode(false);
    measurement.removeAttribute("data-multiline");
    Object.assign(measurement.style, {
      position: "fixed",
      visibility: "hidden",
      pointerEvents: "none",
      left: "-10000px",
      top: "0",
      display: "block",
      width: "max-content",
      minWidth: "0",
      maxWidth: "none",
      height: "auto",
      maxHeight: "none",
      fontSize: "14px",
      fontWeight: "400",
      lineHeight: "19px",
      transform: "none",
    });
    const fieldClones = fields.map((field) => {
      const clone = field.cloneNode(true);
      clone.removeAttribute("data-wrap");
      Object.assign(clone.style, {
        display: "inline-block",
        width: "max-content",
        minWidth: "0",
        maxWidth: "none",
        whiteSpace: "nowrap",
        overflowWrap: "normal",
      });
      measurement.appendChild(clone);
      return clone;
    });
    const separatorClone = global.document.createElement("span");
    separatorClone.className = "secondary-body-separator";
    separatorClone.textContent = separator;
    measurement.appendChild(separatorClone);
    global.document.body.appendChild(measurement);

    const fieldWidths = fieldClones.map((field) => field.getBoundingClientRect().width);
    const separatorWidth = separatorClone.getBoundingClientRect().width;
    measurement.remove();

    const rowSizes = [];
    const wrappingIndexes = [];
    for (let index = 0; index < itemCount;) {
      const fieldWidth = fieldWidths[index] || 0;
      if (fieldWidth > availableWidth + 0.5) wrappingIndexes.push(index);
      const nextWidth = fieldWidths[index + 1];
      if (
        index + 1 < itemCount
        && fieldWidth <= availableWidth + 0.5
        && nextWidth <= availableWidth + 0.5
        && fieldWidth + separatorWidth + nextWidth <= availableWidth + 0.5
      ) {
        rowSizes.push(2);
        index += 2;
      } else {
        rowSizes.push(1);
        index += 1;
      }
    }
    return { rowSizes, wrappingIndexes };
  }

  function sameSecondaryBodyLayout(left, right) {
    return (
      left.rowSizes.length === right.rowSizes.length
      && left.rowSizes.every((size, index) => size === right.rowSizes[index])
      && left.wrappingIndexes.length === right.wrappingIndexes.length
      && left.wrappingIndexes.every((value, index) => value === right.wrappingIndexes[index])
    );
  }

  function SecondaryBody({ body: legacyBody, items, separator = " ｜ ", children, dataIds, className, ...rest }) {
    // `items` is the only public generation API. Keep legacy `body` rendering
    // here only so previously saved previews do not become blank.
    let resolvedItems = [];
    if (Array.isArray(items)) resolvedItems = items;
    else if (legacyBody != null) resolvedItems = [{ value: legacyBody }];
    const itemCount = resolvedItems.length;
    const forcedMultiline = itemCount > 2;
    const elementRef = React.useRef(null);
    const [itemLayout, setItemLayout] = React.useState(() => ({
      rowSizes: defaultSecondaryBodyRowSizes(itemCount),
      wrappingIndexes: [],
    }));
    const resolvedRowSizes = resolvedSecondaryBodyRowSizes(itemCount, itemLayout.rowSizes);
    const multiline = (
      forcedMultiline
      || resolvedRowSizes.length > 1
      || itemLayout.wrappingIndexes.length > 0
    );

    React.useLayoutEffect(() => {
      const element = elementRef.current;
      if (!element) return undefined;

      const update = () => {
        const next = measureSecondaryBodyLayout(element, itemCount, separator);
        if (!next) return;
        setItemLayout((current) => sameSecondaryBodyLayout(current, next) ? current : next);
      };
      update();

      const resizeObserver = typeof global.ResizeObserver === "function"
        ? new global.ResizeObserver(update)
        : null;
      resizeObserver?.observe(element);
      const mutationObserver = typeof global.MutationObserver === "function"
        ? new global.MutationObserver(update)
        : null;
      mutationObserver?.observe(element, { childList: true, characterData: true, subtree: true });
      return () => {
        resizeObserver?.disconnect();
        mutationObserver?.disconnect();
      };
    }, [itemCount, items, legacyBody, children, separator]);

    return (
      <p
        ref={elementRef}
        className={cx("secondary-body", className)}
        data-segmented="true"
        data-multiline={multiline ? "true" : "false"}
        {...rest}
      >
        {children ?? renderSecondaryBodyItems(resolvedItems, separator, itemLayout)}
      </p>
    );
  }

  function DataDisplay({ label, value, supportingText, dataIds, className, ...rest }) {
    return (
      <div className={cx("data-display", className)} {...rest}>
        <p className="data-display-label">{label}</p>
        <p className="data-display-value">{value}</p>
        <p className="data-display-supporting">{supportingText}</p>
      </div>
    );
  }

  function repeatsNumericUnit(value, unit) {
    if (typeof value !== "string" || typeof unit !== "string") return false;
    const normalizedValue = value.normalize("NFKC").trim().toLowerCase();
    const normalizedUnit = unit.normalize("NFKC").trim().toLowerCase();
    if (!normalizedUnit || !normalizedValue.endsWith(normalizedUnit)) return false;
    return /^[+-]?[0-9]+(?:\.[0-9]+)?$/.test(normalizedValue.slice(0, -normalizedUnit.length).trim());
  }

  function InfoBlock({ primaryText, secondaryText, unit, visual, dataIds, className, ...rest }) {
    const visualType = visual?.type;
    const visualIcon = visual?.icon;
    const progress = progressPercentage(primaryText);
    const circumference = 2 * Math.PI * 18;
    const progressLength = circumference * progress / 100;
    let visualNode = null;
    if (visualType === "progressCircle") {
      visualNode = (
        <div className="info-block-progress" aria-hidden="true">
          <svg viewBox="0 0 44 44">
            <circle className="info-block-progress-track" cx="22" cy="22" r="18" />
            <circle
              className="info-block-progress-bar"
              cx="22"
              cy="22"
              r="18"
              strokeDasharray={`${progressLength.toFixed(2)} ${circumference.toFixed(2)}`}
            />
          </svg>
          <div className="info-block-progress-inner">
            <GeneratedCardMask src={visualIcon} className="info-block-progress-icon" />
          </div>
        </div>
      );
    } else if (visualType === "icon") {
      visualNode = (
        <div className="info-block-visual" aria-hidden="true">
          {visual?.color === "native" ? (
            <img className="info-block-icon" data-color="native" src={assetUrl(visualIcon)} alt="" />
          ) : (
            <GeneratedCardMask src={visualIcon} className="info-block-icon-mask" />
          )}
        </div>
      );
    }

    return (
      <div className={cx("info-block", className)} data-component="info-block" {...rest}>
        <div className="info-block-copy">
          <p className="info-block-primary">
            <span className="info-block-primary-value">{primaryText}</span>
            {unit != null && !repeatsNumericUnit(primaryText, unit)
              && <span className="info-block-unit">{unit}</span>}
          </p>
          <p className="info-block-secondary">{secondaryText}</p>
        </div>
        {visualNode}
      </div>
    );
  }

  function TopTextBottomValue({ items = [], className, ...rest }) {
    const itemCount = items.length;
    return (
      <div className={cx("top-text-bottom-value", className)} data-component="top-text-bottom-value" {...rest}>
        {items.map(({ key, label, value, unit, dataIds }, index) => (
          <div className="top-text-bottom-value-item" key={key ?? index}>
            <p className="top-text-bottom-value-label">{label}</p>
            <p className="top-text-bottom-value-number">{value}</p>
            <p className="top-text-bottom-value-unit">{unit}</p>
          </div>
        ))}
        {items.slice(0, -1).map((item, index) => (
          <span
            className="top-text-bottom-value-divider"
            key={`divider-${item?.key ?? index}`}
            style={{ left: `${((index + 1) / itemCount) * 100}%` }}
            aria-hidden="true"
          />
        ))}
      </div>
    );
  }

  function TableText({ items = [], className, ...rest }) {
    return (
      <div
        className={cx("table-text", className)}
        {...rest}
        data-spacing={items.length >= 3 ? "adaptive" : "default"}
      >
        {items.map(({ key, label, parameter, dataIds, dataValueMaps }, index) => (
          <div className="table-text-item" key={key ?? index}>
            <p className="table-text-label">{label}</p>
            <p className="table-text-parameter">{parameter}</p>
          </div>
        ))}
      </div>
    );
  }

  function TextBlock({ items = [], className, ...rest }) {
    return (
      <div className={cx("text-block", className)} data-component="text-block" {...rest}>
        {items.map(({ key, label, parameter, dataIds }, index) => (
          <div className="text-block-item" key={key ?? index}>
            <div className="text-block-copy">
              <p className="text-block-label">{label}</p>
              <p className="text-block-parameter">{parameter}</p>
            </div>
          </div>
        ))}
      </div>
    );
  }

  TextBlock.__clawStackMinHeight = 0;

  function WeatherSummaryCard({ city, temperature, condition, airQuality, high, low, icon, ariaLabel, className, ...rest }) {
    const resolvedLabel = ariaLabel || `${city}${temperature}，${condition}，${airQuality}，最高${high}最低${low}`;
    const weatherKey = `${condition || ""} ${icon || ""}`.toLowerCase();
    let weather = "cloudy";
    if (weatherKey.includes("sunny") || weatherKey.includes("晴")) weather = "sunny";
    else if (weatherKey.includes("rain") || weatherKey.includes("雨")) weather = "rain";
    let appearance = "cloudy-gradient";
    if (weather === "sunny") appearance = "sunny-gradient";
    else if (weather === "rain") appearance = "slate-gradient";
    return (
      <Card
        size="2x2"
        appearance={appearance}
        className={cx("weather-icon-demo-card", className)}
        style={{ borderRadius: 24 }}
        data-weather={weather}
        role="img"
        aria-label={resolvedLabel}
        {...rest}
      >
        <div className="weather-icon-demo-content">
          <div className="weather-icon-demo-title-row">
            <div className="weather-icon-demo-title">{city}</div>
            <WeatherIcon src={icon} />
          </div>
          <div className="weather-icon-demo-reading"><div className="weather-icon-demo-temp">{temperature}</div></div>
          <div className="weather-icon-demo-meta">{condition} ｜ {airQuality}<br />{high}/{low}</div>
        </div>
      </Card>
    );
  }

  function SecondaryBodyCard({ title, value, lines = [], className, ...rest }) {
    return (
      <div className={cx("secondary-body-card", className)} {...rest}>
        <div className="secondary-body-card-top">
          <p className="single-line-title">{title}</p>
          {value != null && <EmphasizedData value={value} />}
        </div>
        <div className="secondary-body-card-bottom">
          {lines.map((line, index) => <SecondaryBody key={index} items={[{ value: line }]} />)}
        </div>
      </div>
    );
  }

  function ProgressLine1({ currentValue = 0, totalValue = 100, leftLabel, rightLabel, color = "blue", dataIds, className, ...rest }) {
    return (
      <div
        className={cx("pb", className)}
        data-color={color}
        style={{ "--pb-current": clamp(currentValue, 0, Number(totalValue) || 100), "--pb-total": Number(totalValue) || 100 }}
        {...rest}
      >
        <div className="pb-track"><div className="pb-range" /></div>
        <div className="pb-label-row">
          <span className="pb-label-left">{leftLabel}</span>
          <span className="pb-label-right">{rightLabel}</span>
        </div>
      </div>
    );
  }

  function ProgressLine2({ currentValue = 0, totalValue = 100, mode = "light", barColor, value, unit, items, dataIds, className, ...rest }) {
    const resolvedTotal = Number(totalValue) > 0 ? Number(totalValue) : 100;
    const resolvedCurrent = clamp(currentValue, 0, resolvedTotal);
    const percent = percentageFrom(resolvedCurrent, resolvedTotal);
    const hasDisplayValue = Boolean(items) || value != null;
    return (
      <div
        className={cx("pl2", className)}
        data-component="progress-line2"
        data-mode={mode}
        role="progressbar"
        aria-valuenow={visiblePercentage(percent)}
        aria-valuemin="0"
        aria-valuemax="100"
        style={{
          "--pl2-current": resolvedCurrent,
          "--pl2-total": resolvedTotal,
          ...(barColor ? { "--pl2-bar": barColor } : null),
        }}
        {...rest}
      >
        <EmphasizedData
          value={hasDisplayValue ? value : visiblePercentage(percent)}
          unit={hasDisplayValue ? unit : "%"}
          items={items}
        />
        <div className="pl2-track"><div className="pl2-bar" /></div>
      </div>
    );
  }

  function ProgressLine2WithData({ value, unit, items, ...props }) {
    return <ProgressLine2 {...props} value={value} unit={unit} items={items} />;
  }

  function H_BarChart({ items = [], mode = "light", className, ...rest }) {
    return (
      <div className={cx("bar-chart", className)} data-mode={mode} {...rest}>
        {items.map(({ key, label, valueUnit, percent, dataIds }, index) => {
          const resolvedPercent = clamp(percent);
          return (
            <div
              className="bar-chart-item"
              key={key ?? index}
              role="progressbar"
              aria-label={`${label} ${valueUnit}`}
              aria-valuenow={resolvedPercent}
              aria-valuemin="0"
              aria-valuemax="100"
            >
              <div className="bar-chart-meta">
                <p className="bar-chart-label">{label}</p>
                <p className="bar-chart-value-unit">{valueUnit}</p>
              </div>
              <div className="bar-chart-track" aria-hidden="true">
                <div className="bar-chart-bar" style={{ "--bar-chart-percent": resolvedPercent }} />
              </div>
            </div>
          );
        })}
      </div>
    );
  }

  function Gauge({ value, min = 1, max = 100, label, mode = "light", dataIds, className, ...rest }) {
    const numericMin = Number(min);
    const numericMax = Number(max);
    const resolvedMin = Number.isFinite(numericMin) ? numericMin : 1;
    const resolvedMax = Number.isFinite(numericMax) && numericMax > resolvedMin ? numericMax : 100;
    const numericValue = Number(value);
    const resolvedValue = Number.isFinite(numericValue)
      ? Math.min(resolvedMax, Math.max(resolvedMin, numericValue))
      : resolvedMin;
    const percent = clamp(((resolvedValue - resolvedMin) / (resolvedMax - resolvedMin)) * 100);
    return (
      <div
        className={cx("gauge", className)}
        data-mode={mode}
        role="progressbar"
        aria-label={`${label} ${value}`}
        aria-valuenow={resolvedValue}
        aria-valuemin={resolvedMin}
        aria-valuemax={resolvedMax}
        style={{ "--gauge-percent": percent }}
        {...rest}
      >
        <div className="gauge-arc" aria-hidden="true">
          <svg viewBox="0 0 94 94">
            <path className="gauge-track" d="M15.70 75 A42 42 0 1 1 78.30 75" pathLength="100" />
            <path className="gauge-bar" d="M15.70 75 A42 42 0 1 1 78.30 75" pathLength="100" />
          </svg>
        </div>
        <div className="gauge-copy">
          <p className="gauge-value">{value}</p>
          <div className="gauge-meta"><span>{label}</span></div>
        </div>
      </div>
    );
  }

  function ProgressRing({ value = 0, size = 44, strokeWidth = 6, trackColor = "var(--pc-track)", barColor = "#64bb5c", icon, iconSize = "sm", visibleOverflow = false, precision = 0, appearance }) {
    const center = size / 2;
    // 0827 only narrows the stroke from 8vp to 6vp. Keep the approved
    // centerline geometry: 44 -> r18, 52 -> r22, 96 -> r44.
    const radius = size / 2 - 4;
    const exactCircumference = 2 * Math.PI * radius;
    const circumference = precision > 0 ? exactCircumference.toFixed(precision) : Math.round(exactCircumference);
    const filled = precision > 0
      ? (exactCircumference * clamp(value) / 100).toFixed(precision)
      : Math.round(Number(circumference) * clamp(value) / 100);
    return (
      <div className="ring-wrap" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={visibleOverflow ? { display: "block", overflow: "visible" } : undefined} aria-hidden="true">
          <circle cx={center} cy={center} r={radius} fill="none" stroke={trackColor} strokeWidth={strokeWidth} />
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke={barColor}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={`${filled} ${circumference}`}
            transform={`rotate(-90 ${center} ${center})`}
          />
        </svg>
        <div className="ring-center">
          <div className="pc-center-icon" data-size={iconSize}>
            {appearance === "card" ? <GeneratedCardMask src={icon} size={iconSize} /> : <Icon src={icon} />}
          </div>
        </div>
      </div>
    );
  }

  function ProgressCircleSingle({ value, icon, displayValue, label, secondaryLabel, ariaLabel, appearance, size, trackColor, barColor, dataIds, className, ...rest }) {
    const threeLines = secondaryLabel != null;
    const compact = size === "compact";
    const ringSize = compact ? 44 : 52;
    const resolvedTrack = appearance === "card" ? "var(--card-progress-track)" : (trackColor || "rgba(0,0,0,.10)");
    const resolvedBar = appearance === "card" ? "var(--card-progress-bar)" : (barColor || "#64bb5c");
    const sharesPercentageBinding = dataIds?.value != null && dataIds.displayValue === dataIds.value;
    let resolvedDisplayValue = displayValue;
    if (resolvedDisplayValue == null || sharesPercentageBinding) {
      if (isFormattedPercentage(value)) {
        resolvedDisplayValue = value.trim();
      } else {
        resolvedDisplayValue = formatPercentage(value);
      }
    }
    return (
      <div className={cx("pc-single-combo", className)} data-size={compact ? "compact" : undefined} role="img" aria-label={ariaLabel || `${label} ${resolvedDisplayValue}`} {...rest}>
        <ProgressRing value={progressPercentage(value)} size={ringSize} strokeWidth={6} trackColor={resolvedTrack} barColor={resolvedBar} icon={icon} iconSize="single" visibleOverflow={appearance !== "card"} precision={appearance === "card" ? 1 : 0} appearance={appearance} />
        <span className="pc-stat-text" data-lines={threeLines ? "3" : undefined}>
          <span className="pc-stat-label">{label}</span>
          {threeLines ? (
            <span className="pc-stat-detail">
              <span className="pc-stat-value">{resolvedDisplayValue}</span>
              <span className="pc-stat-label-secondary">{secondaryLabel}</span>
            </span>
          ) : <span className="pc-stat-value">{resolvedDisplayValue}</span>}
        </span>
      </div>
    );
  }

  function ProgressCircle({ value, icon, externalText, size = "sm", density, ariaLabel, appearance, trackColor = "rgba(0,0,0,.10)", barColor, dataIds, className, ...rest }) {
    const diameter = size === "md" ? 96 : 44;
    const iconSize = size === "md" ? "md" : "sm";
    const resolvedTrack = appearance === "card" ? "var(--card-progress-track)" : trackColor;
    const resolvedBar = appearance === "card" ? "var(--card-progress-bar)" : (barColor || "#64bb5c");
    const resolvedExternalText = formatProgressCircleText(externalText ?? value);
    const resolvedProgressValue = progressPercentage(externalText ?? value);
    return (
      <div className={cx("pc-component", className)} data-density={density} role="img" aria-label={ariaLabel || resolvedExternalText} {...rest}>
        <ProgressRing value={resolvedProgressValue} size={diameter} strokeWidth={6} trackColor={resolvedTrack} barColor={resolvedBar} icon={icon} iconSize={iconSize} precision={appearance === "card" ? 1 : 0} appearance={appearance} />
        <div className="pc-external-value">{resolvedExternalText}</div>
      </div>
    );
  }

  function NumericRatio({ icon, value, unit, appearance, dataIds, className, ...rest }) {
    const resolvedUnit = unit ?? (typeof value === "number" ? "%" : "");
    const resolvedValue = typeof value === "number" ? visiblePercentage(value) : value;
    return (
      <span className={cx("numeric-ratio", className)} {...rest}>
        <span className="numeric-ratio-icon">{appearance === "card" ? <GeneratedCardMask src={icon} /> : <Icon src={icon} />}</span>
        <span className="numeric-ratio-value">{resolvedValue}{resolvedUnit}</span>
      </span>
    );
  }

  function NumericRatioStack({ items = [], appearance, className, ...rest }) {
    return (
      <div className={cx("numeric-ratio-stack", className)} {...rest}>
        {items.map((item, index) => <NumericRatio key={item.key ?? index} {...item} appearance={appearance} />)}
      </div>
    );
  }

  function ChecklistItem({ title, meta, done = false, dataIds, className, ...rest }) {
    return (
      <div className={cx("cli", className)} {...rest}>
        <div className="cli-row">
          <div className="cli-checkbox" data-done={String(done)} role="checkbox" aria-checked={String(done)}>
            {done && <span className="cli-check-icon" aria-hidden="true">✓</span>}
          </div>
          <div className="cli-content">
            <span className="cli-title">{title}</span>
            <span className="cli-meta">{meta}</span>
          </div>
        </div>
      </div>
    );
  }

  function EventCard({ title, time, location, density, dataIds, className, ...rest }) {
    const compact = density === "compact";
    return (
      <div className={cx("ec", className)} data-density={compact ? "compact" : undefined} {...rest}>
        <div className="ec-rail" aria-hidden="true"><span className="ec-dot" /><span className="ec-line" /></div>
        <div className="ec-content">
          <span className="ec-title">{title}</span>
          {compact ? (
            <div className="ec-meta">
              <span className="ec-time">{time}</span>
              {location != null && <span className="ec-meta-separator" aria-hidden="true">｜</span>}
              {location != null && <span className="ec-location">{location}</span>}
            </div>
          ) : (
            <>
              <span className="ec-time">{time}</span>
              {location != null && <span className="ec-location">{location}</span>}
            </>
          )}
        </div>
      </div>
    );
  }

  function ButtonIcon({ icon }) {
    if (!icon) return null;
    return <span className="btn-icon-mask" style={{ "--button-icon-url": `url("${assetUrl(icon)}")` }} />;
  }

  function PillButton({ label, icon, variant = "emphasis", color = "primary", appearance, disabled = false, actionId, className, ...rest }) {
    return (
      <button className={cx("btn", "pill-btn", className)} data-variant={variant} data-color={color} data-appearance={appearance} disabled={disabled} {...rest}>
        <span className="btn-inner">
          {icon && <span className="btn-icon" aria-hidden="true"><ButtonIcon icon={icon} /></span>}
          <span className="btn-label">{label}</span>
        </span>
      </button>
    );
  }

  function CircleButton({ icon, ariaLabel, variant = "emphasis", color = "primary", appearance, disabled = false, actionId, className, ...rest }) {
    return (
      <button className={cx("btn", "circle-btn", className)} data-variant={variant} data-color={color} data-appearance={appearance} disabled={disabled} aria-label={ariaLabel} {...rest}>
        <span className="btn-inner"><span className="btn-icon" aria-hidden="true"><ButtonIcon icon={icon} /></span></span>
      </button>
    );
  }

  function CardButton({ text, icon, disabled = false, actionId, className, ...rest }) {
    return (
      <button
        type="button"
        className={cx("card-action-btn", className)}
        disabled={disabled}
        {...rest}
      >
        <span className="card-action-btn__content">
          {icon ? (
            <span
              className="card-action-btn__icon"
              style={{ "--card-button-icon-url": `url("${assetUrl(icon)}")` }}
              aria-hidden="true"
            />
          ) : (
            <span className="card-action-btn__icon-placeholder" aria-hidden="true" />
          )}
          <span className="card-action-btn__label">{text}</span>
        </span>
      </button>
    );
  }

  const componentContracts = Object.freeze({
    Card: { optional: ["children", "size", "appearance", "background", "padding", "direction", "gap", "align", "justify"], size: Object.keys(CARD_SIZE_PRESETS), appearance: Object.keys(CARD_APPEARANCES) },
    Stack: { optional: ["children", "direction", "gap", "align", "justify", "wrap", "flex", "basis", "width", "minWidth", "height", "minHeight", "mt", "mb", "ml", "mr", "position", "top", "right", "bottom", "left", "alignSelf", "surface"], surface: ["backplate"] },
    Grid: { optional: ["children", "columns", "rows", "gap", "rowGap", "columnGap", "flex", "basis", "width", "minWidth", "height", "minHeight", "align", "justify", "mt", "mb"] },
    Icon: { optional: ["name", "src", "size", "alt", "decorative"] },
    SingleLineTitle: { required: ["title"], optional: ["dataIds"] },
    DoubleLineTitle: { required: ["title", "secondaryInfo"], optional: ["dataIds"] },
    Badge: { required: ["value"], optional: ["dataIds"], color: ["blue", "orange", "green", "red", "purple", "cyan", "pink"] },
    EmphasizedData: { requiredOneOf: ["value", "items"], optional: ["unit", "dataIds"] },
    EmphasisText: { required: ["mainText", "secondaryText"], optional: ["dataIds"] },
    SecondaryBody: { required: ["items"], itemsMinLength: 1, optional: ["separator"] },
    DataDisplay: { required: ["label", "value", "supportingText"], optional: ["dataIds"] },
    InfoBlock: { required: ["primaryText", "secondaryText"], optional: ["unit", "visual", "dataIds"] },
    TopTextBottomValue: { required: ["items"], itemsMinLength: 2 },
    TableText: { required: ["items"], itemsMinLength: 2 },
    TextBlock: { required: ["items"], itemsMinLength: 2 },
    WeatherSummaryCard: { required: ["city", "temperature", "condition", "airQuality", "high", "low", "icon"], optional: ["ariaLabel"] },
    SecondaryBodyCard: { required: ["title", "lines"], optional: ["value"] },
    // Runtime compatibility only: keep old JSX renderable, but do not include
    // this removed variant in the model-facing generation whitelist.
    ProgressLine1: { required: ["currentValue", "totalValue", "leftLabel", "rightLabel"], optional: ["dataIds"], color: ["blue", "orange", "yellow", "purple", "red", "green", "pink"] },
    ProgressLine2: { required: ["currentValue", "totalValue"], optional: ["barColor", "value", "unit", "items", "dataIds"], mode: ["light", "dark"] },
    H_BarChart: { required: ["items"], itemsMinLength: 2, mode: ["light", "dark"] },
    Gauge: { required: ["value", "label"], optional: ["min", "max", "dataIds"], mode: ["light", "dark"] },
    ProgressCircleSingle: { required: ["value", "icon", "label"], optional: ["displayValue", "secondaryLabel", "ariaLabel", "appearance", "size", "trackColor", "barColor", "dataIds"], size: ["compact"] },
    ProgressCircle: { required: ["icon", "externalText"], optional: ["value", "density", "ariaLabel", "appearance", "trackColor", "barColor", "dataIds"], size: ["sm", "md"] },
    NumericRatio: { required: ["icon", "value"], optional: ["unit", "appearance", "dataIds"] },
    NumericRatioStack: { required: ["items"], optional: ["appearance"] },
    ChecklistItem: { required: ["title", "meta"], optional: ["done", "dataIds"] },
    EventCard: { required: ["title", "time"], optional: ["location", "density", "dataIds"], density: ["compact"] },
    PillButton: { required: ["label"], optional: ["icon", "appearance", "disabled", "actionId"], variant: ["emphasis", "normal"], color: ["primary", "secondary", "success", "discovery", "danger", "warning", "caution"] },
    CircleButton: { required: ["icon", "ariaLabel"], optional: ["appearance", "disabled", "actionId"], variant: ["emphasis", "normal"], color: ["primary", "secondary", "success", "discovery", "danger", "warning", "caution"] },
    CardButton: { required: ["text"], optional: ["icon", "disabled", "actionId"] },
  });

  global.ClawWidgetDesignSystem = Object.freeze({
    Card,
    Stack,
    Grid,
    Icon,
    AppIcon,
    WeatherIcon,
    SingleLineTitle,
    DoubleLineTitle,
    Badge,
    EmphasizedData,
    EmphasisText,
    SecondaryBody,
    DataDisplay,
    InfoBlock,
    TopTextBottomValue,
    TableText,
    TextBlock,
    WeatherSummaryCard,
    SecondaryBodyCard,
    ProgressLine1,
    ProgressLine2,
    ProgressLine2WithData,
    H_BarChart,
    Gauge,
    ProgressRing,
    ProgressCircleSingle,
    ProgressCircle,
    NumericRatio,
    NumericRatioStack,
    ChecklistItem,
    EventCard,
    PillButton,
    CircleButton,
    CardButton,
    componentContracts,
    cardSizePresets: CARD_SIZE_PRESETS,
    assetUrl,
  });

})(window);
