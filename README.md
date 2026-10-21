# 🎯 IELTS Master Coach — AI Band 8.5 Preparation & Speaking Simulator

An advanced AI conversational agent built with **Google Agent Development Kit (ADK)**, **Gemini 2.5 Flash**, **Vertex AI Memory Bank**, **Cloud Firestore**, **Google Cloud Storage**, and **A2UI Rich Presentation Cards**.

IELTS Master Coach is designed to prepare test-takers across all 4 IELTS skills (Speaking, Writing, Reading, Listening) with a flagship focus on real-time examiner simulations, writing metrics audits, and visual Task 1 data interpretation.

---

## 🌟 Key Capabilities & Tools

1. **🧠 Long-Term Memory (Vertex AI Memory Bank):**
   - Automatically tracks candidate's target band score (e.g. Band 7.5 / 8.0).
   - Retains persistent speaking hesitations, recurring grammar slips, and weak essay structures across sessions.

2. **🎴 Rich Presentation UI (A2UI v0.8):**
   - Renders Speaking Part 2 Cue Cards with preparation countdown timers.
   - Generates multi-criteria diagnostic scorecards and academic collocation cheat sheets.

3. **📊 Cambridge Score Engine:**
   - Official IELTS overall score rounding arithmetic (`.25` $\rightarrow$ `.5`, `.75` $\rightarrow$ `1.0`, `.125` $\rightarrow$ `.0`).
   - Identifies candidate's lowest sub-score bottleneck and maps to CEFR levels (C2 to A2).

4. **📝 Writing Task 1 & 2 Analytics:**
   - **Task 1 Visual Generator:** Generates statistical Bar, Line, and Pie charts via `matplotlib` and hosts them on Cloud Storage for data interpretation practice.
   - **Writing Metrics Engine:** Evaluates word count penalty deficit, Type-Token Ratio (TTR) lexical diversity, paragraph structure, and run-on sentences (>35 words).

5. **🎙️ Real-Time Speaking Simulation:**
   - Integrated Web Speech API microphone input in the frontend chat interface.
   - Speech rate analytics (Words Per Minute / WPM against the 110–150 WPM benchmark).
   - Automatic filler word detection (`um`, `uh`, `like`, `you know`).

6. **📚 Firestore Question Bank:**
   - Centralized practice item catalog across all 4 skills stored in Cloud Firestore (`ielts_prompts`).

---

## 🏗️ Architecture & Project Structure

```
ielts-master-coach/
├── app/
│   ├── agent.py               # Root Agent, 8 domain tools, prompt logic
│   ├── a2ui_utils.py          # A2UI v0.8 callback & A2A datapart wrapper
│   ├── fast_api_app.py        # ADK FastAPI runner with Memory Bank wiring
│   └── app_utils/             # Memory service registry & helpers
├── frontend/
│   ├── main.py                # FastAPI A2A Proxy (Browser -> A2A -> Agent Engine)
│   └── static/
│       └── index.html         # IELTS Chat UI + Voice Mic + A2UI Card Renderer
├── tests/
│   └── unit/
│       └── test_ielts_engine.py # Comprehensive unit test suite (100% pass)
├── seed_firestore.py          # Firestore database seeder
├── project_brief.md           # Workshop project design specification
├── agents-cli-manifest.yaml   # Agent manifest configuration
└── pyproject.toml             # Python dependencies
```

---

## 🚀 Local Run & Verification

### 1. Run Unit Tests
```bash
./.venv/bin/python -m pytest tests/unit/test_ielts_engine.py -v
```

### 2. Launch Local Web Chat Frontend
```bash
cd frontend && python main.py
```
Open your browser at `http://localhost:8080` to chat with **IELTS Master Coach**, practice with the microphone, or click quick-action prompt chips!
