import type { CSSProperties, KeyboardEvent, MouseEvent, ReactNode } from "react";

const REPEAT_BY_DATA_MODEL_TYPES = new Set<string>([
  "Extended.List",
  "Extended.Tabs",
  "Extended.Navigation",
  "List",
  "Tabs",
  "Navigation",
]);

/** Compose data-model path for `{ path: "field" }` bindings under a repeating template (`/listPath/idx/...`). */
function resolveBindingLeafPath(scopePrefix: string | null | undefined, path: string): string {
  if (path.startsWith("/")) return path;
  const s =
    scopePrefix != null && String(scopePrefix).length > 0 ? String(scopePrefix).trim() : "";
  if (s.length === 0) return path;
  const base = s.endsWith("/") ? s.slice(0, -1) : s;
  const rel = path.replace(/^\/+/, "");
  return base.startsWith("/") ? `${base}/${rel}` : `/${base}/${rel}`;
}

function scopeForIndexedPath(listPath: string, index: number): string {
  const b = listPath.trim();
  if (b.length === 0) return `/${index}`;
  const base = b.endsWith("/") ? b.slice(0, -1) : b;
  return base.startsWith("/") ? `${base}/${index}` : `/${base}/${index}`;
}
import type { UIGraph } from "@genui-sdk/graph";
import { GENUI_DEFAULT_FORM_ID, mergeCommonStyles } from "@genui-sdk/components";
import {
  extractAction,
  isPathOnlyBinding,
  resolvePathBindingsInValue,
  runActionDispatch,
  stripActionFromProps,
  type InteractionHost,
} from "@genui-sdk/interactions";
import type { ComponentRegistry } from "./registry.js";
import {
  GRID_WINDOW_BREAKPOINT_TOKEN,
  interpolateGridColumnsTemplate,
} from "./grid-columns-template.js";

const EXTENDED_IF = "Extended.If";
const EXTENDED_GRID = "Extended.Grid";
const EXTENDED_BUTTON = "Extended.Button";
const EXTENDED_TEXT = "Extended.Text";

const EXTENDED_TEXT_INPUT = "Extended.TextInput";
const EXTENDED_SELECT = "Extended.Select";
const EXTENDED_RADIO = "Extended.Radio";
const EXTENDED_CHECKBOX = "Extended.Checkbox";
const EXTENDED_CHECKBOX_GROUP = "Extended.CheckboxGroup";

const FORM_FIELD_NODE_TYPES = new Set<string>([
  EXTENDED_TEXT_INPUT,
  EXTENDED_SELECT,
  EXTENDED_RADIO,
  EXTENDED_CHECKBOX,
  EXTENDED_CHECKBOX_GROUP,
]);

const FALLBACK_SURFACE_ID = "default";

export type RenderTreeOptions = {
  /** When set, `action` on **Extended.Button** / **Extended.Text** may invoke `functionCall` (e.g. `openUrl`) or `event` (resolved `context` → {@link InteractionHost.submitForm}). */
  interactionHost?: InteractionHost | null;
  /**
   * Target A2UI surface for `{"path":"..."}` prop bindings (v0.9 `updateDataModel`).
   * Defaults to {@link UIGraph.getActiveSurfaceId} when omitted.
   */
  surfaceId?: string | null;
  /**
   * `id` of the host `<form>`; forwarded as the HTML `form` attribute on Extended form controls
   * so `readFormValuesByFormId` can collect them. Defaults to {@link GENUI_DEFAULT_FORM_ID}.
   * Set to `null` to omit the `form` attribute (e.g. controls already nested inside a form).
   */
  formId?: string | null;
  /**
   * Called after the user edits a path-bound **Extended.TextInput** so the host can re-render
   * (the graph mutates in place; React will not refresh without this).
   */
  onDataModelUserEdit?: () => void;
  /**
   * Breakpoint token for **Extended.Grid** `columnsTemplate` only: mustache blocks may use
   * `$__WindowBreakpoint` inside `{{ ... }}` (see {@link interpolateGridColumnsTemplate}).
   * Typical values: `xs`, `sm`, `md`. When set, overrides `/__WindowBreakpoint` in the data model.
   */
  windowBreakpoint?: string | null;
};

type BindingScopePrefix = string | null | undefined;

function mergeActionOnClick(
  restProps: Record<string, unknown>,
  action: unknown,
  host: InteractionHost,
  nodeId: string,
  graph: UIGraph,
  surfaceId: string | null | undefined,
  formId: string | null | undefined,
  bindingScopePrefix: BindingScopePrefix,
): Record<string, unknown> {
  const getDataModelLeaf = (path: string): unknown => {
    if (!surfaceId) return "";
    const resolvedPath = resolveBindingLeafPath(bindingScopePrefix, path);
    const got = graph.getDataModelValue(surfaceId, resolvedPath);
    if (got === undefined || got === null) return "";
    return got;
  };

  const formIdResolved = formId === undefined ? GENUI_DEFAULT_FORM_ID : formId;
  const sKey = effectiveSurfaceKey(surfaceId);
  const wireSurfaceId = sKey;
  const getSelectedGroupValue = (groupID: string): string => {
    if (typeof document === "undefined") return "";
    if (formIdResolved == null || String(formIdResolved).length === 0) return "";
    const form = document.getElementById(String(formIdResolved));
    if (!form || form.tagName !== "FORM") return "";
    const htmlName = `${sKey}__g__${groupID}`;
    const inputs = (form as HTMLFormElement).querySelectorAll<HTMLInputElement>("input[type=radio]");
    for (let i = 0; i < inputs.length; i++) {
      const inp = inputs[i];
      if (inp.name === htmlName && inp.checked) return inp.value;
    }
    return "";
  };

  const actionClick = (e: MouseEvent<HTMLElement>) => {
    e.stopPropagation();
    if (restProps.enabled === false) return;
    void runActionDispatch(action, host, {
      componentId: nodeId,
      surfaceId: wireSurfaceId,
      eventData: { x: e.clientX, y: e.clientY },
      getDataModelLeaf,
      getSelectedGroupValue,
    });
  };

  const existing = restProps.onClick;
  if (typeof existing === "function") {
    const prev = existing as (ev: MouseEvent<HTMLElement>) => void;
    return {
      ...restProps,
      onClick: (e: MouseEvent<HTMLElement>) => {
        void actionClick(e);
        prev(e);
      },
    };
  }
  return { ...restProps, onClick: actionClick };
}

/**
 * Spreads `styles` into the top-level props so Extended components receive a
 * uniform flat structure regardless of whether the node came from the a2ui
 * protocol (which nests style fields inside `styles: {...}`) or the mini
 * protocol (which already places them at the top level).
 */
function flattenStyles(props: Record<string, unknown>): Record<string, unknown> {
  const { styles, ...rest } = props;
  if (styles && typeof styles === "object" && !Array.isArray(styles)) {
    return { ...rest, ...(styles as Record<string, unknown>) };
  }
  return props;
}

function resolveDataBindingsInValue(
  graph: UIGraph,
  surfaceId: string | null | undefined,
  value: unknown,
  bindingScopePrefix: BindingScopePrefix,
): unknown {
  const getLeaf = (path: string): unknown => {
    if (!surfaceId) return "";
    const resolvedPath = resolveBindingLeafPath(bindingScopePrefix, path);
    const got = graph.getDataModelValue(surfaceId, resolvedPath);
    if (got === undefined || got === null) return "";
    return got;
  };
  return resolvePathBindingsInValue(value, getLeaf);
}

function resolveDataBindingsInProps(
  graph: UIGraph,
  surfaceId: string | null | undefined,
  props: Record<string, unknown>,
  bindingScopePrefix: BindingScopePrefix,
): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(props)) {
    out[k] = resolveDataBindingsInValue(graph, surfaceId, v, bindingScopePrefix);
  }
  return out;
}

function effectiveSurfaceKey(surfaceId: string | null | undefined): string {
  return surfaceId != null && String(surfaceId).length > 0 ? String(surfaceId) : FALLBACK_SURFACE_ID;
}

function resolveWindowBreakpoint(
  graph: UIGraph,
  surfaceId: string | null | undefined,
  options: RenderTreeOptions | null | undefined,
): string {
  const fromHost = options?.windowBreakpoint;
  if (typeof fromHost === "string" && fromHost.trim().length > 0) {
    return fromHost.trim();
  }
  if (surfaceId) {
    const fromModel = graph.getDataModelValue(surfaceId, "/__WindowBreakpoint");
    if (typeof fromModel === "string" && fromModel.trim().length > 0) {
      return fromModel.trim();
    }
  }
  return "sm";
}

/**
 * Injects HTML `name` (and optional `form`) for Extended form controls so
 * `FormData` / `readFormValuesByFormId` can read values. Field names:
 * - `surfaceId__nodeId` for single controls (text, select, checkbox group “全选”).
 * - `surfaceId__g__${group}` for radio groups and checkboxes that share `group`.
 *
 * Skips when the node already provides a non-empty `name` string.
 */
function injectGenuiFormAssociation(
  nodeType: string,
  surfaceId: string | null | undefined,
  nodeId: string,
  flatProps: Record<string, unknown>,
  formId: string | null | undefined,
): Record<string, unknown> {
  if (!FORM_FIELD_NODE_TYPES.has(nodeType)) {
    return flatProps;
  }

  const hasExplicitName = typeof flatProps.name === "string" && flatProps.name.length > 0;
  const s = effectiveSurfaceKey(surfaceId);
  let computedName: string;
  if (nodeType === EXTENDED_RADIO) {
    const g =
      typeof flatProps.group === "string" && flatProps.group.length > 0 ? flatProps.group : "radio";
    computedName = `${s}__g__${g}`;
  } else if (nodeType === EXTENDED_CHECKBOX) {
    const g = typeof flatProps.group === "string" && flatProps.group.length > 0 ? flatProps.group : "cb";
    computedName = `${s}__g__${g}`;
  } else {
    computedName = `${s}__${nodeId}`;
  }

  const next: Record<string, unknown> = {
    ...flatProps,
    name: hasExplicitName ? flatProps.name : computedName,
  };
  if (formId != null && formId.length > 0) {
    next.form = formId;
  }
  return next;
}

/**
 * Recursively renders a single node (by ID) from the graph.
 *
 * If a node references children that have not yet arrived in the stream,
 * a lightweight loading placeholder is shown in their place, giving the UI
 * an incremental build-up effect during streaming.
 */
function renderNodeById(
  graph: UIGraph,
  nodeId: string,
  registry: ComponentRegistry,
  options: RenderTreeOptions | null | undefined,
  bindingScopePrefix?: BindingScopePrefix,
): ReactNode {
  const surfaceId = options?.surfaceId ?? graph.getActiveSurfaceId();

  const node = graph.getNode(nodeId);

  const instanceKey =
    bindingScopePrefix != null && String(bindingScopePrefix).length > 0
      ? `${bindingScopePrefix}::${nodeId}`
      : nodeId;

  // Node declared as a child but command hasn't arrived yet — show placeholder
  if (!node) {
    return (
      <span
        key={nodeId}
        data-node-id={nodeId}
        style={{
          display: "inline-block",
          padding: "4px 8px",
          borderRadius: 6,
          fontSize: 12,
          color: "#94a3b8",
          background: "rgba(148, 163, 184, 0.15)",
          border: "1px dashed rgba(148, 163, 184, 0.4)",
        }}
      >
        …
      </span>
    );
  }

  if (node.type === EXTENDED_IF) {
    const raw = node.props as Record<string, unknown>;
    const cleaned = stripActionFromProps(raw);
    const flat = resolveDataBindingsInProps(graph, surfaceId, flattenStyles(cleaned), bindingScopePrefix);
    const cond = Boolean(flat.condition);
    const ifIds = Array.isArray(flat.childrenIf)
      ? (flat.childrenIf as unknown[]).filter((x): x is string => typeof x === "string")
      : [];
    const elseIds = Array.isArray(flat.childrenElse)
      ? (flat.childrenElse as unknown[]).filter((x): x is string => typeof x === "string")
      : [];
    const branchIds = cond ? ifIds : elseIds;
    const wrapStyle: CSSProperties = {
      minWidth: 0,
      ...mergeCommonStyles(flat),
    };
    return (
      <div key={instanceKey} data-node-id={nodeId} style={wrapStyle}>
        {branchIds.map((cid) => renderNodeById(graph, cid, registry, options, bindingScopePrefix))}
      </div>
    );
  }

  const Cmp = registry[node.type];
  if (!Cmp) {
    return (
      <div
        key={instanceKey}
        data-node-id={nodeId}
        style={{
          padding: 12,
          borderRadius: 8,
          border: "1px dashed #f97316",
          color: "#9a3412",
          fontSize: 13,
        }}
      >
        Unknown component type: <code>{node.type}</code>
      </div>
    );
  }

  const tpl = node.dynamicChildrenTemplate;
  const expandAsTemplate =
    tpl !== undefined &&
    REPEAT_BY_DATA_MODEL_TYPES.has(node.type) &&
    typeof tpl.path === "string" &&
    tpl.path.length > 0 &&
    typeof tpl.componentId === "string" &&
    tpl.componentId.length > 0;

  let childElements: ReactNode | undefined;
  if (expandAsTemplate && surfaceId) {
    const raw = graph.getDataModelValue(surfaceId, tpl!.path);
    const items = Array.isArray(raw) ? raw : [];
    childElements =
      items.length > 0
        ? items.map((_, idx) =>
            renderNodeById(
              graph,
              tpl!.componentId,
              registry,
              options,
              scopeForIndexedPath(tpl!.path, idx),
            ),
          )
        : undefined;
  } else if (node.children.length > 0) {
    childElements = node.children.map((childId: string) =>
      renderNodeById(graph, childId, registry, options, bindingScopePrefix),
    );
  } else {
    childElements = undefined;
  }

  const rawProps = node.props as Record<string, unknown>;
  const action = extractAction(rawProps);
  const restProps = stripActionFromProps(rawProps);
  const host = options?.interactionHost ?? null;

  // Flatten a2ui `styles: {...}` into top-level props so Extended components
  // receive the same flat structure as mini-protocol nodes.
  const flatProps = resolveDataBindingsInProps(graph, surfaceId, flattenStyles(restProps), bindingScopePrefix);
  // The generated fusion glass uses a native blur parameter, not CSS Gaussian sigma.
  // 210 CSS pixels averages away all three colors on a 150px card. Adapt only
  // this generated layer; retain the original value in the exported A2UI graph.
  if (nodeId === "fusionBallGlassLayer" && graph.getNode("fusionBallBackground") &&
      (flatProps.backdropBlur as { radius?: number } | undefined)?.radius === 210) {
    flatProps.backdropBlur = { radius: 24 };
  }

  let forwardedProps: Record<string, unknown> = flatProps;
  const supportsActionClick = true;
  const formIdForAssociation =
    options?.formId === undefined ? GENUI_DEFAULT_FORM_ID : options.formId;

  if (supportsActionClick && action != null && host != null) {
    forwardedProps = mergeActionOnClick(
      flatProps,
      action,
      host,
      nodeId,
      graph,
      surfaceId,
      formIdForAssociation,
      bindingScopePrefix,
    );
    if (![EXTENDED_BUTTON, "Button", "Extended.Checkbox", "Checkbox"].includes(node.type)) {
      forwardedProps.role = "button";
      forwardedProps.tabIndex = flatProps.enabled === false ? -1 : 0;
      forwardedProps["aria-disabled"] = flatProps.enabled === false || undefined;
      forwardedProps.onKeyDown = (event: KeyboardEvent<HTMLElement>) => {
        if (event.target === event.currentTarget && (event.key === "Enter" || event.key === " ")) {
          event.preventDefault();
          event.currentTarget.click();
        }
      };
    }
  }
  const accessibility = flatProps.accessibility;
  if (accessibility && typeof accessibility === "object") {
    const a = accessibility as Record<string, unknown>;
    if (typeof a.label === "string") forwardedProps["aria-label"] = a.label;
    if (typeof a.description === "string") forwardedProps["aria-description"] = a.description;
    if (a.decorative === true) forwardedProps["aria-hidden"] = true;
  }
  forwardedProps = injectGenuiFormAssociation(
    node.type,
    surfaceId,
    nodeId,
    forwardedProps,
    formIdForAssociation,
  );

  if (node.type === EXTENDED_TEXT_INPUT && surfaceId) {
    const pre = flattenStyles(restProps);
    const textLeaf = pre.text;
    if (isPathOnlyBinding(textLeaf)) {
      const modelPath = textLeaf.path;
      forwardedProps = {
        ...forwardedProps,
        onDataModelTextChange: (v: string) => {
          graph.setDataModelValue(surfaceId, resolveBindingLeafPath(bindingScopePrefix, modelPath), v);
          options?.onDataModelUserEdit?.();
        },
      };
    }
  }

  if (node.type === EXTENDED_GRID || node.type === "Grid") {
    const ct = forwardedProps.columnsTemplate;
    if (
      typeof ct === "string" &&
      ct.includes("{{") &&
      ct.includes(GRID_WINDOW_BREAKPOINT_TOKEN)
    ) {
      const bp = resolveWindowBreakpoint(graph, surfaceId, options);
      forwardedProps = {
        ...forwardedProps,
        columnsTemplate: interpolateGridColumnsTemplate(ct, bp),
      };
    }
  }

  return (
    <Cmp key={instanceKey} data-node-id={nodeId} {...forwardedProps}>
      {childElements}
    </Cmp>
  );
}

/**
 * Renders the entire UI tree rooted at `graph.getRoot()`.
 *
 * @param graph    - A UIGraph instance (may be partially populated during streaming).
 * @param registry - Component registry mapping type names to React components.
 * @param options  - Optional {@link RenderTreeOptions.interactionHost} for **`action.functionCall`** / **`action.event`** (e.g. Extended.Button, Extended.Text).
 * @returns A React element tree, or null if the graph has no root yet.
 */
export function renderTree(
  graph: UIGraph,
  registry: ComponentRegistry,
  options?: RenderTreeOptions | null,
): ReactNode {
  const root = graph.getRoot();
  if (!root) return null;
  return renderNodeById(graph, root.id, registry, options);
}

export type { InteractionHost } from "@genui-sdk/interactions";
