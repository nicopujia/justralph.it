# justralph.it design system

## Intent

This design system defines the visual and interaction language for `justralph.it`.

It is derived from:

- the product idea in `notes/project/000_idea/000_assessment.md`
- the startup framing in `notes/project/justralphit_startup.md`
- the visual references in `photos guide/`

The goal is to make the product feel like a serious AI operating environment for teams, not a generic chatbot or a friendly consumer SaaS app.

## Product posture

`justralph.it` should feel:

- operational
- structured
- exact
- calm under pressure
- premium through restraint

It should not feel:

- playful
- bubbly
- overly futuristic
- noisy
- overly decorated
- consumer-social

## Primary audience

The first version is for agencies and small teams coordinating product work with AI assistance.

That means the interface should optimize for:

- trust over novelty
- clarity over personality overload
- workflow structure over entertainment
- long-session comfort over short marketing impact

## Visual thesis

The product should look like an AI control room with editorial discipline.

The reference screenshots consistently suggest:

- near-black canvases
- thin dividers instead of heavy cards
- muted text hierarchy
- strong use of empty space
- restrained white actions
- a hybrid type system with technical UI text and occasional serif authority

The result should feel closer to a quiet internal tool for professionals than to a vibrant startup landing page.

## Core principles

### 1. Build with silence

Use negative space as a primary design tool. Let the interface breathe. Do not fill surfaces just because space is available.

### 2. Prefer linework over containers

Use borders, separators, grids, and subtle surface changes before introducing heavy cards, shadows, or colored panels.

### 3. Make hierarchy obvious without shouting

Hierarchy should come from scale, spacing, alignment, and contrast, not from many colors competing at once.

### 4. Keep actions deliberate

Primary actions should be visually clear and relatively rare. If everything is emphasized, nothing is emphasized.

### 5. Use serif as authority, not decoration

Serif moments should be selective: hero statements, pricing figures, key titles, and occasional high-level labels. Never use serif for dense controls, navigation, or form-heavy UI.

### 6. Design for long cognitive sessions

This product revolves around reading, thinking, asking, refining, and monitoring. Visual rhythm must reduce fatigue.

## Theme model

The system is dark-first only.

This is not a bright mode product with a dark skin layered on top. Contrast, spacing, borders, and typography should be tuned for dark surfaces from the beginning.

## Color system

### Role of color

Color should support structure and state, not branding spectacle.

The palette should stay mostly neutral with one restrained accent family for focus, selected states, and active intelligence cues.

### Foundation palette

Suggested base tokens:

```text
--bg-canvas:        #0A0A0A
--bg-elevated:      #0F0F10
--bg-panel:         #131314
--bg-panel-2:       #171718
--bg-hover:         #1C1C1E
--bg-active:        #222225

--border-soft:      #202124
--border-default:   #2A2B2F
--border-strong:    #34363B

--text-primary:     #F3F2EE
--text-secondary:   #B4B1A8
--text-muted:       #7E7A73
--text-disabled:    #5F5B55

--accent-primary:   #C7D2FE
--accent-strong:    #E6EBFF
--accent-muted:     #97A3C9

--success:          #9BC79A
--warning:          #D6B77A
--danger:           #D08D8D
--info:             #8FAFD1
```

### Color behavior

- The default experience is 85 to 90 percent neutral.
- Accent color appears mainly in focus rings, active tabs, selected states, key links, and status cues.
- White should be used as a high-value contrast tool, especially on primary actions and key text.
- Avoid bright neon tones.
- Avoid purple-led branding unless there is a later strategic reason to rebrand.

### Surface rules

- `canvas` for app background and large empty areas
- `elevated` for app bars, sidebars, modal shells, and sticky surfaces
- `panel` for cards, settings sections, composer shells, metrics blocks
- `panel-2` only when nested emphasis is needed

Do not stack many elevated layers. Most screens should read as one continuous environment.

## Typography system

### Type direction

Use a hybrid system:

- a clean sans for UI, body copy, labels, navigation, and controls
- a restrained serif for brand and authority moments

### Recommended families

Suggested starting point:

- Sans: `Manrope`, `Suisse Intl`, `Geist`, or a similarly structured grotesk
- Serif: `Cormorant Garamond`, `Canela`, or another refined high-contrast serif

If licensing or hosting becomes a constraint, choose substitutes that preserve the same contrast between technical and editorial tones.

### Usage rules

- Sans is the default everywhere.
- Serif is reserved for hero statements, plan pricing, major empty states, selected section titles, and occasional brand phrases.
- Never use serif in sidebars, dense dashboards, chat message metadata, or settings forms.

### Type scale

```text
Display XL: 64/72
Display L:  48/56
H1:         36/42
H2:         28/34
H3:         22/28
H4:         18/24
Body L:     18/30
Body M:     16/26
Body S:     14/22
Label:      12/16
Meta:       11/14
```

### Weight guidance

- Use medium and regular more often than bold.
- Let size and spacing create emphasis before weight does.
- Use bold sparingly in dense product screens.

### Numeric styling

Large pricing, counters, or session metrics can use serif numerals if the moment is strategic and isolated.

## Spacing system

Use a disciplined 4px base scale.

```text
4, 8, 12, 16, 24, 32, 40, 48, 64, 80, 96
```

Guidance:

- 8 to 16 for tight UI relationships
- 24 to 32 for component padding
- 40 to 64 for section separation
- 80 plus for hero or onboarding layouts

The product should feel spacious, especially in chat, onboarding, and empty states.

## Layout system

### Product shell

The product shell should follow the structure implied by the references:

- left rail for primary navigation
- top utility bar for global search, status, notifications, and profile
- large central work area
- optional right utility panels only when necessary

### Width behavior

- Dense workflow screens can stretch wide.
- Reading and decision screens should use narrower text measures.
- Chat and onboarding content should avoid spanning the full screen without control.

### Grids

- Use clear rectangular grids.
- Prefer alignment consistency over asymmetrical flourish.
- Calendar, table, and dashboard surfaces should feel architectural.

## Radius, borders, and shadows

### Radius

Use restrained radii.

```text
--radius-xs: 4px
--radius-sm: 6px
--radius-md: 8px
--radius-lg: 12px
```

Default to `6px` or `8px`. Avoid pill-heavy shapes except for a few compact status chips.

### Borders

Borders are core to the system.

- Use 1px borders extensively.
- Let dividers define structure.
- Use stronger borders only for active or focused states.

### Shadows

Shadows should be minimal.

- Prefer contrast and borders over large blurs.
- Use soft shadow only for modals, floating menus, and elevated overlays.

## Motion system

Motion should feel calm and purposeful.

### Principles

- No decorative bouncing
- No hyperactive micro-interactions
- Fast enough to feel precise, slow enough to feel intentional

### Timing

```text
Fast:   120ms
Base:   180ms
Slow:   260ms
```

### Use cases

- fade and slight rise on page entry
- staggered reveal for onboarding steps or dashboard panels
- subtle opacity or surface shift on hover
- smooth panel expansion for settings and inspector surfaces

## Interaction language

### Buttons

Use three primary button styles:

1. Primary: high-contrast light button on dark background
2. Secondary: dark surface with border
3. Ghost: text-led action with subtle hover state

Rules:

- Keep primary buttons rare enough to matter.
- Do not overuse filled accent buttons.
- Large CTA buttons should feel confident and flat, not candy-like.

### Inputs

Inputs should feel embedded in the system architecture.

- dark field backgrounds
- subtle border
- strong readable caret and placeholder contrast
- clear focus ring using the accent family
- enough vertical padding for long sessions

### Tabs and segmented controls

The references suggest understated segmented controls.

- selected state: subtle filled panel or stronger border
- unselected state: low-contrast text
- avoid bright color fills

### Navigation

Navigation should be understated and spatially stable.

- left rail icons first, text where necessary
- active states via contrast and surface shift
- avoid loud badges unless the state is urgent

### Search

Search is a core global primitive.

- place prominently in the top bar
- generous width
- quiet placeholder text
- leading icon, minimal chrome

## Component rules

### Chat workspace

This is the heart of the product.

- Keep the canvas spacious.
- Let messages float with limited chrome.
- Use alignment, avatar markers, and subtle bubbles rather than heavy threaded cards.
- The composer should feel grounded and tools should stay secondary to text entry.
- User focus should remain on the evolving specification and active reasoning process.

### Onboarding and sign-in

Based on the references, onboarding should feel premium and sparse.

- center or split-screen compositions work well
- combine operational form layout with one atmospheric brand surface
- keep copy short and serious
- social sign-in buttons should look flat, bordered, and aligned

### Settings

Settings should use stacked bordered sections with clear headers and restrained form styling.

- one concern per block
- generous padding
- actions aligned consistently
- helper text low contrast but readable
- profile entry should be reachable from the top utility bar avatar or account mark
- internal settings navigation can use quiet segmented tabs when the screen contains a few closely related subviews
- payment management can expand inline inside the profile area when it belongs to account ownership, instead of forcing a separate route
- usage views should show token and cost signals with quiet metrics and a simple bordered breakdown table

### New project modal

Project creation should feel like opening an operating workspace, not filling a marketing form.

- trigger it from the project rail and empty project states with one clear `New Project` action
- use a restrained modal shell with thin borders, quiet atmosphere, and enough width for a serious first brief
- require a project title and one initial description field
- treat the description as the first user message in the project chat so creation flows directly into execution
- after submit, move the operator straight into the new workspace instead of leaving them in a dead-end confirmation state

### Dashboard metrics

Metrics should feel quiet and trustworthy.

- large value
- concise label
- minimal color
- simple empty states

Do not turn metrics into colorful growth-marketing widgets.

### Pricing

Pricing is one of the few places where editorial presence can increase.

- serif pricing figure is acceptable
- keep the card architecture simple
- use one clear plan emphasis
- avoid fake urgency styling

### Tables, timelines, and planners

For execution-oriented views:

- use rigid grid logic
- rely on dividers and alignment
- keep backgrounds mostly flat
- use one active-cell or active-row treatment at a time

## State system

### Empty states

Empty states should feel intentional, not apologetic.

- short headline
- one line of explanation
- one next step
- lots of space around the message

### Loading states

- use subtle pulse or shimmer sparingly
- prefer structural placeholders over spinning novelty
- keep loading feedback calm and professional

### Success, warning, danger

- state colors should be desaturated
- use text and icon first, color second
- reserve stronger fills for destructive confirmations only

## Content and copy style

The interface should sound:

- direct
- competent
- restrained
- practical

It should not sound:

- overly cheerful
- cute
- salesy
- vague

Examples:

- Good: `Clarify the deployment environment`
- Good: `Session blocked until credentials are provided`
- Bad: `Let's make some magic happen!`
- Bad: `Awesome, you’re all set :)`

## Brand expression

### Logo behavior

The logo should be simple, sharp, and highly legible on dark surfaces.

It should feel more like a mark for a systems tool than a mascot.

### Imagery

If imagery is used, follow the visual cue from the references:

- monochrome or desaturated
- atmospheric
- abstract or texture-led
- supportive, never dominant

Avoid colorful illustrations, 3D blobs, and generic AI sparkles.

## Accessibility and usability

Dark UI quality depends on discipline.

Requirements:

- keep body text readable against dark surfaces
- avoid ultra-low contrast gray-on-black combinations for important text
- ensure all interactive states are visible without relying only on color
- keep focus rings clear and keyboard-friendly
- maintain touch-friendly hit areas on mobile

## Responsive behavior

The system must work on desktop and mobile.

### Desktop

- preserve wide negative space
- use rails and utility bars
- allow chat and execution views to breathe

### Mobile

- collapse rails into overlays or bottom navigation only when justified
- keep the composer always accessible
- reduce decorative split-screen onboarding in favor of single-column clarity
- maintain serif usage, but scale it down carefully so it remains refined, not theatrical

## Implementation guidance

When implemented in React and TypeScript, this system should be codified as:

- CSS variables for tokens
- shared typography utilities
- reusable surface primitives
- consistent input, button, and panel variants
- layout primitives for shell, sections, and reading widths

The first implemented routed frontend baseline lives in `client/src/App.tsx`, `client/src/components/system/landing-page.tsx`, and `client/src/components/system/app-placeholder.tsx`.

Recommended token groups:

- `color`
- `text`
- `space`
- `radius`
- `border`
- `motion`
- `z-index`

## Initial component inventory

The first design system release should cover:

- app shell
- top bar
- side rail
- search bar
- chat message group
- chat composer
- question prompt block
- requirements checklist item
- panel
- metric card
- form field
- button family
- segmented control
- tab bar
- settings section
- table/grid primitives
- empty state
- modal and command surface
- new project modal

## Anti-patterns to avoid

- generic purple-on-black AI visuals
- excessive gradients across product surfaces
- soft, bubbly SaaS cards everywhere
- oversized corner radii
- too many accent colors
- playful mascot energy
- dense pages with no breathing room
- serif used inside operational micro-UI

## One-sentence direction

Design `justralph.it` like a disciplined AI execution workspace: dark, structured, spacious, technically clear, and selectively editorial.
