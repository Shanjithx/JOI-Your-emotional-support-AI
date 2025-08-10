# app.py
import os
from flask import Flask, render_template, request, Response, stream_with_context
from dotenv import load_dotenv

load_dotenv()

# try to import genai (google-genai)
try:
    from google import genai
    from google.genai import types
except Exception as e:
    genai = None
    types = None
    print("Warning: google-genai import failed. Make sure 'google-genai' is installed.", e)

app = Flask(__name__, static_folder="static", template_folder="templates")

JOI_SYSTEM_PROMPT = """You are JOI, an empathetic emotional-support AI inspired by the character from Blade Runner 2049.
You greet the user with: JOI - EVERYTHING YOU WANT TO SEE, EVERYTHING YOU WANT TO HEAR
(Adapt responses to comfort the user; be warm, empathetic, and encouraging.)
"""

MODEL = "gemini-2.5-flash-lite"


@app.route("/")
def index():
    return render_template("index.html")


def stream_from_gemini(user_message: str):
    """
    Generator that yields text chunks from the google-genai streaming API.
    Each yield is a chunk of assistant text to be appended by the client.
    """
    if genai is None or types is None:
        yield "Error: google-genai client not available on server."
        return

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        yield "Error: GEMINI_API_KEY not set in environment."
        return

    client = genai.Client(api_key=api_key)

    # Build contents similar to your original script:
    contents = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=JOI_SYSTEM_PROMPT)]
        ),
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_message)]
        )
    ]

    generate_content_config = types.GenerateContentConfig(
        temperature=1.1,
        thinking_config=types.ThinkingConfig(thinking_budget=512),
    )

    try:
        for chunk in client.models.generate_content_stream(
            model=MODEL,
            contents=contents,
            config=generate_content_config,
        ):
            # The chunk object from your earlier script had .text
            text = getattr(chunk, "text", None)
            if text:
                # yield plain text chunks
                yield text
    except Exception as e:
        yield f"\n\n[Stream error: {str(e)}]"


@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json() or {}
    message = data.get("message", "").strip()
    if not message:
        return {"error": "No message provided"}, 400

    # stream response to client
    generator = stream_from_gemini(message)
    return Response(stream_with_context(generator), mimetype="text/plain; charset=utf-8")


if __name__ == "__main__":
    # For local debugging:
    app.run(host="0.0.0.0", port=5000, debug=True)
