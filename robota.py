from flask import Flask, request, jsonify, send_file, render_template
import os
import asyncio
import sys
import tempfile
import edge_tts
from groq import Groq
from langdetect import detect, LangDetectException

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

app = Flask(__name__)

# ── Groq API Key ──────────────────────────────────────────────
GROQ_API_KEY = "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"   # ← paste your new Groq key here

LANGUAGE_CONFIG = {
    "en": {"name": "English",  "tts_voice": "en-US-AriaNeural"},
    "hi": {"name": "Hindi",    "tts_voice": "hi-IN-SwaraNeural"},
    "gu": {"name": "Gujarati", "tts_voice": "gu-IN-DhwaniNeural"},
}

SYSTEM_PROMPT = """You are a friendly, helpful multilingual robot assistant
built for a workshop. You speak English, Hindi, and Gujarati.
Always reply in the SAME language the user speaks to you.
Keep responses SHORT (10-20 sentences max). Be warm and encouraging."""

AUDIO_OUTPUT_FILE = os.path.join(tempfile.gettempdir(), "robot_response.mp3")


def detect_language(text):
    try:
        detected = detect(text)
        return detected if detected in LANGUAGE_CONFIG else "en"
    except LangDetectException:
        return "en"


async def _tts_save(text, voice):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(AUDIO_OUTPUT_FILE)


def generate_speech(text, lang_code):
    voice = LANGUAGE_CONFIG.get(lang_code, LANGUAGE_CONFIG["en"])["tts_voice"]
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_tts_save(text, voice))
    loop.close()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_text = data.get("text", "").strip()

    if not user_text:
        return jsonify({"error": "No text provided"}), 400

    # Detect language
    lang_code = detect_language(user_text)
    lang_name = LANGUAGE_CONFIG.get(lang_code, LANGUAGE_CONFIG["en"])["name"]

    # Get AI response from Groq
    try:
        client = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"[Reply ONLY in {lang_name}]\nUser: {user_text}"},
            ],
            max_tokens=150,
            temperature=0.7,
        )
        reply = response.choices[0].message.content.strip()
    except Exception as e:
        reply = "Sorry, I had a thinking error. Please try again!"
        lang_code = "en"

    # Generate speech
    try:
        generate_speech(reply, lang_code)
    except Exception as e:
        return jsonify({"reply": reply, "lang": lang_code, "audio": False})

    return jsonify({"reply": reply, "lang": lang_code, "audio": True})


@app.route("/audio")
def audio():
    if os.path.exists(AUDIO_OUTPUT_FILE):
        return send_file(AUDIO_OUTPUT_FILE, mimetype="audio/mpeg")
    return jsonify({"error": "No audio file"}), 404


if __name__ == "__main__":
    app.run(debug=True, port=5000)
