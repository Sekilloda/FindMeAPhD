import os
from dotenv import load_dotenv

from groq import Groq
from openai import OpenAI

# Load API keys from .env file
load_dotenv()

# Live Models Available (August 2026)
# The router will attempt the first tier, and if it encounters a rate limit or error, 
# it will automatically fall back to the next tier in the list.
TIERED_MODELS = {
    "fast": [
        # Fastest models for JSON extraction and simple logic
        ("groq", "qwen/qwen3.6-27b"), 
        ("gemini", "gemini-3.5-flash-lite"),
        ("openrouter", "google/gemma-4-26b-a4b-it:free")
    ],
    "reasoning": [
        # Capable reasoning models for grading and generating reports
        ("gemini", "gemini-3.5-flash"), 
        ("groq", "openai/gpt-oss-120b"),
        ("openrouter", "nvidia/nemotron-3-ultra-550b-a55b:free")
    ],
    "context": [
        # Highest context window models for reading dense documentation
        ("gemini", "gemini-3.6-flash"), 
        ("openrouter", "nvidia/nemotron-3-super-120b-a12b:free"),
        ("groq", "openai/gpt-oss-20b")
    ]
}

class LLMRouter:
    """
    Custom built tiered router. Attempts API calls iteratively through ranked providers.
    """
    
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
                if provider == "groq":
                    result = LLMRouter._call_groq(model_name, messages, json_mode, max_tokens)
                elif provider == "gemini":
                    result = LLMRouter._call_gemini(model_name, messages, json_mode, max_tokens)
                elif provider == "openrouter":
                    result = LLMRouter._call_openrouter(model_name, messages, json_mode, max_tokens)
                else:
                    raise ValueError(f"Unknown provider: {provider}")
                
                if not result:
                    raise Exception("Model returned an empty or None response.")
                    
                return result
                    
            except Exception as e:
                print(f"[Router] Tier {rank + 1} Failed ({provider}): {str(e)}")
                last_error = str(e)
                continue # Try the next tier
                
        # If all tiers fail
        raise Exception(f"All model tiers exhausted. Last error: {last_error}")

    @staticmethod
    def _call_groq(model_name: str, messages: list, json_mode: bool, max_tokens: int):
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
        # Gemini provides an OpenAI-compatible endpoint, making this boilerplate cleaner
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
        
        # OpenRouter handles JSON via system prompts mostly for free models, 
        # but we can pass response_format if the underlying model supports it.
        # To be safe and avoid 400 errors from specific models not supporting the arg,
        # we will rely on the prompt instructing it for OpenRouter.
            
        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message.content
