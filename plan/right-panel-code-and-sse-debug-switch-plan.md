# `openAI-agent-starter-python` 首页右侧代码展示与 SSE 调试面板切换方案

参考方案：`/Users/wenyiqing/Desktop/agents/agent-example/openAI-agent-starter/plan/right-panel-code-and-sse-debug-switch-plan.md`

参考项目：`/Users/wenyiqing/Desktop/agents/agent-example/openAI-agent-starter`

目标项目：`/Users/wenyiqing/Desktop/agents/agent-example/openAI-agent-starter-python`

目标：让 `openAI-agent-starter-python` 具备和 `openAI-agent-starter` 类似的右侧面板体验：

- 用户首次进入首页时，右侧展示现有 `CodeViewer` 代码信息；
- 用户发送消息、开始执行后，右侧自动切换为 SSE 调试面板；
- SSE 调试面板展示 `/chat` 返回的原始 SSE 事件；
- 清空历史后，右侧恢复 `CodeViewer`；
- 不破坏现有聊天、工具灯、停止生成、历史恢复等功能。

---

## 1. 参考方案能力

参考方案中目标实现包含：

- `src/components/DebugPanel.tsx`；
- `src/components/DebugPanel.module.css`；
- `src/api.ts` 中的 `RawSseEvent`；
- `sendMessageStream(..., callbacks)` 支持 `onRawEvent`；
- `App.tsx` 中的：
  - `debugEvents`；
  - `rightPanelMode: 'code' | 'debug'`；
  - 初始显示 `CodeViewer`；
  - 开始发送后切换 `DebugPanel`；
  - 清空历史后切回 `CodeViewer`。

参考方案核心写法：

```tsx
const [debugEvents, setDebugEvents] = useState<RawSseEvent[]>([]);
const [rightPanelMode, setRightPanelMode] = useState<'code' | 'debug'>('code');
```

右侧渲染：

```tsx
<div className={styles.codePanel}>
  {rightPanelMode === 'code' ? (
    <CodeViewer />
  ) : (
    <DebugPanel events={debugEvents} onClear={() => setDebugEvents([])} />
  )}
</div>
```

---

## 2. 当前项目现状

### 2.1 当前右侧固定展示 CodeViewer

文件：`src/App.tsx`

当前右侧固定渲染：

```tsx
<div className={styles.codePanel}>
  <CodeViewer />
</div>
```

当前已经有 `CodeViewer`，且展示内容是 Python 版 `handler.py` 示例，所以不需要新增代码展示组件。

### 2.2 当前没有 DebugPanel

目标项目目前没有：

```txt
src/components/DebugPanel.tsx
src/components/DebugPanel.module.css
```

需要从参考项目复制并适配。

### 2.3 当前 API 层没有 raw SSE 事件回调

文件：`src/api.ts`

当前 `StreamCallbacks` 只有业务回调：

```ts
export interface StreamCallbacks {
  onTextDelta: (delta: string) => void;
  onToolCalled: (toolName: string) => void;
  onDone: () => void;
  onError: (err: Error) => void;
}
```

当前 `dispatchSseChunk` 解析 SSE 后只分发业务事件，没有把原始事件给 UI。

### 2.4 后端已经返回标准 SSE

文件：`agents/chat/index.py`

后端通过 Python helper `sse_event(event, data)` 输出 SSE：

```py
def sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
```

当前会出现：

- `text_delta`
- `tool_called`
- `done`
- `error`

本次切换面板基础功能不要求改后端。

---

## 3. 目标交互

### 3.1 首次进入页面

右侧显示现有 `CodeViewer`。

```txt
左侧：聊天区
右侧：代码展示 CodeViewer
```

### 3.2 用户发送消息后

在 `handleSend` 开始时立即执行：

```ts
setRightPanelMode('debug');
```

行为：

1. 用户点击 preset 或手动发送；
2. 右侧立即从 `CodeViewer` 切换到 `DebugPanel`；
3. `/chat` SSE 事件逐条进入 DebugPanel；
4. 文本仍进入左侧 assistant 气泡；
5. `tool_called` 仍驱动工具灯高亮。

### 3.3 执行结束后

右侧继续保持 `DebugPanel`，不要自动切回 `CodeViewer`。

原因：

- 用户执行结束后通常想看完整 SSE 日志；
- 自动切回会让调试信息消失；
- 和参考方案保持一致。

### 3.4 清空历史后

清空历史时：

- abort 当前请求；
- 清空消息；
- 清空 `debugEvents`；
- 右侧切回 `CodeViewer`；
- 重置 `conversationIdRef`，保持现有历史清空逻辑。

---

## 4. API 层改造

文件：`src/api.ts`

### 4.1 新增 RawSseEvent 类型

```ts
export interface RawSseEvent {
  eventType: string;
  data: unknown;
  raw: string;
  timestamp: number;
}
```

字段说明：

- `eventType`：SSE `event:` 名称；
- `data`：`JSON.parse` 后的数据；
- `raw`：原始 `data:` 字符串；
- `timestamp`：前端收到事件的时间。

### 4.2 扩展 StreamCallbacks

改为：

```ts
export interface StreamCallbacks {
  onTextDelta: (delta: string) => void;
  onToolCalled: (toolName: string) => void;
  onDone: () => void;
  onError: (err: Error) => void;
  onRawEvent?: (event: RawSseEvent) => void;
}
```

### 4.3 在 dispatchSseChunk 中推送 raw event

在：

```ts
const parsed = JSON.parse(data);
```

之后、`switch` 之前新增：

```ts
if (cb.onRawEvent) {
  cb.onRawEvent({
    eventType,
    data: parsed,
    raw: data,
    timestamp: Date.now(),
  });
}
```

解析失败时也推送：

```ts
} catch {
  if (cb.onRawEvent) {
    cb.onRawEvent({
      eventType,
      data: null,
      raw: data,
      timestamp: Date.now(),
    });
  }
}
```

这样 `DebugPanel` 能展示所有后端 SSE，包括坏帧。

### 4.4 多行 data 的兼容性

当前 Python 后端的 `sse_event()` 每个事件只有一行 `data:`，现有解析逻辑可用。

如果后续后端改为多行 `data:`，建议把：

```ts
let data = '';
```

改为：

```ts
const dataLines: string[] = [];
```

并将所有 `data:` 行拼接为：

```ts
const data = dataLines.join('\n');
```

本次无需优先改造。

---

## 5. 新增 DebugPanel 组件

新增：

```txt
src/components/DebugPanel.tsx
src/components/DebugPanel.module.css
```

可以直接参考 `openAI-agent-starter/src/components/DebugPanel.tsx` 或参考方案来源项目的 `DebugPanel`。

### 5.1 组件接口

```ts
import type { RawSseEvent } from '../api';

interface Props {
  events: RawSseEvent[];
  onClear: () => void;
}
```

### 5.2 展示内容

- 顶部标题：`SSE Debug` / `SSE 调试`；
- 事件数量；
- 清除按钮；
- 空状态；
- 自动滚动到底部；
- 每条事件显示：
  - `eventType`；
  - 时间；
  - JSON payload。

### 5.3 事件类型样式

建议支持当前 Python 后端已有事件：

```css
.type_text_delta
.type_tool_called
.type_done
.type_error
.type_unknown
```

可选预留 OpenAI Agents SDK 调试事件：

```css
.type_debug_msg
.type_raw_response_event
.type_run_item_stream_event
```

---

## 6. App.tsx 改造

文件：`src/App.tsx`

### 6.1 新增 import

```ts
import DebugPanel from './components/DebugPanel';
import type { RawSseEvent } from './api';
```

当前已有：

```ts
import CodeViewer from './components/CodeViewer';
```

保留即可。

### 6.2 新增状态

```ts
const [debugEvents, setDebugEvents] = useState<RawSseEvent[]>([]);
const [rightPanelMode, setRightPanelMode] = useState<'code' | 'debug'>('code');
```

### 6.3 发送消息时切换 DebugPanel

在 `handleSend` 开始处执行：

```ts
setRightPanelMode('debug');
```

是否清空上一轮事件有两种选择：

- 保留：便于看多轮完整流；
- 清空：每轮更干净。

推荐先保留，用户可以通过 DebugPanel 的清除按钮手动清空。

### 6.4 onRawEvent 记录事件

在 `sendMessageStream` callbacks 中新增：

```ts
onRawEvent(event) {
  setRightPanelMode('debug');
  setDebugEvents(prev => [...prev, event]);
},
```

完整位置示意：

```ts
const ctrl = sendMessageStream(text, {
  onTextDelta(delta) {
    updateBotMessage(content => content + delta);
  },

  onToolCalled(toolName) {
    // existing lamp logic
  },

  onRawEvent(event) {
    setRightPanelMode('debug');
    setDebugEvents(prev => [...prev, event]);
  },

  onDone: finishStream,

  onError() {
    updateBotMessage(content => content || t('status.error'));
    finishStream();
  },
}, conversationIdRef.current);
```

### 6.5 清空历史后切回 CodeViewer

当前 `handleClearHistory` 会移除旧 conversation id、生成新 id 并清空消息。

建议增强为：

```ts
const handleClearHistory = useCallback(() => {
  if (abortCtrlRef.current) {
    abortCtrlRef.current.abort();
    abortCtrlRef.current = null;
  }

  localStorage.removeItem(CONVERSATION_ID_STORAGE_KEY);
  const newId = crypto.randomUUID();
  localStorage.setItem(CONVERSATION_ID_STORAGE_KEY, newId);
  conversationIdRef.current = newId;

  setMessages([]);
  setDebugEvents([]);
  setRightPanelMode('code');
  setLoading(false);
}, []);
```

### 6.6 右侧条件渲染

当前：

```tsx
<div className={styles.codePanel}>
  <CodeViewer />
</div>
```

改为：

```tsx
<div className={styles.codePanel}>
  {rightPanelMode === 'code' ? (
    <CodeViewer />
  ) : (
    <DebugPanel events={debugEvents} onClear={() => setDebugEvents([])} />
  )}
</div>
```

---

## 7. i18n 文案

文件：

```txt
src/i18n/en.ts
src/i18n/zh.ts
```

当前 `MessageKeys` 通常由 `en.ts` 推导，所以建议先改 `en.ts`，再同步 `zh.ts`。

### 7.1 英文

新增：

```ts
// Debug panel
"debug.title": "SSE Debug",
"debug.events": "events",
"debug.clear": "Clear",
"debug.empty": "Waiting for SSE events...",
"debug.emptyHint": "After sending a message, all raw backend data will be displayed here.",
```

### 7.2 中文

新增：

```ts
// Debug panel
"debug.title": "SSE 调试",
"debug.events": "事件",
"debug.clear": "清除",
"debug.empty": "等待 SSE 事件...",
"debug.emptyHint": "发送消息后，所有原始后端数据将在此处显示。",
```

### 7.3 状态文案注意

当前中英文 `status.stopped` 和 `status.error` 使用了 emoji。如果本次只写方案，不需要改；如果后续实现时想保持 ASCII，可另行统一调整。

---

## 8. 样式与布局注意事项

文件：`src/App.module.css`

当前 `.codePanel` 已经有：

```css
.codePanel {
  flex: 0 0 42%;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}
```

建议补充 `min-height: 0`，确保右侧 DebugPanel 内部滚动稳定：

```css
.codePanel {
  flex: 0 0 42%;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}
```

`DebugPanel.module.css` 中确保：

```css
.panel {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}
```

---

## 9. 后端是否需要改造

本次基础切换功能不需要改后端。

当前 Python 后端已经通过 `agents/chat/index.py` 输出业务 SSE：

- `text_delta`：来自 `raw_response_event` + `ResponseTextDeltaEvent`；
- `tool_called`：来自 `run_item_stream_event` 中的 `tool_called`；
- `error`：异常或缺少 message；
- `done`：`finally` 中统一输出，包含 `{ stopped }`。

如果希望 DebugPanel 展示更多 OpenAI Agents SDK 原始事件，可以在 `_event_stream()` 中额外 yield debug 事件，例如：

```py
yield sse_event("debug_msg", {
    "type": event.type,
    "name": getattr(event, "name", None),
})
```

如果要展示更完整的 SDK event，需要注意有些对象不可 JSON 序列化，不能直接 `json.dumps(event)`。建议只挑选稳定字段，避免把大对象全部塞进 SSE。

初版建议先只展示现有业务 SSE，风险最小。

---

## 10. 推荐实施步骤

1. 新增 `RawSseEvent` 类型到 `src/api.ts`；
2. 给 `StreamCallbacks` 增加 `onRawEvent?: ...`；
3. 在 `dispatchSseChunk` 中推送 raw event；
4. 新增 `src/components/DebugPanel.tsx`；
5. 新增 `src/components/DebugPanel.module.css`；
6. 修改 `src/i18n/en.ts`、`src/i18n/zh.ts` 增加 debug 文案；
7. 修改 `src/App.tsx`：
   - import `DebugPanel`；
   - import `RawSseEvent`；
   - 新增 `debugEvents`；
   - 新增 `rightPanelMode`；
   - `handleSend` 切到 debug；
   - `onRawEvent` 记录事件；
   - `handleClearHistory` abort 当前请求、清空 debug 并切回 code；
   - 右侧条件渲染 `CodeViewer` / `DebugPanel`；
8. 修改 `src/App.module.css`，确保 `.codePanel` 有 `min-height: 0`；
9. 运行 `npx tsc --noEmit`；
10. 启动页面验证交互。

---

## 11. 验证清单

### 11.1 初始状态

- 首页右侧显示 `CodeViewer`；
- 不显示空白 DebugPanel；
- 左侧聊天窗口、输入框、preset 正常；
- 历史恢复 loading 正常。

### 11.2 发送消息后

- 点击 preset 或手动发送后，右侧立即切到 DebugPanel；
- 能看到 `text_delta`；
- 如果触发工具，能看到 `tool_called`；
- 完成后能看到 `done`，payload 包含 `stopped`；
- 错误时能看到 `error`；
- 左侧聊天内容仍正常流式输出。

### 11.3 停止生成

- 点击 stop 后前端 SSE 读取被 abort；
- 左侧 assistant 气泡显示已停止；
- `loading` 恢复为 false；
- 右侧仍保持 DebugPanel，保留停止前已经收到的事件；
- 后端 `/stop` 请求失败时仍按现有逻辑提示。

### 11.4 清空历史

- 消息清空；
- 当前请求被 abort；
- `debugEvents` 清空；
- 右侧恢复 `CodeViewer`；
- localStorage 中的 conversation id 被替换；
- 新一轮发送仍能再次切到 DebugPanel。

### 11.5 回归

- 工具灯仍正常亮起；
- stop 按钮仍可中断；
- history 刷新恢复不受影响；
- `npx tsc --noEmit` 通过。

---

## 12. 注意事项

- 不建议用 `debugEvents.length > 0` 决定右侧面板，因为用户可能手动清空 DebugPanel 但仍希望留在调试视图；应使用显式 `rightPanelMode`。
- 不建议执行结束后自动切回 `CodeViewer`，否则用户无法查看完整 SSE 日志。
- `handleClearHistory` 建议同时 abort 当前请求，否则清空后旧流仍可能继续写入消息或 debug 事件。
- Python 后端 debug 扩展时不要直接序列化 SDK event 对象，优先输出小而稳定的字段。
