================================================================================
NINA SDK — API CONTRACT SPECIFICATION
Version: 1.0.0
Status: Draft
Scope: Runtime-agnostic (Node.js, Python, or any host runtime)
================================================================================

DESIGN PRINCIPLES
--------------------------------------------------------------------------------
P1. NINA is an action layer, not a chatbot. Every conversation turn resolves
    to one of: an action invocation, a clarification request, or a direct
    informational response.
P2. No exceptions. Every public method returns a result object containing
    either `data` or `error`. The host application never wraps NINA calls
    in try/catch (or equivalent).
P3. Actions are self-describing. The LLM decides when to invoke an action
    based solely on the action's name, description, and inputSchema. NINA
    contains zero hardcoded intent rules.
P4. No framework lock-in. The contract is defined in terms of plain data
    structures (JSON-serializable) and language-native function references
    for handlers. Naming below uses camelCase; language bindings MAY adapt
    to local conventions (e.g., snake_case in Python) but MUST preserve
    semantics.

UNIVERSAL RESULT ENVELOPE
--------------------------------------------------------------------------------
Every public method returns:

  {
    ok:      boolean,          // true if operation succeeded
    data:    <method-specific payload> | null,
    error:   <ErrorObject> | null    // see ERROR OBJECT SCHEMA
  }

Exactly one of `data` / `error` is non-null.


================================================================================
1. nina.init(config)
================================================================================

PURPOSE
  Initializes a NINA instance. Must be called before any other method.
  Idempotent per instance: calling twice returns NINA_ALREADY_INITIALIZED.

CONFIG SHAPE
  {
    llm: {                                  // REQUIRED
      provider:    string,                  // "openai" | "anthropic" | "custom"
      model:       string,                  // e.g. "claude-sonnet-4"
      apiKey:      string,                  // ignored if provider = "custom"
      endpoint:    string?,                 // override base URL
      adapter:     function?,              // REQUIRED if provider = "custom".
                                            // Signature: (promptPayload) ->
                                            // LLMCompletion (see §7 note)
      temperature: number?,                 // default 0.2 (action precision)
      maxTokens:   number?                  // default 1024
    },
    session: {                              // OPTIONAL
      store:       "memory" | StoreAdapter, // default "memory"
                                            // StoreAdapter: { get(id), set(id,
                                            // state), delete(id) } — async OK
      ttlSeconds:  number?,                 // default 1800; 0 = no expiry
      maxTurns:    number?                  // history window, default 20
    },
    behavior: {                             // OPTIONAL
      confidenceThreshold: number?,         // 0..1, default 0.75. Below this,
                                            // NINA asks for clarification
                                            // instead of calling an action
      maxClarifications:   number?,         // per intent, default 2
      allowChitchat:       boolean?,        // default true. If false, off-task
                                            // messages return intent
                                            // "unsupported"
      language:            string?          // BCP-47 hint, default "auto"
    },
    identity: {                             // OPTIONAL
      agentName:   string?,                 // default "NINA"
      persona:     string?,                 // injected into system prompt
      systemContext: string?                // domain facts (e.g. store name,
                                            // business hours)
    },
    hooks: {                                // OPTIONAL — all fire-and-observe
      onActionCall:   function?,            // (actionName, input, sessionId)
      onActionResult: function?,            // (actionName, result, sessionId)
      onError:        function?             // (errorObject, sessionId)
    }
  }

RETURNS (data)
  {
    instanceId:   string,                   // UUID for this NINA instance
    llmReady:     boolean,                  // connectivity verified
    sessionStore: "memory" | "custom",
    version:      string
  }

ERRORS (returned, never thrown)
  NINA_CONFIG_INVALID          — config fails structural validation;
                                 error.details lists each bad path
  NINA_LLM_UNREACHABLE         — provider handshake failed
  NINA_LLM_AUTH_FAILED         — apiKey rejected
  NINA_ADAPTER_INVALID         — provider "custom" without valid adapter fn
  NINA_STORE_INVALID           — StoreAdapter missing get/set/delete
  NINA_ALREADY_INITIALIZED     — init called twice on same instance


================================================================================
2. nina.register(action)
================================================================================

PURPOSE
  Registers one developer-defined capability. May be called any time after
  init, including at runtime (hot registration). Also accepts an array of
  actions; result is per-action in data.registered / data.failed.

ACTION DEFINITION SHAPE
  {
    name: string,             // REQUIRED. ^[a-z][a-z0-9_]{2,63}$
                              // Unique per instance. Verb-first recommended
                              // (e.g. "track_order", "cancel_subscription")

    description: string,      // REQUIRED. 20–500 chars. MUST state, in plain
                              // language: what the action does, when it
                              // should be used, and when it should NOT be
                              // used. This is the LLM's ONLY routing signal
                              // besides the schema (Principle P3).

    inputSchema: object,      // REQUIRED. JSON Schema (draft 2020-12 subset:
                              // type, properties, required, enum, items,
                              // description, default, minimum, maximum,
                              // minLength, maxLength, format).
                              // Every property MUST have a description.
                              // Root type MUST be "object".

    handler: function,        // REQUIRED. (input, context) -> any
                              // input:   validated object matching inputSchema
                              // context: { sessionId, userMessage, locale,
                              //            sessionData }
                              // May be sync or async. Return value MUST be
                              // JSON-serializable. To signal a domain failure,
                              // return { _error: { code, message } } — NINA
                              // surfaces it as ACTION_DOMAIN_ERROR.

    confirmation: boolean?,   // default false. If true, NINA asks the user
                              // to confirm before invoking (for destructive
                              // or financial operations).

    timeoutMs: number?,       // default 10000. Handler exceeding this yields
                              // ACTION_TIMEOUT.

    examples: string[]?       // 0–5 sample user utterances. Injected into
                              // the system prompt to improve routing. Not
                              // used as hard rules.
  }

VALIDATION RULES (evaluated in order; first failure wins per action)
  V1. name matches pattern and is not reserved ("chat","session","init",
      "register","help")
  V2. name not already registered          -> NINA_ACTION_DUPLICATE
  V3. description length within bounds     -> NINA_ACTION_DESCRIPTION_INVALID
  V4. inputSchema parses as valid JSON Schema subset, root = object,
      all properties described             -> NINA_ACTION_SCHEMA_INVALID
  V5. handler is callable                  -> NINA_ACTION_HANDLER_INVALID
  V6. instance is initialized              -> NINA_NOT_INITIALIZED

RETURNS (data)
  {
    name:        string,
    registered:  true,
    actionCount: number      // total actions now registered
  }

ERROR BEHAVIOR
  Registration is atomic per action. A failed registration leaves the
  registry untouched. Batch registration is NOT atomic across the batch;
  data reports { registered: string[], failed: [{name, error}] }.


================================================================================
3. nina.chat(userMessage, sessionId)
================================================================================

PURPOSE
  The core entry point. Takes one natural-language message, resolves intent,
  optionally invokes exactly one action (v1 supports single-action turns;
  multi-step plans resolve across turns via session state), and returns a
  structured turn result.

INPUTS
  userMessage: string        // REQUIRED. 1–8000 chars after trim.
  sessionId:   string        // REQUIRED. Developer-supplied opaque ID.
                             // Unknown IDs implicitly create a session.

PROCESSING CONTRACT (guaranteed order)
  1. Validate inputs.
  2. Load session (create if absent).
  3. Build system prompt (see §6) with registered action manifest + history.
  4. LLM resolves: intent, target action (or none), extracted inputs,
     confidence, missing fields.
  5. If confidence < behavior.confidenceThreshold OR required fields
     missing -> return clarification turn (NO action invoked).
  6. If action.confirmation = true and not yet confirmed in session ->
     return confirmation request turn (NO action invoked).
  7. Validate extracted inputs against inputSchema. On mismatch -> retry
     extraction once, then clarification turn.
  8. Invoke handler with timeout. Capture result or error.
  9. LLM composes naturalLanguageResponse from action result.
 10. Persist turn to session. Return.

RETURNS (data) — the Turn object
  {
    turnId:        string,            // UUID
    sessionId:     string,

    intent:        string,            // resolved intent label. One of:
                                      //   action name (e.g. "track_order")
                                      //   "clarification"  — NINA needs info
                                      //   "confirmation"   — awaiting user OK
                                      //   "chitchat"       — conversational,
                                      //                      no action match
                                      //   "unsupported"    — no capability
                                      //                      covers the ask

    actionCalled:  string | null,     // action name if a handler ran

    actionInput:   object | null,     // validated input passed to handler

    actionResult:  any | null,        // raw JSON-serializable handler return
                                      // (null if no action ran or it failed)

    actionError:   ErrorObject | null,// ACTION_* error if handler failed;
                                      // turn still returns ok:true at the
                                      // envelope level — the conversation
                                      // succeeded even if the action did not

    naturalLanguageResponse: string,  // ALWAYS present. The text to show
                                      // the end user.

    confidence:    number,            // 0..1, LLM's routing confidence

    clarificationNeeded: {            // null unless intent = "clarification"
      missingFields: string[],        // schema paths still required
      question:      string,          // suggested question (mirrors
                                      // naturalLanguageResponse)
      pendingAction: string           // action awaiting completion
    } | null,

    usage: {                          // optional, provider-dependent
      promptTokens:     number?,
      completionTokens: number?,
      latencyMs:        number
    }
  }

ERRORS (envelope-level — turn could not be produced at all)
  NINA_NOT_INITIALIZED
  NINA_MESSAGE_INVALID          — empty / over length
  NINA_SESSION_ID_INVALID       — non-string or empty
  NINA_NO_ACTIONS_REGISTERED    — chat called with empty registry and
                                  behavior.allowChitchat = false
  NINA_LLM_UNREACHABLE
  NINA_LLM_RATE_LIMITED         — error.details.retryAfterMs provided
  NINA_LLM_RESPONSE_MALFORMED   — model output unparseable after 2 retries
  NINA_SESSION_STORE_FAILURE    — custom store get/set failed

  Note: handler failures (ACTION_TIMEOUT, ACTION_RUNTIME_ERROR,
  ACTION_DOMAIN_ERROR) are NOT envelope errors. They appear in
  turn.actionError, and naturalLanguageResponse explains the failure
  to the end user gracefully.


================================================================================
4. nina.session(sessionId)
================================================================================

PURPOSE
  Inspect and manage a session. Returns a session view plus management
  operations. Read operations never create a session.

RETURNS (data) — the Session object
  {
    sessionId:    string,
    createdAt:    string,             // ISO 8601
    lastActiveAt: string,
    expiresAt:    string | null,      // null if ttlSeconds = 0
    turnCount:    number,

    history: [                        // bounded by session.maxTurns
      {
        turnId:    string,
        role:      "user" | "nina",
        content:   string,            // userMessage or naturalLanguageResponse
        intent:    string | null,
        actionCalled: string | null,
        timestamp: string
      }
    ],

    pending: {                        // null if nothing in flight
      type:          "clarification" | "confirmation",
      action:        string,
      collectedInput: object,         // fields gathered so far
      missingFields:  string[],
      attemptsUsed:   number          // vs behavior.maxClarifications
    } | null,

    data: object                      // developer scratch space. Persisted
                                      // with the session; passed to handlers
                                      // as context.sessionData
  }

EXPOSED OPERATIONS (each returns the universal envelope)
  session.get(sessionId)                   -> Session object
  session.setData(sessionId, object)       -> merged data (shallow merge)
  session.clearPending(sessionId)          -> Session object (cancels
                                              clarification/confirmation flow)
  session.reset(sessionId)                 -> { sessionId, reset: true }
                                              (clears history + pending,
                                              keeps data)
  session.delete(sessionId)                -> { sessionId, deleted: true }

ERRORS
  NINA_NOT_INITIALIZED
  NINA_SESSION_NOT_FOUND
  NINA_SESSION_ID_INVALID
  NINA_SESSION_DATA_INVALID     — setData payload not JSON-serializable
  NINA_SESSION_STORE_FAILURE


================================================================================
5. ERROR OBJECT SCHEMA
================================================================================

SHAPE
  {
    code:        string,        // stable machine-readable code (below)
    message:     string,        // human-readable, English, no PII
    category:    "config" | "registration" | "input" | "llm"
                 | "action" | "session" | "internal",
    retryable:   boolean,       // safe to retry the same call as-is
    details:     object | null, // code-specific structured context
    timestamp:   string         // ISO 8601
  }

COMPLETE ERROR CATALOG
  Code                          Category      Retryable  Message template
  ----------------------------------------------------------------------------
  NINA_CONFIG_INVALID           config        no   "Invalid config: {paths}."
  NINA_ADAPTER_INVALID          config        no   "Custom provider requires a
                                                    callable adapter."
  NINA_STORE_INVALID            config        no   "Session store must
                                                    implement get, set, delete."
  NINA_ALREADY_INITIALIZED      config        no   "Instance already
                                                    initialized."
  NINA_NOT_INITIALIZED          config        no   "Call nina.init() first."
  NINA_ACTION_NAME_INVALID      registration  no   "Action name '{name}' must
                                                    match ^[a-z][a-z0-9_]{2,63}$
                                                    and not be reserved."
  NINA_ACTION_DUPLICATE         registration  no   "Action '{name}' is already
                                                    registered."
  NINA_ACTION_DESCRIPTION_INVALID registration no  "Description must be 20–500
                                                    characters."
  NINA_ACTION_SCHEMA_INVALID    registration  no   "inputSchema invalid at
                                                    {path}: {reason}."
  NINA_ACTION_HANDLER_INVALID   registration  no   "Handler must be callable."
  NINA_MESSAGE_INVALID          input         no   "userMessage must be a
                                                    non-empty string ≤ 8000
                                                    chars."
  NINA_SESSION_ID_INVALID       input         no   "sessionId must be a
                                                    non-empty string."
  NINA_NO_ACTIONS_REGISTERED    input         no   "No actions registered and
                                                    chitchat is disabled."
  NINA_LLM_UNREACHABLE          llm           yes  "Could not reach LLM
                                                    provider: {reason}."
  NINA_LLM_AUTH_FAILED          llm           no   "LLM provider rejected
                                                    credentials."
  NINA_LLM_RATE_LIMITED         llm           yes  "Rate limited. Retry after
                                                    {retryAfterMs} ms."
  NINA_LLM_RESPONSE_MALFORMED   llm           yes  "Model returned unparseable
                                                    output after retries."
  ACTION_TIMEOUT                action        yes  "Action '{name}' exceeded
                                                    {timeoutMs} ms."
  ACTION_RUNTIME_ERROR          action        no   "Action '{name}' raised:
                                                    {summary}."   // details
                                                    holds sanitized stack info
  ACTION_DOMAIN_ERROR           action        no   "{developer-provided
                                                    message}"     // from
                                                    handler's _error return
  ACTION_INPUT_REJECTED         action        no   "Extracted input failed
                                                    schema validation at
                                                    {path}."
  NINA_SESSION_NOT_FOUND        session       no   "No session '{id}'."
  NINA_SESSION_DATA_INVALID     session       no   "Session data must be
                                                    JSON-serializable."
  NINA_SESSION_STORE_FAILURE    session       yes  "Session store operation
                                                    '{op}' failed."
  NINA_INTERNAL                 internal      yes  "Unexpected internal error.
                                                    Ref: {traceId}."


================================================================================
6. INTERNAL SYSTEM PROMPT TEMPLATE
================================================================================

Placeholders use {{double_braces}}. The template is rendered fresh on every
chat() turn. The model is required to respond with a single JSON object
(the Resolution object, schema appended to the prompt).

--------------------------------------------------------------------------------
You are {{agent_name}}, an action-resolution agent embedded inside a host
application. You are NOT a general-purpose assistant. Your only job is to
map the user's message to one of the registered actions below, or to ask
for missing information, or to respond conversationally when no action
applies.

{{#if persona}}
PERSONA
{{persona}}
{{/if}}

{{#if system_context}}
DOMAIN CONTEXT (facts about the host system — treat as ground truth)
{{system_context}}
{{/if}}

REGISTERED ACTIONS
You may select at most ONE action per turn. Each action lists when it
should and should not be used. Never invent actions. Never fabricate
parameter values the user did not state or that cannot be inferred from
conversation history.

{{#each actions}}
---
action: {{name}}
description: {{description}}
requires_confirmation: {{confirmation}}
input_schema:
{{input_schema_json}}
{{#if examples}}
example user requests:
{{#each examples}}  - "{{this}}"
{{/each}}
{{/if}}
{{/each}}
---

CONVERSATION HISTORY (most recent last; up to {{max_turns}} turns)
{{#each history}}
[{{role}}] {{content}}
{{/each}}

{{#if pending}}
PENDING FLOW
The user is mid-flow for action "{{pending.action}}"
({{pending.type}}). Already collected: {{pending.collected_input_json}}.
Still missing: {{pending.missing_fields}}. Interpret the new message
primarily as a continuation of this flow, but allow the user to change
topic or cancel.
{{/if}}

CURRENT USER MESSAGE
{{user_message}}

DECISION RULES
1. Select an action ONLY if the user's intent clearly matches its
   description. When uncertain, prefer clarification over a wrong call.
2. Extract input values strictly conforming to the action's input_schema.
   If any required field is missing or ambiguous, do NOT guess: set
   resolution to "clarify" and list missing_fields.
3. If the matched action has requires_confirmation: true and the user has
   not explicitly confirmed in this flow, set resolution to "confirm".
4. If the message is conversational and {{allow_chitchat}} is true,
   set resolution to "chitchat" and reply briefly, steering toward what
   you can do.
5. If no action covers the request, set resolution to "unsupported" and
   say so honestly. Never pretend a capability exists.
6. Respond to the user in {{language}} (or mirror the user's language
   if set to "auto").
7. Report confidence as your honest probability (0.0–1.0) that the chosen
   resolution and extracted inputs are correct.

OUTPUT FORMAT
Respond with ONLY a single JSON object, no prose, matching:
{
  "resolution": "action" | "clarify" | "confirm" | "chitchat" | "unsupported",
  "action": string | null,
  "input": object | null,
  "missing_fields": string[],
  "confidence": number,
  "user_reply": string
}
--------------------------------------------------------------------------------

POST-ACTION COMPOSITION PROMPT (second LLM call, after handler returns)
--------------------------------------------------------------------------------
You are {{agent_name}}. The action "{{action_name}}" was executed for the
user's request: "{{user_message}}".

Result ({{result_status}}):
{{action_result_json}}

Write a concise reply to the user in {{language}} conveying this result.
Do not expose internal field names, stack traces, or system details. If
the result indicates failure, apologize briefly, state what went wrong in
plain terms, and suggest a next step. Respond with ONLY the reply text.
--------------------------------------------------------------------------------

================================================================================
END OF SPECIFICATION
================================================================================
