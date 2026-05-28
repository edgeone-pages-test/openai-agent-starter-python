const zh = {
  // Header
  "app.title": "OpenAI Agents Starter",
  "app.subtitle": "运行在 EdgeOne Makers 上，支持会话记忆、Agent Tools",

  // Empty state
  "empty.title": "OpenAI Agents Starter",
  "empty.hint": "我是运行在 EdgeOne 环境中的 OpenAI Agents，支持自定义工具、会话记忆，并帮助你完成天气查询、穿衣建议、翻译和文本统计。",
  "empty.features": "EdgeOne Store · Session Memory · Agent Tools",

  // Chat input
  "chat.placeholder": "发消息…  ⏎ 发送 · Shift+⏎ 换行",
  "chat.hint": "由 OpenAI Agents SDK 驱动 · 仅供演示",

  // Preset questions
  "preset.1": "现在北京天气怎么样，有什么穿衣建议吗？",
  "preset.2": "帮我翻译英文\"你好，欢迎来到北京！\"，并统计翻译字符数。",

  // Tool indicators
  "tool.weather": "天气查询",
  "tool.clothing": "穿衣建议",
  "tool.translate": "文本翻译",
  "tool.statistics": "文本统计",

  // Status & errors
  "status.error": "⚠️ 请求失败，请检查后端服务是否启动。",
  "status.stopped": "⏹ *已停止生成*",
  "status.backendError": "⚠️ 后端中断请求失败，服务端可能仍在运行。",

  // Language toggle
  "lang.switch": "English",
} as const;

export default zh;
