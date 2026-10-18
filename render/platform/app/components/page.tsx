import type { Metadata } from "next";
import { ComponentGallery } from "@/src/ComponentGallery";

export const metadata: Metadata = {
  title: "Fusion 组件总览",
  description: "由 Fusion renderer 实时渲染的 Compact DSL 组件总览。",
};

export default function ComponentsPage() {
  return <ComponentGallery />;
}
