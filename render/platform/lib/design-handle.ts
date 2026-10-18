/**
 * Port of design_handle.ets — Harmony design preset merge for compact DSL.
 */

type StylePropsMap = Record<string, unknown>;

interface PaddingStyle {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

interface CheckboxMarkStyle {
  strokeColor: string;
  size: number;
  strokeWidth: number;
}

interface ConstraintSizeStyle {
  minWidth?: number;
  maxWidth?: number;
}

interface FontStyle {
  size: number;
  weight: number;
}

interface UnderlineColorStyle {
  normal: string;
  typing: string;
  error: string;
  disable: string;
}

function padding(left: number, top: number, right: number, bottom: number): PaddingStyle {

  const p: PaddingStyle = { left, top, right, bottom };

  return p;

}



function checkboxMark(strokeColor: string, size: number, strokeWidth: number): CheckboxMarkStyle {

  const m: CheckboxMarkStyle = { strokeColor, size, strokeWidth };

  return m;

}



function constraintSizeMin(minWidth: number): ConstraintSizeStyle {

  const c: ConstraintSizeStyle = { minWidth };

  return c;

}



function constraintSizeMax(maxWidth: number): ConstraintSizeStyle {

  const c: ConstraintSizeStyle = { maxWidth };

  return c;

}



function fontStyle(size: number, weight: number): FontStyle {

  const f: FontStyle = { size, weight };

  return f;

}



function underlineColor(normal: string, typing: string, error: string, disable: string): UnderlineColorStyle {

  const u: UnderlineColorStyle = { normal, typing, error, disable };

  return u;

}



function createEmptyStyleMap(): StylePropsMap {

  const empty: StylePropsMap = {};

  return empty;

}



function createRadioDefault(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['width'] = 20;

  s['height'] = 20;

  s['borderRadius'] = 10;

  s['checkedBackgroundColor'] = '#FF0A59F7';

  s['uncheckedBorderColor'] = '#66000000';

  s['indicatorColor'] = '#FFFFFFFF';

  return s;

}



function createCheckboxDefault(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['height'] = 20;

  s['borderRadius'] = 10;

  s['selectedColor'] = '#FF0A59F7';

  s['unSelectedColor'] = '#66000000';

  s['mark'] = checkboxMark('#FFFFFFFF', 20, 2);

  s['shape'] = 'circle';

  return s;

}



function createCheckboxGroupDefault(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['height'] = 48;

  s['borderRadius'] = 8;

  s['padding'] = padding(0, 12, 0, 12);

  s['fontSize'] = 14;

  s['fontColor'] = '#E5000000';

  s['fontWeight'] = 400;

  s['selectedColor'] = '#FF0A59F7';

  s['unSelectedColor'] = '#66000000';

  s['mark'] = checkboxMark('#FFFFFFFF', 24, 2);

  s['checkboxShape'] = 'circle';

  return s;

}



function createToggleDefault(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['width'] = 36;

  s['height'] = 20;

  s['borderRadius'] = 18;

  s['selectedColor'] = '#FF0A59F7';

  s['unSelectedColor'] = '#19000000';

  s['switchPointColor'] = '#FFFFFFFF';

  return s;

}



function createTabDefault(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['height'] = 36;

  s['borderRadius'] = 18;

  s['padding'] = padding(16, 8, 16, 8);

  s['selectColor'] = '#FFFFFFFF';

  s['unselectedColor'] = '#99000000';

  s['defaultBackgroundColor'] = '#0C000000';

  s['selectBackgroundColor'] = '#FF0A59F7';

  s['fontSize'] = 16;

  s['fontWeight'] = 500;

  s['iconSize'] = 16;

  s['space'] = 6;

  return s;

}



function createSelectDefault(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['height'] = 40;

  s['constraintSize'] = constraintSizeMin(68);

  s['borderRadius'] = 20;

  s['padding'] = padding(16, 8, 8, 8);

  s['backgroundColor'] = '#0C000000';

  s['font'] = fontStyle(16, 500);

  s['fontColor'] = '#E5000000';

  s['space'] = 2;

  s['arrowPosition'] = 'end';

  return s;

}



function createSelectSmall(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['height'] = 28;

  s['constraintSize'] = constraintSizeMin(56);

  s['borderRadius'] = 14;

  s['padding'] = padding(8, 4, 12, 4);

  s['backgroundColor'] = '#0C000000';

  s['font'] = fontStyle(14, 500);

  s['fontColor'] = '#E5000000';

  s['space'] = 2;

  s['arrowPosition'] = 'end';

  return s;

}



function createInputBox(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['height'] = 40;

  s['borderRadius'] = 20;

  s['padding'] = padding(16, 8, 16, 8);

  s['backgroundColor'] = '#0C000000';

  s['placeholderColor'] = '#99000000';

  s['caretColor'] = '#FF0A59F7';

  s['showUnderline'] = false;

  s['fontSize'] = 16;

  s['fontWeight'] = 400;

  s['fontColor'] = '#E5000000';

  s['textAlign'] = 'start';

  return s;

}



function createInputLine(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['height'] = 48;

  s['borderRadius'] = 0;

  s['placeholderColor'] = '#99000000';

  s['caretColor'] = '#FF0A59F7';

  s['showUnderline'] = true;

  s['underlineColor'] = underlineColor('#33000000', '#7F000000', '#FFE84026', '#33000000');

  s['fontSize'] = 16;

  s['fontWeight'] = 400;

  s['fontColor'] = '#E5000000';

  s['textAlign'] = 'start';

  return s;

}



function createProgressLinear(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['type'] = 'linear';

  s['height'] = 4;

  s['borderRadius'] = 2;

  s['backgroundColor'] = '#19000000';

  s['color'] = '#FF0A59F7';

  return s;

}



function createProgressEclipse(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['type'] = 'eclipse';

  s['width'] = 20;

  s['height'] = 20;

  s['color'] = '#19000000';

  return s;

}



function createTextTitle(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['fontSize'] = 16;

  s['fontWeight'] = 'medium';

  s['fontColor'] = '#E5000000';

  return s;

}



function createTextTitleBrand(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['fontSize'] = 16;

  s['fontWeight'] = 'medium';

  s['fontColor'] = '#FF0A59F7';

  return s;

}



function createTextTitleWarning(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['fontSize'] = 16;

  s['fontWeight'] = 'medium';

  s['fontColor'] = '#FFE84026';

  return s;

}



function createTextBody(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['fontSize'] = 14;

  s['fontWeight'] = 'regular';

  s['fontColor'] = '#E5000000';

  return s;

}



function createTextSubtitle(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['fontSize'] = 14;

  s['fontWeight'] = 'regular';

  s['fontColor'] = '#99000000';

  return s;

}



function createTextCaption(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['fontSize'] = 12;

  s['fontWeight'] = 'regular';

  s['fontColor'] = '#E5000000';

  return s;

}



function createTextLink(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['fontSize'] = 14;

  s['fontWeight'] = 'medium';

  s['fontColor'] = '#FF0A59F7';

  return s;

}



function createTextSuccess(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['fontSize'] = 14;

  s['fontWeight'] = 'regular';

  s['fontColor'] = '#FF64BB5C';

  return s;

}



function createTextWarning(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['fontSize'] = 14;

  s['fontWeight'] = 'regular';

  s['fontColor'] = '#FFE84026';

  return s;

}



function createTextAlert(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['fontSize'] = 14;

  s['fontWeight'] = 'regular';

  s['fontColor'] = '#FFED6F21';

  return s;

}



function createTextOutlinePrimary(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['height'] = 16;

  s['constraintSize'] = constraintSizeMax(68);

  s['borderRadius'] = 4;

  s['borderWidth'] = 1;

  s['borderColor'] = '#FFE84026';

  s['padding'] = padding(4, 2, 4, 2);

  s['flexShrink'] = 0;

  s['fontSize'] = 10;

  s['fontWeight'] = 'medium';

  s['fontColor'] = '#FFE84026';

  s['maxLines'] = 1;

  s['textOverflow'] = 'ellipsis';

  return s;

}



function createTextOutlineNeutral(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['height'] = 16;

  s['constraintSize'] = constraintSizeMax(68);

  s['borderRadius'] = 4;

  s['borderWidth'] = 1;

  s['borderColor'] = '#66000000';

  s['padding'] = padding(4, 2, 4, 2);

  s['flexShrink'] = 0;

  s['fontSize'] = 10;

  s['fontWeight'] = 'medium';

  s['fontColor'] = '#E5000000';

  s['maxLines'] = 1;

  s['textOverflow'] = 'ellipsis';

  return s;

}



function createDividerLine(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['strokeWidth'] = 1;

  s['vertical'] = false;

  s['color'] = '#33000000';

  return s;

}



function createDividerBar(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['strokeWidth'] = 8;

  s['vertical'] = false;

  s['color'] = '#0C000000';

  return s;

}



function createBtnDefault(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['height'] = 40;

  s['borderRadius'] = 20;

  s['padding'] = padding(16, 8, 16, 8);

  s['backgroundColor'] = '#0C000000';

  s['fontColor'] = '#FF0A59F7';

  s['fontSize'] = 16;

  s['fontWeight'] = 500;

  return s;

}



function createBtnPrimary(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['height'] = 40;

  s['borderRadius'] = 20;

  s['padding'] = padding(16, 8, 16, 8);

  s['backgroundColor'] = '#FF0A59F7';

  s['fontColor'] = '#FFFFFFFF';

  s['fontSize'] = 16;

  s['fontWeight'] = 500;

  return s;

}



function createBtnDanger(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['height'] = 40;

  s['borderRadius'] = 20;

  s['padding'] = padding(16, 8, 16, 8);

  s['backgroundColor'] = '#0C000000';

  s['fontColor'] = '#FFE84026';

  s['fontSize'] = 16;

  s['fontWeight'] = 500;

  return s;

}



function createBtnSmall(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['height'] = 28;

  s['borderRadius'] = 14;

  s['padding'] = padding(8, 4, 8, 4);

  s['backgroundColor'] = '#0C000000';

  s['fontColor'] = '#FF0A59F7';

  s['fontSize'] = 14;

  s['fontWeight'] = 500;

  return s;

}



function createBtnText(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['height'] = 40;

  s['borderRadius'] = 20;

  s['padding'] = padding(16, 8, 16, 8);

  s['fontColor'] = '#FF0A59F7';

  s['fontSize'] = 16;

  s['fontWeight'] = 500;

  return s;

}



function createBtnIcon(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['width'] = 48;

  s['height'] = 48;

  s['borderRadius'] = 24;

  s['padding'] = padding(12, 12, 12, 12);

  s['backgroundColor'] = '#0C000000';

  s['flexShrink'] = 0;

  return s;

}



function createBtnIconSm(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['width'] = 40;

  s['height'] = 40;

  s['borderRadius'] = 20;

  s['padding'] = padding(8, 8, 8, 8);

  s['backgroundColor'] = '#0C000000';

  s['flexShrink'] = 0;

  return s;

}



function createImageAppIcon(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['width'] = 20;

  s['height'] = 20;

  s['borderRadius'] = 4;

  s['clip'] = true;

  s['flexShrink'] = 0;

  s['aspectRatio'] = 1.0;

  s['objectFit'] = 'cover';

  return s;

}



function createImageSystemIcon(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['width'] = 20;

  s['height'] = 20;

  s['flexShrink'] = 0;

  s['aspectRatio'] = 1.0;

  s['objectFit'] = 'contain';

  return s;

}



function createImageIcon(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['width'] = 48;

  s['height'] = 48;

  s['padding'] = padding(12, 12, 12, 12);

  s['borderRadius'] = 24;

  s['clip'] = true;

  s['flexShrink'] = 0;

  s['aspectRatio'] = 1.0;

  s['objectFit'] = 'contain';

  s['backgroundColor'] = '#0C000000';

  return s;

}



function createImageThumbnail(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['width'] = 56;

  s['height'] = 56;

  s['borderRadius'] = 12;

  s['clip'] = true;

  s['flexShrink'] = 0;

  s['aspectRatio'] = 1.0;

  s['objectFit'] = 'cover';

  return s;

}



function createImageThumbnailSm(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['width'] = 48;

  s['height'] = 48;

  s['borderRadius'] = 12;

  s['clip'] = true;

  s['flexShrink'] = 0;

  s['aspectRatio'] = 1.0;

  s['objectFit'] = 'cover';

  return s;

}



function createImageThumbnailPortrait(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['width'] = 56;

  s['height'] = 56;

  s['borderRadius'] = 12;

  s['clip'] = true;

  s['flexShrink'] = 0;

  s['objectFit'] = 'cover';

  return s;

}



function createImageGrid(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['width'] = 'matchParent';

  s['height'] = 'matchParent';

  s['borderRadius'] = 12;

  s['clip'] = true;

  s['objectFit'] = 'cover';

  return s;

}



function createImageHero(): StylePropsMap {

  const s: StylePropsMap = createEmptyStyleMap();

  s['width'] = 'matchParent';

  s['height'] = 'matchParent';

  s['borderRadius'] = 16;

  s['clip'] = true;

  s['objectFit'] = 'cover';

  return s;

}



function resolveCanonicalComponentType(componentType: string): string | null {

  const lower = componentType.toLowerCase();

  if (lower === 'radio') {

    return 'Radio';

  }

  if (lower === 'checkbox') {

    return 'Checkbox';

  }

  if (lower === 'checkboxgroup') {

    return 'CheckboxGroup';

  }

  if (lower === 'toggle') {

    return 'Toggle';

  }

  if (lower === 'tabcontent') {

    return 'TabContent';

  }

  if (lower === 'select') {

    return 'Select';

  }

  if (lower === 'textinput') {

    return 'TextInput';

  }

  if (lower === 'progress') {

    return 'Progress';

  }

  if (lower === 'text') {

    return 'Text';

  }

  if (lower === 'divider') {

    return 'Divider';

  }

  if (lower === 'button') {

    return 'Button';

  }

  if (lower === 'image') {

    return 'Image';

  }

  return null;

}



function isMultiStyleComponent(canonicalType: string): boolean {

  return canonicalType === 'Select' || canonicalType === 'TextInput' || canonicalType === 'Progress' ||

    canonicalType === 'Text' || canonicalType === 'Divider' || canonicalType === 'Button' ||

    canonicalType === 'Image';

}



function getDefaultDesignName(canonicalType: string): string {

  if (canonicalType === 'Radio' || canonicalType === 'Checkbox' || canonicalType === 'CheckboxGroup' ||

    canonicalType === 'Toggle' || canonicalType === 'TabContent') {

    return 'default';

  }

  if (canonicalType === 'Select' || canonicalType === 'Button') {

    return 'default';

  }

  if (canonicalType === 'TextInput') {

    return 'box';

  }

  if (canonicalType === 'Progress') {

    return 'linear';

  }

  if (canonicalType === 'Text') {

    return 'title';

  }

  if (canonicalType === 'Divider') {

    return 'line';

  }

  if (canonicalType === 'Image') {

    return 'app-icon';

  }

  return '';

}



function getPresetByDesign(canonicalType: string, designName: string): StylePropsMap {

  if (canonicalType === 'Radio') {

    return createRadioDefault();

  }

  if (canonicalType === 'Checkbox') {

    return createCheckboxDefault();

  }

  if (canonicalType === 'CheckboxGroup') {

    return createCheckboxGroupDefault();

  }

  if (canonicalType === 'Toggle') {

    return createToggleDefault();

  }

  if (canonicalType === 'TabContent') {

    return createTabDefault();

  }

  if (canonicalType === 'Select') {

    if (designName === 'small') {

      return createSelectSmall();

    }

    return createSelectDefault();

  }

  if (canonicalType === 'TextInput') {

    if (designName === 'line') {

      return createInputLine();

    }

    return createInputBox();

  }

  if (canonicalType === 'Progress') {

    if (designName === 'eclipse') {

      return createProgressEclipse();

    }

    return createProgressLinear();

  }

  if (canonicalType === 'Text') {

    if (designName === 'title-brand') {

      return createTextTitleBrand();

    }

    if (designName === 'title-warning') {

      return createTextTitleWarning();

    }

    if (designName === 'body') {

      return createTextBody();

    }

    if (designName === 'subtitle') {

      return createTextSubtitle();

    }

    if (designName === 'caption') {

      return createTextCaption();

    }

    if (designName === 'link') {

      return createTextLink();

    }

    if (designName === 'success') {

      return createTextSuccess();

    }

    if (designName === 'warning') {

      return createTextWarning();

    }

    if (designName === 'alert') {

      return createTextAlert();

    }

    if (designName === 'outline-primary') {

      return createTextOutlinePrimary();

    }

    if (designName === 'outline-neutral') {

      return createTextOutlineNeutral();

    }

    return createTextTitle();

  }

  if (canonicalType === 'Divider') {

    if (designName === 'bar') {

      return createDividerBar();

    }

    return createDividerLine();

  }

  if (canonicalType === 'Button') {

    if (designName === 'primary') {

      return createBtnPrimary();

    }

    if (designName === 'danger') {

      return createBtnDanger();

    }

    if (designName === 'small') {

      return createBtnSmall();

    }

    if (designName === 'text') {

      return createBtnText();

    }

    if (designName === 'icon') {

      return createBtnIcon();

    }

    if (designName === 'icon-sm') {

      return createBtnIconSm();

    }

    return createBtnDefault();

  }

  if (canonicalType === 'Image') {

    if (designName === 'system-icon') {

      return createImageSystemIcon();

    }

    if (designName === 'icon') {

      return createImageIcon();

    }

    if (designName === 'thumbnail') {

      return createImageThumbnail();

    }

    if (designName === 'thumbnail-sm') {

      return createImageThumbnailSm();

    }

    if (designName === 'thumbnail-portrait') {

      return createImageThumbnailPortrait();

    }

    if (designName === 'grid') {

      return createImageGrid();

    }

    if (designName === 'hero') {

      return createImageHero();

    }

    return createImageAppIcon();

  }

  return createEmptyStyleMap();

}



function isKnownDesign(canonicalType: string, designName: string): boolean {

  if (canonicalType === 'Select') {

    return designName === 'default' || designName === 'small';

  }

  if (canonicalType === 'TextInput') {

    return designName === 'box' || designName === 'line';

  }

  if (canonicalType === 'Progress') {

    return designName === 'linear' || designName === 'eclipse';

  }

  if (canonicalType === 'Text') {

    return designName === 'title' || designName === 'title-brand' || designName === 'title-warning' ||

      designName === 'body' || designName === 'subtitle' || designName === 'caption' ||

      designName === 'link' || designName === 'success' || designName === 'warning' ||

      designName === 'alert' || designName === 'outline-primary' || designName === 'outline-neutral';

  }

  if (canonicalType === 'Divider') {

    return designName === 'line' || designName === 'bar';

  }

  if (canonicalType === 'Button') {

    return designName === 'default' || designName === 'primary' || designName === 'danger' ||

      designName === 'small' || designName === 'text' || designName === 'icon' || designName === 'icon-sm';

  }

  if (canonicalType === 'Image') {

    return designName === 'app-icon' || designName === 'system-icon' || designName === 'icon' ||

      designName === 'thumbnail' || designName === 'thumbnail-sm' || designName === 'thumbnail-portrait' ||

      designName === 'grid' || designName === 'hero';

  }

  return false;

}



function resolveDesignName(canonicalType: string, styleProps: StylePropsMap): string {

  const defaultDesign = getDefaultDesignName(canonicalType);

  if (!isMultiStyleComponent(canonicalType)) {

    return defaultDesign;

  }



  const designRaw = styleProps['design'];

  if (designRaw === undefined || designRaw === null) {

    return defaultDesign;

  }



  const designName = String(designRaw);

  if (isKnownDesign(canonicalType, designName)) {

    return designName;

  }



  return defaultDesign;

}



function mergePresetIntoStyles(existing: StylePropsMap, preset: StylePropsMap): StylePropsMap {

  const merged: StylePropsMap = createEmptyStyleMap();

  const presetKeys: string[] = Object.keys(preset);

  for (let j = 0; j < presetKeys.length; j++) {

    const presetKey = presetKeys[j];

    merged[presetKey] = preset[presetKey];

  }



  const existingKeys: string[] = Object.keys(existing);

  for (let i = 0; i < existingKeys.length; i++) {

    const key = existingKeys[i];

    if (key !== 'design') {

      merged[key] = existing[key];

    }

  }



  return merged;

}



const LAYOUT_COMPONENT_TYPES: string[] =
  ['Row', 'Column', 'List', 'Stack', 'Grid', 'Navigation', 'Tabs'];

function isLayoutComponent(componentType: string): boolean {
  const lower = componentType.toLowerCase();

  for (let i = 0; i < LAYOUT_COMPONENT_TYPES.length; i++) {
    if (LAYOUT_COMPONENT_TYPES[i].toLowerCase() === lower) {
      return true;
    }
  }

  return false;
}

function createLayoutDefaultStyles(): StylePropsMap {
  const s: StylePropsMap = createEmptyStyleMap();
  s['borderRadius'] = 12;
  return s;
}

function mergeDefaultsUnderUser(defaults: StylePropsMap, existing: StylePropsMap): StylePropsMap {
  const merged: StylePropsMap = createEmptyStyleMap();
  const defaultKeys: string[] = Object.keys(defaults);

  for (let i = 0; i < defaultKeys.length; i++) {
    merged[defaultKeys[i]] = defaults[defaultKeys[i]];
  }

  const existingKeys: string[] = Object.keys(existing);

  for (let j = 0; j < existingKeys.length; j++) {
    const key = existingKeys[j];

    if (key !== 'design') {
      merged[key] = existing[key];
    }
  }

  return merged;
}



function stripDesign(styleProps: StylePropsMap): StylePropsMap {

  const result: StylePropsMap = createEmptyStyleMap();

  const keys: string[] = Object.keys(styleProps);

  for (let i = 0; i < keys.length; i++) {

    const key = keys[i];

    if (key !== 'design') {

      result[key] = styleProps[key];

    }

  }

  return result;

}



/**

 * 根据组件类型与可选 design，将预设样式合并进 styles。

 * preset 打底，existing 同名字段（含 fontColor）覆盖 preset；未知 design 回退到该组件的默认 preset。

 */

export function applyDesignStyles(

  componentType: string,

  styleProps: StylePropsMap

): StylePropsMap {

  const canonicalType = resolveCanonicalComponentType(componentType);

  if (canonicalType === null) {

    const stripped = stripDesign(styleProps);

    if (isLayoutComponent(componentType)) {
      return mergeDefaultsUnderUser(createLayoutDefaultStyles(), stripped);
    }

    return stripped;

  }



  const designName = resolveDesignName(canonicalType, styleProps);

  const preset = getPresetByDesign(canonicalType, designName);

  return mergePresetIntoStyles(styleProps, preset);

}
