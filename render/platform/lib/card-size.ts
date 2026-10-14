export type PreviewCardSize = "2x2" | "2x4";

export interface PreviewDimensions {
  width: number;
  height: number;
}

export const PREVIEW_CARD_SIZE_PRESETS: Readonly<Record<PreviewCardSize, PreviewDimensions>> = {
  "2x2": { width: 150, height: 150 },
  "2x4": { width: 300, height: 150 },
};

export function previewDimensionsFor(size: PreviewCardSize): PreviewDimensions {
  return PREVIEW_CARD_SIZE_PRESETS[size];
}
