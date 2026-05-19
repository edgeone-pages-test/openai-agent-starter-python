# OpenAI Agent Starter - Complete Analysis & Documentation

This directory contains comprehensive documentation analyzing the OpenAI Agent Starter project architecture, focusing on the EdgeOne Pages Functions serverless backend.

## 📚 Documentation Files

### 1. **ANALYSIS.md** - Complete Deep Dive
The most comprehensive reference. Covers:
- Project structure overview
- Chat handler mechanics (streaming/SSE)
- Generator/yield patterns
- Handler return data flow
- EdgeOne platform context interaction
- Response format specifications
- Summary tables and quick reference

**Use this when**: You need a complete understanding of the system

---

### 2. **DIAGRAMS.md** - Visual Architecture
Detailed ASCII diagrams and flowcharts:
- Request/response flow diagram
- Streaming event lifecycle
- Async generator polling mechanism
- Context object structure
- Session lifecycle
- Tool calling sequence
- Error handling flow
- Directory-to-route mapping
- SSE protocol details
- Cancellation flow

**Use this when**: You need to visualize how components interact

---

### 3. **IMPLEMENTATION_GUIDE.md** - Code Patterns & Examples
Practical, copy-paste-ready code:
- Handler function template
- SSE event helpers
- Session adapter implementation
- Tool definition patterns
- Logging patterns
- Asyncio patterns
- Error handling examples
- Local testing setup
- Configuration patterns
- Stop/cancel handlers
- History retrieval
- Implementation checklist

**Use this when**: You're implementing new handlers or features

---

## 🎯 Quick Start - By Use Case

### I want to understand how the chat handler works
1. Start with **ANALYSIS.md** § 2 (Chat Handler Deep Dive)
2. Look at **DIAGRAMS.md** § 1 (Request/Response Flow)
3. Reference **IMPLEMENTATION_GUIDE.md** § 1 (Handler Template)

### I need to implement a new handler
1. Check **DIAGRAMS.md** § 8 (Directory-to-Route Mapping)
2. Copy template from **IMPLEMENTATION_GUIDE.md** § 1
3. Add your business logic following the pattern
4. Test with mock context (**IMPLEMENTATION_GUIDE.md** § 8)

### I want to understand streaming/SSE
1. Read **ANALYSIS.md** § 2.4 (SSE Response Format)
2. See examples in **DIAGRAMS.md** § 2 & 9
3. Use **IMPLEMENTATION_GUIDE.md** § 2 (SSE Helpers)
4. Review raw format in **IMPLEMENTATION_GUIDE.md** § 9

### I need to handle conversation history
1. Read **ANALYSIS.md** § 4 (EdgeOne Context Interaction)
2. Review **DIAGRAMS.md** § 5 (Session Lifecycle)
3. Copy session code from **IMPLEMENTATION_GUIDE.md** § 3
4. See history handler in **IMPLEMENTATION_GUIDE.md** § 12

### I'm debugging cancellation/abort
1. Check **ANALYSIS.md** § 6 (Cancel Mechanism)
2. View flow in **DIAGRAMS.md** § 10 (Cancellation Flow)
3. Review handler in **IMPLEMENTATION_GUIDE.md** § 11

### I need to add tools
1. See tool patterns in **IMPLEMENTATION_GUIDE.md** § 4
2. Review tool calling in **DIAGRAMS.md** § 6
3. Reference **ANALYSIS.md** § 9 (Agent & Tools)

---

## 🔑 Key Concepts Summary

### Handler Signature
```python
async def handler(context: Any) -> AsyncGenerator[str, None]:
    # Yields SSE-formatted event strings
    yield sse_event("event_type", {"data": "..."})
```

### SSE Event Format
```
event: text_delta
data: {"delta":"token"}

event: tool_called
data: {"tool":"function_name"}

event: done
data: {"stopped":false}
```

### Context Object
```python
context.conversation_id      # Unique session ID
context.request.body         # Request JSON
context.store               # Persistent KV store
context.request.signal      # Cancel signal
context.utils.abort_active_run()  # Abort mechanism
```

### Session Management
- **get_items()**: Load conversation history
- **add_items()**: Save user messages, assistant responses, tool calls
- Automatic by OpenAI Agents SDK

### Polling Loop Pattern
```python
# Race between three conditions:
done, _ = await asyncio.wait(
    {pending, cancel_task},
    timeout=15,  # Heartbeat
    return_when=asyncio.FIRST_COMPLETED,
)
# Check: cancel_signal? timeout? stream event?
```

---

## 📋 Architecture at a Glance

```
POST /chat {"message": "..."}
    ↓
chat/index.py::handler(context)
    ├─ Extract context (id, message, store, signal)
    ├─ Setup session (for history)
    ├─ Create agent + runner
    └─ Stream events:
        ├─ Convert LLM tokens → text_delta
        ├─ Detect tool calls → tool_called
        ├─ Send heartbeat → ping
        └─ Signal done → done

Response: SSE Stream
    text_delta
    text_delta
    tool_called
    ping (every 15s)
    done
```

---

## 🛠️ File Structure in agents-python/

```
agents-python/
├── chat/
│   ├── index.py              # Main /chat handler (streams SSE)
│   ├── stop.py               # /chat/stop (cancel mechanism)
│   ├── _model.py             # LLM config (private)
│   ├── _session.py           # EdgeOne session adapter (private)
│   └── _logger.py            # Logging utility (private)
└── history/
    └── index.py              # /history handler (retrieves messages)
```

**Key**: Files starting with `_` are private (not exposed as routes)

---

## 🔄 Request/Response Lifecycle

### Success Flow
```
1. Client sends POST /chat {"message": "..."}
2. Handler validates message
3. Handler creates session (loads history)
4. Handler runs agent with streaming
5. For each token/event, yields SSE event
6. Sends heartbeat ping every 15 seconds
7. On completion, yields "done" event
8. Response stream closes
```

### Cancellation Flow
```
1. User clicks Stop button
2. Client sends POST /chat/stop {"conversation_id": "..."}
3. Platform sets context.request.signal
4. /chat handler detects signal in polling loop
5. Handler breaks loop and cleanup
6. Yields "done" {"stopped": true}
```

### Error Flow
```
1. Handler detects error (missing message, etc.)
2. Yields "error" event with message
3. Yields "done" event to close stream
```

---

## 💡 Critical Implementation Details

### 1. Async Generator Return Type
- **Must return** `AsyncGenerator[str, None]`
- **Each yield** is a complete SSE event string
- Platform handles HTTP headers automatically

### 2. Heartbeat Mechanism
- Sends "ping" event every 15 seconds
- Prevents CDN/gateway timeouts
- Keeps connection alive during long operations

### 3. Cleanup is Critical
- Finally block must execute `agen.aclose()`
- Propagates GeneratorExit upstream
- Closes LLM API connection (aborts request)
- Prevents resource leaks

### 4. Session Adapter Pattern
- EdgeOneSession wraps platform KV store
- Implements OpenAI Agents SDK session protocol
- SDK automatically calls get_items() and add_items()
- Transparent history management

### 5. Cancel Signal
- Platform sets `context.request.signal` (asyncio.Event)
- Handler detects in polling loop
- Clean break and cleanup
- Client receives "done" {"stopped": true}

---

## 📖 Reading Order

**For first-time understanding:**
1. Start with this README
2. Read **ANALYSIS.md** sections 1-2
3. Study **DIAGRAMS.md** sections 1-3
4. Skim **ANALYSIS.md** section 5 (Response Format)
5. Review **IMPLEMENTATION_GUIDE.md** section 1 (Template)

**For implementation:**
1. Check **DIAGRAMS.md** section 8 (Routing)
2. Copy template from **IMPLEMENTATION_GUIDE.md** § 1
3. Reference patterns in **IMPLEMENTATION_GUIDE.md**
4. Test with mock context

**For debugging:**
1. Check **ANALYSIS.md** § 10 (Key Patterns)
2. Review **DIAGRAMS.md** (relevant section)
3. Look at **IMPLEMENTATION_GUIDE.md** (error handling)

---

## 🎓 Learning Goals

After reading this documentation, you should understand:

- ✅ How the handler function works (async generator)
- ✅ SSE event format and how it streams to client
- ✅ Generator/yield pattern and resource cleanup
- ✅ How context object provides platform integration
- ✅ Session adapter for automatic history management
- ✅ Async/await patterns and concurrent waiting
- ✅ Cancellation flow and abort mechanism
- ✅ Tool calling and semantic events
- ✅ Error handling and graceful degradation
- ✅ How to implement new handlers

---

## 🔗 Cross-References

### Topic: How handler returns data
- **ANALYSIS.md** § 3 (Handler Return Data)
- **DIAGRAMS.md** § 1 (Request/Response Flow)
- **IMPLEMENTATION_GUIDE.md** § 2 (SSE Helpers)

### Topic: Context interaction
- **ANALYSIS.md** § 4 (EdgeOne Context)
- **DIAGRAMS.md** § 4 (Context Object)
- **IMPLEMENTATION_GUIDE.md** § 3 (Session Adapter)

### Topic: Streaming mechanism
- **ANALYSIS.md** § 2.5 (Generator/Yield Pattern)
- **DIAGRAMS.md** § 3 (Async Generator Polling)
- **IMPLEMENTATION_GUIDE.md** § 6 (Asyncio Patterns)

### Topic: Session management
- **ANALYSIS.md** § 4.2 (Session Adapter)
- **DIAGRAMS.md** § 5 (Session Lifecycle)
- **IMPLEMENTATION_GUIDE.md** § 3 (Session Implementation)

### Topic: Cancellation
- **ANALYSIS.md** § 6 (Cancel Mechanism)
- **DIAGRAMS.md** § 10 (Cancellation Flow)
- **IMPLEMENTATION_GUIDE.md** § 11 (Stop Handler)

---

## 🚀 Next Steps

1. **Read ANALYSIS.md** for complete technical understanding
2. **Study DIAGRAMS.md** to visualize flows
3. **Reference IMPLEMENTATION_GUIDE.md** while coding
4. **Test locally** using mock context pattern
5. **Deploy to EdgeOne** when ready

---

## 📝 Document Statistics

- **ANALYSIS.md**: 1000+ lines, 12 major sections
- **DIAGRAMS.md**: 500+ lines, 10 detailed diagrams
- **IMPLEMENTATION_GUIDE.md**: 700+ lines, 13 code sections
- **Total**: 2200+ lines of comprehensive documentation

---

## ✨ Key Takeaways

1. **AsyncGenerator Pattern**: Handler returns async generator yielding SSE event strings
2. **SSE Streaming**: Uses standard Server-Sent Events format (event + data)
3. **Session Adapter**: Transparently manages conversation history via KV store
4. **Concurrent Control**: Races between stream events, cancel signals, and timeouts
5. **Resource Cleanup**: Critical finally block propagates cleanup upstream
6. **Platform Integration**: Context object provides conversation ID, store, and signals
7. **Tool Calling**: Semantic events separate from token deltas for UI indicators
8. **Graceful Degradation**: Works with or without storage, session, or cancel signal

---

Generated: 2024-2025
Covers: OpenAI Agent Starter with EdgeOne Pages Functions

