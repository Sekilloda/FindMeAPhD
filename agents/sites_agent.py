import sqlite3
import os
import json
from core.llm_router import LLMRouter

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'db', 'system.db')
REF_DOC_PATH = os.path.join(os.path.dirname(__file__), '..', 'db', 'reference_document.json')

class SitesAgent:
    def __init__(self):
        pass

    def run(self):
        """
        Uses LLM to discover and output a list of target sites to search,
        along with scraping instructions.
        """
        # Load reference document to see what they want
        if not os.path.exists(REF_DOC_PATH):
            print("No reference document found. Cannot discover sites.")
            return

        with open(REF_DOC_PATH, 'r') as f:
            ref_doc = json.load(f)

        prompt = f"""
        Given the following user preferences for physics:
        {json.dumps(ref_doc['physics_interests'], indent=2)}

        Suggest 3 specific search targets (URLs) to find PhD positions or Physics schools.
        Provide the output strictly as a JSON object with a single key "sites" that contains an array of objects with keys:
        - "site_url": string
        - "scraping_method": string (e.g. 'search bar query', 'site: url google search', 'xpath')
        - "target_type": string ('course' or 'phd')
        """

        response = LLMRouter.get_completion(
            prompt=prompt,
            system_prompt="You are the Sites Agent. Output ONLY a valid JSON object.",
            task_type="fast",
            json_mode=True
        )

        try:
            parsed = json.loads(response)
            sites_data = parsed.get("sites", [])
            if not sites_data and isinstance(parsed, list):
                sites_data = parsed # Fallback if model ignored object rule
            
            self._save_to_db(sites_data)
            print(f"Added {len(sites_data)} sites to DB.")
        except Exception as e:
            print("Failed to parse sites JSON:", e)

    def _save_to_db(self, sites_data):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        for site in sites_data:
            cursor.execute(
                "INSERT INTO sites (site_url, scraping_method, target_type) VALUES (?, ?, ?)",
                (site.get('site_url'), site.get('scraping_method'), site.get('target_type'))
            )
        conn.commit()
        conn.close()

if __name__ == "__main__":
    agent = SitesAgent()
    agent.run()
