"""Ralphy chatbot: LLM-powered requirement extraction with confidence scoring.

Asks questions iteratively until confidence across all requirement dimensions
reaches threshold. Then generates structured tasks for the Ralph Loop.
"""

import json
import logging
import os
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "moonshotai/kimi-k2"
CONFIDENCE_THRESHOLD = 90  # all dimensions must reach this %

DIMENSIONS = [
    "functional",       # what does it do?
    "technical_stack",  # language, framework, infra
    "data_model",       # entities, relationships, storage
    "auth",             # authentication, authorization, roles
    "deployment",       # where/how it runs, env vars, services
    "testing",          # test strategy, coverage expectations
    "edge_cases",       # error handling, constraints, limits
]

SYSTEM_PROMPT = """\
You are Ralphy, an expert software architect and requirement extractor.

Your job: ask the user questions about their project idea until you have enough
information to create a complete, unambiguous task list for an autonomous AI
coding agent (Ralph) to implement.

## How you work

1. The user gives you an initial idea.
2. You ask ONE focused question at a time, targeting the weakest dimension.
3. After each answer, you reassess confidence across all dimensions.
4. When ALL dimensions reach {threshold}% confidence, you generate tasks.

## Confidence dimensions (0-100 each)

- **functional**: What the software does. Features, user stories, main flows.
- **technical_stack**: Language, framework, database, key libraries.
- **data_model**: Entities, fields, relationships, storage format.
- **auth**: Authentication, authorization, user roles. (Score 90+ if the project has no auth needs.)
- **deployment**: How/where it runs. Local, VPS, cloud. Environment variables, ports.
- **testing**: Test strategy. Unit, integration, E2E. What must be tested.
- **edge_cases**: Error handling, input validation, rate limits, constraints.

## Response format

You MUST respond with valid JSON (no markdown, no code fences):

{{
  "message": "Your question or response to the user (markdown OK inside this string)",
  "confidence": {{
    "functional": <0-100>,
    "technical_stack": <0-100>,
    "data_model": <0-100>,
    "auth": <0-100>,
    "deployment": <0-100>,
    "testing": <0-100>,
    "edge_cases": <0-100>
  }},
  "ready": false
}}

When ALL dimensions >= {threshold}, set "ready": true and add a "tasks" field:

{{
  "message": "I have enough information. Here are the tasks I'll create for Ralph:",
  "confidence": {{ ... all >= {threshold} ... }},
  "ready": true,
  "tasks": [
    {{
      "title": "Short imperative title",
      "body": "Acceptance: ...\\nDesign: ...\\nNotes: ...",
      "priority": 1,
      "parent": null
    }},
    {{
      "title": "Second task (depends on first)",
      "body": "Acceptance: ...",
      "priority": 2,
      "parent": "task-001"
    }}
  ],
  "project": {{
    "name": "project-name",
    "language": "Python",
    "framework": "FastAPI",
    "description": "One-line description",
    "test_command": "uv run pytest",
    "lint_command": "uv run ruff check ."
  }}
}}

## Task quality rules

- Tasks must be sequential and dependency-ordered (parent field)
- Each task must have clear acceptance criteria in the body
- Tasks must be atomic: one testable unit of work
- First tasks should set up project structure and core data models
- Later tasks build features on top
- Include a final task for documentation and cleanup
- Priority: 1 = do first, higher = do later

## Behavior rules

- Ask ONE question at a time. Never ask multiple questions in one message.
- Be specific. "What database?" not "Tell me about the technical details."
- If the user's answer is vague, ask a follow-up to clarify.
- Don't assume. If unsure, ask.
- Score auth at 90+ if the project genuinely doesn't need authentication.
- Score dimensions honestly -- don't inflate to reach threshold faster.
- Before setting ready=true, verify there are ZERO contradictions in the requirements.
  If you spot a contradiction, ask the user to resolve it. Never generate tasks with ambiguity.
- The task list you generate is what an autonomous AI agent will implement without
  human oversight. Every gap or ambiguity becomes a bug. Be thorough.
""".format(threshold=CONFIDENCE_THRESHOLD)


@dataclass
class ChatState:
    """Per-session chatbot conversation state."""

    messages: list[dict] = field(default_factory=list)
    confidence: dict[str, int] = field(default_factory=lambda: {d: 0 for d in DIMENSIONS})
    ready: bool = False
    tasks: list[dict] | None = None
    project: dict | None = None

    def to_dict(self) -> dict:
        return {
            "confidence": self.confidence,
            "ready": self.ready,
            "threshold": CONFIDENCE_THRESHOLD,
        }


# Per-session chat states
_chat_states: dict[str, ChatState] = {}


def get_chat_state(session_id: str) -> ChatState:
    if session_id not in _chat_states:
        _chat_states[session_id] = ChatState()
    return _chat_states[session_id]


async def chat(session_id: str, user_message: str, *, model: str = DEFAULT_MODEL) -> dict:
    """Send a user message, get LLM response with confidence scores.

    Returns dict with: message, confidence, ready, tasks (if ready), project (if ready).
    """
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY not set. "
            "Export it: export OPENROUTER_API_KEY=sk-or-..."
        )

    state = get_chat_state(session_id)

    # Build conversation
    state.messages.append({"role": "user", "content": user_message})

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *state.messages,
    ]

    # Call OpenRouter (try json_object format, fall back to raw)
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Try with json_object format first
        resp = await client.post(
            OPENROUTER_URL, headers=headers,
            json={**payload, "response_format": {"type": "json_object"}},
        )
        # If model doesn't support json_object, retry without it
        if resp.status_code == 400:
            logger.info("Model doesn't support json_object format, retrying without")
            resp = await client.post(OPENROUTER_URL, headers=headers, json=payload)

    if resp.status_code != 200:
        error = resp.text
        logger.error("OpenRouter error %d: %s", resp.status_code, error)
        raise RuntimeError(f"LLM API error: {resp.status_code}")

    data = resp.json()
    content = data["choices"][0]["message"]["content"]

    # Parse LLM response
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        logger.error("LLM returned non-JSON: %s", content[:200])
        # Wrap raw text as a message
        parsed = {
            "message": content,
            "confidence": state.confidence,
            "ready": False,
        }

    # Update state
    assistant_msg = parsed.get("message", "")
    state.messages.append({"role": "assistant", "content": content})

    if "confidence" in parsed:
        for dim in DIMENSIONS:
            val = parsed["confidence"].get(dim)
            if isinstance(val, (int, float)):
                state.confidence[dim] = int(val)

    state.ready = parsed.get("ready", False)

    if state.ready:
        state.tasks = parsed.get("tasks")
        state.project = parsed.get("project")

    return {
        "message": assistant_msg,
        "confidence": state.confidence,
        "ready": state.ready,
        "tasks": state.tasks,
        "project": state.project,
    }
