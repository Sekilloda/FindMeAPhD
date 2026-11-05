import os
import urllib.request
from dotenv import load_dotenv

from openai import OpenAI

# Load API keys from .env file if present
load_dotenv()

LOCAL_URL = os.getenv("LOCAL_LLM_URL", "http://127.0.0.1:8080/v1")

# Tiered models ranking: Local first, then fallbacks
TIERED_MODELS = {
    "fast": [
        ("local", "qwen3.6-35b-a3b"),
        ("groq", "qwen/qwen3.6-27b"), 
        ("gemini", "gemini-3.5-flash-lite"),
        ("openrouter", "google/gemma-4-26b-a4b-it:free")
    ],
    "reasoning": [
        ("local", "qwen3.6-35b-a3b"),
        ("local", "qwen3.8-27b"),
        ("gemini", "gemini-3.5-flash"), 
        ("groq", "openai/gpt-oss-120b"),
        ("openrouter", "nvidia/nemotron-3-ultra-550b-a55b:free")
    ],
    "context": [
        ("local", "qwen3.6-35b-a3b"),
        ("local", "qwen3.8-27b"),
        ("gemini", "gemini-3.6-flash"), 
        ("openrouter", "nvidia/nemotron-3-super-120b-a12b:free"),
        ("groq", "openai/gpt-oss-20b")
    ]
}

class LLMRouter:
    """
    Tiered router: Attempts local llama-server first, then cascades to cloud APIs if available.
    """
    
    @staticmethod
    def is_local_running() -> bool:
        """Checks if local llama-server is responding at http://127.0.0.1:8080/health"""
        try:
            req = urllib.request.Request("http://127.0.0.1:8080/health")
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                return resp.status in (200, 204)
        except Exception:
            return False

    @staticmethod
    def ensure_local_running() -> bool:
        """
        Ensures local llama-server router is active.
        If down, automatically spawns ~/Models/start-llama-router.sh in the background.
        """
        if LLMRouter.is_local_running():
            return True

        router_script = os.path.expanduser("~/Models/start-llama-router.sh")
        if os.path.exists(router_script) and os.access(router_script, os.X_OK):
            try:
                import subprocess
                import time
                print("[Router] Local llama-server is not running. Auto-launching ~/Models/start-llama-router.sh...")
                subprocess.Popen(
                    [router_script],
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                for _ in range(12):
                    time.sleep(0.5)
                    if LLMRouter.is_local_running():
                        print("[Router] [✓] Successfully launched local llama-server router on http://127.0.0.1:8080.")
                        return True
            except Exception as e:
                print(f"[Router] Failed to auto-launch local llama-server: {e}")

        return False

    @staticmethod
    def unload_models():
        """
        Frees unified memory by stopping any loaded model worker processes.
        The router daemon on port 8080 remains listening and will reload models on demand.
        """
        try:
            import subprocess
            cmd = "ps -ef | grep 'llama-server' | grep -v 'models-preset' | grep -v grep | awk '{print $2}'"
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            pids = res.stdout.strip().split()
            for pid in pids:
                if pid:
                    subprocess.run(["kill", "-9", pid], check=False)
            if pids:
                print(f"[Router] Unloaded {len(pids)} model worker(s) and released memory back to macOS.")
        except Exception as e:
            print(f"[Router] Model unload check failed: {e}")

    @staticmethod
    def get_completion(prompt: str = None, system_prompt: str = None, messages: list = None, task_type: str = "reasoning", json_mode: bool = False, max_tokens: int = 4000):
        if messages is None:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            if prompt:
                messages.append({"role": "user", "content": prompt})

        tiers = TIERED_MODELS.get(task_type, TIERED_MODELS["fast"])
        last_error = None
        
        for rank, (provider, model_name) in enumerate(tiers):
            print(f"[Router] Attempting Tier {rank + 1}: {provider} -> {model_name}")
            try:
                result = None
                if provider == "local":
                    result = LLMRouter._call_local(model_name, messages, json_mode, max_tokens)
                elif provider == "groq":
                    if not os.getenv("GROQ_API_KEY"):
                        print("[Router] Skipping Groq (GROQ_API_KEY not configured)")
                        continue
                    result = LLMRouter._call_groq(model_name, messages, json_mode, max_tokens)
                elif provider == "gemini":
                    if not os.getenv("GEMINI_API_KEY"):
                        print("[Router] Skipping Gemini (GEMINI_API_KEY not configured)")
                        continue
                    result = LLMRouter._call_gemini(model_name, messages, json_mode, max_tokens)
                elif provider == "openrouter":
                    if not os.getenv("OPENROUTER_API_KEY"):
                        print("[Router] Skipping OpenRouter (OPENROUTER_API_KEY not configured)")
                        continue
                    result = LLMRouter._call_openrouter(model_name, messages, json_mode, max_tokens)
                else:
                    raise ValueError(f"Unknown provider: {provider}")
                
                if not result:
                    raise Exception("Model returned an empty or None response.")
                    
                return result
                    
            except Exception as e:
                print(f"[Router] Tier {rank + 1} Failed ({provider}): {str(e)}")
                last_error = str(e)
                continue
                
        raise Exception(f"All model tiers exhausted. Last error: {last_error}")

    @staticmethod
    def _call_local(model_name: str, messages: list, json_mode: bool, max_tokens: int):
        client = OpenAI(
            base_url=LOCAL_URL,
            api_key="local-server",
            timeout=180.0
        )
        kwargs = {
            "model": model_name,
            "messages": messages,
            "max_tokens": max(max_tokens, 3500),
            "temperature": 0.2
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        content = choice.message.content
        if not content and hasattr(choice.message, "reasoning_content"):
            content = choice.message.reasoning_content
        return content

    @staticmethod
    def _call_groq(model_name: str, messages: list, json_mode: bool, max_tokens: int):
        from groq import Groq
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        kwargs = {
            "model": model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.2
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    @staticmethod
    def _call_gemini(model_name: str, messages: list, json_mode: bool, max_tokens: int):
        client = OpenAI(
            api_key=os.getenv("GEMINI_API_KEY"),
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )
        kwargs = {
            "model": model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.2
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    @staticmethod
    def _call_openrouter(model_name: str, messages: list, json_mode: bool, max_tokens: int):
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"),
        )
        kwargs = {
            "model": model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.2
        }
        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message.content
