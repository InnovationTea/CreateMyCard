(function registerJsxBindingPreview(global) {
  "use strict";
  const displayUnitsKey = Symbol("displayUnits");
  const unitSlotProps = {
    EmphasizedData: 'value', ProgressLine2: 'value', ProgressLine2WithData: 'value',
    NumericRatio: 'value', NumericRatioStack: 'value', InfoBlock: 'primaryText',
  };

  function normalizeUnitSlot(target, dataIds, values, componentName) {
    const prop = unitSlotProps[componentName];
    const id = dataIds && dataIds[prop];
    if (!prop || typeof id !== 'string' || !Object.prototype.hasOwnProperty.call(values, id)) return;
    const value = values[id];
    target[prop] = value;
    if (Object.prototype.hasOwnProperty.call(dataIds, 'unit')) return;
    const numeric = (typeof value === 'number' && Number.isFinite(value))
      || (typeof value === 'string' && /^[+-]?\d+(?:\.\d+)?$/.test(value.trim()));
    if (numeric && target.unit == null) {
      const declared = values[displayUnitsKey] && values[displayUnitsKey][id];
      if (declared) target.unit = declared;
      else if (['NumericRatio', 'NumericRatioStack'].includes(componentName) && typeof value === 'number') {
        target.unit = '%';
      }
    } else if (typeof value === 'string' && !numeric) {
      delete target.unit;
    }
  }

  function displayBindingValue(values, id) {
    const value = values[id];
    const unit = values[displayUnitsKey] && values[displayUnitsKey][id];
    const numeric = (typeof value === "number" && Number.isFinite(value))
      || (typeof value === "string" && /^[+-]?\d+(?:\.\d+)?$/.test(value.trim()));
    return unit && numeric ? `${String(value).trim()}${unit}` : value;
  }

  const emphasizedUnitPattern = new RegExp(
    String.raw`\s*([+-]?\d+(?:\.\d+)?)\s*`
      + String.raw`(次[/／]分钟|次[/／]分|bpm|公里/小时|千米/小时|毫秒|分钟|小时|千卡|公里|千米|`
      + String.raw`GB可用|TB|GB|MB|KB|mA|mV|A|V|W|秒|分|天|步|米|克|升|元|次|个|级|%|％)`,
    "gi",
  );
  const emphasizedCelsiusPattern = /^\s*([+-]?\d+(?:\.\d+)?)\s*(?:℃|°\s*C|摄氏度)\s*$/i;

  function isFormattedEmphasizedValue(value) {
    if (typeof value !== "string") return false;
    if (emphasizedCelsiusPattern.test(value)) return true;
    emphasizedUnitPattern.lastIndex = 0;
    let position = 0;
    let count = 0;
    let match;
    while ((match = emphasizedUnitPattern.exec(value)) != null) {
      if (match.index !== position) return false;
      count += 1;
      position = emphasizedUnitPattern.lastIndex;
    }
    return count > 0 && value.slice(position).trim() === "";
  }

  function bindingValues(context) {
    const values = Object.create(null);
    const units = Object.create(null);
    const entries = context && Array.isArray(context.data) ? context.data : [];
    for (const entry of entries) {
      if (!entry || typeof entry.id !== "string" || !entry.id) continue;
      values[entry.id] = entry.value;
      if (typeof entry.displayUnit === "string") units[entry.id] = entry.displayUnit;
    }
    Object.defineProperty(values, displayUnitsKey, { value: units });
    return values;
  }

  function resolveDataIds(target, dataIds, dataValueMaps, values, unresolved, componentName = null) {
    if (!dataIds || typeof dataIds !== "object" || Array.isArray(dataIds)) return target;
    for (const [prop, id] of Object.entries(dataIds)) {
      const timeRange = componentName === "EventCard" && prop === "time";
      const multiField = (componentName === "EmphasisText" && ["mainText", "secondaryText"].includes(prop))
        || (componentName === "InfoBlock" && prop === "secondaryText")
        || (componentName === "TableText" && prop === "parameter");
      const validArray = Array.isArray(id) && id.every((item) => typeof item === "string" && item);
      if (validArray && ((timeRange && id.length === 2) || (multiField && id.length >= 2))) {
        const missing = id.filter((item) => !Object.prototype.hasOwnProperty.call(values, item));
        missing.forEach((item) => unresolved.add(item));
        if (!missing.length) target[prop] = id.map((item) => String(displayBindingValue(values, item)))
          .join(timeRange ? " – " : " ｜ ");
        continue;
      }
      if (typeof id !== "string" || !id) continue;
      if (Object.prototype.hasOwnProperty.call(values, id)) {
        const numericProp = prop === "currentValue" || prop === "totalValue"
          || (["ProgressCircleSingle", "Gauge"].includes(componentName) && prop === "value");
        const separateUnit = prop === "value" && Object.prototype.hasOwnProperty.call(dataIds, "unit");
        const unitSlot = unitSlotProps[componentName] === prop;
        const value = numericProp || separateUnit || unitSlot ? values[id] : displayBindingValue(values, id);
        const valueMap = dataValueMaps && typeof dataValueMaps === "object" && !Array.isArray(dataValueMaps)
          ? dataValueMaps[prop]
          : null;
        if (
          typeof value === "boolean"
          && valueMap
          && typeof valueMap === "object"
          && !Array.isArray(valueMap)
          && typeof valueMap.true === "string"
          && typeof valueMap.false === "string"
        ) {
          target[prop] = valueMap[String(value)];
        } else {
          target[prop] = value;
        }
      } else {
        unresolved.add(id);
      }
    }
    normalizeUnitSlot(target, dataIds, values, componentName);
    return target;
  }

  function canonicalizeEmphasizedData(props, resolved, values) {
    const dataIds = props && props.dataIds;
    const valueId = dataIds && typeof dataIds === "object" && !Array.isArray(dataIds)
      ? dataIds.value
      : null;
    if (
      typeof valueId === "string"
      && Object.prototype.hasOwnProperty.call(values, valueId)
      && isFormattedEmphasizedValue(values[valueId])
      && !Object.prototype.hasOwnProperty.call(dataIds, "unit")
    ) {
      delete resolved.unit;
    }

    if (Array.isArray(props && props.items) && Array.isArray(resolved.items)) {
      for (let index = 0; index < props.items.length; index += 1) {
        const sourceItem = props.items[index];
        const resolvedItem = resolved.items[index];
        if (!sourceItem || typeof sourceItem !== "object" || Array.isArray(sourceItem)) continue;
        const itemIds = sourceItem.dataIds;
        const itemValueId = itemIds && typeof itemIds === "object" && !Array.isArray(itemIds)
          ? itemIds.value
          : null;
        if (
          resolvedItem
          && typeof itemValueId === "string"
          && Object.prototype.hasOwnProperty.call(values, itemValueId)
          && isFormattedEmphasizedValue(values[itemValueId])
          && !Object.prototype.hasOwnProperty.call(itemIds, "unit")
        ) {
          delete resolvedItem.unit;
        }
      }

      const boundFormatted = props.items.flatMap((item) => {
        if (!item || typeof item !== "object" || Array.isArray(item)) return [];
        const itemIds = item.dataIds;
        const id = itemIds && typeof itemIds === "object" && !Array.isArray(itemIds)
          ? itemIds.value
          : null;
        return typeof id === "string"
          && Object.prototype.hasOwnProperty.call(values, id)
          && isFormattedEmphasizedValue(values[id])
          ? [id]
          : [];
      });
      if (
        boundFormatted.length === 1
        && !props.items.some(item => item?.dataIds && Object.prototype.hasOwnProperty.call(item.dataIds, 'unit'))
        && props.items.every((item) => {
          if (!item || typeof item !== "object" || Array.isArray(item)) return true;
          const itemIds = item.dataIds;
          return !itemIds
            || typeof itemIds !== "object"
            || Array.isArray(itemIds)
            || itemIds.value === boundFormatted[0];
        })
      ) {
        delete resolved.items;
        delete resolved.unit;
        resolved.value = values[boundFormatted[0]];
        resolved.dataIds = { value: boundFormatted[0] };
      }
    }
    return resolved;
  }

  function resolveProps(props, values, unresolved, componentName = null) {
    const resolved = { ...props };
    resolveDataIds(
      resolved,
      props && props.dataIds,
      props && props.dataValueMaps,
      values,
      unresolved,
      componentName,
    );
    delete resolved.dataValueMaps;
    if (props && Array.isArray(props.items)) {
      resolved.items = props.items.map((item) => {
        if (!item || typeof item !== "object" || Array.isArray(item)) return item;
        const resolvedItem = resolveDataIds(
          { ...item },
          item.dataIds,
          item.dataValueMaps,
          values,
          unresolved,
          componentName === 'InfoBlock' ? null : componentName,
        );
        delete resolvedItem.dataValueMaps;
        return resolvedItem;
      });
    }
    return componentName === "EmphasizedData"
      ? canonicalizeEmphasizedData(props, resolved, values)
      : resolved;
  }

  function createBoundDesignSystem(React, designSystem) {
    const BindingContext = React.createContext(Object.freeze({ values: Object.create(null), unresolved: new Set() }));
    const components = {};

    for (const [name, Component] of Object.entries(designSystem || {})) {
      if (typeof Component !== "function") {
        components[name] = Component;
        continue;
      }
      const BoundComponent = React.forwardRef((props, ref) => {
        const state = React.useContext(BindingContext);
        const resolved = resolveProps(props || {}, state.values, state.unresolved, name);
        if (ref != null) resolved.ref = ref;
        return React.createElement(Component, resolved);
      });
      BoundComponent.displayName = `Bound${name}`;
      BoundComponent.__clawStackMinHeight = Component.__clawStackMinHeight;
      components[name] = BoundComponent;
    }

    function Provider({ context, unresolved, children }) {
      const state = React.useMemo(() => ({
        values: bindingValues(context),
        unresolved: unresolved || new Set(),
      }), [context, unresolved]);
      return React.createElement(BindingContext.Provider, { value: state }, children);
    }

    return Object.freeze({ components: Object.freeze(components), Provider });
  }

  global.JsxBindingPreview = Object.freeze({
    bindingValues,
    isFormattedEmphasizedValue,
    resolveProps,
    createBoundDesignSystem,
  });
})(typeof window !== "undefined" ? window : globalThis);
