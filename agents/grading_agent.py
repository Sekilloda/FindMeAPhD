import sqlite3
import os
import json
from core.llm_router import LLMRouter

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'db', 'system.db')
REF_DOC_PATH = os.path.join(os.path.dirname(__file__), '..', 'db', 'reference_document.json')

class GradingAgent:
    """
    Evaluates each offering across Geography, Academic, and Financial axes.
    Updates the database with numerical scores.
    """
    
    def __init__(self):
        with open(REF_DOC_PATH, 'r') as f:
            self.ref_doc = json.load(f)

    def run(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM offerings")
        offerings = cursor.fetchall()
        
        for off in offerings:
            print(f"Grading offering: {off['title']} at {off['institution']}")
            scores = self._grade_offering(dict(off))
            self._update_db(scores, off['id'], conn)
            
        conn.close()
        
    def _grade_offering(self, offering):
        prompt = f"""
        User Preferences:
        {json.dumps(self.ref_doc, indent=2)}
        
        Offering Details:
        {json.dumps(offering, indent=2)}
        
        Evaluate this offering based on the preferences. Assign three scores (0-10):
        1. score_geography (based on region, travel ease, location)
        2. score_academic (based on topics mentioned, prestige, type)
        3. score_financial (based on compensation, cost of living assumptions for the location)
        
        Output strictly valid JSON with the following keys:
        - "score_geography": float
        - "score_academic": float
        - "score_financial": float
        """

        response = LLMRouter.get_completion(
            prompt=prompt,
            system_prompt="You are a strict grading agent. Output ONLY valid JSON containing the three score keys.",
            task_type="reasoning",
            json_mode=True
        )
        
        try:
            scores = json.loads(response)
            # Calculate total
            total = sum(float(v) for k, v in scores.items() if v is not None)
            scores['total_score'] = total
            return scores
        except Exception as e:
            print(f"Failed to parse scores for offering {offering['id']}: {e}")
            return {"score_geography": 0, "score_academic": 0, "score_financial": 0, "total_score": 0}

    def _update_db(self, scores, offering_id, conn):
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE offerings SET 
               score_geography = ?, score_academic = ?, score_financial = ?, total_score = ?
               WHERE id = ?""",
            (
                scores.get('score_geography'),
                scores.get('score_academic'),
                scores.get('score_financial'),
                scores.get('total_score'),
                offering_id
            )
        )
        conn.commit()

if __name__ == "__main__":
    agent = GradingAgent()
    agent.run()
