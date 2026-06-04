import { useState, useCallback, useEffect, useRef } from 'react';
import type { Message, ToolLampState } from './types';
import { fetchConversationHistory, sendMessageStream, stopAgent } from './api';
import type { RawSseEvent } from './api';
import { I18nProvider, LangToggle, useT, MessageKeys } from './i18n';
import ToolIndicators from './components/ToolIndicators';
import ChatWindow from './components/ChatWindow';
import ChatInput from './components/ChatInput';
import CodeViewer from './components/CodeViewer';
import DebugPanel from './components/DebugPanel';
import { deleteSnapshot, loadSnapshot, saveSnapshot } from './lib/chatUiStore';
import styles from './App.module.css';

const LAMP_IDS = ['get_weather', 'get_clothing_advice', 'translate_text', 'text_statistics'] as const;
const LAMP_ICONS: Record<string, string> = { get_weather: '☀️', get_clothing_advice: '👔', translate_text: '🌐', text_statistics: '📊' };
const LAMP_I18N_KEYS: Record<string, string> = { get_weather: 'tool.weather', get_clothing_advice: 'tool.clothing', translate_text: 'tool.translate', text_statistics: 'tool.statistics' };

const CONVERSATION_ID_STORAGE_KEY = 'eo_conversation_id';

// 模块级去重标记 —— 不受 React StrictMode 组件卸载/重挂载影响。
// useRef 在 StrictMode 双渲染时可能被重置，但模块变量不会。
let _historyFetchInFlight = false;

/** Returns existing conversation ID from localStorage, or null if first visit */
function getExistingConversationId(): string | null {
  return localStorage.getItem(CONVERSATION_ID_STORAGE_KEY);
}

/** Returns existing or creates a new conversation ID */
function getOrCreateConversationId(): string {
  const cached = getExistingConversationId();
  if (cached) return cached;

  const conversationId = crypto.randomUUID();
  localStorage.setItem(CONVERSATION_ID_STORAGE_KEY, conversationId);
  return conversationId;
}

export default function App() {
  return (
    <I18nProvider>
      <LangToggle />
      <AppInner />
    </I18nProvider>
  );
}

function AppInner() {
  const { t } = useT();

  const buildLamps = useCallback((tFn: (key: MessageKeys) => string): ToolLampState[] =>
    LAMP_IDS.map(id => ({
      id,
      label: tFn(LAMP_I18N_KEYS[id] as MessageKeys),
      icon: LAMP_ICONS[id],
      active: false,
      animKey: 0,
    })),
  []);

  const [messages, setMessages] = useState<Message[]>([]);
  const [lamps, setLamps]       = useState<ToolLampState[]>(() => buildLamps(t));
  const [loading, setLoading]   = useState(false);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [debugEvents, setDebugEvents] = useState<RawSseEvent[]>([]);
  const [rightPanelMode, setRightPanelMode] = useState<'code' | 'debug'>('code');

  const botMsgIdRef = useRef<string>('');
  const abortCtrlRef = useRef<AbortController | null>(null);
  const hadExistingConversationIdRef = useRef(getExistingConversationId() !== null);
  const conversationIdRef = useRef<string>(getOrCreateConversationId());
  const initDoneRef = useRef(false);
  const snapshotTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Update lamp labels when language changes
  useEffect(() => {
    setLamps(prev =>
      prev.map(l => ({
        ...l,
        label: t(LAMP_I18N_KEYS[l.id] as MessageKeys),
      }))
    );
  }, [t]);

  useEffect(() => {
    if (messages.length === 0) return;
    if (!initDoneRef.current) return;

    if (snapshotTimerRef.current) clearTimeout(snapshotTimerRef.current);
    snapshotTimerRef.current = setTimeout(() => {
      saveSnapshot(conversationIdRef.current, messages).catch(err => {
        console.warn('[chatUiStore] snapshot save failed:', err);
      });
    }, 500);

    return () => {
      if (snapshotTimerRef.current) clearTimeout(snapshotTimerRef.current);
    };
  }, [messages]);

  useEffect(() => {
    // First visit: no existing conversation → skip history fetch for instant load
    if (!hadExistingConversationIdRef.current) {
      setHistoryLoading(false);
      return;
    }

    const convId = conversationIdRef.current;
    let restoredFromSnapshot = false;
    let snapshotMessageCount = 0;

    const restoreSnapshot = () => loadSnapshot(convId).then(snapshot => {
      snapshotMessageCount = snapshot.length;
      if (snapshot.length > 0) {
        restoredFromSnapshot = true;
        setMessages(snapshot);
        setHistoryLoading(false);
      }
    }).catch(() => {});

    // 模块级标记防止 StrictMode 双渲染导致并发后端请求 → 409。
    // 本地 snapshot 恢复仍然执行，避免第二次挂载卡在 loading。
    if (_historyFetchInFlight) {
      restoreSnapshot().finally(() => setHistoryLoading(false));
      return;
    }
    _historyFetchInFlight = true;

    restoreSnapshot().finally(() => {
      fetchConversationHistory(convId).then(history => {
        if (history.length > 0) {
          if (!restoredFromSnapshot || history.length > snapshotMessageCount) {
            setMessages(history);
          }
          saveSnapshot(convId, history).catch(() => {});
        }
      }).finally(() => {
        _historyFetchInFlight = false;
        setHistoryLoading(false);
      });
    });
  }, []);

  /** Update the current bot message's content via an updater function. */
  const updateBotMessage = useCallback((updater: (content: string) => string) => {
    setMessages(prev =>
      prev.map(m =>
        m.id === botMsgIdRef.current
          ? { ...m, content: updater(m.content) }
          : m
      )
    );
  }, []);

  /** Clear the assistant message's `streaming` flag (hides the blinking caret). */
  const clearBotStreaming = useCallback(() => {
    setMessages(prev => {
      let changed = false;
      const next = prev.map(m => {
        if (m.id === botMsgIdRef.current && m.streaming) {
          changed = true;
          const { streaming, ...rest } = m;
          return rest;
        }
        return m;
      });
      return changed ? next : prev;
    });
  }, []);

  const finishStream = useCallback(() => {
    setLoading(false);
    abortCtrlRef.current = null;
  }, []);

  const handleSend = useCallback(async (text: string) => {
    initDoneRef.current = true;
    setRightPanelMode('debug');

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      timestamp: Date.now(),
    };

    const botMsgId = crypto.randomUUID();
    botMsgIdRef.current = botMsgId;
    const botMsg: Message = {
      id: botMsgId,
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      streaming: true,
    };

    setMessages(prev => [...prev, userMsg, botMsg]);
    setLoading(true);

    const ctrl = sendMessageStream(text, {
      onTextDelta(delta) {
        updateBotMessage(content => content + delta);
      },

      onToolCalled(toolName) {
        setLamps(prev =>
          prev.map(l =>
            l.id === toolName
              ? { ...l, active: true, animKey: l.animKey + 1 }
              : l
          )
        );
        setTimeout(() => {
          setLamps(prev =>
            prev.map(l => (l.id === toolName ? { ...l, active: false } : l))
          );
        }, 1000);
      },

      onRawEvent(event) {
        // Coalesce consecutive text_delta events into a single growing entry,
        // so a multi-paragraph response doesn't flood the debug panel with
        // hundreds of one-token rows.
        if (event.eventType === 'text_delta') {
          const delta = (event.data as { delta?: string } | null)?.delta ?? '';
          setRightPanelMode('debug');
          setDebugEvents(prev => {
            const last = prev[prev.length - 1];
            if (last && last.eventType === 'text_delta') {
              const prevDelta = (last.data as { delta?: string } | null)?.delta ?? '';
              const merged: RawSseEvent = {
                ...last,
                data: { delta: prevDelta + delta },
                raw: last.raw + delta,
                timestamp: event.timestamp,
              };
              return [...prev.slice(0, -1), merged];
            }
            return [...prev, event];
          });
          return;
        }
        setRightPanelMode('debug');
        setDebugEvents(prev => [...prev, event]);
      },

      onDone() {
        clearBotStreaming();
        finishStream();
      },

      onError() {
        clearBotStreaming();
        updateBotMessage(content => content || t("status.error"));
        finishStream();
      },
    }, conversationIdRef.current);

    abortCtrlRef.current = ctrl;
  }, [updateBotMessage, clearBotStreaming, finishStream, t]);

  const handleClearHistory = useCallback(() => {
    if (abortCtrlRef.current) {
      abortCtrlRef.current.abort();
      abortCtrlRef.current = null;
    }

    const oldConvId = conversationIdRef.current;
    deleteSnapshot(oldConvId).catch(() => {});

    localStorage.removeItem(CONVERSATION_ID_STORAGE_KEY);
    const newId = crypto.randomUUID();
    localStorage.setItem(CONVERSATION_ID_STORAGE_KEY, newId);
    conversationIdRef.current = newId;
    setMessages([]);
    setDebugEvents([]);
    setRightPanelMode('code');
    setLoading(false);
    initDoneRef.current = false;
  }, []);

  const handleStop = useCallback(() => {
    // 1. 立即中断前端 SSE 读取
    if (abortCtrlRef.current) {
      abortCtrlRef.current.abort();
      abortCtrlRef.current = null;
    }

    // 2. 前端立即显示已中断（乐观 UI，不等后端）
    updateBotMessage(content => content ? content + '\n\n' + t("status.stopped") : t("status.stopped"));
    setLoading(false);

    // 3. 后端异步执行中断，失败时提示用户
    stopAgent(conversationIdRef.current).then(ok => {
      if (!ok) {
        updateBotMessage(content => content + '\n\n' + t("status.backendError"));
      }
    });
  }, [updateBotMessage, t]);

  return (
    <div className={styles.shell}>
      <div className={styles.blob1} />
      <div className={styles.blob2} />

      <div className={styles.stage}>
        <div className={styles.chatPanel}>
          <header className={styles.header}>
            <div className={styles.headerLeft}>
              <span className={styles.logo}>⬡</span>
              <div>
                <p className={styles.title}>{t("app.title")}</p>
                <p className={styles.subtitle}>{t("app.subtitle")}</p>
              </div>
            </div>
            <ToolIndicators lamps={lamps} />
          </header>

          <div className={styles.chatWindowShell}>
            <ChatWindow messages={messages} loading={loading} />
            {historyLoading && messages.length === 0 && (
              <div className={styles.historyOverlay}>
                <div className={styles.historySpinner} />
              </div>
            )}
          </div>
          <ChatInput onSend={handleSend} onStop={handleStop} onClear={handleClearHistory} disabled={loading} />
        </div>

        <div className={styles.codePanel}>
          {rightPanelMode === 'code' ? (
            <CodeViewer />
          ) : (
            <DebugPanel events={debugEvents} onClear={() => setDebugEvents([])} />
          )}
        </div>
      </div>
    </div>
  );
}
