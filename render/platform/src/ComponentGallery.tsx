"use client";

import { Component, useMemo, useState, type ReactNode } from "react";
import { defaultRegistry, renderTree } from "@genui-sdk/renderer";
import { compileMiniDsl } from "@/lib/mini-renderer";
import {
  COMPONENT_GALLERY,
  GALLERY_GROUPS,
  type GalleryCardSize,
  type GalleryComponent,
} from "./component-gallery-data";
import styles from "./ComponentGallery.module.css";

type SizeFilter = "all" | GalleryCardSize;
type Theme = "light" | "dark";

class SpecimenBoundary extends Component<
  { children: ReactNode },
  { message: string }
> {
  state = { message: "" };

  static getDerivedStateFromError(error: Error) {
    return { message: error.message };
  }

  render() {
    if (this.state.message) {
      return (
        <p className={styles.renderError} role="alert">
          渲染失败：{this.state.message}
        </p>
      );
    }
    return this.props.children;
  }
}

function ComponentPreview({ component }: { component: GalleryComponent }) {
  const result = useMemo(() => {
    try {
      return {
        compiled: compileMiniDsl(component.source, { size: component.size }),
        error: "",
      };
    } catch (error) {
      return {
        compiled: null,
        error: error instanceof Error ? error.message : String(error),
      };
    }
  }, [component]);

  if (result.error || !result.compiled) {
    return (
      <p className={styles.renderError} role="alert">
        DSL 编译失败：{result.error}
      </p>
    );
  }

  return (
    <div className={styles.previewGroup}>
      <div
        className={styles.cardViewport}
        style={{ width: component.width, height: component.height }}
        data-renderer-engine="fusion-renderer"
        data-gallery-component={component.name}
      >
        <SpecimenBoundary>
          {renderTree(result.compiled.graph, defaultRegistry, {
            formId: null,
            onDataModelUserEdit: () => undefined,
            interactionHost: {
              functionCall: () => undefined,
              submitForm: () => undefined,
            },
          })}
        </SpecimenBoundary>
      </div>
      <span className={styles.previewMeta}>
        {component.width} × {component.height} · {result.compiled.expandedCount} 个运行时节点
      </span>
    </div>
  );
}

function propType(prop: string): string {
  if (prop === "颜色组") return "visual tokens";
  if (prop.includes("items[")) return "array · required";
  if (prop === "onClick") return "Action[] · required";
  if (prop.endsWith("?")) return "optional";
  return "required / constrained";
}

function ComponentSection({
  component,
  index,
}: {
  component: GalleryComponent;
  index: string;
}) {
  return (
    <section className={styles.section} id={component.id}>
      <div className={styles.sectionHead}>
        <div className={styles.sectionTitle}>{index} {component.name}</div>
        <div className={styles.sectionDescription}>{component.summary}</div>
      </div>

      <div className={styles.componentCard}>
        <div className={styles.propsTable}>
          <div className={styles.propsHeader}>Props</div>
          {component.props.map(prop => (
            <div className={styles.propsRow} key={prop}>
              <div className={styles.propName}>
                <code>{prop}</code>
                <span>{propType(prop)}</span>
              </div>
              <div className={styles.propValues}>
                <span className={styles.propChip}>Compact DSL</span>
                <span className={styles.propChip}>由组件合同与 Runtime 校验</span>
              </div>
            </div>
          ))}
        </div>

        <div className={styles.subsection}>
          <div className={styles.subsectionLabel}>使用规则</div>
          <div className={styles.ruleList}>
            <div className={styles.ruleItem}>
              <span>使用场景</span>
              <p>{component.usage}</p>
            </div>
            <div className={styles.ruleItem}>
              <span>适用尺寸</span>
              <div className={styles.badges}>
                {component.sizes.map(size => (
                  <span key={size} className={styles.sizeBadge}>{size}</span>
                ))}
              </div>
            </div>
            <div className={styles.ruleItem}>
              <span>样式来源</span>
              <p>基础组件由 Renderer 直接渲染；高阶组件读取共享的 visual-recipes-v1。</p>
            </div>
          </div>
        </div>

        <div className={styles.subsection}>
          <div className={styles.subsectionLabel}>典型用法</div>
          <div className={styles.exampleStage}>
            <ComponentPreview component={component} />
          </div>
        </div>

        <div className={styles.subsection}>
          <div className={styles.subsectionLabel}>Compact DSL</div>
          <details className={styles.dslDetails}>
            <summary>查看示例源码</summary>
            <pre>{component.source}</pre>
          </details>
        </div>
      </div>
    </section>
  );
}

export function ComponentGallery() {
  const [query, setQuery] = useState("");
  const [size, setSize] = useState<SizeFilter>("all");
  const [theme, setTheme] = useState<Theme>("light");
  const normalizedQuery = query.trim().toLocaleLowerCase();
  const visibleComponents = COMPONENT_GALLERY.filter(component => {
    const matchesSize = size === "all" || component.sizes.includes(size);
    const searchable = [component.name, component.summary, component.usage, ...component.props]
      .join(" ")
      .toLocaleLowerCase();
    return matchesSize && (!normalizedQuery || searchable.includes(normalizedQuery));
  });

  return (
    <main className={styles.galleryShell} data-theme={theme}>
      <header className={styles.topHeader}>
        <div>
          <div className={styles.headerTitle}>Fusion Compact DSL · Component Library</div>
          <div className={styles.headerMeta}>
            {COMPONENT_GALLERY.length} 个组件 · 4 大分类 · Renderer 实时预览
          </div>
        </div>
        <div className={styles.headerActions}>
          <a href="/">DSL 渲染器</a>
          <button
            type="button"
            className={styles.themeButton}
            onClick={() => setTheme(current => current === "light" ? "dark" : "light")}
          >
            <span aria-hidden="true">{theme === "light" ? "◐" : "◑"}</span>
            {theme === "light" ? "暗色" : "亮色"}
          </button>
        </div>
      </header>

      <div className={styles.mainContent}>
        <nav className={styles.toc} aria-label="组件目录">
          {GALLERY_GROUPS.map((group, groupIndex) => {
            const components = COMPONENT_GALLERY.filter(item => item.category === group.title);
            return (
              <div className={styles.tocFragment} key={group.id}>
                {groupIndex > 0 && <div className={styles.tocSeparator} />}
                <div className={styles.tocGroup}>
                  <div className={styles.tocTitle}>{groupIndex + 1} {group.title}</div>
                  <div className={styles.tocLinks}>
                    {components.map((component, componentIndex) => (
                      <a className={styles.tocLink} href={`#${component.id}`} key={component.id}>
                        {groupIndex + 1}.{componentIndex + 1} {component.name}
                      </a>
                    ))}
                  </div>
                </div>
              </div>
            );
          })}
        </nav>

        <section className={styles.filterBar} aria-label="筛选组件">
          <label className={styles.searchBox}>
            <span aria-hidden="true">⌕</span>
            <input
              type="search"
              value={query}
              onChange={event => setQuery(event.target.value)}
              placeholder="搜索组件、用途或属性"
              aria-label="搜索组件"
            />
          </label>
          <div className={styles.sizeFilter} role="group" aria-label="按卡片尺寸筛选">
            {(["all", "2x2", "2x4"] as const).map(value => (
              <button
                key={value}
                type="button"
                aria-pressed={size === value}
                onClick={() => setSize(value)}
              >
                {value === "all" ? "全部" : value}
              </button>
            ))}
          </div>
          <span className={styles.resultCount}>{visibleComponents.length} / {COMPONENT_GALLERY.length}</span>
        </section>

        {GALLERY_GROUPS.map((group, groupIndex) => {
          const items = visibleComponents.filter(component => component.category === group.title);
          if (!items.length) return null;
          return (
            <div key={group.id}>
              <div className={styles.categoryDivider} id={group.id}>
                <span>{groupIndex + 1} {group.title} —— {group.description}</span>
              </div>
              {items.map(component => {
                const componentIndex = COMPONENT_GALLERY
                  .filter(item => item.category === group.title)
                  .findIndex(item => item.id === component.id);
                return (
                  <ComponentSection
                    key={component.id}
                    component={component}
                    index={`${groupIndex + 1}.${componentIndex + 1}`}
                  />
                );
              })}
            </div>
          );
        })}

        {!visibleComponents.length && (
          <section className={styles.emptyState}>
            <strong>没有匹配的组件</strong>
            <p>请调整关键词或卡片尺寸筛选。</p>
          </section>
        )}

        <footer className={styles.pageFooter}>
          <span>Fusion Component Library</span>
          <span>Compact DSL · visual-recipes-v1</span>
        </footer>
      </div>
    </main>
  );
}
