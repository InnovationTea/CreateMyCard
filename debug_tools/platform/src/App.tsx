import { useEffect, useState } from 'react';
import { Navigate, NavLink, Route, Routes, useMatch } from 'react-router-dom';
import { WorkbenchProvider } from './context';
import CallHistory from './components/CallHistory';
import SettingsPanel from './components/SettingsPanel';
import { EndToEndRoute } from './routes/EndToEndRoute';
import { InterfaceRoute } from './routes/InterfaceRoute';
import { RendererRoute } from './routes/RendererRoute';
import { DeviceRenderRoute } from './routes/DeviceRenderRoute';
import { BatchRoute } from './routes/BatchRoute';
import { BatchTraceRoute } from './routes/BatchTraceRoute';
import { BatchTaskCenterRoute } from './routes/BatchTaskCenterRoute';
import { BatchTaskCreateRoute } from './routes/BatchTaskCreateRoute';
import { BatchGalleryCaptureRoute } from './routes/BatchGalleryCaptureRoute';
import { PostprocessDashboardRoute } from './routes/PostprocessDashboardRoute';
import { QualityRoute } from './routes/QualityRoute';
import { QualityCompareRoute } from './routes/QualityCompareRoute';
import { QualityEvaluationRoute } from './routes/QualityEvaluationRoute';
import { ValidationFailureCaptureRoute } from './routes/ValidationFailureCaptureRoute';
import { QualityImportRoute } from './routes/QualityImportRoute';

const navigation = [
  { path: '/end-to-end', label: '端到端调试', detail: 'Main Agent · Agent 调试' },
  { path: '/interface', label: '接口调试', detail: 'WebSocket · API 调试' },
  { path: '/renderer', label: '卡片渲染', detail: 'GenUI · 预览检查' },
  { path: '/device-render', label: '设备渲染', detail: 'HDC · 编译与设备预览' },
  { path: '/batch', label: '批量测试', detail: '数据集 · Trace 分析' },
  { path: '/quality', label: '质量评分', detail: '样本选择 · 评分与对比' },
  { path: '/settings', label: '连接配置', detail: '地址 · 固定参数' },
];

function Shell() {
  const isEndToEnd = useMatch('/end-to-end') !== null;
  const [hasVisitedEndToEnd, setHasVisitedEndToEnd] = useState(isEndToEnd);
  useEffect(() => {
    if (isEndToEnd) setHasVisitedEndToEnd(true);
  }, [isEndToEnd]);
  return (
    <div className="workbench-shell">
      <aside className="navigation-rail">
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true">&lt;/&gt;</div>
          <div>
            <strong>AI Widget</strong>
            <span>Debug Workbench</span>
          </div>
        </div>
        <nav aria-label="调试模块">
          {navigation.map((item) => (
            <NavLink
              className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
              to={item.path}
              key={item.path}
            >
              <span className="nav-item-icon" aria-hidden="true">{item.label.slice(0, 1)}</span>
              <span>
                <strong>{item.label}</strong>
                <small>{item.detail}</small>
              </span>
            </NavLink>
          ))}
        </nav>
        <CallHistory />
        <div className="rail-footer">统一测试入口 · 本地调试</div>
      </aside>

      <main className="workbench-main">
        <section className="route-content">
          {/* 保留已打开的会话和连接，导航只切换可见性，不触发卸载清理。 */}
          {(isEndToEnd || hasVisitedEndToEnd) && (
            <div className="end-to-end-route" hidden={!isEndToEnd}>
              <EndToEndRoute />
            </div>
          )}
          <Routes>
            <Route path="/end-to-end" element={null} />
            <Route path="/interface" element={<InterfaceRoute />} />
            <Route path="/renderer" element={<RendererRoute />} />
            <Route path="/device-render" element={<DeviceRenderRoute />} />
            <Route path="/batch" element={<BatchTaskCenterRoute />} />
            <Route path="/batch/new" element={<BatchTaskCreateRoute />} />
            <Route path="/batch/tasks/:taskId" element={<BatchRoute />} />
            <Route path="/batch/legacy/:runId" element={<BatchRoute />} />
            <Route path="/quality" element={<QualityRoute />} />
            <Route path="/quality/import" element={<QualityImportRoute />} />
            <Route path="/quality/compare" element={<QualityCompareRoute />} />
            <Route path="/quality/evaluation" element={<QualityEvaluationRoute />} />
            <Route path="/settings" element={<SettingsPanel />} />
            <Route path="*" element={<Navigate replace to="/end-to-end" />} />
          </Routes>
        </section>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <WorkbenchProvider>
      <Routes>
        <Route path="/batch/runs/:runId/gallery-capture" element={<BatchGalleryCaptureRoute />} />
        <Route
          path="/batch/runs/:runId/validation-failure-capture"
          element={<ValidationFailureCaptureRoute />}
        />
        <Route path="/batch/runs/:runId/samples/:sampleId/trace" element={<BatchTraceRoute />} />
        <Route
          path="/batch/runs/:runId/postprocess/:executionId/plugins/:pluginId"
          element={<PostprocessDashboardRoute />}
        />
        <Route path="*" element={<Shell />} />
      </Routes>
    </WorkbenchProvider>
  );
}
