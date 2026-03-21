# Idea

## Functioning

'justralph.it' is a web-app startup focusing on leveraging the functioning of ralph-loops by giving the user a series of highly-consistent questions to iterate on the user's initial prompt, and long-term goal, all with the objective of building everything without any issues/contradictory patterns.

## UI direction

The initial design-system specification for the product lives in `notes/project/003_UI/001_design_system.md`.

The first implemented routed frontend for that system now lives in `client/src/App.tsx`, with the landing page at `/`, the projects index at `/app/projects`, the project workspace at `/app/projects/:projectId`, and the account surfaces at `/app/settings` and `/app/pricing`.

The main app-shell plan button now routes directly into the settings plan view through `/app/settings?tab=plan`.

## Example - Web-App Flow

1. The user has an idea, in this example, he wants to create a to-do app. He writes the initial prompt, something like: "Build me a to-do app. Make no mistakes".

2. Based on the initial prompt provided, the agent (Ralphy), will ask a series of questions to ensure that, before writing a single line of code, all requirements, instructions, goals, to-dos and overall project memory is consistent, accurate, and completely aligned with the user's request. 

3. After multiple iterations from this initial session, (which will be in a chatbot), the ralph loop will begin to implement every to-do necessary until it eithers A) it finishes, B) interrups the session when it requires user intervention (API keys, verification, auth, etc), then in this case, once the user provides what's necessary, it will go back to the tasks.

4. Once the results have been achieved, the agent (basically an open-code session terminal wrapped in a chatbot) will provide the results. 

### Notes - Technicals

- The webapp is going to be build with React/Typescript
- Each prompt sent by the user is going to be treated as a 'session' (a new github repo), different from the Ralph Loop sessions
- The ralph-loops (what we'll be focusing on) have to run trought opencode and we'll have to make sure that part 1) provides an excessive amount of questions (+50 if necessary), so the part 2) begins running the loop.
