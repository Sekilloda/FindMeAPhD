import json
import os
from typing import Dict, Any

DOCS_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "agent_registry.json")

class MetaAgent:
    """
    The Meta Agent is responsible for maintaining the system documentation
    regarding the capabilities, required intelligence level, and model mapping
    for all other agents in the swarm.
    """
    
    def __init__(self):
        self.registry = self._load_registry()
        
    def _load_registry(self) -> Dict[str, Any]:
        if os.path.exists(DOCS_PATH):
            with open(DOCS_PATH, 'r') as f:
                return json.load(f)
        return self._get_default_registry()
        
    def _get_default_registry(self) -> Dict[str, Any]:
        return {
            "agents": {
                "InterviewerAgent": {
                    "role": "Extract user preferences for theoretical physics opportunities",
                    "intelligence_level": "reasoning",
                    "inputs": ["User Voice/Text"],
                    "outputs": ["reference_document.json"],
                    "recommended_model": "gemini-3.5-flash"
                },
                "SitesAgent": {
                    "role": "Discover and document scraping instructions for search targets",
                    "intelligence_level": "reasoning",
                    "inputs": ["General query"],
                    "outputs": ["sites.db entries"],
                    "recommended_model": "gemini-3.5-flash"
                },
                "HunterGathererAgent": {
                    "role": "Scrape sites and extract structured data",
                    "intelligence_level": "fast",
                    "inputs": ["sites.db entry", "HTML/Search Results"],
                    "outputs": ["offerings.db entries"],
                    "recommended_model": "qwen3.6-27b"
                },
                "GradingAgent": {
                    "role": "Score offerings against user preferences",
                    "intelligence_level": "context",
                    "inputs": ["offerings.db entry", "reference_document.json"],
                    "outputs": ["offerings.db score updates"],
                    "recommended_model": "gemini-3.6-flash"
                },
                "RankerAgent": {
                    "role": "Synthesize scores and generate human-readable report",
                    "intelligence_level": "reasoning",
                    "inputs": ["offerings.db"],
                    "outputs": ["final_ranking.md"],
                    "recommended_model": "gemini-3.5-flash"
                }
            },
            "routing_strategy": "Custom tiered fallback router natively integrating Groq, Gemini, and OpenRouter APIs."
        }
        
    def save_registry(self):
        """Saves the current registry state to disk."""
        with open(DOCS_PATH, 'w') as f:
            json.dump(self.registry, f, indent=4)
            
    def display_system_status(self):
        """Prints the system configuration and agent mapping."""
        print("=== System Swarm Configuration ===")
        for agent_name, details in self.registry["agents"].items():
            print(f"- {agent_name}:")
            print(f"    Role: {details['role']}")
            print(f"    Intelligence Level Needed: {details['intelligence_level']}")
            print(f"    Recommended Model: {details['recommended_model']}")
        print("==================================")

if __name__ == "__main__":
    agent = MetaAgent()
    agent.save_registry()
    agent.display_system_status()
