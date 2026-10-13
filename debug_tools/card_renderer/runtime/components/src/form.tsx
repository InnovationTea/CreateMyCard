"use client";

import type { CSSProperties, FormEventHandler, ReactNode } from "react";

export interface FormProps {
  /** Must match the `form` prop on Input, Select, Radio, Checkbox, and Button. */
  id: string;
  children?: ReactNode;
  style?: CSSProperties;
  /** Runs after the default `preventDefault` on submit. */
  onSubmit?: FormEventHandler<HTMLFormElement>;
}

/**
 * Form root with `display: contents` so flex layouts (Row/Column/Card) are unchanged.
 * Default submit handler calls `preventDefault` to avoid full-page navigation.
 */
export function Form({ id, children, style, onSubmit }: FormProps) {
  return (
    <form
      id={id}
      style={{ display: "contents", margin: 0, ...style }}
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit?.(e);
      }}
    >
      {children}
    </form>
  );
}
