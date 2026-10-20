export function serviceConfigLabel(key: string): string {
  return key.replace(/^WIDGET_SERVICE_/i, "").replace(/\./g, "_").toUpperCase();
}
