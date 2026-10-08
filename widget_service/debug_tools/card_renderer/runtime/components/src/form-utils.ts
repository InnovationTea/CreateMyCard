/** Default `id` for the platform preview &lt;form&gt; (pairs with `form` on controls). */
export const GENUI_DEFAULT_FORM_ID = "genui-form-main";

/**
 * Reads fields from a form by its `id` (pairs with `form="..."` on controls).
 * Returns null if the element is missing or not a &lt;form&gt;.
 */
export function readFormValuesByFormId(formId: string): Record<string, string> | null {
  if (typeof document === "undefined") return null;
  const el = document.getElementById(formId);
  if (!el || el.tagName !== "FORM") return null;
  const fd = new FormData(el as HTMLFormElement);
  const values: Record<string, string> = {};
  fd.forEach((v, k) => {
    values[k] = typeof v === "string" ? v : (v as File).name;
  });
  return values;
}
