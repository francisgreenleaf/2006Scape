# Agent Terminal Cleanup Plan

## Goal

Make the in-client Agent Terminal feel calmer and easier to work in, with no multi-line wrapping in the side panel and a tab affordance that reads as a compact tool instead of a cramped text surface.

The current pain points are visible in the tab screenshot and in the code:

- The selected tab slot is small, but the terminal identity is being carried by text-like drawing and an oversized terminal glyph.
- `AgentTerminalLog.renderLines(...)` wraps every entry to fit the narrow panel, so long tool names, app-server status, and assistant messages create noisy multi-row blocks.
- The panel uses a bordered, high-contrast console treatment that competes with the old client chrome.

## Proposed Implementation

### 1. Make terminal entries single-line by design

Files:

- `2006Scape Client/src/main/java/AgentTerminalLog.java`
- `2006Scape Client/src/main/java/Game.java`

Replace `renderLines(TextDrawingArea font, int maxWidth)` wrapping behavior with a single-line render path:

- Keep one rendered row per log entry.
- Preserve the timestamp and short label.
- Truncate the message to fit the available pixel width with an ellipsis.
- Prefer dropping the middle of very long structured text when useful, so `"rs.travel_to_landmark_until_arrived_XS: ok ..."` keeps the tool/status identity and end result.
- Clamp stored messages sooner for terminal display, while keeping existing client/server logs as the durable evidence surface.

Acceptance:

- No terminal entry can produce more than one visible row.
- Scroll offset math counts entries, not wrapped render lines.
- Long app-server messages such as `Codex app-server initialized` fit without layout churn.
- Long tool results remain recognizable rather than becoming wall text.

### 2. Separate terminal summary text from detailed evidence

Files:

- `2006Scape Client/src/main/java/AgentTerminalLog.java`
- `2006Scape Client/src/main/java/CodexAppServerClient.java`

Make terminal copy concise at the source where it is naturally noisy:

- Tool start: `tool rs.observe_state_XS`
- Tool result: `ok rs.observe_state_XS 84ms`
- Turn lifecycle: `turn started`, `turn done`, `turn interrupted`
- Assistant output: first short sentence or first N display characters only.
- Errors and warnings keep their leading cause, truncated after the useful part.

Do not remove full detail from the server bridge logs, agent-session JSONL, Markdown summaries, or Codex transcript enrichment. The side panel should be a dashboard, not the audit trail.

Acceptance:

- A normal `/agent status` flow fits in a readable sequence of short rows.
- A busy tool loop does not flood the panel with wrapped JSON-ish text.
- Important failures still show enough cause to act.

### 3. Refine panel layout for scanning

File:

- `2006Scape Client/src/main/java/Game.java`

Keep the panel inside the existing inventory side area, but reduce visual heaviness:

- Use the darker content area as the main terminal surface and make the outer border more subdued.
- Shorten header to `Agent` or `Agent Console`; keep status right-aligned but truncate by pixel width, not character count.
- Give rows consistent left padding and use a dim timestamp/label treatment if feasible.
- Keep the input row stable and single-line, with the cursor and prompt never resizing the field.

Implementation note: the current text API draws one color per string, so dimming timestamp/label independently may require splitting the row into prefix and message draw calls. If that adds too much fragility, keep one-color rows for this pass and prioritize no wrapping.

Acceptance:

- Terminal rows do not touch the border.
- Header/status cannot overlap.
- Input text clips from the left as it does today and never wraps.

### 4. Replace the cramped tab treatment with an icon-first affordance

File:

- `2006Scape Client/src/main/java/Game.java`

Update `drawAgentTerminalIcon(...)` so the tab slot reads as a small terminal button:

- Keep it icon-first: a compact `>` prompt and short baseline.
- Avoid long label text in the tab slot.
- Tighten the box dimensions so it sits comfortably inside the existing bottom-left tab hitbox.
- Use selected/unselected colors that match the existing redstone tab state without the bright icon looking clipped.

Acceptance:

- In the bottom-left tab, no text appears clipped or partly hidden.
- Selected and unselected states are legible at 1x and `-scale 2`.
- The tab does not look like a second miniature terminal panel.

### 5. Add focused tests for no-wrap rendering

File:

- `2006Scape Client/src/test/java/AgentTerminalLogTest.java`

Add JUnit tests around the rendering helper rather than screenshot-only validation:

- Long messages render as exactly one `RenderLine`.
- Very narrow widths still render one non-empty clipped line.
- Newline/tab/control characters are normalized before rendering.
- Scroll math remains stable when many long entries are added.

If the implementation keeps width fitting tied to `TextDrawingArea`, add a small test-visible helper that truncates by character budget, or introduce a package-private width strategy so tests do not need a live client font.

Validation command:

```sh
mvn -q -pl "2006Scape Client" test
```

### 6. Visually verify in the real client

Use the documented local client flow only after code is implemented and packaged. Prefer a client-only restart if the server is healthy.

Suggested manual proof:

```sh
mvn -q -pl "2006Scape Client" -DskipTests package
./scripts/start-client.sh -scale 2 -no-nav
```

Then in the client:

- Open the Agent tab.
- Run `/agent status`.
- Run one intentionally long task line or status-producing command.
- Capture a compact screenshot with:

```sh
agent-navigation/tools/capture-client-screenshot.sh --prefix agent-terminal-cleanup --native-size
```

Acceptance:

- Screenshot shows no wrapped rows.
- The tab icon is clean in the bottom-left slot.
- Terminal remains usable at both native scale and `-scale 2`.

## Risk Notes

- The side panel is inherently narrow, so single-line display means some detail must be clipped. That is acceptable because durable logs already carry full evidence.
- `TextDrawingArea` pixel width APIs are old client code; keep changes narrow and test helper logic separately where possible.
- Do not broaden this into a full client theme pass. The intended result is a cleaner terminal experience inside the existing 2006-era chrome.
