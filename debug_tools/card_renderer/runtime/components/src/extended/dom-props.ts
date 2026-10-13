import type { HTMLAttributes } from "react";

/** Forward only DOM metadata and handlers, never raw protocol fields. */
export function domProps(props: Record<string, unknown>): HTMLAttributes<HTMLElement> {
  const result: Record<string, unknown> = {};
  for (const key of ["onClick", "onKeyDown", "role", "tabIndex", "aria-label", "aria-description", "aria-disabled", "aria-hidden", "data-node-id"]) {
    if (props[key] !== undefined) result[key] = props[key];
  }
  return result;
}
