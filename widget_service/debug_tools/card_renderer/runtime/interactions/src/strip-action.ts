const ACTION_KEY = "action";

/**
 * Removes `action` from node props so it is not forwarded to React/DOM.
 */
export function stripActionFromProps(props: Record<string, unknown>): Record<string, unknown> {
  if (!Object.prototype.hasOwnProperty.call(props, ACTION_KEY)) {
    return props;
  }
  const { [ACTION_KEY]: _, ...rest } = props;
  return rest;
}

export function extractAction(props: Record<string, unknown>): unknown {
  return props[ACTION_KEY];
}
