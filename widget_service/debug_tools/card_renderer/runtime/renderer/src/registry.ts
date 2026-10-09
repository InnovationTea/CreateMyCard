import type { ComponentType, ReactNode } from "react";
import {
  Card,
  Checkbox,
  ExtendedButton,
  ExtendedCheckbox,
  ExtendedCheckboxGroup,
  ExtendedColumn,
  ExtendedDivider,
  ExtendedGrid,
  ExtendedGridRow,
  ExtendedImage,
  ExtendedList,
  ExtendedNavigation,
  ExtendedProgress,
  ExtendedRadio,
  ExtendedRow,
  ExtendedSelectField,
  ExtendedStack,
  ExtendedTabContent,
  ExtendedTabs,
  ExtendedText,
  ExtendedTextInput,
  ExtendedToggle,
  ExtendedWeb,
  Input,
  Radio,
  Select,
} from "@genui-sdk/components";

/**
 * Props passed to every registered component.
 * Contains all node props forwarded from the graph, plus resolved React children.
 */
export type RegistryComponentProps = Record<string, unknown> & {
  children?: ReactNode;
};

/** Maps graph node `type` strings to React components. */
export type ComponentRegistry = Record<
  string,
  ComponentType<RegistryComponentProps>
>;

export const defaultRegistry: ComponentRegistry = {
  // mini-protocol component names → Extended components (flat-prop style)
  Card: Card as ComponentType<RegistryComponentProps>,
  Row: ExtendedRow as ComponentType<RegistryComponentProps>,
  Column: ExtendedColumn as ComponentType<RegistryComponentProps>,
  Text: ExtendedText as ComponentType<RegistryComponentProps>,
  Button: ExtendedButton as ComponentType<RegistryComponentProps>,
  Image: ExtendedImage as ComponentType<RegistryComponentProps>,
  // Form controls keep their mini-specific renderers for now
  Radio: ExtendedRadio as unknown as ComponentType<RegistryComponentProps>,
  Checkbox: ExtendedCheckbox as unknown as ComponentType<RegistryComponentProps>,
  Input: ExtendedTextInput as unknown as ComponentType<RegistryComponentProps>,
  TextInput: ExtendedTextInput as ComponentType<RegistryComponentProps>,
  Grid: ExtendedGrid as ComponentType<RegistryComponentProps>,
  GridRow: ExtendedGridRow as ComponentType<RegistryComponentProps>,
  List: ExtendedList as ComponentType<RegistryComponentProps>,
  Stack: ExtendedStack as ComponentType<RegistryComponentProps>,
  Tabs: ExtendedTabs as ComponentType<RegistryComponentProps>,
  TabContent: ExtendedTabContent as ComponentType<RegistryComponentProps>,
  Select: ExtendedSelectField as ComponentType<RegistryComponentProps>,
  Toggle: ExtendedToggle as ComponentType<RegistryComponentProps>,
  Progress: ExtendedProgress as ComponentType<RegistryComponentProps>,
  Divider: ExtendedDivider as ComponentType<RegistryComponentProps>,
  Web: ExtendedWeb as ComponentType<RegistryComponentProps>,
  Navigation: ExtendedNavigation as ComponentType<RegistryComponentProps>,
  CheckboxGroup: ExtendedCheckboxGroup as ComponentType<RegistryComponentProps>,



  "Extended.Text": ExtendedText as ComponentType<RegistryComponentProps>,
  "Extended.Button": ExtendedButton as ComponentType<RegistryComponentProps>,
  "Extended.Card": Card as ComponentType<RegistryComponentProps>,
  "Extended.TextInput": ExtendedTextInput as ComponentType<RegistryComponentProps>,
  "Extended.Row": ExtendedRow as ComponentType<RegistryComponentProps>,
  "Extended.Column": ExtendedColumn as ComponentType<RegistryComponentProps>,
  "Extended.List": ExtendedList as ComponentType<RegistryComponentProps>,
  "Extended.Stack": ExtendedStack as ComponentType<RegistryComponentProps>,
  "Extended.Grid": ExtendedGrid as ComponentType<RegistryComponentProps>,
  "Extended.GridRow": ExtendedGridRow as ComponentType<RegistryComponentProps>,
  "Extended.Image": ExtendedImage as ComponentType<RegistryComponentProps>,
  "Extended.Divider": ExtendedDivider as ComponentType<RegistryComponentProps>,
  "Extended.Toggle": ExtendedToggle as ComponentType<RegistryComponentProps>,
  "Extended.Progress": ExtendedProgress as ComponentType<RegistryComponentProps>,
  "Extended.Radio": ExtendedRadio as ComponentType<RegistryComponentProps>,
  "Extended.Checkbox": ExtendedCheckbox as ComponentType<RegistryComponentProps>,
  "Extended.CheckBox": ExtendedCheckbox as ComponentType<RegistryComponentProps>,
  "Extended.CheckboxGroup": ExtendedCheckboxGroup as ComponentType<RegistryComponentProps>,
  "Extended.Tabs": ExtendedTabs as ComponentType<RegistryComponentProps>,
  "Extended.TabContent": ExtendedTabContent as ComponentType<RegistryComponentProps>,
  "Extended.Select": ExtendedSelectField as ComponentType<RegistryComponentProps>,
  "Extended.Web": ExtendedWeb as ComponentType<RegistryComponentProps>,
  "Extended.Navigation": ExtendedNavigation as ComponentType<RegistryComponentProps>,
};
