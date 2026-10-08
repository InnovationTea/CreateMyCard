import type { CSSProperties } from "react";

export interface CheckboxProps {
  /** Label text shown beside the box. */
  label: string;
  name: string;
  /** Initial checked state (uncontrolled). */
  checked?: boolean;
  /** Id of the target &lt;form&gt; when the checkbox is not nested inside it. */
  form?: string;
}

const labelStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 8,
  fontSize: 14,
  color: "#334155",
  cursor: "pointer",
};

export function Checkbox({ label, name, checked, form }: CheckboxProps) {
  return (
    <label style={labelStyle}>
      <input
        type="checkbox"
        name={name}
        form={form}
        defaultChecked={checked}
        style={{ accentColor: "#4f46e5", cursor: "pointer" }}
      />
      {label}
    </label>
  );
}
