"use client";

import { useState } from "react";
import type { CSSProperties } from "react";

export interface RadioProps {
  /** Group label (legend). */
  label: string;
  /** Shared `name` for native radio group semantics. */
  name: string;
  /** Option labels; each becomes a radio value. */
  options: string[];
  /** Id of the target &lt;form&gt; when the group is not nested inside it. */
  form?: string;
}

const fieldsetStyle: CSSProperties = {
  border: "none",
  margin: 0,
  padding: 0,
  display: "flex",
  flexDirection: "column",
  gap: 8,
  minWidth: 0,
};

const legendStyle: CSSProperties = {
  padding: 0,
  marginBottom: 4,
  fontSize: 14,
  fontWeight: 600,
  color: "#0f172a",
};

const rowStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
  fontSize: 14,
  color: "#334155",
  cursor: "pointer",
};

export function Radio({ label, name, options, form }: RadioProps) {
  const [selected, setSelected] = useState(options[0] ?? "");

  return (
    <fieldset style={fieldsetStyle} form={form}>
      <legend style={legendStyle}>{label}</legend>
      {options.map((opt, i) => (
        <label key={`${opt}-${i}`} style={rowStyle}>
          <input
            type="radio"
            name={name}
            form={form}
            value={opt}
            checked={selected === opt}
            onChange={() => setSelected(opt)}
            style={{ accentColor: "#4f46e5", cursor: "pointer" }}
          />
          {opt}
        </label>
      ))}
    </fieldset>
  );
}
