# Hypatia - Theoretical Physics Multi-Agent Swarm

Hypatia is a robust, multi-agent AI system built to autonomously find, scrape, evaluate, and rank academic offerings (PhD positions, Summer/Winter Schools, and Courses) in Theoretical Physics.

## Features

- **Voice Interviewer UI**: A Gradio-based voice application that chats with you naturally to extract your highly specific preferences (core topics, geography, financial requirements) into a structured JSON profile.
- **Autonomous Agent Swarm**: Powered by **LangGraph**, a suite of distinct agents work in a pipeline:
  1. **Sites Agent**: Determines the best URLs and search queries for the job.
  2. **Hunter-Gatherer (Search) Agent**: Scrapes academic job boards and extracts structured data while bypassing basic anti-bot limits.
  3. **Grading Agent**: Evaluates every scraped offering against your personal criteria, generating a score out of 10 for Geography, Academic Fit, and Finances.
  4. **Ranker Agent**: Synthesizes the top findings into a beautifully formatted, actionable Markdown report (`final_ranking.md`).
- **Custom Tiered LLM Router**: Seamlessly cascades between Groq (Qwen/Llama), Gemini, and OpenRouter models. If a rate limit (429) or validation error occurs on one tier, the system instantly catches it and routes to the next tier without crashing.

## Prerequisites

- Python 3.10+
- API Keys for **Groq**, **Gemini**, and **OpenRouter**.

## Installation

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd quick-hypatia
   ```

2. **Set up the virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure your API Keys:**
   Create a `.env` file in the root directory (this is git-ignored) and add your keys:
   ```env
   GROQ_API_KEY=your_groq_key
   GEMINI_API_KEY=your_gemini_key
   OPENROUTER_API_KEY=your_openrouter_key
   ```

4. **Initialize the Database:**
   ```bash
   python db/init_db.py
   ```

## Usage

### 1. Set Your Preferences (Voice AI)
Run the Voice Interviewer to tell the system what you are looking for:
```bash
python ui/interviewer_app.py
```
Open the provided local link (e.g., `http://127.0.0.1:7860`) in your browser. Speak into your microphone to converse with the agent. Once the agent is satisfied, it will automatically save your profile to `db/reference_document.json`.

### 2. Run the Autonomous Swarm
Once your preferences are saved, launch the LangGraph swarm to find your PhDs/courses:
```bash
python core/workflow.py
```
The agents will log their progress in the terminal. If a model fails or hits a rate limit, you will see the system intelligently cascade to backup models. 

### 3. Review the Results
Open the generated `final_ranking.md` file in the root directory to read the final synthesized report, complete with scores, breakdowns, and application advice!
