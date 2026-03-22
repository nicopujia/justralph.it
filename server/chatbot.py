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
from pkgs.tasks.main import list_tasks

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
# Tuned for 2-3 turn convergence with batch questions (21 Qs in turn 1).
# Math simulation: with these values a dimension goes 0 -> 45 -> 82 -> 90+ in 3 turns.
MAX_DELTA = 45               # big jumps -- batch answers carry lots of info
SHORT_MSG_LEN = 80           # "short" means < 80 chars
SHORT_MSG_DELTA = 15         # even short messages can move scores meaningfully
BATCH_BONUS_THRESHOLD = 500  # user messages longer than this get a delta bonus
BATCH_BONUS_DELTA = 15       # extra delta for batch answers (added to MAX_DELTA)
EMA_ALPHA = 0.9              # fast convergence -- 90% new, 10% old

BASE_WEIGHTS: dict[str, float] = {
    "functional": 2.0,
    "technical_stack": 1.5,
    "data_model": 1.5,
    "auth": 1.0,
    "deployment": 1.0,
    "testing": 1.0,
    "edge_cases": 1.0,
}
READINESS_THRESHOLD = 50
MIN_DIM_SCORE = 50
RELEVANCE_CUTOFF = 0.3

# Questions-per-dimension for adaptive questioning.
QUESTIONS_PER_DIM_INITIAL = 3
QUESTION_REDUCTION_FACTOR = 0.6  # 60% fewer Qs per dim when confidence >= 60

# Phase caps based on cumulative user content length (chars).
# Lowered thresholds: batch answers produce 500-1000 chars easily.
_PHASE_CHAR_THRESHOLDS: list[tuple[int, int, int]] = [
    #  (max_chars, phase, cap)
    (100,   1, 65),   # initial idea pitch
    (350,   2, 90),   # first batch of answers
    (700,   3, 100),  # second round -- uncapped
]
_PHASE_FINAL = (4, 100)  # beyond threshold -- fully uncapped


def _get_phase(total_chars: int = 0) -> int:
    """Determine conversation phase from content volume."""
    for max_chars, phase, _ in _PHASE_CHAR_THRESHOLDS:
        if total_chars <= max_chars:
            return phase
    return _PHASE_FINAL[0]


def _phase_cap(total_chars: int = 0) -> int:
    """Score cap based on how much content the user has provided."""
    for max_chars, _, cap in _PHASE_CHAR_THRESHOLDS:
        if total_chars <= max_chars:
            return cap
    return _PHASE_FINAL[1]


def _questions_for_dim(dim: str, confidence: dict[str, int]) -> int:
    """How many questions to ask for a dimension based on current confidence."""
    score = confidence.get(dim, 0)
    if score >= 90:
        return 0   # covered
    if score >= 60:
        return max(1, round(QUESTIONS_PER_DIM_INITIAL * (1 - QUESTION_REDUCTION_FACTOR)))
    return QUESTIONS_PER_DIM_INITIAL


def _build_question_guidance(confidence: dict[str, int], relevance: dict[str, float]) -> str:
    """Build per-dimension question count guidance for the system prompt."""
    lines = []
    total = 0
    for dim in DIMENSIONS:
        if relevance.get(dim, 1.0) <= RELEVANCE_CUTOFF:
            lines.append(f"- **{dim}**: SKIP (not relevant)")
            continue
        n = _questions_for_dim(dim, confidence)
        total += n
        score = confidence.get(dim, 0)
        if n == 0:
            lines.append(f"- **{dim}**: COVERED ({score}%) -- no questions needed")
        else:
            lines.append(f"- **{dim}**: ask {n} question(s) ({score}% current)")
    lines.insert(0, f"**Total questions this turn: {total}**\n")
    return "\n".join(lines)


def _clamp_score(new: int, prev: int, phase_max: int, msg_len: int) -> int:
    clamped = min(new, phase_max)
    max_d = SHORT_MSG_DELTA if msg_len < SHORT_MSG_LEN else MAX_DELTA
    # Batch answer bonus: long messages can jump further
    if msg_len > BATCH_BONUS_THRESHOLD:
        max_d = min(max_d + BATCH_BONUS_DELTA, 60)
    if clamped > prev + max_d:
        clamped = prev + max_d
    return max(0, min(100, clamped))


def _smooth(new: int, prev: int) -> int:
    if new <= prev:
        return new
    if prev == 0:
        return new  # first real score -- no dampening against zero baseline
    return round(EMA_ALPHA * new + (1 - EMA_ALPHA) * prev)


def _compute_readiness(confidence: dict[str, int], relevance: dict[str, float]) -> float:
    num = sum(confidence.get(d, 0) * BASE_WEIGHTS[d] * relevance.get(d, 1.0) for d in DIMENSIONS)
    den = sum(BASE_WEIGHTS[d] * relevance.get(d, 1.0) for d in DIMENSIONS)
    return num / den if den else 0.0


def _is_ready(state: "ChatState") -> bool:
    """Ready when weighted readiness >= 50% and all relevant dimensions >= 50%.

    No minimum question count -- if the user provides enough detail in one
    prompt to hit the threshold, that's valid.
    """
    if state.weighted_readiness < READINESS_THRESHOLD:
        return False
    for d in DIMENSIONS:
        if state.relevance.get(d, 1.0) > RELEVANCE_CUTOFF:
            if state.confidence.get(d, 0) < MIN_DIM_SCORE:
                return False
    return True


def _describe_gaps(state: "ChatState") -> str:
    """Human-readable list of dimensions blocking readiness."""
    gaps = []
    for d in DIMENSIONS:
        if state.relevance.get(d, 1.0) <= RELEVANCE_CUTOFF:
            continue
        score = state.confidence.get(d, 0)
        if score < MIN_DIM_SCORE:
            gaps.append(f"{d.replace('_', ' ')} ({score}%, needs {MIN_DIM_SCORE}%)")
    if state.weighted_readiness < READINESS_THRESHOLD:
        gaps.append(f"overall readiness {state.weighted_readiness:.0f}% (needs {READINESS_THRESHOLD}%)")
    return ", ".join(gaps) if gaps else "almost there"


def _strip_task_content(message: str) -> str:
    """Remove task-list-like content from a chat message.

    Detects 5+ consecutive lines that look like numbered tasks or bullet-point
    task titles and collapses them. Prevents the LLM from dumping a task list
    inside the message text.
    """
    import re
    lines = message.split("\n")
    cleaned: list[str] = []
    task_run: list[str] = []

    def _is_task_line(line: str) -> bool:
        s = line.strip()
        return bool(re.match(r"^\d+[\.\)]\s+\S", s) or re.match(r"^[-*]\s+\*?\*?[A-Z]", s))

    for line in lines:
        if _is_task_line(line):
            task_run.append(line)
        else:
            if len(task_run) >= 5:
                cleaned.append(f"*({len(task_run)} tasks generated -- see Tasks tab)*")
            else:
                cleaned.extend(task_run)
            task_run = []
            cleaned.append(line)

    if len(task_run) >= 5:
        cleaned.append(f"*({len(task_run)} tasks generated -- see Tasks tab)*")
    else:
        cleaned.extend(task_run)

    return "\n".join(cleaned)


def _auto_score_irrelevant(state: "ChatState") -> None:
    """Auto-set confidence to 95 for dimensions the LLM marked irrelevant.

    Prevents dead dimensions from confusing the LLM while they're already
    excluded from the readiness check by RELEVANCE_CUTOFF.
    """
    for d in DIMENSIONS:
        if state.relevance.get(d, 1.0) <= RELEVANCE_CUTOFF:
            if state.confidence.get(d, 0) < 90:
                state.confidence[d] = 95


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


def _conversation_summary(state: "ChatState", max_messages: int = 30) -> str:
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
        "gate": lambda s: _get_phase(_total_user_chars(s)) >= 2,
        "gate_reason": "Need Phase 2+ (200+ chars of conversation) for architecture suggestions",
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
    "modify": {
        "mode": "inject",
        "model": None,
        "gate": lambda s: s.user_msg_count >= 1,
        "gate_reason": "Need at least 1 message",
        "system": """\
You are a task modification advisor for a software project.

## Context
{conversation}

## Current confidence scores
{confidence_summary}

## User request
{original}

## Task
Based on the user's request, suggest specific task modifications:
- Which tasks to add, remove, or update
- Priority changes
- Dependency adjustments
- Scope refinements

Format each suggestion as:
- ACTION: [ADD/REMOVE/UPDATE] task-title -- reason

Be specific and actionable. Only suggest changes relevant to the user's request.""",
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
    import hashlib
    import uuid

    if tool not in TOOL_CONFIGS:
        raise ValueError(f"Unknown tool: {tool}")

    state = get_chat_state(session_id)
    config = TOOL_CONFIGS[tool]

    # Circuit breaker: if tool has failed 3+ consecutive times, disable it
    if state.tool_fail_counts.get(tool, 0) >= 3:
        raise RuntimeError(
            f"'{tool}' has failed 3 consecutive times. "
            "Try a different tool or continue chatting to change context."
        )

    # Per-tool progressive cooldown (3s base, 10s on 2nd use, 30s on 3rd+)
    now = time.time()
    usage = state.tool_usage_counts.get(tool, 0)
    last_ts = state.tool_timestamps.get(tool, 0.0)
    cooldown = 3.0 if usage <= 1 else (10.0 if usage == 2 else 30.0)
    if now - last_ts < cooldown:
        remaining = round(cooldown - (now - last_ts))
        raise RuntimeError(f"Rate limited. Wait {remaining}s before running {tool} again.")

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

    # Inject task status context when tasks exist (loop phase)
    try:
        cwd_path = session_dir or state.session_dir
        if cwd_path:
            all_tasks = list_tasks(cwd=str(cwd_path))
            if all_tasks:
                task_lines = [f"- [{t.status.upper()}] {t.title}" for t in all_tasks]
                system_prompt += (
                    "\n\n## Current task statuses\n" + "\n".join(task_lines)
                )
    except Exception:
        pass

    # Conditionally remove auth section for architect if auth is irrelevant
    if tool == "architect":
        auth_relevant = state.relevance.get("auth", 1.0) > RELEVANCE_CUTOFF
        if not auth_relevant:
            system_prompt = system_prompt.replace(
                "3. Auth strategy (or note if not needed)\n", ""
            )

    # Context hash dedup: reject if prompt is identical to last run of same tool
    prompt_hash = hashlib.md5(system_prompt.encode()).hexdigest()[:12]
    if prompt_hash == state.tool_context_hashes.get(tool):
        raise RuntimeError(
            f"Same context as the last {tool} run. "
            "Add more detail to the conversation first, then try again."
        )

    # On repeat runs: inject anti-repetition instructions + previous result as negative example
    run_number = usage + 1
    if run_number > 1:
        system_prompt += f"\n\nThis is run #{run_number} of {tool}. You MUST produce COMPLETELY DIFFERENT output."
        prev_result = state.tool_last_results.get(tool, "")
        if prev_result:
            snippet = prev_result[:500]
            system_prompt += f"\n\nPrevious result (DO NOT repeat this):\n{snippet}\n\nProvide fresh, alternative ideas."

    # Nonce to prevent any caching
    system_prompt += f"\n\n<!-- run-id: {uuid.uuid4().hex[:8]} -->"

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
        state.tool_fail_counts[tool] = state.tool_fail_counts.get(tool, 0) + 1
        raise RuntimeError("Tool timed out (120s). Try a shorter conversation or different tool.")
    except FileNotFoundError:
        raise RuntimeError("OpenCode not found on PATH")
    elapsed_ms = int((time.time() - start) * 1000)

    if not output:
        output = result.stderr.strip() or ""
        if not output:
            state.tool_fail_counts[tool] = state.tool_fail_counts.get(tool, 0) + 1
            raise RuntimeError("Tool returned no output. Try rephrasing or adding more context.")

    content = _extract_content(output)
    content = _strip_code_fences(content)

    # Validate result quality
    if len(content.strip()) < 50:
        state.tool_fail_counts[tool] = state.tool_fail_counts.get(tool, 0) + 1
        raise RuntimeError("Tool produced insufficient output. Try adding more context to the conversation.")

    # Success: update dedup state, reset fail counter
    state.tool_context_hashes[tool] = prompt_hash
    state.tool_last_results[tool] = content[:1000]
    state.tool_usage_counts[tool] = run_number
    state.tool_timestamps[tool] = time.time()
    state.tool_fail_counts[tool] = 0

    db.save_tool_invocation(session_id, tool, config["mode"], elapsed_ms, model or DEFAULT_MODEL)

    return {"result": content, "mode": config["mode"], "tool": tool, "elapsed_ms": elapsed_ms, "model": model or DEFAULT_MODEL}


SYSTEM_PROMPT = """\
You are Ralphy, an expert software architect and requirement extractor.

Your job: gather enough requirements from the user to create a complete,
unambiguous task list for an autonomous AI coding agent (Ralph) to implement.
You achieve this in 3-4 exchanges maximum by asking BATCH questions.

## How you work

1. The user describes their project idea (or greets you).
2. If the user has NOT described a project yet (e.g., just said "hello" or
   asked a generic question), respond conversationally and ask them to
   describe their project. Do NOT ask alignment questions yet.
   Keep all confidence scores at 0 until a real project is described.
3. Once a project idea is on the table, respond with a BATCH of targeted
   questions -- multiple questions per dimension, grouped by sector.
4. After each answer, reassess confidence and ask FEWER follow-up questions,
   focusing only on weak/ambiguous dimensions.
5. Set ready=true when all relevant dimensions are covered.

## Batch questioning strategy

{question_guidance}

### Rules for question batches:
- Group questions by dimension with clear headers (e.g., "**Functional:**").
- Number each question within its group.
- Ask concrete, specific questions -- not vague "tell me more".
- If the user already answered something in their project description,
  do NOT re-ask. Score that dimension accordingly and skip it.
- After each user response, reduce questions by ~60% for dimensions where
  confidence >= 60%. Ask 0 questions for dimensions >= 90%.

## Tool-generated messages

Messages prefixed with [Tool: Name] are generated by the user's brainstorming
tools. Treat them as additional context. Acknowledge briefly, then continue
with your batch questions targeting weak dimensions.

## Confidence dimensions (0-100 each)

- **functional**: What the software does. Features, user stories, main flows.
- **technical_stack**: Language, framework, database, key libraries.
- **data_model**: Entities, fields, relationships, storage format.
- **auth**: Authentication, authorization, user roles. (Score 90+ if not needed.)
- **deployment**: How/where it runs. Local, VPS, cloud.
- **testing**: Test strategy. Unit, integration, E2E.
- **edge_cases**: Error handling, input validation, constraints.

## Relevance

Rate 0.0 for dimensions irrelevant to this project (e.g., auth for a CLI tool).
Rate 1.0 for critical dimensions. Reassess each turn. Setting a dimension to
0.0 removes it from readiness calculation entirely.

## Response format

You MUST respond with valid JSON only (no markdown, no code fences):

{{
  "message": "Your response with batch questions (markdown OK inside)",
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
  "message": "I've gathered enough requirements. Review the implementation plan below.",
  "confidence": {{ ... all dimensions 80+ ... }},
  "relevance": {{ ... }},
  "contradictions": [],
  "ready": true,
  "tasks": [
    {{
      "title": "Short imperative title",
      "acceptance_criteria": [
        "Specific, testable condition 1",
        "Specific, testable condition 2",
        "Specific, testable condition 3"
      ],
      "design_notes": [
        "Implementation constraint or approach"
      ],
      "estimated_complexity": "low",
      "priority": 1,
      "parent": null
    }},
    {{
      "title": "Another task",
      "acceptance_criteria": ["..."],
      "design_notes": ["..."],
      "estimated_complexity": "medium",
      "priority": 2,
      "parent": "task-001"
    }}
  ],
  "project": {{
    "name": "project-name", "language": "Python", "framework": "FastAPI",
    "description": "One-line description",
    "test_command": "uv run pytest", "lint_command": "uv run ruff check ."
  }}
}}

IMPORTANT: Keep the "message" field brief -- questions and short acknowledgments only.
Your implementation plan goes in the "tasks" array, which the UI renders as
interactive task cards. When you set ready=true, you MUST include a populated
"tasks" array and a "project" object -- these are required for the handoff to work.
The server validates readiness independently using its own scoring. If it agrees
with your ready=true, it extracts tasks from the structured fields above.

### Task field rules:
- **acceptance_criteria**: 2-5 bullet points. Each MUST be testable (a human could
  verify pass/fail). No vague language like "properly handles" or "works well".
- **design_notes**: 0-3 constraints or approach hints. Optional but valuable.
- **estimated_complexity**: "low" (config, docs, simple CRUD), "medium" (business
  logic, integrations), "high" (complex algorithms, multi-service orchestration).
- **parent**: reference as "task-NNN" matching the ID the server will assign
  (task-001 for the first task, task-002 for the second, etc.).

## Rules

- Ask BATCH questions grouped by dimension. Not one at a time.
- Score honestly. The server validates independently.
- If the user greets you without a project idea, respond warmly and ask
  them to describe what they want to build. Do NOT generate questions yet.
- Before ready=true: verify ZERO contradictions. Every gap becomes a bug.
- After each user answer, check for contradictions with previous answers.
  If conflicting info detected, ask for clarification instead of updating
  confidence. List contradictions in the "contradictions" array.
- If the user's message contains '[Attached: ...]', they have uploaded files.
  Acknowledge the files and factor them into your understanding.
- Don't assume. If ambiguous, ask. If clear, score high and move on.
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
    # Tool dedup: context hash + last result per tool, usage counts, per-tool timestamps
    tool_context_hashes: dict[str, str] = field(default_factory=dict)
    tool_last_results: dict[str, str] = field(default_factory=dict)
    tool_usage_counts: dict[str, int] = field(default_factory=dict)
    tool_timestamps: dict[str, float] = field(default_factory=dict)
    tool_fail_counts: dict[str, int] = field(default_factory=dict)

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
            "phase": _get_phase(_total_user_chars(self)),
        }


def _generate_tasks_fallback(
    state: "ChatState", session_dir: Path | None, model: str,
) -> dict | None:
    """Second-pass LLM call: generate tasks from already-gathered requirements.

    Called when the server confirms readiness but the LLM's response didn't
    include a tasks array. Returns parsed dict with 'tasks' and 'project',
    or None on failure.
    """
    conversation = _conversation_summary(state)
    confidence_summary = ", ".join(
        f"{d}: {state.confidence.get(d, 0)}%" for d in DIMENSIONS
    )
    prompt = (
        "You are a task generation specialist. The requirements conversation below "
        "has been validated as complete. Generate a structured task list.\n\n"
        f"## Conversation\n{conversation}\n\n"
        f"## Confidence scores\n{confidence_summary}\n\n"
        "## Instructions\n"
        "Return ONLY a JSON object with 'tasks' and 'project' fields.\n\n"
        '{\n'
        '  "tasks": [\n'
        '    {\n'
        '      "title": "Short imperative title",\n'
        '      "acceptance_criteria": ["Testable condition 1", "Testable condition 2"],\n'
        '      "design_notes": ["Implementation approach"],\n'
        '      "estimated_complexity": "low|medium|high",\n'
        '      "priority": 1,\n'
        '      "parent": null\n'
        '    }\n'
        '  ],\n'
        '  "project": {\n'
        '    "name": "project-name",\n'
        '    "language": "Python",\n'
        '    "framework": "FastAPI",\n'
        '    "description": "One-line description",\n'
        '    "test_command": "pytest",\n'
        '    "lint_command": "ruff check ."\n'
        '  }\n'
        '}\n\n'
        "Return ONLY valid JSON. No explanation, no code fences."
    )

    cwd = str(session_dir or state.session_dir) if (session_dir or state.session_dir) else None
    try:
        result = subprocess.run(
            [OPENCODE_CMD, "run", prompt, "--model", model, "--format", "json"],
            capture_output=True, text=True, timeout=60,
            cwd=cwd,
        )
        output = result.stdout.strip()
        if not output:
            return None
        content = _extract_content(output)
        content = _strip_code_fences(content)
        parsed = json.loads(content)
        tasks = parsed.get("tasks")
        if not tasks or not isinstance(tasks, list):
            return None
        return parsed
    except Exception as e:
        logger.warning("Task generation fallback failed: %s", e)
        return None


def reconcile_tasks(
    session_id: str,
    session_dir: Path | None = None,
    model: str = DEFAULT_MODEL,
) -> dict | None:
    """Reconciliation agent: reads entire conversation, cross-references all
    extracted tasks, deduplicates, fixes dependencies, fills gaps.

    Returns {"tasks": [...], "project": {...}, "changes_summary": "..."} or None.
    """
    state = get_chat_state(session_id)
    conversation = _conversation_summary(state, max_messages=0)
    existing_tasks = json.dumps(state.tasks or [], indent=2)
    confidence_summary = ", ".join(
        f"{d}: {state.confidence.get(d, 0)}%" for d in DIMENSIONS
    )

    prompt = (
        "You are a task reconciliation specialist. You have the full conversation "
        "between a user and Ralphy, plus the tasks extracted progressively.\n\n"
        f"## Full Conversation\n{conversation}\n\n"
        f"## Current Tasks (extracted progressively)\n{existing_tasks}\n\n"
        f"## Confidence Scores\n{confidence_summary}\n\n"
        "## Instructions\n"
        "1. Read the ENTIRE conversation carefully\n"
        "2. Cross-reference every task against what was actually discussed\n"
        "3. DEDUPLICATE tasks that cover the same requirement\n"
        "4. FIX dependency chains (parent references must be valid task titles)\n"
        "5. FILL GAPS: add tasks for requirements discussed but not captured\n"
        "6. REMOVE tasks that contradict or were superseded by later discussion\n"
        "7. Ensure acceptance criteria are specific and testable\n"
        "8. Assign priorities based on conversation emphasis\n\n"
        "Return ONLY a JSON object:\n"
        '{\n'
        '  "tasks": [\n'
        '    {\n'
        '      "title": "Short imperative title",\n'
        '      "acceptance_criteria": ["Testable condition 1"],\n'
        '      "design_notes": ["Implementation approach"],\n'
        '      "estimated_complexity": "low|medium|high",\n'
        '      "priority": 1,\n'
        '      "parent": null\n'
        '    }\n'
        '  ],\n'
        '  "project": {\n'
        '    "name": "project-name",\n'
        '    "language": "Python",\n'
        '    "framework": "FastAPI",\n'
        '    "description": "One-line description",\n'
        '    "test_command": "pytest",\n'
        '    "lint_command": "ruff check ."\n'
        '  },\n'
        '  "changes_summary": "Brief description of what changed from the original list"\n'
        '}\n\n'
        "Return ONLY valid JSON. No explanation, no code fences."
    )

    cwd = str(session_dir or state.session_dir) if (session_dir or state.session_dir) else None
    try:
        result = subprocess.run(
            [OPENCODE_CMD, "run", prompt, "--model", model, "--format", "json"],
            capture_output=True, text=True, timeout=90,
            cwd=cwd,
        )
        output = result.stdout.strip()
        if not output:
            return None
        content = _extract_content(output)
        content = _strip_code_fences(content)
        parsed = json.loads(content)
        tasks = parsed.get("tasks")
        if not tasks or not isinstance(tasks, list):
            return None
        # Store reconciled tasks in state
        state.tasks = tasks
        if parsed.get("project"):
            state.project = parsed["project"]
        return parsed
    except Exception as e:
        logger.warning("Task reconciliation failed: %s", e)
        return None


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

    # Build adaptive question guidance + readiness projection
    question_guidance = _build_question_guidance(state.confidence, state.relevance)
    readiness_note = ""
    if state.weighted_readiness > 0:
        gaps = _describe_gaps(state)
        readiness_note = (
            f"\n\n## Readiness status\n"
            f"Current weighted readiness: {state.weighted_readiness:.0f}% (threshold: {READINESS_THRESHOLD}%)\n"
            f"Gaps: {gaps}\n"
            f"Focus your questions on the weakest dimensions listed above."
        )
    system = SYSTEM_PROMPT.replace("{question_guidance}", question_guidance + readiness_note)

    # Build the full prompt for opencode: system prompt + conversation history.
    # Truncate to keep prompt manageable: always include the first user message
    # (project description) + last N messages. Target ~8K chars of history.
    MAX_HISTORY_CHARS = 8000
    msgs = state.messages
    if len(msgs) > 2:
        first_user = [msgs[0]] if msgs[0]["role"] == "user" else []
        rest = msgs[1:] if first_user else msgs
        # Take from the end until we hit the char budget
        trimmed: list[dict] = []
        budget = MAX_HISTORY_CHARS - sum(len(m["content"]) for m in first_user)
        for msg in reversed(rest):
            cost = len(msg["content"])
            if budget - cost < 0 and trimmed:
                break
            trimmed.append(msg)
            budget -= cost
        trimmed.reverse()
        msgs = first_user + trimmed

    conversation = f"{system}\n\n## Conversation so far\n\n"
    for msg in msgs:
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
    chars = _total_user_chars(state)
    phase_max = _phase_cap(chars)

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

    # Auto-score irrelevant dimensions so they don't drag down readiness
    _auto_score_irrelevant(state)

    # Stall escalation: if readiness hasn't improved in 2 turns, uncap scores
    prev_readiness = state.weighted_readiness
    state.weighted_readiness = _compute_readiness(state.confidence, state.relevance)

    if hasattr(state, "_stall_count"):
        if state.weighted_readiness <= prev_readiness and prev_readiness > 0:
            state._stall_count += 1
        else:
            state._stall_count = 0
    else:
        state._stall_count = 0

    # If stalled 2+ turns, re-clamp with uncapped phase (force phase 4)
    if state._stall_count >= 2:
        logger.info("Readiness stalled %d turns at %.1f%%, escalating to uncapped", state._stall_count, state.weighted_readiness)
        if "confidence" in parsed and not contradictions:
            for dim in DIMENSIONS:
                raw = parsed["confidence"].get(dim)
                if not isinstance(raw, (int, float)):
                    continue
                prev = state.confidence[dim]
                clamped = _clamp_score(int(raw), prev, 100, user_msg_len)
                state.confidence[dim] = _smooth(clamped, prev)
            state.weighted_readiness = _compute_readiness(state.confidence, state.relevance)

    state.ready = _is_ready(state)

    # ALWAYS extract tasks/project from LLM response (don't gate on readiness).
    # Preserves tasks from the turn where the LLM reaches readiness even if
    # the server's clamped scores lag by 1-2%. Only overwrite with non-empty.
    llm_tasks = parsed.get("tasks")
    llm_project = parsed.get("project")
    if llm_tasks and isinstance(llm_tasks, list):
        state.tasks = llm_tasks
    if llm_project and isinstance(llm_project, dict):
        state.project = llm_project

    # Detect LLM/server readiness mismatch
    llm_said_ready = parsed.get("ready", False)
    if llm_said_ready and not state.ready:
        gaps = _describe_gaps(state)
        logger.warning(
            "LLM/server readiness mismatch: LLM=True, server=False (readiness=%.1f%%). Gaps: %s",
            state.weighted_readiness, gaps,
        )
        assistant_msg = (
            f"Almost there! I need a bit more detail on: {gaps}. "
            "Let me ask a few more targeted questions."
        )

    # Two-step generation: if ready but no tasks, make a focused second call
    if state.ready and not state.tasks:
        logger.warning(
            "Readiness confirmed but no tasks in LLM response (session=%s) -- "
            "attempting fallback task generation",
            session_id,
        )
        fallback = _generate_tasks_fallback(state, session_dir, model)
        if fallback:
            state.tasks = fallback.get("tasks")
            if not state.project and fallback.get("project"):
                state.project = fallback["project"]

    # Final guard: never signal ready without tasks
    if state.ready and not state.tasks:
        logger.warning(
            "Readiness confirmed but no tasks after fallback (session=%s) -- "
            "downgrading ready to false",
            session_id,
        )
        state.ready = False
        assistant_msg += (
            "\n\nI'm ready to create your implementation plan. "
            "Let me finalize the task list -- one more moment..."
        )

    # Strip task-like content from message (prevents LLM dumping tasks in chat)
    assistant_msg = _strip_task_content(assistant_msg)

    db.save_chat_state(
        session_id,
        state.confidence,
        state.relevance,
        state.ready,
        state.weighted_readiness,
        state.tasks,
        state.project,
    )

    # A3: Record timestamp + reset tool cooldowns (new context = fresh tool runs)
    state.last_message_time = time.time()
    state.tool_usage_counts.clear()
    state.tool_context_hashes.clear()

    # Compute questions remaining for frontend display
    questions_remaining = sum(
        _questions_for_dim(d, state.confidence)
        for d in DIMENSIONS
        if state.relevance.get(d, 1.0) > RELEVANCE_CUTOFF
    )

    return {
        "message": assistant_msg,
        "confidence": state.confidence,
        "relevance": state.relevance,
        "ready": state.ready,
        "weighted_readiness": state.weighted_readiness,
        "question_count": state.user_msg_count,
        "phase": _get_phase(_total_user_chars(state)),
        "tasks": state.tasks,
        "project": state.project,
        "contradictions": contradictions,
        "questions_remaining": questions_remaining,
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
    # Track the preceding user message length so replay matches live scoring.
    replay_chars = 0
    last_user_msg_len = SHORT_MSG_LEN + 1  # safe default
    for msg in state.messages:
        if msg["role"] == "user":
            last_user_msg_len = len(msg.get("content", ""))
            replay_chars += last_user_msg_len
            continue
        # Assistant message -- try to parse its JSON content
        try:
            parsed = json.loads(msg["content"])
        except (json.JSONDecodeError, TypeError):
            continue

        # Skip turns with contradictions (same logic as live chat)
        if parsed.get("contradictions"):
            continue

        phase_max = _phase_cap(replay_chars)
        if "confidence" in parsed:
            for dim in DIMENSIONS:
                raw = parsed["confidence"].get(dim)
                if not isinstance(raw, (int, float)):
                    continue
                prev = state.confidence[dim]
                clamped = _clamp_score(int(raw), prev, phase_max, last_user_msg_len)
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
        "phase": _get_phase(_total_user_chars(state)),
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
