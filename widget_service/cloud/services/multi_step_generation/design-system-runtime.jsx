/* global React */

/**
 * Claw Widget 0827 design-system runtime.
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

  /* ── 1.2.1 背景模板：所有示例卡片只能引用以下规范 Token ── */
  --card-bg-light-blue:linear-gradient(180deg,rgba(10,89,247,.10) 0%,rgba(255,255,255,0) 100%),#fff;
  --card-bg-light-red:linear-gradient(180deg,rgba(230,69,102,.10) 0%,rgba(255,255,255,0) 100%),#fff;
  --card-bg-light-yellow:linear-gradient(180deg,rgba(247,206,0,.10) 0%,rgba(255,255,255,0) 100%),#fff;
  --card-bg-light-green:linear-gradient(180deg,rgba(100,187,92,.10) 0%,rgba(255,255,255,0) 100%),#fff;
  --card-bg-light-cyan:linear-gradient(180deg,rgba(70,177,227,.10) 0%,rgba(255,255,255,0) 100%),#fff;
  --card-bg-dark-sunny:linear-gradient(180deg,#317AF7 0%,#46B1E3 100%);
  --card-bg-dark-rain:linear-gradient(180deg,rgb(23,53,115) 0%,rgb(0,143,191) 68%,rgb(65,116,217) 100%);
  --card-bg-dark-cloudy:linear-gradient(180deg,rgb(43,50,66) 0%,rgb(116,134,160) 68%,rgb(90,108,132) 100%);
  --card-bg-dark-health:linear-gradient(180deg,#ED6F21 0%,#F9A01E 100%);
  --card-bg-dark-sleep:linear-gradient(180deg,#AC49F5 0%,#C386F0 100%);

  /* 天气·多椭圆深色渐变模板 — 场景配色 */
  --card-bg-dark-rain-right-bottom-color:rgba(65,116,217,1);
  --card-bg-dark-rain-left-bottom-color:rgba(0,143,191,1);
  --card-bg-dark-rain-top-color:rgba(23,53,115,1);
  --card-bg-dark-cloudy-right-bottom-color:rgb(90,108,132);
  --card-bg-dark-cloudy-left-bottom-color:rgb(116,134,160);
  --card-bg-dark-cloudy-top-color:rgb(43,50,66);
  --card-bg-dark-type0-right-bottom-color:#FAA89E;
  --card-bg-dark-type0-left-bottom-color:#FF8E3E;
  --card-bg-dark-type0-top-color:#BF3F26;

  /* 多椭圆模板几何 — 相对宿主卡片尺寸（百分比），不再锁定 160×160vp
     基准换算（160×160vp）：右下 100vp @ 96/80 · 左下 160vp @ -40/70 · 上方 210vp @ -25/-90
     2×2（160×160vp）与 2×4（320×160vp）直接套用同一组百分比 */
  --card-bg-dark-ellipse-right-bottom-size:62.5%;
  --card-bg-dark-ellipse-right-bottom-x:60%;
  --card-bg-dark-ellipse-right-bottom-y:50%;
  --card-bg-dark-ellipse-left-bottom-size:100%;
  --card-bg-dark-ellipse-left-bottom-x:-25%;
  --card-bg-dark-ellipse-left-bottom-y:43.75%;
  --card-bg-dark-ellipse-top-size:131.25%;
  --card-bg-dark-ellipse-top-x:-15.625%;
  --card-bg-dark-ellipse-top-y:-56.25%;
  --card-bg-dark-backplate:rgba(255,255,255,.05);
  --card-bg-dark-blur:50px;

  /* 2×4（320×160vp）专用规格：纵向分布与 2×2 一致（上方盖到 y≈120，下方 40vp 露角），
     横向铺满整卡无白缝；上方椭圆横向拉宽为椭圆，底部两椭圆横向拉开并保证下沿覆盖 */
  --card-bg-dark-ellipse-2x4-right-bottom-size:68.75%;   /* 220vp 宽 */
  --card-bg-dark-ellipse-2x4-right-bottom-h:62.5%;       /* 100vp 高 */
  --card-bg-dark-ellipse-2x4-right-bottom-x:56.25%;      /* 180vp */
  --card-bg-dark-ellipse-2x4-right-bottom-y:50%;         /* 80vp */
  --card-bg-dark-ellipse-2x4-left-bottom-size:87.5%;     /* 280vp 宽 */
  --card-bg-dark-ellipse-2x4-left-bottom-h:100%;         /* 160vp 高 */
  --card-bg-dark-ellipse-2x4-left-bottom-x:-18.75%;      /* -60vp */
  --card-bg-dark-ellipse-2x4-left-bottom-y:43.75%;       /* 70vp */
  --card-bg-dark-ellipse-2x4-top-size:131.25%;           /* 420vp 宽 */
  --card-bg-dark-ellipse-2x4-top-h:131.25%;              /* 210vp 高 */
  --card-bg-dark-ellipse-2x4-top-x:-15.625%;             /* -50vp */
  --card-bg-dark-ellipse-2x4-top-y:-56.25%;              /* -90vp */

  /* ── 1.2.3 按背景类型映射的按钮色 ── */
  --button-light-blue-bg:rgba(10,89,247,.10);
  --button-light-blue-content:#0A59F7;
  --button-dark-bg:#FFFFFF;

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
  --top-text-bottom-value-divider:rgba(0,0,0,.2);

  /* ── Component Background Color Tokens ── */
  --comp_background_primary:#ffffff;
  --comp_background_secondary:rgba(0,0,0,.10);
  --comp_background_tertiary:rgba(0,0,0,.05);

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
  /* ── Progress Circle Tokens (Dark) ── */
  --pc-track:rgba(255,255,255,.10);
}

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
  width: 36px;
  min-width: 36px;
  height: 36px;
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
.pill-btn .btn-icon img{
  display:block;width:20px;height:20px;
  filter:brightness(0) invert(1);}
.circle-btn .btn-icon{
  flex-basis:20px;width:20px;height:20px;
  font-size:20px;line-height:20px;}
.circle-btn .btn-icon img{display:block;width:20px;height:20px;object-fit:contain;}
.circle-btn[data-variant="emphasis"] .btn-icon img{filter:brightness(0) invert(1);}
.circle-btn[data-variant="normal"] .btn-icon img{filter:brightness(0);opacity:.8;}
.btn-label {
  position: relative;
  z-index: 1;
  font: inherit;}
.button-card-position-demo{
  position:relative;width:160px;height:160px;border-radius:20px;
  background:var(--card-bg-light-blue);
  border:1px solid rgba(0,0,0,.06);overflow:hidden;}
.button-card-position-demo .pill-btn{
  position:absolute;left:12px;bottom:12px;
  --btn-bg:var(--button-light-blue-bg);--btn-bg-hover:var(--button-light-blue-bg);--btn-bg-active:var(--button-light-blue-bg);--btn-text:var(--button-light-blue-content)}
.button-card-position-demo .circle-btn{
  position:absolute;right:12px;bottom:12px;
  --btn-bg:var(--button-light-blue-content);--btn-bg-hover:var(--button-light-blue-content);--btn-bg-active:var(--button-light-blue-content);--btn-text:#fff}
#pillbutton .pill-btn{
  --btn-bg:var(--button-light-blue-bg);--btn-bg-hover:var(--button-light-blue-bg);--btn-bg-active:var(--button-light-blue-bg);--btn-text:var(--button-light-blue-content);}
#circlebutton .circle-btn{
  --btn-bg:var(--button-light-blue-content);--btn-bg-hover:var(--button-light-blue-content);--btn-bg-active:var(--button-light-blue-content);--btn-text:#fff;}
#circlebutton .circle-btn .btn-icon img{filter:brightness(0) invert(1);opacity:1}

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
  --card-button-theme-color:var(--card-action-text,var(--button-light-blue-content));
  background:color-mix(in srgb,var(--card-button-theme-color) 10%,transparent);
  color:var(--card-button-theme-color);
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
.card-action-btn__label{
  order:1;
  flex:1 1 auto;
  min-width:0;
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap;
  text-align:left;}
.generated-card-frame[data-tone="dark"] .card-action-btn{
  background:rgba(255,255,255,.20);
  color:#fff;}

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
  background:var(--card-bg-light-blue);
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
  left:var(--card-bg-dark-ellipse-right-bottom-x);top:var(--card-bg-dark-ellipse-right-bottom-y);
  width:var(--card-bg-dark-ellipse-right-bottom-size);
  aspect-ratio:1/1;background:var(--card-bg-dark-ellipse-right-bottom-color);}
.card-bg-dark__ellipse--left-bottom{
  left:var(--card-bg-dark-ellipse-left-bottom-x);top:var(--card-bg-dark-ellipse-left-bottom-y);
  width:var(--card-bg-dark-ellipse-left-bottom-size);
  aspect-ratio:1/1;background:var(--card-bg-dark-ellipse-left-bottom-color);}
.card-bg-dark__ellipse--top{
  left:var(--card-bg-dark-ellipse-top-x);top:var(--card-bg-dark-ellipse-top-y);
  width:var(--card-bg-dark-ellipse-top-size);
  aspect-ratio:1/1;background:var(--card-bg-dark-ellipse-top-color);}
.card-bg-dark__backplate{
  position:absolute;inset:0;width:100%;height:100%;
  border-radius:inherit;background:var(--card-bg-dark-backplate);
  -webkit-backdrop-filter:blur(var(--card-bg-dark-blur));
  backdrop-filter:blur(var(--card-bg-dark-blur));}
.card-bg-dark--rain{
  background:var(--card-bg-dark-rain);
  --card-bg-dark-ellipse-right-bottom-color:var(--card-bg-dark-rain-right-bottom-color);
  --card-bg-dark-ellipse-left-bottom-color:var(--card-bg-dark-rain-left-bottom-color);
  --card-bg-dark-ellipse-top-color:var(--card-bg-dark-rain-top-color);}
.card-bg-dark--cloudy{
  background:var(--card-bg-dark-cloudy);
  --card-bg-dark-ellipse-right-bottom-color:var(--card-bg-dark-cloudy-right-bottom-color);
  --card-bg-dark-ellipse-left-bottom-color:var(--card-bg-dark-cloudy-left-bottom-color);
  --card-bg-dark-ellipse-top-color:var(--card-bg-dark-cloudy-top-color);}
.weather-icon-demo-card{
  position:relative;isolation:isolate;contain:paint;overflow:hidden;
  box-sizing:border-box;width:160px;height:160px;padding:12px;border-radius:24px;
  background:transparent;border:0;}
.weather-icon-demo-card[data-weather="sunny"]{
  background:var(--card-bg-dark-sunny);}
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
/* ── emphasis · 实心填充 + 白字 ───────────── */
.btn[data-variant="emphasis"][data-color="primary"]  { --btn-bg:var(--blue-400);   --btn-bg-hover:var(--blue-500);   --btn-bg-active:var(--blue-600);   --btn-text:#fff;}
.btn[data-variant="emphasis"][data-color="secondary"]{ --btn-bg:var(--gray-600);   --btn-bg-hover:var(--gray-700);   --btn-bg-active:var(--gray-800);   --btn-text:#fff;}
.btn[data-variant="emphasis"][data-color="success"]  { --btn-bg:var(--green-400);  --btn-bg-hover:var(--green-500);  --btn-bg-active:var(--green-600);  --btn-text:#fff;}
.btn[data-variant="emphasis"][data-color="warning"]  { --btn-bg:var(--orange-400); --btn-bg-hover:var(--orange-500); --btn-bg-active:var(--orange-600); --btn-text:#fff;}
.btn[data-variant="emphasis"][data-color="caution"]  { --btn-bg:var(--yellow-400); --btn-bg-hover:var(--yellow-500); --btn-bg-active:var(--yellow-600); --btn-text:var(--text);}
.btn[data-variant="emphasis"][data-color="danger"]   { --btn-bg:var(--red-400);    --btn-bg-hover:var(--red-500);    --btn-bg-active:var(--red-600);    --btn-text:#fff;}
.btn[data-variant="emphasis"][data-color="discovery"]{ --btn-bg:var(--purple-400); --btn-bg-hover:var(--purple-500); --btn-bg-active:var(--purple-600); --btn-text:#fff;}

/* ── normal · 浅色底 + 同色字 ─────────────── */
.btn[data-variant="normal"][data-color="primary"]  { --btn-bg:var(--blue-50);   --btn-bg-hover:var(--blue-100);  --btn-bg-active:var(--blue-100);  --btn-text:var(--blue-400);}
.btn[data-variant="normal"][data-color="secondary"]{ --btn-bg:var(--gray-100);  --btn-bg-hover:var(--gray-150);  --btn-bg-active:var(--gray-200);  --btn-text:var(--text);}
.btn[data-variant="normal"][data-color="success"]  { --btn-bg:var(--green-50);  --btn-bg-hover:var(--green-100); --btn-bg-active:var(--green-100); --btn-text:var(--green-400);}
.btn[data-variant="normal"][data-color="warning"]  { --btn-bg:var(--orange-50); --btn-bg-hover:var(--orange-100);--btn-bg-active:var(--orange-100);--btn-text:var(--orange-400);}
.btn[data-variant="normal"][data-color="caution"]  { --btn-bg:var(--yellow-50); --btn-bg-hover:var(--yellow-100);--btn-bg-active:var(--yellow-100);--btn-text:var(--yellow-400);}
.btn[data-variant="normal"][data-color="danger"]   { --btn-bg:var(--red-50);    --btn-bg-hover:var(--red-100);   --btn-bg-active:var(--red-100);   --btn-text:var(--red-400);}
.btn[data-variant="normal"][data-color="discovery"]{ --btn-bg:var(--purple-50); --btn-bg-hover:var(--purple-100);--btn-bg-active:var(--purple-100);--btn-text:var(--purple-400);}

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
  gap:8px;
  width:100%;
  min-width:0;
  --pl2-bar:var(--blue-400);}
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
  background:rgba(0,0,0,.10);}
.pl2[data-mode="dark"] .pl2-track{background:rgba(255,255,255,.40);}
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
  stroke:color-mix(in srgb,var(--gauge-theme-color,var(--button-light-blue-content)) 20%,transparent);}
.gauge-bar{
  stroke:var(--gauge-theme-color,var(--button-light-blue-content));
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
  background:var(--card-bg-dark-sunny);}
.pl2-demo-card[data-mode="light"] .ed-val,
.pl2-demo-card[data-mode="light"] .ed-unit{color:#fff;}
.pl2-demo-card[data-mode="light"] .single-line-title{color:rgba(255,255,255,.60);}
.pl2-demo-card[data-mode="light"] .pl2-layout-title{color:rgba(255,255,255,.60);}
.pl2-demo-card[data-mode="dark"]{
  background:var(--card-bg-light-blue);}
.pl2-demo-card[data-mode="light"] .pill-btn{
  --btn-bg:var(--button-dark-bg);--btn-bg-hover:var(--button-dark-bg);--btn-bg-active:var(--button-dark-bg);--btn-text:#317AF7;}
.pl2-demo-card[data-mode="dark"] .pill-btn{
  --btn-bg:var(--button-light-blue-bg);--btn-bg-hover:var(--button-light-blue-bg);--btn-bg-active:var(--button-light-blue-bg);--btn-text:var(--button-light-blue-content);}

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
  background:linear-gradient(180deg,#AC49F5 0%,#C386F0 100%);}
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
  background:var(--card-bg-light-blue);color:var(--font-primary);overflow:hidden}
.pc-demo-title{
  height:12px;line-height:12px;font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;
  font-size:12px;font-weight:400;color:rgba(0,0,0,.6);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pc-type12-card{height:160px}
.pc-type12-main{height:92px;display:grid;grid-template-columns:64px 64px;gap:8px}
.pc-type12-zone{width:64px;height:92px;display:flex;align-items:center;justify-content:center;min-width:0}
.pc-type12-button{
  width:136px;height:36px;margin-top:8px;border:0;border-radius:30px;
  display:flex;align-items:center;justify-content:center;gap:8px;
  background:var(--button-light-blue-bg);color:var(--button-light-blue-content);font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;
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
  /* Keep the 12px unit inside the value's 38px layout box. Baseline alignment
     combines the two font metrics and can make the flex item's box 3px taller,
     causing the next semantic component to be reported as overlapping. */
  align-items:flex-end;
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
  gap:0;
  min-width:0;
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;
  text-align:left;}
.emphasis-text-main{
  margin:0;
  font-size:var(--fs-ts);
  font-weight:700;
  line-height:27px;
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
  color:var(--font-primary);
  text-align:left;
  white-space:normal;
  overflow-wrap:anywhere;}
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
  border:1px dashed var(--border-strong);
  border-radius:var(--radius-xl);
  background:var(--card-bg-light-blue);}
/* ── Summary · 辅助说明纯文本 ───────────────────── */
.summary-text{
  margin:0;min-width:0;max-width:100%;
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;
  font-size:var(--fs-cm);font-weight:400;line-height:1.4;color:var(--font-secondary);
  white-space:normal;overflow-wrap:anywhere;}

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
  width:136px;
  height:64px;
  flex:0 0 64px;
  padding:0 8px;
  border-radius:16px;
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:4px;
  overflow:hidden;
  background:rgba(255,255,255,.20);
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
  filter:brightness(0) invert(1);}
.info-block-icon[data-color="native"]{filter:none;}
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
.info-block-progress-track{stroke:rgba(255,255,255,.10);}
.info-block-progress-bar{
  stroke:#fff;
  stroke-linecap:round;}
.info-block-progress-inner{
  position:absolute;
  inset:0;
  display:flex;
  align-items:center;
  justify-content:center;}
.info-block-progress-inner img{
  display:block;
  width:20px;
  height:20px;
  opacity:.90;
  filter:brightness(0) invert(1);}

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
  min-width:0;
  flex-direction:column;
  gap:2px;
  font-family:"HarmonyHeiTi","HarmonyOS Sans SC","HarmonyOS Sans",sans-serif;}
.table-text-item{
  display:flex;
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
  width:100%;
  height:64px;
  max-height:100%;
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
  background:color-mix(in srgb,var(--text-block-theme-color,var(--button-light-blue-content)) 10%,transparent);}
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
  color:var(--text-block-theme-color,var(--button-light-blue-content));}
.text-block-parameter{
  font-size:var(--fs-cm);
  font-weight:500;
  line-height:16px;
  color:var(--text-block-theme-color,var(--button-light-blue-content));
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
  border:1.5px solid #ff2f23;
  background:transparent;
  border-radius:50%;}
.ec-line{
  flex:1;
  width:1px;
  min-height:0;
  margin-top:5px;
  background:#d8d8d8;}
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
  margin-bottom:4px;}
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
  border-radius:16px;background:var(--card-bg-dark-rain);}

/* ── Badge ────────────────────────────────────────── */
.badge{
  height:16px;border-radius:8px;
  display:inline-flex;align-items:center;justify-content:center;
  padding:0 6px;
  font-size:.625rem;font-weight:500;
  --badge-color:var(--blue-400);
  background:color-mix(in srgb, var(--badge-color) 10%, transparent);
  color:var(--badge-color);}
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
  opacity:.6;}
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
  color:color-mix(in srgb,var(--bar-chart-theme-color,var(--button-light-blue-content)) 60%,transparent);}
.bar-chart-value-unit{
  flex:0 0 auto;
  margin:0;
  font-size:var(--fs-bm);
  font-weight:700;
  line-height:20px;
  color:color-mix(in srgb,var(--bar-chart-theme-color,var(--button-light-blue-content)) 60%,transparent);
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
  background:color-mix(in srgb,var(--bar-chart-theme-color,var(--button-light-blue-content)) 20%,transparent);}
.bar-chart-bar{
  width:clamp(0%,calc(var(--bar-chart-percent,0) * 1%),100%);
  height:100%;
  min-height:6px;
  max-height:6px;
  border-radius:2px;
  background:var(--bar-chart-theme-color,var(--button-light-blue-content));}
[data-theme="dark"] .bar-chart:not([data-mode="light"]) .bar-chart-label,
.bar-chart[data-mode="dark"] .bar-chart-label{color:rgba(255,255,255,.50);}
[data-theme="dark"] .bar-chart:not([data-mode="light"]) .bar-chart-value-unit,
.bar-chart[data-mode="dark"] .bar-chart-value-unit{color:rgba(255,255,255,.50);}
[data-theme="dark"] .bar-chart:not([data-mode="light"]) .bar-chart-track,
.bar-chart[data-mode="dark"] .bar-chart-track{background:rgba(255,255,255,.20);}
[data-theme="dark"] .bar-chart:not([data-mode="light"]) .bar-chart-bar,
.bar-chart[data-mode="dark"] .bar-chart-bar{background:#fff;}

/* ── Generated Card mode ───────────────────────────
   Component geometry and palettes stay here; card composition is expressed
   declaratively with Card, Stack, and Grid props. */
.generated-card-background{
  position:absolute;inset:0;z-index:0;display:block;width:100%;height:100%;
  overflow:hidden;border-radius:inherit;pointer-events:none;
  -webkit-clip-path:inset(0 round 20px);clip-path:inset(0 round 20px);}
.generated-card-frame > :not(.generated-card-background){position:relative;z-index:1;}
.generated-card-background__ellipse{position:absolute;display:block;border-radius:50%;}
.generated-card-background__ellipse[data-position="right-bottom"]{
  left:60%;top:50%;width:62.5%;aspect-ratio:1/1;
  background:var(--card-bg-ellipse-right-bottom);}
.generated-card-background__ellipse[data-position="left-bottom"]{
  left:-25%;top:43.75%;width:100%;aspect-ratio:1/1;
  background:var(--card-bg-ellipse-left-bottom);}
.generated-card-background__ellipse[data-position="top"]{
  left:-15.625%;top:-56.25%;width:131.25%;aspect-ratio:1/1;
  background:var(--card-bg-ellipse-top);}
.generated-card-background__backplate{
  position:absolute;inset:0;display:block;width:100%;height:100%;
  border-radius:inherit;background:rgba(255,255,255,.05);
  -webkit-backdrop-filter:blur(50px);backdrop-filter:blur(50px);}
.generated-card-background[data-card-size="2x4"] .generated-card-background__ellipse[data-position="right-bottom"]{
  left:180px;top:80px;width:220px;height:100px;aspect-ratio:auto;}
.generated-card-background[data-card-size="2x4"] .generated-card-background__ellipse[data-position="left-bottom"]{
  left:-60px;top:70px;width:280px;height:160px;aspect-ratio:auto;}
.generated-card-background[data-card-size="2x4"] .generated-card-background__ellipse[data-position="top"]{
  left:-50px;top:-90px;width:420px;height:210px;aspect-ratio:auto;}
.generated-card-background[data-appearance="cloudy-gradient"]{
  background:linear-gradient(180deg,rgb(43,50,66) 0%,rgb(116,134,160) 68%,rgb(90,108,132) 100%);
  --card-bg-ellipse-right-bottom:rgb(90,108,132);
  --card-bg-ellipse-left-bottom:rgb(116,134,160);
  --card-bg-ellipse-top:rgb(43,50,66);}
.generated-card-background[data-appearance="slate-gradient"]{
  background:linear-gradient(180deg,rgb(23,53,115) 0%,rgb(0,143,191) 68%,rgb(65,116,217) 100%);
  --card-bg-ellipse-right-bottom:rgb(65,116,217);
  --card-bg-ellipse-left-bottom:rgb(0,143,191);
  --card-bg-ellipse-top:rgb(23,53,115);}
.generated-card-background[data-appearance="type0-gradient"]{
  background:transparent;
  --card-bg-ellipse-right-bottom:#FAA89E;
  --card-bg-ellipse-left-bottom:#FF8E3E;
  --card-bg-ellipse-top:#BF3F26;}
.generated-card-frame{
  --font-primary:var(--card-primary);
  --font-secondary:var(--card-secondary);
  --font-tertiary:var(--card-tertiary);
  --text-block-theme-color:var(--card-action-text);
  --card-progress-track:rgba(0,0,0,.10);
  --card-progress-bar:#64BB5C;
  --card-progress-icon:rgba(0,0,0,.60);
  --top-text-bottom-value-divider:rgba(0,0,0,.20);
  --checklist-bg:rgba(0,0,0,.05);
  --checklist-checkbox-bg:rgba(0,0,0,.10);
  --checklist-checkbox-border:rgba(0,0,0,.20);
  --checklist-check-color:var(--card-primary);
  font-family:"HarmonyOS Sans SC","HarmonyOS Sans",-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;}
.generated-card-frame[data-tone="dark"]{
  --text-block-theme-color:#FFFFFF;
  --card-progress-track:rgba(255,255,255,.10);
  --card-progress-bar:#FFFFFF;
  --card-progress-icon:rgba(255,255,255,.60);
  --top-text-bottom-value-divider:rgba(255,255,255,.20);
  --checklist-bg:rgba(255,255,255,.10);
  --checklist-checkbox-bg:rgba(255,255,255,.20);
  --checklist-checkbox-border:rgba(255,255,255,.40);
  --checklist-check-color:#FFFFFF;}
.generated-card-frame [data-surface="backplate"]{
  box-sizing:border-box;
  padding:6px;
  border-radius:16px;
  overflow:hidden;}
.generated-card-frame[data-tone="light"] [data-surface="backplate"]{
  background:rgba(255,255,255,.40);
  box-shadow:inset 0 0 0 1px rgba(0,0,0,.025);}
.generated-card-frame[data-tone="dark"] [data-surface="backplate"]{
  background:rgba(255,255,255,.10);}
.generated-card-frame .single-line-title,
.generated-card-frame .double-line-title-main,
.generated-card-frame .double-line-title-sub,
.generated-card-frame .ed,
.generated-card-frame .emphasis-text,
.generated-card-frame .secondary-body,
.generated-card-frame .summary-text,
.generated-card-frame .data-display,
.generated-card-frame .pc-external-value,
.generated-card-frame .pc-stat-text,
.generated-card-frame .numeric-ratio,
.generated-card-frame .ec-title,
.generated-card-frame .ec-time,
.generated-card-frame .ec-location,
.generated-card-frame .pill-btn{font-family:inherit;}
.generated-card-frame .title-demo-row{position:relative;width:100%;min-height:12px;height:auto;gap:4px;align-items:flex-start;}
.generated-card-frame .single-line-title-layout{
  box-sizing:border-box;width:100%;min-height:12px;height:auto;padding-right:0;}
.generated-card-frame .title-demo-row[data-has-icon="true"] .single-line-title-layout,
.generated-card-frame .title-demo-row[data-has-icon="true"] .double-line-title{padding-right:24px;}
.generated-card-frame .single-line-title{
  font-size:12px;font-weight:400;line-height:18px;color:var(--card-secondary);}
.generated-card-frame .ec-title{
  color:var(--card-primary);}
.generated-card-frame .ec-time,
.generated-card-frame .ec-location{
  color:var(--card-secondary);}
.generated-card-frame .double-line-title{
  box-sizing:border-box;width:100%;min-height:28px;height:auto;padding-right:0;gap:4px;}
.generated-card-frame .double-line-title-main{
  font-size:12px;font-weight:700;line-height:18px;color:var(--card-primary);}
.generated-card-frame .double-line-title-sub{
  font-size:12px;font-weight:500;line-height:18px;color:var(--card-secondary);}
.generated-card-frame .title-area-icon{
  position:absolute;top:0;right:0;width:20px;height:20px;border-radius:4px;object-fit:var(--title-icon-fit,contain);}
.generated-card-frame .ed-val{
  font-size:38px;font-weight:700;line-height:1;color:var(--card-primary);}
.generated-card-frame .pl2 .ed-val{line-height:1;}
.generated-card-frame .ed-unit{
  font-size:12px;font-weight:400;line-height:1.5;color:var(--card-secondary);}
.generated-card-frame .pl2 .ed-unit{line-height:1;}
.generated-card-frame .emphasis-text-main{
  font-size:20px;font-weight:700;line-height:27px;color:var(--card-primary);}
.generated-card-frame .emphasis-text-secondary{
  font-size:12px;font-weight:400;line-height:16px;color:var(--card-secondary);}
.generated-card-frame .secondary-body{
  font-size:14px;font-weight:400;line-height:19px;color:var(--card-primary);}
.generated-card-frame .summary-text{
  font-size:10px;font-weight:400;line-height:14px;color:var(--card-secondary);}
.generated-card-frame .summary-text[data-density="tight"]{line-height:12px;}
.generated-card-frame .pc-external-value{
  font-size:10px;font-weight:500;line-height:14px;color:var(--card-primary);}
.generated-card-frame .generated-card-mask{
  display:block;flex:0 0 auto;background-color:currentColor;
  -webkit-mask:var(--generated-card-icon-url) no-repeat center/contain;
  mask:var(--generated-card-icon-url) no-repeat center/contain;}
.generated-card-frame .pc-center-icon .generated-card-mask[data-size="sm"],
.generated-card-frame .pc-center-icon .generated-card-mask[data-size="md"],
.generated-card-frame .pc-center-icon .generated-card-mask[data-size="single"]{width:20px;height:20px;}
.generated-card-frame .numeric-ratio-icon .generated-card-mask{width:12px;height:12px;color:var(--card-secondary);}
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
  --btn-bg:var(--card-action-bg);
  --btn-bg-hover:var(--card-action-bg);
  --btn-bg-active:var(--card-action-bg);
  --btn-text:var(--card-action-text);
  background:var(--card-action-bg);}
.generated-card-frame .btn[data-appearance="card"]::before{display:none;}
.generated-card-frame .pill-btn[data-appearance="card"]{
  box-sizing:border-box;display:inline-flex;width:136px;min-width:136px;height:36px;padding:0;border-radius:30px;flex:none;}
.generated-card-frame [data-surface="backplate"] .pill-btn[data-appearance="card"]{
  width:120px;min-width:120px;max-width:120px;align-self:center;}
.generated-card-frame .circle-btn[data-appearance="card"]{
  --btn-bg:var(--card-circle-bg);
  --btn-bg-hover:var(--card-circle-bg);
  --btn-bg-active:var(--card-circle-bg);
  --btn-text:var(--card-circle-text);
  position:relative;display:inline-flex;width:36px;min-width:36px;height:36px;padding:0;border-radius:50%;
  background:var(--card-circle-bg);}
.generated-card-frame .btn-icon-mask{
  display:block;width:100%;height:100%;background:var(--card-action-icon);
  -webkit-mask:var(--button-icon-url) no-repeat center/contain;
  mask:var(--button-icon-url) no-repeat center/contain;}
.generated-card-frame .circle-btn[data-appearance="card"] .btn-icon-mask{
  background:var(--card-circle-icon);}

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
    styleElement.textContent = RUNTIME_STYLES;
    document.head.appendChild(styleElement);
  }

  ensureRuntimeStyles();

  const ASSET_ROOT = "resources/base/media/";

  const CARD_APPEARANCES = Object.freeze({
    "blue-soft": {
      background: "linear-gradient(180deg,rgba(10,89,247,.10) 0%,rgba(255,255,255,0) 100%),#fff",
      boxShadow: "0 2px 8px rgba(0,0,0,.10)",
      "--card-primary": "#000",
      "--card-secondary": "rgba(0,0,0,.6)",
      "--card-tertiary": "rgba(0,0,0,.4)",
      "--card-action-bg": "rgba(10,89,247,.10)",
      "--card-action-text": "#0A59F7",
      "--card-action-icon": "#0A59F7",
      "--card-circle-bg": "#0A59F7",
      "--card-circle-text": "#fff",
      "--card-circle-icon": "#fff",
    },
    "green-soft": {
      background: "linear-gradient(180deg,rgba(100,187,92,.10) 0%,rgba(255,255,255,0) 100%),#fff",
      boxShadow: "0 2px 8px rgba(0,0,0,.10)",
      "--card-primary": "#000",
      "--card-secondary": "rgba(0,0,0,.6)",
      "--card-tertiary": "rgba(0,0,0,.4)",
      "--card-action-bg": "rgba(100,187,92,.10)",
      "--card-action-text": "#64BB5C",
      "--card-action-icon": "#64BB5C",
      "--card-circle-bg": "#64BB5C",
      "--card-circle-text": "#fff",
      "--card-circle-icon": "#fff",
    },
    "neutral-soft": {
      background: "linear-gradient(180deg,rgba(0,0,0,.10) 0%,rgba(255,255,255,0) 100%),#fff",
      boxShadow: "0 2px 8px rgba(0,0,0,.10)",
      "--card-primary": "#000",
      "--card-secondary": "rgba(0,0,0,.6)",
      "--card-tertiary": "rgba(0,0,0,.4)",
      "--card-action-bg": "rgba(0,0,0,.10)",
      "--card-action-text": "#000",
      "--card-action-icon": "#000",
      "--card-circle-bg": "#000",
      "--card-circle-text": "#fff",
      "--card-circle-icon": "#fff",
    },
    "pink-soft": {
      background: "linear-gradient(180deg,rgba(230,69,102,.10) 0%,rgba(255,255,255,0) 100%),#fff",
      boxShadow: "0 2px 8px rgba(0,0,0,.10)",
      "--card-primary": "#000",
      "--card-secondary": "rgba(0,0,0,.6)",
      "--card-tertiary": "rgba(0,0,0,.4)",
      "--card-action-bg": "rgba(230,69,102,.10)",
      "--card-action-text": "#E64566",
      "--card-action-icon": "#E64566",
      "--card-circle-bg": "#E64566",
      "--card-circle-text": "#fff",
      "--card-circle-icon": "#fff",
    },
    "yellow-soft": {
      background: "linear-gradient(180deg,rgba(247,206,0,.10) 0%,rgba(255,255,255,0) 100%),#fff",
      boxShadow: "0 2px 8px rgba(0,0,0,.10)",
      "--card-primary": "#000",
      "--card-secondary": "rgba(0,0,0,.6)",
      "--card-tertiary": "rgba(0,0,0,.4)",
      "--card-action-bg": "rgba(247,206,0,.10)",
      "--card-action-text": "#F7CE00",
      "--card-action-icon": "#F7CE00",
      "--card-circle-bg": "#F7CE00",
      "--card-circle-text": "#fff",
      "--card-circle-icon": "#fff",
    },
    "cyan-soft": {
      background: "linear-gradient(180deg,rgba(70,177,227,.10) 0%,rgba(255,255,255,0) 100%),#fff",
      boxShadow: "0 2px 8px rgba(0,0,0,.10)",
      "--card-primary": "#000",
      "--card-secondary": "rgba(0,0,0,.6)",
      "--card-tertiary": "rgba(0,0,0,.4)",
      "--card-action-bg": "rgba(70,177,227,.10)",
      "--card-action-text": "#46B1E3",
      "--card-action-icon": "#46B1E3",
      "--card-circle-bg": "#46B1E3",
      "--card-circle-text": "#fff",
      "--card-circle-icon": "#fff",
    },
    "sunny-gradient": {
      background: "linear-gradient(180deg,#317AF7 0%,#46B1E3 100%)",
      boxShadow: "0 2px 8px rgba(0,0,0,.18)",
      "--card-primary": "#fff",
      "--card-secondary": "rgba(255,255,255,.6)",
      "--card-tertiary": "rgba(255,255,255,.4)",
      "--card-action-bg": "#fff",
      "--card-action-text": "#317AF7",
      "--card-action-icon": "#317AF7",
      "--card-circle-bg": "#fff",
      "--card-circle-text": "#317AF7",
      "--card-circle-icon": "#317AF7",
    },
    "cloudy-gradient": {
      background: "linear-gradient(180deg,rgb(43,50,66) 0%,rgb(116,134,160) 68%,rgb(90,108,132) 100%)",
      boxShadow: "0 2px 8px rgba(0,0,0,.18)",
      "--card-primary": "#fff",
      "--card-secondary": "rgba(255,255,255,.6)",
      "--card-tertiary": "rgba(255,255,255,.4)",
      "--card-action-bg": "#fff",
      "--card-action-text": "#2B3242",
      "--card-action-icon": "#2B3242",
      "--card-circle-bg": "#fff",
      "--card-circle-text": "#2B3242",
      "--card-circle-icon": "#2B3242",
    },
    "slate-gradient": {
      background: "linear-gradient(180deg,rgb(23,53,115) 0%,rgb(0,143,191) 68%,rgb(65,116,217) 100%)",
      boxShadow: "0 2px 8px rgba(0,0,0,.18)",
      "--card-primary": "#fff",
      "--card-secondary": "rgba(255,255,255,.6)",
      "--card-tertiary": "rgba(255,255,255,.4)",
      "--card-action-bg": "#fff",
      "--card-action-text": "#173573",
      "--card-action-icon": "#173573",
      "--card-circle-bg": "#fff",
      "--card-circle-text": "#173573",
      "--card-circle-icon": "#173573",
    },
    "purple-gradient": {
      background: "linear-gradient(180deg,#AC49F5 0%,#C386F0 100%)",
      boxShadow: "0 2px 8px rgba(0,0,0,.18)",
      "--card-primary": "#fff",
      "--card-secondary": "rgba(255,255,255,.6)",
      "--card-tertiary": "rgba(255,255,255,.4)",
      "--card-action-bg": "#fff",
      "--card-action-text": "#AC49F5",
      "--card-action-icon": "#AC49F5",
      "--card-circle-bg": "#fff",
      "--card-circle-text": "#AC49F5",
      "--card-circle-icon": "#AC49F5",
    },
    "orange-gradient": {
      background: "linear-gradient(180deg,#ED6F21 0%,#F9A01E 100%)",
      boxShadow: "0 2px 8px rgba(0,0,0,.18)",
      "--card-primary": "#fff",
      "--card-secondary": "rgba(255,255,255,.6)",
      "--card-tertiary": "rgba(255,255,255,.4)",
      "--card-action-bg": "#fff",
      "--card-action-text": "#ED6F21",
      "--card-action-icon": "#ED6F21",
      "--card-circle-bg": "#fff",
      "--card-circle-text": "#ED6F21",
      "--card-circle-icon": "#ED6F21",
    },
    "type0-gradient": {
      background: "#BF3F26",
      boxShadow: "0 2px 8px rgba(0,0,0,.18)",
      "--card-primary": "#fff",
      "--card-secondary": "rgba(255,255,255,.6)",
      "--card-tertiary": "rgba(255,255,255,.4)",
      "--card-action-bg": "#fff",
      "--card-action-text": "#BF3F26",
      "--card-action-icon": "#BF3F26",
      "--card-circle-bg": "#fff",
      "--card-circle-text": "#BF3F26",
      "--card-circle-icon": "#BF3F26",
    },
  });

  const MULTI_ELLIPSE_CARD_APPEARANCES = new Set([
    "cloudy-gradient",
    "slate-gradient",
    "type0-gradient",
  ]);

  const DARK_CARD_APPEARANCES = new Set([
    "sunny-gradient",
    "cloudy-gradient",
    "slate-gradient",
    "purple-gradient",
    "orange-gradient",
    "type0-gradient",
  ]);

  function cx(...values) {
    return values.filter(Boolean).join(" ");
  }

  function clamp(value, min = 0, max = 100) {
    const number = Number(value);
    if (!Number.isFinite(number)) return min;
    return Math.min(max, Math.max(min, number));
  }

  const FORMATTED_PERCENTAGE_PATTERN = /^\s*\d+(?:\.\d+)?\s*%\s*$/;

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
    if (!MULTI_ELLIPSE_CARD_APPEARANCES.has(appearance)) return null;
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
    const cardAppearance = CARD_APPEARANCES[appearance];
    let cardTone;
    if (cardAppearance) cardTone = DARK_CARD_APPEARANCES.has(appearance) ? "dark" : "light";
    return (
      <div
        className={cx("ds-frame", cardAppearance && "generated-card-frame", className)}
        data-appearance={appearance}
        data-card-size={semanticSize}
        data-tone={cardTone}
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
        {cardAppearance && !background && <CardBackground appearance={appearance} size={semanticSize} />}
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
          minHeight,
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
          minHeight,
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

  function TitleIcon({ icon, alt = "", fit = "contain", inverted = false }) {
    if (!icon) return null;
    return (
      <Icon
        src={icon}
        alt={alt}
        decorative={!alt}
        className="title-area-icon"
        style={{ "--title-icon-fit": fit, objectFit: fit, filter: inverted ? "brightness(0) invert(1)" : undefined }}
      />
    );
  }

  function SingleLineTitle({ title, icon, iconAlt, iconFit = "contain", invertIcon = false, dataIds, className, ...rest }) {
    return (
      <div className={cx("title-demo-row", className)} data-has-icon={icon ? "true" : "false"} {...rest}>
        <div className="single-line-title-layout"><p className="single-line-title">{title}</p></div>
        <TitleIcon icon={icon} alt={iconAlt} fit={iconFit} inverted={invertIcon} />
      </div>
    );
  }

  function DoubleLineTitle({ title, secondaryInfo, icon, iconAlt, iconFit = "contain", invertIcon = false, dataIds, className, ...rest }) {
    return (
      <div className={cx("title-demo-row", className)} data-has-icon={icon ? "true" : "false"} {...rest}>
        <div className="double-line-title">
          <p className="double-line-title-main">{title}</p>
          <p className="double-line-title-sub">{secondaryInfo}</p>
        </div>
        <TitleIcon icon={icon} alt={iconAlt} fit={iconFit} inverted={invertIcon} />
      </div>
    );
  }

  function Badge({ value, children, color = "blue", dataIds, className, ...rest }) {
    return <span className={cx("badge", className)} data-color={color} {...rest}>{children ?? value}</span>;
  }

  const emphasizedUnitPattern = /\s*([+-]?\d+(?:\.\d+)?)\s*(次\/分|公里\/小时|千米\/小时|毫秒|分钟|小时|千卡|公里|千米|GB可用|TB|GB|MB|KB|mA|mV|A|V|W|秒|分|天|步|米|克|升|元|次|个|%|％)/g;
  const emphasizedCelsiusPattern = /^\s*([+-]?\d+(?:\.\d+)?)\s*(?:℃|°\s*C)\s*$/i;

  function normalizeEmphasizedItem(item) {
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
    const normalized = (items || [{ value, unit }]).flatMap(normalizeEmphasizedItem);
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

  function renderTextItems(items, separator) {
    return items.map((item, index) => (
      <React.Fragment key={item.key ?? index}>
        {index > 0 && separator}
        {item.label != null && item.label !== "" && <span>{item.label}</span>}
        <span>{item.value}</span>
      </React.Fragment>
    ));
  }

  function SecondaryBody({ body, items, separator = " ｜ ", children, dataIds, className, ...rest }) {
    const segmented = Array.isArray(items);
    return (
      <p
        className={cx("secondary-body", className)}
        data-segmented={segmented ? "true" : undefined}
        {...rest}
      >
        {children ?? (segmented ? renderTextItems(items, separator) : body)}
      </p>
    );
  }

  function Summary({ content, items, separator = " ｜ ", children, density, wrap = false, dataIds, className, ...rest }) {
    const segmented = Array.isArray(items);
    return (
      <p
        className={cx("summary-text", className)}
        data-density={density}
        data-wrap={wrap ? "true" : undefined}
        data-segmented={segmented ? "true" : undefined}
        {...rest}
      >
        {children ?? (segmented ? renderTextItems(items, separator) : content)}
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
            <img src={assetUrl(visualIcon)} alt="" />
          </div>
        </div>
      );
    } else if (visualType === "icon") {
      visualNode = (
        <div className="info-block-visual" aria-hidden="true">
          <img
            className="info-block-icon"
            data-color={visual?.color === "native" ? "native" : undefined}
            src={assetUrl(visualIcon)}
            alt=""
          />
        </div>
      );
    }

    return (
      <div className={cx("info-block", className)} data-component="info-block" {...rest}>
        <div className="info-block-copy">
          <p className="info-block-primary">
            <span className="info-block-primary-value">{primaryText}</span>
            {unit != null && <span className="info-block-unit">{unit}</span>}
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
      <div className={cx("table-text", className)} {...rest}>
        {items.map(({ key, label, parameter, dataIds }, index) => (
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
          {lines.map((line, index) => <SecondaryBody key={index} body={line} />)}
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

  function ProgressCircleSingle({ value, icon, displayValue, label, secondaryLabel, ariaLabel, appearance, trackColor, barColor, dataIds, className, ...rest }) {
    const threeLines = secondaryLabel != null;
    const resolvedTrack = appearance === "card" ? "var(--card-progress-track)" : (trackColor || "rgba(0,0,0,.10)");
    const resolvedBar = appearance === "card" ? "var(--card-progress-bar)" : (barColor || "#64bb5c");
    const resolvedDisplayValue = displayValue ?? (isFormattedPercentage(value) ? value.trim() : formatPercentage(value));
    return (
      <div className={cx("pc-single-combo", className)} role="img" aria-label={ariaLabel || `${label} ${resolvedDisplayValue}`} {...rest}>
        <ProgressRing value={progressPercentage(value)} size={52} strokeWidth={6} trackColor={resolvedTrack} barColor={resolvedBar} icon={icon} iconSize="single" visibleOverflow={appearance !== "card"} precision={appearance === "card" ? 1 : 0} appearance={appearance} />
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
    const resolvedExternalText = externalText ?? formatPercentage(value);
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

  function EventCard({ title, time, location, dataIds, className, ...rest }) {
    return (
      <div className={cx("ec", className)} {...rest}>
        <div className="ec-rail" aria-hidden="true"><span className="ec-dot" /><span className="ec-line" /></div>
        <div className="ec-content">
          <span className="ec-title">{title}</span>
          <span className="ec-time">{time}</span>
          {location != null && <span className="ec-location">{location}</span>}
        </div>
      </div>
    );
  }

  function ButtonIcon({ icon, appearance }) {
    if (!icon) return null;
    if (appearance === "card") {
      return <span className="btn-icon-mask" style={{ "--button-icon-url": `url("${assetUrl(icon)}")` }} />;
    }
    return <Icon src={icon} />;
  }

  function PillButton({ label, icon, variant = "emphasis", color = "primary", appearance, disabled = false, actionId, className, ...rest }) {
    return (
      <button className={cx("btn", "pill-btn", className)} data-variant={variant} data-color={color} data-appearance={appearance} disabled={disabled} {...rest}>
        <span className="btn-inner">
          {icon && <span className="btn-icon" aria-hidden="true"><ButtonIcon icon={icon} appearance={appearance} /></span>}
          <span className="btn-label">{label}</span>
        </span>
      </button>
    );
  }

  function CircleButton({ icon, ariaLabel, variant = "emphasis", color = "primary", appearance, disabled = false, actionId, className, ...rest }) {
    return (
      <button className={cx("btn", "circle-btn", className)} data-variant={variant} data-color={color} data-appearance={appearance} disabled={disabled} aria-label={ariaLabel} {...rest}>
        <span className="btn-inner"><span className="btn-icon" aria-hidden="true"><ButtonIcon icon={icon} appearance={appearance} /></span></span>
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
          {icon && (
            <span
              className="card-action-btn__icon"
              style={{ "--card-button-icon-url": `url("${assetUrl(icon)}")` }}
              aria-hidden="true"
            />
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
    SingleLineTitle: { required: ["title"], optional: ["icon", "iconAlt", "iconFit", "invertIcon", "dataIds"] },
    DoubleLineTitle: { required: ["title", "secondaryInfo"], optional: ["icon", "iconAlt", "iconFit", "invertIcon", "dataIds"] },
    Badge: { required: ["value"], optional: ["dataIds"], color: ["blue", "orange", "green", "red", "purple", "cyan", "pink"] },
    EmphasizedData: { requiredOneOf: ["value", "items"], optional: ["unit", "dataIds"] },
    EmphasisText: { required: ["mainText", "secondaryText"], optional: ["dataIds"] },
    SecondaryBody: { requiredOneOf: ["body", "items"], optional: ["separator", "dataIds"] },
    Summary: { requiredOneOf: ["content", "items"], optional: ["separator", "dataIds"] },
    DataDisplay: { required: ["label", "value", "supportingText"], optional: ["dataIds"] },
    InfoBlock: { required: ["primaryText", "secondaryText", "visual"], optional: ["unit", "dataIds"] },
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
    ProgressCircleSingle: { required: ["value", "icon", "label"], optional: ["displayValue", "secondaryLabel", "ariaLabel", "appearance", "trackColor", "barColor", "dataIds"] },
    ProgressCircle: { required: ["icon", "externalText"], optional: ["value", "density", "ariaLabel", "appearance", "trackColor", "barColor", "dataIds"], size: ["sm", "md"] },
    NumericRatio: { required: ["icon", "value"], optional: ["unit", "appearance", "dataIds"] },
    NumericRatioStack: { required: ["items"], optional: ["appearance"] },
    ChecklistItem: { required: ["title", "meta"], optional: ["done", "dataIds"] },
    EventCard: { required: ["title", "time"], optional: ["location", "dataIds"] },
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
    Summary,
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
