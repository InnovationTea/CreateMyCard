/**
 * Adapt the cloud Compact converter's `onClick: [{ call, args }]` extension to
 * the action shape consumed by the Web interaction host.
 */
export function adaptCloudEventProps(
  props: Record<string, unknown>,
): Record<string, unknown> {
  const onClick = props.onClick;
  if (!Array.isArray(onClick) || !onClick.every(isCloudEventHandler)) {
    return props;
  }
  const adapted = { ...props };
  if (adapted.action === undefined) {
    adapted.action = onClick.map((handler) => ({ functionCall: handler }));
  }
  delete adapted.onClick;
  return adapted;
}

function isCloudEventHandler(value: unknown): value is Record<string, unknown> & { call: string } {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  return typeof (value as Record<string, unknown>).call === "string";
}
