# Path H: Demo & Hackathon Scope Decisions

Date: 2026-03-21

## H27. Minimum Viable Demo

**Decision:** End-to-end flow for a simple project.

1. User opens justralph.it in browser
2. Ralphy chatbot asks questions, extracts intent
3. Confidence criteria met -> "Just Ralph It" button appears
4. User clicks -> GitHub repo created -> bd issues populated -> Ralph Loop starts
5. UI shows split view: issues list updating in real-time + terminal-like agent output
6. Ralph processes issues, commits code, pushes to GitHub
7. User gets a working repo with passing tests

## H28. Deployment

**Decision:** Deployment IS part of the demo. Ralph should be able to deploy.

- PROMPT.xml already has full deployment workflow (Staging, NoStaging conditions)
- The agent has root + internet access on the VPS -- can deploy
- This differentiates justralph.it from vibe-coding tools that only generate code

## H29. Timeline

**Decision:** 2 days. Everything must work by then.

- Professional/clean standards despite time constraints
- Focus on what needs to work, not polish
- Integration with other teams happens independently (H30)

## H30. Integration Protocol

**Decision:** Independent development. Other teams adapt to our interfaces.

- We define our input contract (bd issues via `bd create`) and output contract (hooks + WebSocket events)
- If something doesn't match, we fix along the way
- No shared API spec document -- pragmatic integration
