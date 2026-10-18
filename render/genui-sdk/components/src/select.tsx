import type { CSSProperties } from "react";

export interface SelectProps {
  label: string;
  name: string;
  options: string[];
  placeholder?: string;
  /** Id of the target &lt;form&gt; when the select is not nested inside it. */
  form?: string;
}

const selectStyle: CSSProperties = {
  padding: "8px 10px",
  borderRadius: 8,
  border: "1px solid rgba(15, 23, 42, 0.2)",
  fontSize: 14,
  color: "#0f172a",
  background: "#fff",
  minWidth: 0,
  maxWidth: "100%",
  boxSizing: "border-box",
};

export function Select({ label, name, options, placeholder, form }: SelectProps) {
  return (
    <label
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 6,
        fontSize: 14,
        width: "100%",
        maxWidth: 400,
      }}
    >
      <span style={{ fontWeight: 600, color: "#0f172a" }}>{label}</span>
      <select
        name={name}
        form={form}
        defaultValue={placeholder !== undefined ? "" : options[0] ?? ""}
        style={selectStyle}
      >
        {placeholder !== undefined ? (
          <option value="" disabled>
            {placeholder}
          </option>
        ) : null}
        {options.map((o, i) => (
          <option key={`${o}-${i}`} value={o}>
            {o}
          </option>
        ))}
      </select>
    </label>
  );
}
