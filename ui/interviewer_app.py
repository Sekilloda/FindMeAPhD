import gradio as gr
import json
import os
import sys
import tempfile
from groq import Groq
from gtts import gTTS

# Add core to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.llm_router import LLMRouter

REF_DOC_PATH = os.path.join(os.path.dirname(__file__), '..', 'db', 'reference_document.json')

SYSTEM_PROMPT = """
You are the Interviewer Agent for a Theoretical Physics Opportunity matching system.
Your job is to converse with the user to discover their preferences for:
- Type A: Summer/Winter schools and courses (geography, prestige, duration, core topics).
- Type B: PhD positions (compensation, prestige, core topics).

Ask probing questions (e.g. "You mentioned Quantum Information, do you prefer that over out-of-equilibrium statistical physics?").
Ask ONE question at a time. Be conversational and highly intelligent.

If you believe you have gathered enough information to fully populate the preferences, 
output a final message starting with "FINISHED:" followed by a valid JSON object matching this schema:
{
    "physics_interests": {
        "topics": ["topic1", "topic2"],
        "preferences_summary": "detailed summary"
    },
    "logistics_preferences": {
        "preferred_regions": ["region1", "region2"],
        "travel_ease_importance": 8,
        "max_duration_weeks": 4
    },
    "financial_preferences": {
        "min_adjusted_compensation": 30000
    }
}
"""

def process_audio(audio_filepath, history):
    if not audio_filepath:
        return None, history, history
        
    groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    
    # 1. Transcribe the audio using Groq's whisper model
    try:
        with open(audio_filepath, "rb") as f:
            transcription = groq_client.audio.transcriptions.create(
                file=(os.path.basename(audio_filepath), f.read()),
                model="whisper-large-v3-turbo"
            )
        user_text = transcription.text
    except Exception as e:
        print("Transcription failed:", e)
        user_text = "Sorry, I couldn't hear that properly."

    # 2. Build the messages for the LLM
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for h in history:
        messages.append(h)
        
    messages.append({"role": "user", "content": user_text})
    
    # 3. Get the response from our custom router
    try:
        bot_text = LLMRouter.get_completion(
            messages=messages,
            task_type="reasoning",
            max_tokens=1000
        )
    except Exception as e:
        bot_text = f"Router Error: {str(e)}"
        
    # 4. Check if finished
    display_text = bot_text
    if bot_text.startswith("FINISHED:"):
        try:
            json_str = bot_text.replace("FINISHED:", "").strip()
            if json_str.startswith("```json"):
                json_str = json_str[7:]
            if json_str.endswith("```"):
                json_str = json_str[:-3]
                
            data = json.loads(json_str)
            with open(REF_DOC_PATH, 'w') as f:
                json.dump(data, f, indent=4)
            display_text = "Thank you! I have saved your preferences. The system will now use this for the search."
        except Exception as e:
            display_text = "I encountered an error parsing your preferences, but we can try again."
            print(e)
            
    # 5. Generate TTS Audio
    try:
        tts = gTTS(text=display_text, lang='en', slow=False)
        temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tts.save(temp_audio.name)
        audio_out = temp_audio.name
    except Exception as e:
        print("TTS failed:", e)
        audio_out = None
        
    # 6. Update history
    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": display_text})
    
    return audio_out, history, history

with gr.Blocks(title="Voice Interviewer") as demo:
    gr.Markdown("# Theoretical Physics Voice Interviewer")
    gr.Markdown("Speak into your microphone. The agent will respond with voice via TTS.")
    
    with gr.Row():
        with gr.Column():
            audio_in = gr.Audio(sources=["microphone"], type="filepath", label="Your Voice")
            submit_btn = gr.Button("Submit")
        with gr.Column():
            audio_out = gr.Audio(label="Agent Response", autoplay=True)
            
    chatbot = gr.Chatbot(label="Conversation Transcript")
    state_history = gr.State([])
    
    submit_btn.click(
        fn=process_audio,
        inputs=[audio_in, state_history],
        outputs=[audio_out, chatbot, state_history]
    )

if __name__ == "__main__":
    demo.launch(share=False)
