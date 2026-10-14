import type { CSSProperties } from "react";

export interface InputProps {
  label: string;
  name: string;
  type?: "text" | "email" | "password" | "number";
  placeholder?: string;
  /** Id of a &lt;form&gt; (e.g. from {@link Form}) when fields are not nested inside it. */
  form?: string;
}

const inputStyle: CSSProperties = {
  padding: "8px 10px",
  borderRadius: 8,
  border: "1px solid rgba(15, 23, 42, 0.2)",
  fontSize: 14,
  color: "#0f172a",
  background: "#fff",
  width: "100%",
  maxWidth: 400,
  boxSizing: "border-box",
};

export function Input({ label, name, type = "text", placeholder, form }: InputProps) {
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
      <input
        name={name}
        type={type}
        placeholder={placeholder}
        form={form}
        style={inputStyle}
      />
    </label>
  );
}
