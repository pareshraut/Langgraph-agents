# test_openai_quota.py

import os
import openai

# — Insert your key here for testing (or export OPENAI_API_KEY in your shell) —
os.environ["OPENAI_API_KEY"] = ""

# Tell the SDK where to find it
openai.api_key = os.getenv("OPENAI_API_KEY")

def test_chat(model="gpt-3.5-turbo"):
    try:
        resp = openai.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": "Say hello in one word."}],
            max_tokens=5,
        )
        print(f"[✓] {model} call succeeded:", resp.choices[0].message.content)
    except openai.RateLimitError as e:
        print(f"[✗] Rate limit hit for {model}:", e)
    except openai.AuthenticationError as e:
        print(f"[✗] Authentication error:", e)
    except openai.OpenAIError as e:
        print(f"[✗] Other OpenAI error:", e)
    except Exception as e:
        print(f"[✗] Unexpected error:", e)

if __name__ == "__main__":
    print("Testing gpt-3.5-turbo…")
    test_chat("gpt-3.5-turbo")
    print("\nTesting gpt-4o…")
    test_chat("gpt-4o")
