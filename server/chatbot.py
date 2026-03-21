"""Ralphy chatbot: requirement extraction via OpenCode.

Each chat message spawns `opencode run` with the Ralphy system prompt.
Uses the same runtime, model, and API config as the loop agents.
No separate API key needed.
"""

import json
import logging
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

import server.db as db

logger = logging.getLogger(__name__)

OPENCODE_CMD = shutil.which("opencode") or str(Path.home() / ".opencode" / "bin" / "opencode")
DEFAULT_MODEL = "opencode-go/kimi-k2.5"

DIMENSIONS = [
    "functional",       # what does it do?
    "technical_stack",  # language, framework, infra
    "data_model",       # entities, relationships, storage
    "auth",             # authentication, authorization, roles
    "deployment",       # where/how it runs, env vars, services
    "testing",          # test strategy, coverage expectations
    "edge_cases",       # error handling, constraints, limits
]

# -- Validation constants ---
MAX_DELTA = 20
SHORT_MSG_LEN = 30
SHORT_MSG_DELTA = 5
EMA_ALPHA = 0.7

BASE_WEIGHTS: dict[str, float] = {
    "functional": 2.0,
    "technical_stack": 1.5,
    "data_model": 1.5,
    "auth": 1.0,
    "deployment": 1.0,
    "testing": 1.0,
    "edge_cases": 1.0,
}
READINESS_THRESHOLD = 85
MIN_DIM_SCORE = 70
MIN_QUESTIONS = 10
RELEVANCE_CUTOFF = 0.3


def _get_phase(user_msg_count: int) -> int:
    if user_msg_count <= 3:
        return 1
    if user_msg_count <= 7:
        return 2
    if user_msg_count <= 10:
        return 3
    return 4


def _phase_cap(user_msg_count: int) -> int:
    if user_msg_count <= 3:
        return 40
    if user_msg_count <= 7:
        return 70
    if user_msg_count <= 10:
        return 90
    return 100


def _clamp_score(new: int, prev: int, phase_max: int, msg_len: int) -> int:
    clamped = min(new, phase_max)
    max_d = SHORT_MSG_DELTA if msg_len < SHORT_MSG_LEN else MAX_DELTA
    if clamped > prev + max_d:
        clamped = prev + max_d
    return max(0, min(100, clamped))


def _smooth(new: int, prev: int) -> int:
    if new <= prev:
        return new
    return round(EMA_ALPHA * new + (1 - EMA_ALPHA) * prev)


def _compute_readiness(confidence: dict[str, int], relevance: dict[str, float]) -> float:
    num = sum(confidence.get(d, 0) * BASE_WEIGHTS[d] * relevance.get(d, 1.0) for d in DIMENSIONS)
    den = sum(BASE_WEIGHTS[d] * relevance.get(d, 1.0) for d in DIMENSIONS)
    return num / den if den else 0.0


def _is_ready(state: "ChatState") -> bool:
    if state.user_msg_count < MIN_QUESTIONS:
        return False
    if state.weighted_readiness < READINESS_THRESHOLD:
        return False
    for d in DIMENSIONS:
        if state.relevance.get(d, 1.0) > RELEVANCE_CUTOFF:
            if state.confidence.get(d, 0) < MIN_DIM_SCORE:
                return False
    return True


# -- Tool helpers -----------------------------------------------------------


def _total_user_chars(state: "ChatState") -> int:
    return sum(len(m["content"]) for m in state.messages if m["role"] == "user")


def _weak_dimensions(state: "ChatState", n: int = 3) -> str:
    """Format the N weakest relevant dimensions for tool prompts."""
    relevant = [
        (d, state.confidence.get(d, 0))
        for d in DIMENSIONS
        if state.relevance.get(d, 1.0) > RELEVANCE_CUTOFF
    ]
    weakest = sorted(relevant, key=lambda x: x[1])[:n]
    return ", ".join(f"{d} ({v}%)" for d, v in weakest)


def _conversation_summary(state: "ChatState", max_messages: int = 10) -> str:
    """Build conversation context string for tool prompts."""
    msgs = state.messages[-max_messages:] if max_messages else state.messages
    lines = []
    for msg in msgs:
        role = "User" if msg["role"] == "user" else "Ralphy"
        content = msg["content"]
        if msg["role"] == "assistant":
            try:
                parsed = json.loads(content)
                content = parsed.get("message", content)
            except (json.JSONDecodeError, TypeError):
                pass
        lines.append(f"**{role}:** {content}")
    return "\n\n".join(lines)


TOOL_CONFIGS: dict[str, dict] = {
    "brainstorm": {
        "mode": "inject",
        "model": None,  # use default
        "gate": lambda s: _total_user_chars(s) >= 120,
        "gate_reason": "Need 120+ characters of conversation first",
        "system": """\
You are a brainstorming assistant for a software project.

## Context
{conversation}

## Current weak dimensions
{weak_dims}

## Task
Generate exactly 5 creative feature ideas or angles the user hasn't explored yet.
Each idea should help clarify the weak dimensions listed above.
Format as a numbered list. Be specific to THIS project. No preamble.""",
    },
    "expand": {
        "mode": "inject",
        "model": None,  # use default
        "gate": lambda s: _total_user_chars(s) >= 120,
        "gate_reason": "Need 120+ characters of conversation first",
        "system": """\
You are an idea expansion specialist for software projects.

## Context
{conversation}

## Current weak dimensions
{weak_dims}

## Task
Expand the project concept with:
- Specific use cases (2-3)
- User personas (1-2)
- Data flow descriptions
- Integration points

Provide exactly 3 use cases and 2 user personas.
Focus on the weak dimensions listed. Format as a structured list. Be specific.""",
    },
    "refine": {
        "mode": "edit",
        "model": "opencode-go/kimi-k2.5",  # fast model for refinement
        "gate": lambda s: s.user_msg_count >= 1,
        "gate_reason": "Need at least 1 message to refine",
        "system": """\
You are a prompt refinement specialist.

## Original text
{original}

## Project context (for reference)
{conversation}

## Task
Rewrite the original text to be:
- More specific and detailed
- Clearer about requirements and constraints
- Better structured for an AI requirements extractor

Return ONLY the improved text. No preamble, no explanation, no quotes.""",
    },
    "architect": {
        "mode": "inject",
        "model": None,  # use default (bigger model)
        "gate": lambda s: _get_phase(s.user_msg_count) >= 2,
        "gate_reason": "Need Phase 2+ (4+ messages) for architecture suggestions",
        "system": """\
You are a system design advisor.

## Context
{conversation}

## Current confidence scores
{confidence_summary}

## Current weak dimensions
{weak_dims}

## Task
Based on the requirements gathered, suggest:
1. Architecture pattern (monolith, microservices, serverless, etc.) with rationale
2. Database choice and schema approach
3. Auth strategy (or note if not needed)
4. Deployment recommendation
5. Key technical decisions

Be specific to THIS project. Format as a numbered list with brief rationale for each.""",
    },
}


# Validate all tool prompts can be formatted with expected kwargs
_TOOL_FORMAT_KWARGS = {
    "conversation": "", "weak_dims": "", "confidence_summary": "", "original": "",
}
for _tool_id, _cfg in TOOL_CONFIGS.items():
    try:
        _cfg["system"].format(**_TOOL_FORMAT_KWARGS)
    except KeyError as e:
        raise ValueError(f"Tool '{_tool_id}' has unknown placeholder: {e}")


async def run_tool(
    session_id: str,
    tool: str,
    context: str = "",
    *,
    session_dir: Path | None = None,
) -> dict:
    """Run a toolset tool. Returns {result, mode, tool, elapsed_ms, model}. Does NOT modify chat state."""
    if tool not in TOOL_CONFIGS:
        raise ValueError(f"Unknown tool: {tool}")

    state = get_chat_state(session_id)
    config = TOOL_CONFIGS[tool]

    # Rate limit (separate from chat rate limit)
    now = time.time()
    if now - state.last_tool_time < 3.0:
        raise RuntimeError("Rate limited. Wait a moment.")
    state.last_tool_time = now

    # Gate check
    if not config["gate"](state):
        raise RuntimeError(config["gate_reason"])

    # Build prompt
    conversation = _conversation_summary(state)
    weak_dims = _weak_dimensions(state)
    confidence_summary = ", ".join(
        f"{d}: {state.confidence.get(d, 0)}%" for d in DIMENSIONS
    )

    # For refine: use provided context (stripped) or last user message
    original = context.strip() if context else ""
    if tool == "refine" and not original:
        user_msgs = [m for m in state.messages if m["role"] == "user"]
        original = user_msgs[-1]["content"] if user_msgs else ""

    system_prompt = config["system"].format(
        conversation=conversation,
        weak_dims=weak_dims,
        confidence_summary=confidence_summary,
        original=original,
    )

    # Conditionally remove auth section for architect if auth is irrelevant
    if tool == "architect":
        auth_relevant = state.relevance.get("auth", 1.0) > RELEVANCE_CUTOFF
        if not auth_relevant:
            system_prompt = system_prompt.replace(
                "3. Auth strategy (or note if not needed)\n", ""
            )

    # Model override per tool
    model = config.get("model")

    # Call opencode
    cwd = str(session_dir or state.session_dir) if (session_dir or state.session_dir) else None
    cmd = [OPENCODE_CMD, "run", system_prompt, "--format", "json"]
    if model:
        cmd.extend(["--model", model])

    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=120, cwd=cwd,
        )
        output = result.stdout.strip()
    except subprocess.TimeoutExpired:
        raise RuntimeError("Tool timed out (120s)")
    except FileNotFoundError:
        raise RuntimeError("OpenCode not found on PATH")
    elapsed_ms = int((time.time() - start) * 1000)

    if not output:
        output = result.stderr.strip() or ""
        if not output:
            raise RuntimeError("Tool returned no output")

    content = _extract_content(output)
    content = _strip_code_fences(content)

    db.save_tool_invocation(session_id, tool, config["mode"], elapsed_ms, model or DEFAULT_MODEL)

    return {"result": content, "mode": config["mode"], "tool": tool, "elapsed_ms": elapsed_ms, "model": model or DEFAULT_MODEL}


SYSTEM_PROMPT = """\
You are Ralphy, an expert software architect and requirement extractor.

Your job: ask the user questions about their project idea until you have enough
information to create a complete, unambiguous task list for an autonomous AI
coding agent (Ralph) to implement.

## How you work

1. The user gives you an initial idea.
2. You ask ONE focused question at a time, targeting the weakest dimension.
3. After each answer, you reassess confidence across all dimensions.
4. Set ready=true when you believe all relevant requirements are thoroughly \
covered. The server validates independently.

## Progressive questioning

Match question depth to conversation phase:
- Questions 1-3 (big picture): What does it do? Who uses it? What tech stack?
- Questions 4-7 (specifics): Data model, auth needs, deployment target, integrations.
- Questions 8-10 (edge cases): Error handling, testing strategy, constraints, scale.
- Questions 11+ (finalize): Fill gaps, verify consistency, resolve contradictions.

Do NOT jump ahead. You MUST ask at least 10 substantive questions before setting ready=true.

## Tool-generated messages

Messages prefixed with [Tool: Name] are generated by the user's brainstorming tools.
Treat them as additional context from the user, not as answers to your questions.
Acknowledge the ideas briefly, then continue with your next focused question
targeting the weakest dimension. Do not ask the user to elaborate on every
tool-generated point -- pick the most impactful one.

## Confidence dimensions (0-100 each)

- **functional**: What the software does. Features, user stories, main flows.
- **technical_stack**: Language, framework, database, key libraries.
- **data_model**: Entities, fields, relationships, storage format.
- **auth**: Authentication, authorization, user roles. (Score 90+ if no auth needed.)
- **deployment**: How/where it runs. Local, VPS, cloud.
- **testing**: Test strategy. Unit, integration, E2E.
- **edge_cases**: Error handling, input validation, constraints.

## Relevance

Rate 0.0 for dimensions irrelevant to this project (e.g., auth for a CLI tool). \
Rate 1.0 for critical dimensions. Reassess each turn.

## Response format

You MUST respond with valid JSON only (no markdown, no code fences):

{{
  "message": "Your question or response (markdown OK inside this string)",
  "confidence": {{
    "functional": <0-100>, "technical_stack": <0-100>, "data_model": <0-100>,
    "auth": <0-100>, "deployment": <0-100>, "testing": <0-100>, "edge_cases": <0-100>
  }},
  "relevance": {{
    "functional": <0.0-1.0>, "technical_stack": <0.0-1.0>, "data_model": <0.0-1.0>,
    "auth": <0.0-1.0>, "deployment": <0.0-1.0>, "testing": <0.0-1.0>, "edge_cases": <0.0-1.0>
  }},
  "contradictions": [],
  "ready": false
}}

When requirements are thoroughly covered, set "ready": true and add:

{{
  "message": "Here are the tasks:",
  "confidence": {{ ... }},
  "relevance": {{ ... }},
  "contradictions": [],
  "ready": true,
  "tasks": [
    {{ "title": "...", "body": "Acceptance: ...\\nDesign: ...", "priority": 1, "parent": null }},
    {{ "title": "...", "body": "...", "priority": 2, "parent": "task-001" }}
  ],
  "project": {{
    "name": "project-name", "language": "Python", "framework": "FastAPI",
    "description": "One-line description",
    "test_command": "uv run pytest", "lint_command": "uv run ruff check ."
  }}
}}

## Rules

- ONE question at a time. Be specific.
- Don't assume. If unsure, ask.
- Score honestly. The server validates independently.
- Before ready=true: verify ZERO contradictions. Every gap becomes a bug.
- After each user answer, check for contradictions with previous answers.
  If the user previously said one thing (e.g., "Python") and now says something
  conflicting (e.g., "JavaScript"), DO NOT update confidence. Instead, set your
  message to ask the user to clarify: "Earlier you mentioned Python, but now
  you're saying JavaScript. Which one should I use?"
- Include a "contradictions" field in your JSON response (array of strings).
  Each string describes a detected contradiction. Empty array if none.
- If the user's message contains '[Attached: ...]', they have uploaded files.
  Acknowledge the files by name and factor them into your understanding of
  the project. Ask what role these files play if unclear.
"""


@dataclass
class ChatState:
    """Per-session chatbot conversation state."""

    messages: list[dict] = field(default_factory=list)
    confidence: dict[str, int] = field(default_factory=lambda: {d: 0 for d in DIMENSIONS})
    relevance: dict[str, float] = field(default_factory=lambda: {d: 1.0 for d in DIMENSIONS})
    ready: bool = False
    tasks: list[dict] | None = None
    project: dict | None = None
    weighted_readiness: float = 0.0
    session_dir: Path | None = None
    last_message_time: float = 0.0
    last_tool_time: float = 0.0

    @property
    def user_msg_count(self) -> int:
        return sum(1 for m in self.messages if m["role"] == "user")

    def to_dict(self) -> dict:
        return {
            "confidence": self.confidence,
            "relevance": self.relevance,
            "ready": self.ready,
            "weighted_readiness": round(self.weighted_readiness, 1),
            "question_count": self.user_msg_count,
            "phase": _get_phase(self.user_msg_count),
        }


_chat_states: dict[str, ChatState] = {}


def get_chat_state(session_id: str) -> ChatState:
    if session_id not in _chat_states:
        # Try loading from DB
        db_state = db.load_chat_state(session_id)
        db_msgs = db.load_chat_messages(session_id)
        if db_state or db_msgs:
            state = ChatState(
                messages=[{"role": m["role"], "content": m["content"]} for m in db_msgs],
                confidence=db_state["confidence"] if db_state else {d: 0 for d in DIMENSIONS},
                relevance=db_state["relevance"] if db_state else {d: 1.0 for d in DIMENSIONS},
                ready=db_state["ready"] if db_state else False,
                tasks=db_state["tasks"] if db_state else None,
                project=db_state["project"] if db_state else None,
                weighted_readiness=db_state["weighted_readiness"] if db_state else 0.0,
            )
            _chat_states[session_id] = state
        else:
            _chat_states[session_id] = ChatState()
    return _chat_states[session_id]


async def chat(session_id: str, user_message: str, *, session_dir: Path | None = None, model: str = DEFAULT_MODEL) -> dict:
    """Send a user message to Ralphy via OpenCode, get response + confidence scores."""
    if not shutil.which(OPENCODE_CMD):
        raise RuntimeError(
            f"'{OPENCODE_CMD}' not found on PATH. "
            "Install OpenCode: https://opencode.ai/docs/installation"
        )

    state = get_chat_state(session_id)

    # A3: Rate limiting
    if time.time() - state.last_message_time < 3.0:
        raise RuntimeError("Please wait a few seconds between messages")

    if session_dir:
        state.session_dir = session_dir

    state.messages.append({"role": "user", "content": user_message})
    db.save_chat_message(session_id, "user", user_message)

    # Build the full prompt for opencode: system prompt + conversation history
    conversation = f"{SYSTEM_PROMPT}\n\n## Conversation so far\n\n"
    for msg in state.messages:
        role = "User" if msg["role"] == "user" else "Ralphy"
        conversation += f"**{role}:** {msg['content']}\n\n"
    conversation += "Now respond as Ralphy with valid JSON:"

    # Spawn opencode run -- uses whatever model opencode.jsonc is configured with
    cwd = str(state.session_dir) if state.session_dir else None
    try:
        result = subprocess.run(
            [OPENCODE_CMD, "run", conversation, "--model", model, "--format", "json"],
            capture_output=True, text=True, timeout=120,
            cwd=cwd,
        )
        output = result.stdout.strip()
    except subprocess.TimeoutExpired:
        raise RuntimeError("OpenCode timed out (120s)")
    except FileNotFoundError:
        raise RuntimeError("OpenCode not found on PATH")

    if not output:
        output = result.stderr.strip() if result.stderr else ""
        if not output:
            raise RuntimeError("OpenCode returned no output")

    # Parse response -- opencode --format json wraps in a JSON envelope
    content = _extract_content(output)
    content = _strip_code_fences(content)

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        logger.warning("LLM returned non-JSON: %s", content[:200])
        parsed = {"message": content, "confidence": state.confidence, "ready": False}

    # Update state
    assistant_msg = parsed.get("message", "")
    state.messages.append({"role": "assistant", "content": json.dumps(parsed)})
    db.save_chat_message(session_id, "assistant", json.dumps(parsed))

    # A1: Contradiction detection -- skip confidence update if contradictions found
    contradictions = parsed.get("contradictions") or []
    if contradictions:
        logger.info("Contradictions detected: %s", contradictions)

    # Validate and apply confidence
    user_msg_len = len(user_message)
    phase_max = _phase_cap(state.user_msg_count)

    if "confidence" in parsed and not contradictions:
        for dim in DIMENSIONS:
            raw = parsed["confidence"].get(dim)
            if not isinstance(raw, (int, float)):
                continue
            prev = state.confidence[dim]
            clamped = _clamp_score(int(raw), prev, phase_max, user_msg_len)
            state.confidence[dim] = _smooth(clamped, prev)

    if "relevance" in parsed:
        for dim in DIMENSIONS:
            rel = parsed["relevance"].get(dim)
            if isinstance(rel, (int, float)):
                state.relevance[dim] = max(0.0, min(1.0, float(rel)))

    state.weighted_readiness = _compute_readiness(state.confidence, state.relevance)
    state.ready = _is_ready(state)

    db.save_chat_state(
        session_id,
        state.confidence,
        state.relevance,
        state.ready,
        state.weighted_readiness,
        state.tasks,
        state.project,
    )

    # Detect LLM-ready vs server-not-ready mismatch
    llm_said_ready = parsed.get("ready", False)
    if llm_said_ready and not state.ready:
        assistant_msg = (
            "I need a few more details to make sure everything is covered. "
            "Let me ask another question..."
        )

    if state.ready:
        state.tasks = parsed.get("tasks")
        state.project = parsed.get("project")
        db.save_chat_state(
            session_id,
            state.confidence,
            state.relevance,
            state.ready,
            state.weighted_readiness,
            state.tasks,
            state.project,
        )

    # A3: Record timestamp after processing
    state.last_message_time = time.time()

    return {
        "message": assistant_msg,
        "confidence": state.confidence,
        "relevance": state.relevance,
        "ready": state.ready,
        "weighted_readiness": state.weighted_readiness,
        "question_count": state.user_msg_count,
        "phase": _get_phase(state.user_msg_count),
        "tasks": state.tasks,
        "project": state.project,
        "contradictions": contradictions,
    }


def undo_last_message(session_id: str) -> dict:
    """Remove last user+assistant pair and recalculate confidence from history.

    Re-parses assistant messages (no LLM re-call needed) to rebuild scores.
    """
    state = get_chat_state(session_id)
    if len(state.messages) < 2:
        raise RuntimeError("Nothing to undo")

    # Remove last 2 messages (user + assistant)
    state.messages = state.messages[:-2]

    # Reset confidence to zeros
    state.confidence = {d: 0 for d in DIMENSIONS}
    state.relevance = {d: 1.0 for d in DIMENSIONS}
    state.ready = False
    state.tasks = None
    state.project = None

    # Replay assistant messages to recalculate confidence
    # Compute user_msg_count at each step for correct phase capping
    user_count = 0
    for msg in state.messages:
        if msg["role"] == "user":
            user_count += 1
            continue
        # Assistant message -- try to parse its JSON content
        try:
            parsed = json.loads(msg["content"])
        except (json.JSONDecodeError, TypeError):
            continue

        # Skip turns with contradictions (same logic as live chat)
        if parsed.get("contradictions"):
            continue

        phase_max = _phase_cap(user_count)
        if "confidence" in parsed:
            for dim in DIMENSIONS:
                raw = parsed["confidence"].get(dim)
                if not isinstance(raw, (int, float)):
                    continue
                prev = state.confidence[dim]
                # Use a default msg length for replay (not short)
                clamped = _clamp_score(int(raw), prev, phase_max, SHORT_MSG_LEN + 1)
                state.confidence[dim] = _smooth(clamped, prev)

        if "relevance" in parsed:
            for dim in DIMENSIONS:
                rel = parsed["relevance"].get(dim)
                if isinstance(rel, (int, float)):
                    state.relevance[dim] = max(0.0, min(1.0, float(rel)))

    state.weighted_readiness = _compute_readiness(state.confidence, state.relevance)
    state.ready = _is_ready(state)

    # Persist updated messages
    db.delete_chat_messages(session_id)
    for msg in state.messages:
        db.save_chat_message(session_id, msg["role"], msg["content"])

    db.save_chat_state(
        session_id,
        state.confidence,
        state.relevance,
        state.ready,
        state.weighted_readiness,
        state.tasks,
        state.project,
    )

    return {
        "confidence": state.confidence,
        "relevance": state.relevance,
        "ready": state.ready,
        "weighted_readiness": round(state.weighted_readiness, 1),
        "question_count": state.user_msg_count,
        "phase": _get_phase(state.user_msg_count),
        "message_count": len(state.messages),
    }


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences (```json ... ```) that LLMs love to add."""
    import re
    # Match ```json\n...\n``` or ```\n...\n```
    m = re.search(r"```(?:\w+)?\s*\n?(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text.strip()


def _extract_content(output: str) -> str:
    """Extract the LLM's response text from opencode's --format json NDJSON output.

    OpenCode emits newline-delimited JSON events:
        {"type": "step_start", ...}
        {"type": "text", "part": {"text": "actual response"}, ...}
        {"type": "step_finish", ...}

    We concatenate all "text" event payloads.
    """
    texts: list[str] = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
            if event.get("type") == "text":
                text = event.get("part", {}).get("text", "")
                if text:
                    texts.append(text)
        except json.JSONDecodeError:
            # Not JSON -- might be raw text, append it
            texts.append(line)
    return "".join(texts) if texts else output
