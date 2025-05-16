import os, json, random, base64
from typing import Optional

# ─── Environment & Clients ────────────────────────────────────────────────────
os.environ["OPENAI_API_KEY"] = ""


from openai import OpenAI
from langchain_openai import ChatOpenAI

client = OpenAI()
llm    = ChatOpenAI(model="gpt-4o", temperature=0.2)

# ─── Ontology ─────────────────────────────────────────────────────────────────
INTENT_ONTOLOGY = {
  "Retirement": {
    "RMD": ["RequestStatus", "TakeRMD", "SetupService"],
    "IRA": ["Open", "Change", "Withdraw", "Convert"],
    "401k": ["General", "Rollover", "Transfer"]
  },
  "Account": {
    "Access": ["PasswordReset", "SecurityCheck", "RequestSupport"],
    "Maintenance": ["ChangeInfo", "Verify", "Hold", "Authorization"],
    "OpenClose": ["Open", "Close", "Combine"]
  },
  "Transactions": {
    "BuySell": ["Buy", "Sell", "Exchange", "Cancel"],
    "Automatic": ["Invest", "Withdraw", "Transfer"],
    "Status": ["CheckStatus", "Verify", "Refund"]
  },
  "PersonalInfo": {
    "Identity": ["NameChange", "SSN", "TaxID"],
    "Contact": ["AddressChange", "EmailPreferences", "PhoneUpdate"]
  },
  "Investments": {
    "Funds": ["Trade", "Exchange", "Redeem"],
    "Stocks": ["Trade", "Quotes"],
    "Bonds": ["Trade"],
    "ETFs": ["Trade"]
  },
  "Support": {
    "Tech": ["OnlineAccess", "Quicken", "Webcast"],
    "Rep": ["Inquiry", "Callback", "Resolution"],
    "Fraud": ["Report"]
  },
  "Statements": {
    "Activity": ["View", "ProofOfFunds"],
    "Tax": ["1099", "5498", "W2", "W9", "Withholding"]
  }
}

# ─── Core Tools & Agents ───────────────────────────────────────────────────────
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts.chat import ChatPromptTemplate
from langgraph.prebuilt.chat_agent_executor import create_react_agent
from langgraph_supervisor import create_supervisor
from langgraph_swarm import create_handoff_tool,create_swarm

# Define handoff tools
transfer_to_disambiguation_agent = create_handoff_tool(
    agent_name="disambiguation_agent",
    description="Transfer user to the disambiguation agent that can help identify the leaf intent.",
)

transfer_to_service_agent = create_handoff_tool(
    agent_name="service_agent",
    description="Transfer user to the service agent that can route to the right deaprtment",
)

@tool
def handle_intent(intent: str) -> str:
    """Handoff the confirmed intent."""
    return f"Transferring you to the {intent} department."

ontology_json = json.dumps(INTENT_ONTOLOGY, indent=2)

escaped_json = ontology_json.replace("{", "{{").replace("}", "}}")

disambiguation_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        (
            "You are an expert in intent disambiguation.  \n"
            "Here is the ontology of intents (JSON):\n"
            "```\n"
            f"{escaped_json}\n"
            "```\n\n"
            "Ask the user yes/no or either/or questions to narrow to a leaf intent, then once user"
            " gives exactly the leaf intent name transfer that leaf intent name to service agent via tool.  "
            "If out of scope, transfer to service agent with intent == Out_of_scope."
        ),
    ),
    ("placeholder", "{messages}"),
])

disambiguation_agent = create_react_agent(
    name="disambiguation_agent",
    model=llm,
    tools=[transfer_to_service_agent],  # no random tool
    prompt=disambiguation_prompt,
)

service_prompt = ChatPromptTemplate.from_messages([
    ("system", "Take the confirmed intent name (a leaf) and produce a handoff message."),
    ("placeholder", "{messages}")
])
service_agent = create_react_agent(
    name="service_agent",
    model=llm,
    tools=[handle_intent,transfer_to_disambiguation_agent],
    prompt=service_prompt
)


# Build and compile the supervisor graph (no STT/TTS tools here)
supervisor_prompt = (
    "You are a customer support supervisor. "
    "Route the conversation between disambiguation_agent and service_agent. " \
    "Once Sevice agent confirms transfer to the appropriate department"
    "If the intent is out of scope, very polietly use service agent to transfer the client to a human agent."
)

# Compile and run!
builder = create_swarm(
    [disambiguation_agent, service_agent], default_active_agent="disambiguation_agent"
)
graph = builder.compile()


## IF needed try using the supervisor agent, which works better if we want to always have a deterministic path. 
# builder = create_supervisor(
#     agents=[disambiguation_agent, service_agent],
#     model=llm,
#     prompt=supervisor_prompt,
# )
# graph = builder.compile()

# ─── Audio I/O (local testing only) ───────────────────────────────────────────
import sounddevice as sd
import string
import imageio_ffmpeg
from pydub import AudioSegment
os.environ["PATH"] += os.pathsep + "/opt/homebrew/bin"

from pydub import AudioSegment
# explicitly point pydub at the binaries:
AudioSegment.converter = "/opt/homebrew/bin/ffmpeg"
AudioSegment.ffprobe   = "/opt/homebrew/bin/ffprobe"
import io
from scipy.io.wavfile import write
import simpleaudio as sa

def record_audio(seconds: int = 5,
                 fs: int = 16000,
                 filename: str = "local_input.wav") -> str:
    """Record from mic and save to WAV."""
    print(f"[Recording {seconds}s]…")
    rec = sd.rec(int(seconds * fs), samplerate=fs, channels=1, dtype="int16")
    sd.wait()
    write(filename, fs, rec)
    return filename

def transcribe_audio(file_path: str) -> str:
    """Use Whisper to transcribe a local WAV file."""
    with open(file_path, "rb") as f:
        resp = client.audio.transcriptions.create(model="whisper-1", file=f)
    return resp.text

def synthesize_speech(text: str) -> AudioSegment:
    """Return a pydub AudioSegment decoded from TTS MP3 bytes."""
    resp = client.audio.speech.create(
        model="tts-1", voice="nova", input=text
    )
    mp3_bytes = resp.content
    # pydub will now use our bundled ffmpeg for both decoding & probing
    audio = AudioSegment.from_file(io.BytesIO(mp3_bytes), format="mp3")
    return audio

def is_exit_command(text: str) -> bool:
    # Remove leading/trailing whitespace, lowercase, strip punctuation
    cleaned = text.strip().lower().translate(
        str.maketrans("", "", string.punctuation)
    )
    return cleaned in ("bye", "goodbye", "exit", "quit", "Thanks, bye.")

def run_conversational_voice_bot(interaction_seconds=5, fs=16000, filename="local_input.wav"):
    state = {"messages": []}
    print("Starting voice chat (say 'bye' or 'goodbye' to end)…")
    while True:
        # 1) record & STT
        record_audio(interaction_seconds, fs, filename)
        user_text = transcribe_audio(filename)
        print("USER:", user_text)

        # 2) check for exit
        if is_exit_command(user_text):
            print("User said exit—ending conversation.")
            # Final goodbye
            farewell = "Thank you for calling!"
            print("BOT :", farewell)
            audio = synthesize_speech(farewell)
            sa.play_buffer(
                audio.raw_data,
                num_channels=audio.channels,
                bytes_per_sample=audio.sample_width,
                sample_rate=audio.frame_rate
            ).wait_done()
            break

        state["messages"].append(HumanMessage(content=user_text))

        # 3) normal routing & reply
        state = graph.invoke(state)
        reply = state["messages"][-1].content
        print("BOT :", reply)

        # 4) TTS & playback
        audio = synthesize_speech(reply)
        sa.play_buffer(
            audio.raw_data,
            num_channels=audio.channels,
            bytes_per_sample=audio.sample_width,
            sample_rate=audio.frame_rate
        ).wait_done()

if __name__ == "__main__":
    run_conversational_voice_bot()
