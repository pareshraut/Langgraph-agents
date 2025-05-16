# Multi-Agent Chatbot Examples

This repository demonstrates two coordination patterns for LLM-based agents using **LangGraph Supervisor** and **LangGraph Swarm** architectures. Under `src/`, you’ll find three example workflows:

* **`agent/`**
  A **voice-enabled customer support** bot implemented in the **Swarm** style by default (but easily switchable to Supervisor).
* **`doc-agent/`**
  An **appointment scheduler** built on the **Supervisor** architecture.
* **`bookings-template/`**
  A **booking workflow** sketch in the **Swarm** architecture.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Quick Start](#quick-start)
3. [Example Workflows](#example-workflows)

   * [Customer Agent (Swarm / Supervisor)](#customer-agent-swarm--supervisor)
   * [Doctor-Scheduler Agent (Supervisor)](#doctor-scheduler-agent-supervisor)
   * [Bookings Template (Swarm)](#bookings-template-swarm)
4. [Voice-Enabled Customer Agent](#voice-enabled-customer-agent)
5. [License](#license)

---

## Architecture Overview

### Supervisor

A single **supervisor** node manages routing to specialized child agents. The workflow always returns control to the supervisor, which decides the next agent or termination step.

![Supervisor Handoff](src/assets/5ac02dee-3fbe-41e2-8ca3-e9f0423d024c.png)

### Swarm

Each agent can hand off directly to any other agent in the group, without a central supervisor. The last active agent drives the next step.

![Swarm Handoff](src/assets/7c6b52bf-554f-4704-88a3-8aee6f53099b.png)

|                    | **Supervisor**            | **Swarm**                                 |
| ------------------ | ------------------------- | ----------------------------------------- |
| **Starting point** | Supervisor                | Last active agent (or default)            |
| **Flow**           | Always back to supervisor | Each agent decides where to hand off next |
| **Interaction**    | Always via supervisor     | Directly between self-sufficient agents   |

![Supervisor vs Swarm Comparison](src/assets/f1d0f6ee-ce96-4a2b-8e34-8c42ee636c05.png)

---

## Quick Start

1. **Install & configure**

   ```bash
   python3.11 -m venv venv
   source venv/bin/activate
   pip install -e .[inmem] langgraph-cli
   ```

2. **Launch LangGraph Dev Studio**

   ```bash
   uvx --refresh \
       --from "langgraph-cli[inmem]" \
       --with-editable . \
       langgraph dev
   ```

   * In Dev Studio you can select any of the three workflows under `src/` and test them interactively.
   * For voice-enabled testing, upload pre-recorded WAVs to the `transcribe_audio` tool, inspect the JSON TTS output, and download/play it locally.

---

## Example Workflows

### Customer Agent (Swarm ↔ Supervisor)

* **Directory**: `src/agent/`
* **Pattern**: By default, demonstrates the **Swarm** handoff between:

  1. **`disambiguation_agent`** (figures out intent)
  2. **`service_agent`** (executes or transfers)
* **Switching**: Change `create_swarm(...)` vs `create_supervisor(...)` in `graph.py` to toggle architectures.

### Doctor-Scheduler Agent (Supervisor)

* **Directory**: `src/doc-agent/`
* **Pattern**: A **Supervisor** routes between:

  1. **`information_agent`** (checks availability)
  2. **`booking_agent`** (sets, cancels, reschedules appointments)

### Bookings Template (Swarm)

* **Directory**: `src/bookings-template/`
* **Pattern**: A minimal **Swarm** example showing tool-calling between flight, hotel, and car-rental agents.

---

## Voice-Enabled Customer Agent

The **Customer Agent** in `src/agent/graph.py` can run locally as a full **voice chatbot**:

1. **Dependencies**

   ```bash
   pip install sounddevice scipy simpleaudio pydub ffmpeg-python
   brew install ffmpeg
   ```

2. **Run**

   ```bash
   python src/agent/graph.py
   ```

   * The script records from your microphone,
   * uses Whisper for STT,
   * invokes the multi-agent workflow,
   * synthesizes the reply with TTS,
   * plays it back—all in a loop until you say “bye.”

3. **Dev Studio Voice Testing**

   * Pre-record a series of WAV files (e.g. `turn1.wav`, `turn2.wav`, …).
   * In Dev Studio, use the **File** uploader on the `transcribe_audio` tool.
   * Examine the JSON with `"tts_base64"` and decode/play locally.

---

## License

MIT © Paresh Raut 
