# Google Gemini Web Internal Architecture & Reverse-Engineering

This document details the internal protocols, data structures, and RPC mechanics of Google Gemini Web (`gemini.google.com`), reverse-engineered from live browser network traffic (`HAR.har` and `HAR baru.har` - 189.9 MB).

---

## 1. Protocol Architecture: WebChannel & Protobuf RPC

Modern Google Gemini Web communicates via two distinct channels:
1. **`batchexecute` (`/_/BardChatUi/data/batchexecute`)**:
   - Standard Google RPC batch endpoint used for user status, quota inquiries, conversation listing, and preference updates.
   - Payloads are nested JSON arrays (JSPB format).
2. **`WebChannel` (`geminiweb-pa.clients6.google.com/v1/processSession`)**:
   - Google's low-latency streaming protocol over HTTP POST and long-polling HTTP GET streams (`TYPE=xmlhttp`, `RID=rpc`).
   - Payloads are raw Base64-encoded Protocol Buffers (`application/x-protobuf`).
3. **`StreamGenerate` (`/_/BardChatUi/data/assistant.lamda.BardFrontendService/StreamGenerate`)**:
   - The direct streaming inference endpoint utilized by this bridge daemon, mapping 1-to-1 with WebChannel's protobuf fields.

---

## 2. The 2×2 Operational Matrix

During live analysis of the 189.9 MB HAR capture, four sequential sessions demonstrated the complete 2×2 operational matrix:

```
                      ┌─────────────────────────────┬─────────────────────────────┐
                      │          4 Hydrogen         │           4 Argon           │
┌─────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ Mode CHAT           │ SESSION 1 (Entry 309 - 352) │ SESSION 2 (Entry 394 - 428) │
│ (Field 50 = 0)      │ Turn 1: "hai"               │ Turn 1: "hai"               │
│                     │ Turn 2: "oke gas"           │ Turn 2: "oke gas"           │
├─────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ Mode TASK           │ SESSION 3 (Entry 476 - 537) │ SESSION 4 (Entry 612 - 682) │
│ (Field 50 = 40)     │ Turn 1: "why white cat      │ Turn 1: "why orange called  │
│                     │         dumb?"              │         orange?"            │
│                     │ Turn 2: "great"             │ Turn 2: "why not apple      │
│                     │                             │         called red?"        │
└─────────────────────┴─────────────────────────────┴─────────────────────────────┘
```

### Detailed Breakdown of Captured Sessions

| Session | Mode | Model | `Field 50` (`featureMode`) | Model ID / Number | Verified Multi-Turn Flow |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Session 1** | **Chat Mode** | **4 Hydrogen** | **`0`** (`UNSPECIFIED`) | `56fdd199312815e2` / `1` | Turn 1: `"hai"` $\rightarrow$ Turn 2: `"oke gas"` |
| **Session 2** | **Chat Mode** | **4 Argon** | **`0`** (`UNSPECIFIED`) | String `"argon"` / **`8`** | Turn 1: `"hai"` $\rightarrow$ Turn 2: `"oke gas"` |
| **Session 3** | **Task Mode** | **4 Hydrogen** | **`40`** (`FEATURE_MODE_REMY`) | `56fdd199312815e2` / `1` | Turn 1: `"why white cat dumb?"` $\rightarrow$ Turn 2: `"great"` |
| **Session 4** | **Task Mode** | **4 Argon** | **`40`** (`FEATURE_MODE_REMY`) | String `"argon"` / **`8`** | Turn 1: `"why orange called orange?"` $\rightarrow$ Turn 2: `"why not apple called red?"` |

---

## 3. UI Mode Transition: `[ Chat | Task ]` Toggle

When a user clicks the toggle pill between `Chat` and `Task` in the Google Gemini web interface:
1. **Preference Persistence**: The browser fires RPC `L5adhe` (`UPDATE_USER_PREFERENCES`) with the active mode choice.
2. **Feature Mode Flag**:
   - `Chat`: Dispatches requests with `Field 50 = 0` (`FEATURE_MODE_UNSPECIFIED`).
   - `Task`: Dispatches requests with `Field 50 = 40` (`FEATURE_MODE_REMY`).
3. **UI Adaptation**:
   - `ZeroState` component renders heading *"Tag me in! What's next?"* and input placeholder *"+ Describe task"*.
   - Available models are strictly constrained to **4 Hydrogen** (Everyday help) and **4 Argon** (Code & analysis).
   - Manual thinking sliders are hidden because the internal Remy agent loop handles planning autonomously.

---

## 4. Multi-Turn Continuation & State Retention

In Google Gemini's database, multi-turn continuity is established by linking turn metadata:
- **Turn 1 (Bootstrap)**:
  - `Parent`: `None`
  - Server issues new conversation ID (`cid`) and reply candidate ID (`rcid`).
- **Turn 2+ (Continuation)**:
  - `Parent`: `[cid, rid, rcid]` of Turn 1.
  - Request body binds `Field 72` (in protobuf) or `inner_req_list[71]` to `[cid, None, None, None, None, None, None, []]`.
  - The turn is appended to the existing thread rather than spawning orphan conversations.

---

## 5. Official Model Header Formats

### 4 Argon (`Code & analysis`) Header Specification
From decoded `x-goog-ext-525001261-bin`:
- `Field 1`: `1`
- `Field 5`: `"argon"`
- `Field 7`: `"en"`
- `Field 8`: `0`
- `Field 9`: `[4, 33, 22, 5, 6, 8, 16, 19, 20, 38]`
- `Field 12`: `2` (Account capacity)
- `Field 15`: `8` (Argon internal model number)
- `Field 16`: `1`
- `Field 17`: `<session_uuid>`
- `Field 18`: `["boq_gemini-web-uiserver_20261113.11_p0"]`
- `Field 20`: Client timezone info
- `Field 25`: `"argon"`

### 4 Hydrogen (`Everyday help`) Header Specification
- `Field 5`: `"56fdd199312815e2"`
- `Field 15`: `1` (Hydrogen internal model number)
