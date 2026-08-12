# HR Policy Agent Lab — Phase 3: Spec-Driven UI Development with Conductor

Welcome to **Phase 3** of the Elevate HR Policy Agent Lab! In this phase, you will get hands-on experience with **Spec-Driven Development (SDD)** using **Conductor** — the specification and track-driven workflow engine for `agy`.

You will drive your AI pair programmer (`agy`) to specify, plan, and build a modern, responsive **Altostrat Singapore HR Policy Assistant Web UI**. The UI will feature real-time streaming of agent execution steps, active tool calls, citations, and thoughtful micro-animations.

---

## 🚀 Quick Start & Setup

> [!TIP]
> **Recommended Environment:** We recommend using **GCP Cloud Shell** or the **Cloud Shell Editor / built-in IDE** for the best setup and development experience.
>
> **Execution Mode:** When launching `agy`, run `agy --dangerously-skip-permissions` to allow `agy` to build and execute workspace commands without repeatedly asking for permissions.

### Step 1: Clone the Repository

If you haven't already, clone the repository in GCP Cloud Shell:

```bash
git clone https://github.com/salomonerobert/elevate-hr-policy-agent.git
cd elevate-hr-policy-agent
```

### Step 2: Install Dependencies & Environment Setup

1. **Set up the Python environment:**
   ```bash
   uv sync
   ```

2. **Configure Environment Variables (`.env`):**
   Copy `.env.example` to `.env` and configure Vertex AI with your GCP Project ID:
   ```bash
   cp .env.example .env
   ```
   Open `.env` and update it to enable Vertex AI and set your GCP Project ID (commenting out `GEMINI_API_KEY` if present):
   ```env
   GOOGLE_GENAI_USE_VERTEXAI=true
   GOOGLE_CLOUD_PROJECT=your_gcp_project_id
   GOOGLE_CLOUD_LOCATION=global
   ```

3. **Install the Conductor extension into `agy`:**
   ```bash
   agy plugins install https://github.com/gemini-cli-extensions/conductor
   ```

4. **Verify Conductor Installation:**
   Launch `agy` with `agy --dangerously-skip-permissions` and check that `/conductor` commands are available (e.g., `/conductor:conductor-status`, `/conductor:conductor-new-track`).

---

## 🛠️ Phase 3: Building the Interactive Web UI with Conductor

In this phase, you will use Conductor to plan and implement a full-stack interactive Web UI for the HR Policy Agent.

### Step 3.1: Initialize the New Track

Launch `agy` in your terminal using the `--dangerously-skip-permissions` flag:

```bash
agy --dangerously-skip-permissions
```

Execute the `/conductor:conductor-new-track` slash command (or paste the command directly):

```text
/conductor:conductor-new-track
```

#### 📋 Initial Prompt for Lab Participants
When `agy` / Conductor prompts you for the goal of the new track, paste the following prompt:

```text
Create a modern, minimal, and functional Web UI for the Altostrat Singapore HR Policy Assistant.

Key Requirements:
1. Tech Stack: FastAPI or Flask backend serving static HTML/CSS/JS frontend, communicating with the ADK HR Policy Agent (`agent/agent.py`).
2. Branding & Styling: Strictly adhere to Altostrat Singapore branding guidelines in `conductor/product-guidelines.md` and `conductor/product.md`. Professional corporate HR palette (slate, navy, subtle gold/blue accents, clean typography).
3. Real-Time Streaming & Visualizations:
   - Stream agent execution steps to the user in real time via Server-Sent Events (SSE) or WebSockets.
   - Live visual status cards displaying when the agent executes tools (e.g. `read_concept`, `list_concepts`, `search_policy_docs`).
   - Collapsible tool call logs showing exact tool arguments and retrieval outputs.
   - Interactive citation badges linking back to handbook concept files.
4. Micro-Animations & Interactivity:
   - Smooth message entrance animations and typing indicators.
   - Animated pulse indicator when the agent is thinking/retrieving.
   - Fluid responsive layout suitable for desktop and mobile.
```

---

### Step 3.2: Guide Conductor During Clarifications & Spec Definition

As Conductor generates the specification (`spec.md`) and implementation plan (`plan.md`), it may ask you clarifying questions (or trigger `/grill-me`). Use the following guidance to answer the model's questions:

| Topic / Question | Recommended Answer / Guidance |
|---|---|
| **Architecture / Framework** | *"Use FastAPI with `EventSource` (Server-Sent Events) to stream agent responses, tool execution events, and final answers cleanly to vanilla HTML/CSS/JavaScript."* |
| **Styling Strategy** | *"Use Vanilla CSS with modern flexbox/grid layout and Google Fonts (Inter / Plus Jakarta Sans). Maintain Altostrat's corporate HR palette (Deep Navy `#1E293B`, Slate `#475569`, Accent Blue `#2563EB`)."* |
| **Tool Call Streaming** | *"Wrap the ADK agent invocation so that each event (tool call start, tool output, text chunk, citation) emits a JSON event over SSE to update the UI timeline live."* |
| **Animation Preferences** | *"Use subtle CSS transitions for message cards, pulsing glowing dots for active tool execution, and smooth slide-ins for chat bubbles."* |
| **Testing & Verification** | *"Ensure backend endpoints have unit tests using `pytest` and that the web server can be launched locally with `uv run uvicorn main:app --reload`."* |

---

### Step 3.3: Execute Implementation with Conductor

Once the track plan (`conductor/tracks/<track_id>/plan.md`) is approved and generated:

1. **Start Implementation:**
   Execute `/conductor:conductor-implement` in `agy`:
   ```text
   /conductor:conductor-implement
   ```

2. **Watch Conductor Work:**
   `agy` will systematically execute the tasks defined in your plan, writing the backend server, frontend UI files, and unit tests while validating each step using TDD.

3. **Check Progress:**
   At any time, you can inspect progress with:
   ```text
   /conductor:conductor-status
   ```

---

## 🏃 Running & Interacting with the Web UI

After Conductor completes implementation:

1. **Start the Web Server:**
   ```bash
   PYTHONPATH=. uv run uvicorn web.server:app --reload --port 8000
   ```
   *(Or the command specified in your generated track README).*

2. **Open the App:**
   Navigate to `http://localhost:8000` in your browser.

3. **Test Interactive Agent Features:**
   - Ask a question: *"How many days of annual leave do full-time employees in Singapore receive?"*
   - Watch the **real-time execution timeline** display tool calls like `list_concepts` and `read_concept` as the agent searches the OKF bundle or Vertex AI Search.
   - Inspect grounded citations and references directly in the UI.

---

## 🎁 Bonus Challenge: Test Sanity Check & Expanding Coverage

After Conductor finishes implementing your track, take time to review and enhance the test suite created during development.

### Step 1: Sanity Check Conductor-Generated Tests
Inspect the test files created by Conductor (e.g., in `tests/` or `web/tests/`) and verify whether:
- The tests validate meaningful application behavior rather than relying on over-simplified mocks.
- Core functionality—such as SSE streaming endpoints, static file delivery, and agent integration—is adequately tested.
- Edge cases (e.g., empty queries, network delays, unknown policy concept lookups, or tool failures) are covered.

Run the generated test suite in your terminal:
```bash
PYTHONPATH=. uv run pytest
```

### Step 2: Prompt `agy` for Targeted & Comprehensive Testing
Prompt `agy` to audit test coverage, identify missing scenarios, and author new tests for uncovered areas.

In `agy`, paste the following prompt:

```text
Please review the tests that Conductor generated during track implementation:
1. Conduct a sanity check on existing test files to confirm assertions are meaningful and reflect actual application behavior.
2. Identify any missing test coverage or unhandled edge cases (e.g., SSE connection drops, malformed requests, tool execution failures, or missing policy concepts).
3. Write and execute additional pytest test cases to cover these specific areas and confirm that all tests pass cleanly.
```

---

## 📁 Repository Structure

```text
.
├── agent/                  # ADK HR Policy Agent logic & tools
├── conductor/              # Conductor context, guidelines, & track specs
│   ├── product.md
│   ├── product-guidelines.md
│   ├── tech-stack.md
│   ├── workflow.md
│   ├── index.md
│   └── tracks/             # Active and completed Conductor tracks
├── knowledge/              # OKF Policy handbook bundle (Track B)
├── data/                   # Original Policy Handbook PDF
├── evals/                  # Agent evaluation benchmarks
└── README_OLD.md           # Original lab overview for Phase 1 & 2
```

---

## 💡 Key Conductor Commands Reference

- `/conductor:conductor-status` — View current project track progress.
- `/conductor:conductor-new-track` — Create and specify a new feature, bug fix, or chore.
- `/conductor:conductor-implement` — Execute planned tasks sequentially with TDD.
- `/conductor:conductor-review` — Perform code and spec review on completed tracks.
