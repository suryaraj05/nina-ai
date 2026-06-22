"""Public type definitions for NINA (PEP 561). Mirrors spec v1.0.0 exactly.
Optional fields use NotRequired; nullable fields use Optional."""
import sys
from typing import Any, Callable, Generic, List, Literal, Optional, TypeVar, Union

if sys.version_info >= (3, 11):
    from typing import NotRequired, TypedDict
else:  # NotRequired / generic TypedDict land in typing on 3.11
    from typing_extensions import NotRequired, TypedDict

T = TypeVar("T")


class LLMConfig(TypedDict):
    provider: str                      # "openai" | "anthropic" | "ollama" | "custom"
    model: str
    apiKey: NotRequired[str]           # required for openai/anthropic; optional for ollama
    endpoint: NotRequired[str]
    adapter: NotRequired[Callable[..., Any]]
    temperature: NotRequired[float]
    maxTokens: NotRequired[int]


class SessionConfig(TypedDict, total=False):
    store: Union[str, Any]             # "memory" | StoreAdapter
    ttlSeconds: float
    maxTurns: int


class BehaviorConfig(TypedDict, total=False):
    confidenceThreshold: float
    maxClarifications: int
    allowChitchat: bool
    language: str


class IdentityConfig(TypedDict, total=False):
    agentName: str
    persona: str
    systemContext: str


class HooksConfig(TypedDict, total=False):
    onActionCall: Callable[[str, dict, str], Any]
    onActionResult: Callable[[str, Any, str], Any]
    onError: Callable[[dict, str], Any]


class NinaConfig(TypedDict):
    llm: LLMConfig
    session: NotRequired[SessionConfig]
    behavior: NotRequired[BehaviorConfig]
    identity: NotRequired[IdentityConfig]
    hooks: NotRequired[HooksConfig]
    debug: NotRequired[bool]


class ActionDefinition(TypedDict):
    name: str
    description: str
    inputSchema: dict
    handler: Callable[..., Any]
    confirmation: NotRequired[bool]
    timeoutMs: NotRequired[int]
    examples: NotRequired[List[str]]


class ErrorObject(TypedDict):
    code: str
    message: str
    category: Literal["config", "registration", "input", "llm",
                      "action", "session", "internal"]
    retryable: bool
    details: Optional[dict]
    timestamp: str


class ClarificationNeeded(TypedDict):
    missingFields: List[str]
    question: str
    pendingAction: str


class Usage(TypedDict, total=False):
    promptTokens: int
    completionTokens: int
    latencyMs: int


class Turn(TypedDict):
    turnId: str
    sessionId: str
    intent: str
    actionCalled: Optional[str]
    actionInput: Optional[dict]
    actionResult: Any
    actionError: Optional[ErrorObject]
    naturalLanguageResponse: str
    confidence: float
    clarificationNeeded: Optional[ClarificationNeeded]
    reasoningUsed: bool
    reasoningSummary: Optional[str]
    usage: Usage


class HistoryEntry(TypedDict):
    turnId: str
    role: Literal["user", "nina"]
    content: str
    intent: Optional[str]
    actionCalled: Optional[str]
    timestamp: str


class PendingFlow(TypedDict):
    type: Literal["clarification", "confirmation"]
    action: str
    collectedInput: dict
    missingFields: List[str]
    attemptsUsed: int
    clarificationStrategy: NotRequired[Optional[str]]


class Session(TypedDict):
    sessionId: str
    createdAt: str
    lastActiveAt: str
    expiresAt: Optional[str]
    turnCount: int
    history: List[HistoryEntry]
    pending: Optional[PendingFlow]
    data: dict


class ReferenceMap(TypedDict):
    lastSearchResults: List[dict]
    lastSingleItem: Optional[dict]
    cartContents: Optional[dict]
    lastActionResult: Optional[dict]


class NinaResult(TypedDict, Generic[T]):
    ok: bool
    data: Optional[T]
    error: Optional[ErrorObject]
    warnings: NotRequired[List[Any]]
