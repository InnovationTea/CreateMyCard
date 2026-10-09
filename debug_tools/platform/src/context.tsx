import { createContext, useCallback, useContext, useEffect, useMemo, useReducer } from 'react';
import type { ReactNode } from 'react';
import {
  applyDebugConfig,
  cloneDebugConfig,
  defaultDebugConfig,
  loadDebugConfig,
  normalizeDebugConfig,
  saveDebugConfig,
} from './config';
import type {
  CardArtifact,
  DebugConfig,
  DebugEvent,
  ToolCallInput,
  ToolCallPatch,
  ToolCallRecord,
  WorkbenchContextValue,
} from './types';

type State = {
  events: DebugEvent[];
  calls: ToolCallRecord[];
  selectedCallId: string | null;
  artifact: CardArtifact | null;
  config: DebugConfig;
};

type Action =
  | { type: 'event'; event: DebugEvent }
  | { type: 'call'; call: ToolCallRecord }
  | { type: 'call-update'; id: string; patch: ToolCallPatch }
  | { type: 'call-select'; id: string | null }
  | { type: 'calls-clear' }
  | { type: 'artifact'; artifact: CardArtifact | null }
  | { type: 'config'; config: DebugConfig }
  | { type: 'config-update'; patch: Partial<DebugConfig> };

const MAX_EVENT_COUNT = 500;
const MAX_CALL_COUNT = 100;
const CALL_HISTORY_STORAGE_KEY = 'ai-widget-debug-call-history:v1';

function createId(prefix: string): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function initialState(): State {
  const config = loadDebugConfig();
  // 在子路由挂载前应用持久化地址；否则它们的 WebSocket effect 首次渲染
  // 可能会先读到旧默认值。
  applyDebugConfig(config);
  let calls: ToolCallRecord[] = [];
  let selectedCallId: string | null = null;
  if (typeof window !== 'undefined') {
    try {
      const stored = window.sessionStorage.getItem(CALL_HISTORY_STORAGE_KEY);
      const parsed = stored ? JSON.parse(stored) as { calls?: unknown; selectedCallId?: unknown } : null;
      if (parsed && Array.isArray(parsed.calls)) {
        calls = parsed.calls.filter((item): item is ToolCallRecord => Boolean(
          item && typeof item === 'object' && typeof (item as ToolCallRecord).id === 'string',
        )).slice(-MAX_CALL_COUNT);
        selectedCallId = typeof parsed.selectedCallId === 'string'
          && calls.some((item) => item.id === parsed.selectedCallId)
          ? parsed.selectedCallId
          : calls.at(-1)?.id ?? null;
      }
    } catch {
      calls = [];
      selectedCallId = null;
    }
  }
  return {
    events: [],
    calls,
    selectedCallId,
    artifact: null,
    config,
  };
}

function mergeConfig(current: DebugConfig, patch: Partial<DebugConfig>): DebugConfig {
  return normalizeDebugConfig({ ...current, ...patch });
}

function reducer(state: State, action: Action): State {
  if (action.type === 'event') {
    return { ...state, events: [...state.events.slice(-(MAX_EVENT_COUNT - 1)), action.event] };
  }
  if (action.type === 'call') {
    const existingIndex = state.calls.findIndex((item) => item.id === action.call.id);
    if (existingIndex >= 0) {
      const calls = [...state.calls];
      calls[existingIndex] = action.call;
      return { ...state, calls };
    }
    return {
      ...state,
      calls: [...state.calls.slice(-(MAX_CALL_COUNT - 1)), action.call],
      selectedCallId: action.call.id,
    };
  }
  if (action.type === 'call-update') {
    const calls = state.calls.map((item) => {
      if (item.id !== action.id) return item;
      const next = { ...item, ...action.patch };
      // Keep duration derived from the canonical timestamps so producers only
      // need to provide finishedAt.  An explicitly supplied duration wins.
      if (next.durationMs == null && next.finishedAt) {
        const started = Date.parse(next.startedAt);
        const finished = Date.parse(next.finishedAt);
        if (Number.isFinite(started) && Number.isFinite(finished)) {
          next.durationMs = Math.max(0, finished - started);
        }
      }
      if (!next.completedAt && next.finishedAt) next.completedAt = next.finishedAt;
      return next;
    });
    return { ...state, calls };
  }
  if (action.type === 'call-select') {
    const selectedCallId = action.id && state.calls.some((item) => item.id === action.id)
      ? action.id
      : null;
    return { ...state, selectedCallId };
  }
  if (action.type === 'calls-clear') {
    return { ...state, calls: [], selectedCallId: null };
  }
  if (action.type === 'artifact') {
    return { ...state, artifact: action.artifact };
  }
  if (action.type === 'config-update') {
    return { ...state, config: mergeConfig(state.config, action.patch) };
  }
  return { ...state, config: action.config };
}

const WorkbenchContext = createContext<WorkbenchContextValue | null>(null);

export function WorkbenchProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, undefined, initialState);

  useEffect(() => {
    applyDebugConfig(state.config);
    saveDebugConfig(state.config);
  }, [state.config]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      window.sessionStorage.setItem(
        CALL_HISTORY_STORAGE_KEY,
        JSON.stringify({ calls: state.calls, selectedCallId: state.selectedCallId }),
      );
    } catch {
      // History is an enhancement; private browsing/storage quotas must not
      // interrupt live calls.
    }
  }, [state.calls, state.selectedCallId]);

  const pushEvent = useCallback(
    (event: Omit<DebugEvent, 'id' | 'timestamp'> & { timestamp?: string }) => {
      dispatch({
        type: 'event',
        event: {
          ...event,
          id: createId('event'),
          timestamp: event.timestamp ?? new Date().toISOString(),
        },
      });
    },
    [],
  );

  const recordCall = useCallback((call: ToolCallInput): string => {
    const id = call.id ?? createId('call');
    dispatch({
      type: 'call',
      call: {
        ...call,
        id,
        request: call.request ?? {},
      },
    });
    return id;
  }, []);

  const updateCall = useCallback((id: string, patch: ToolCallPatch) => {
    dispatch({ type: 'call-update', id, patch });
  }, []);

  const beginCall = useCallback((call: Omit<ToolCallInput, 'status'> & { status?: 'pending' }) => (
    recordCall({ ...call, status: 'pending' })
  ), [recordCall]);

  const finishCall = useCallback((id: string, patch: ToolCallPatch) => {
    const finishedAt = patch.finishedAt ?? new Date().toISOString();
    updateCall(id, { ...patch, finishedAt, status: patch.status ?? 'success' });
  }, [updateCall]);

  const failCall = useCallback((id: string, error: string, patch: ToolCallPatch = {}) => {
    const finishedAt = patch.finishedAt ?? new Date().toISOString();
    updateCall(id, { ...patch, finishedAt, status: 'error', error });
  }, [updateCall]);

  const selectCall = useCallback((id: string | null) => {
    dispatch({ type: 'call-select', id });
  }, []);

  const clearCalls = useCallback(() => {
    dispatch({ type: 'calls-clear' });
  }, []);

  const updateConfig = useCallback((patch: Partial<DebugConfig>) => {
    dispatch({ type: 'config-update', patch });
  }, []);

  const resetConfig = useCallback(() => {
    dispatch({ type: 'config', config: cloneDebugConfig(defaultDebugConfig) });
  }, []);

  const setArtifact = useCallback((artifact: CardArtifact | null) => {
    dispatch({ type: 'artifact', artifact });
  }, []);

  const selectedCall = state.calls.find((item) => item.id === state.selectedCallId) ?? null;

  const value = useMemo<WorkbenchContextValue>(
    () => ({
      events: state.events,
      pushEvent,
      calls: state.calls,
      selectedCallId: state.selectedCallId,
      selectedCall,
      recordCall,
      updateCall,
      beginCall,
      finishCall,
      failCall,
      selectCall,
      clearCalls,
      config: state.config,
      updateConfig,
      resetConfig,
      artifact: state.artifact,
      setArtifact,
    }),
    [
      clearCalls,
      pushEvent,
      recordCall,
      beginCall,
      finishCall,
      failCall,
      resetConfig,
      selectCall,
      setArtifact,
      state.artifact,
      state.calls,
      state.config,
      state.events,
      state.selectedCallId,
      selectedCall,
      updateCall,
      updateConfig,
    ],
  );
  return <WorkbenchContext.Provider value={value}>{children}</WorkbenchContext.Provider>;
}

export function useWorkbench(): WorkbenchContextValue {
  const value = useContext(WorkbenchContext);
  if (!value) {
    throw new Error('useWorkbench 必须在 WorkbenchProvider 内调用');
  }
  return value;
}
