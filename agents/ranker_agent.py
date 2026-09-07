import sqlite3
import os
import json
from core.llm_router import LLMRouter

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'db', 'system.db')
REF_DOC_PATH = os.path.join(os.path.dirname(__file__), '..', 'db', 'reference_document.json')
OUTPUT_REPORT_PATH = os.path.join(os.path.dirname(__file__), '..', 'final_ranking.md')

class RankerAgent:
    """
    Synthesizes the graded offerings into a final, human-readable markdown report.
    """
    
    def __init__(self):
        pass

    def run(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # We only want to rank offerings that have been scored
        cursor.execute("SELECT * FROM offerings WHERE total_score IS NOT NULL ORDER BY total_score DESC LIMIT 10")
        top_offerings = cursor.fetchall()
        conn.close()
        
        if not top_offerings:
            print("No scored offerings found to rank.")
            return
            
        # Convert to list of dicts for JSON serialization
        offerings_list = [dict(off) for off in top_offerings]
        
        with open(REF_DOC_PATH, 'r') as f:
            ref_doc = json.load(f)
            
        prompt = f"""
        User Preferences:
        {json.dumps(ref_doc, indent=2)}
        
        Top Graded Offerings:
        {json.dumps(offerings_list, indent=2)}
        
        Generate a comprehensive, beautifully formatted Markdown report presenting the top offerings.
        Include a numbered ranking, explain *why* they fit the user's preferences (highlighting their specific scores in logistics, academia, and finance), and provide recommendations on next steps.
        """

        response = LLMRouter.get_completion(
            prompt=prompt,
            system_prompt="You are a professional academic advisor. Output a polished Markdown document.",
            task_type="reasoning",
            json_mode=False,
            max_tokens=3000
        )
        
        with open(OUTPUT_REPORT_PATH, 'w') as f:
            f.write(response if response else "Error: The Ranker agent failed to generate a report.")
            
        print(f"Final ranking report generated at {OUTPUT_REPORT_PATH}")

if __name__ == "__main__":
    agent = RankerAgent()
    agent.run()
