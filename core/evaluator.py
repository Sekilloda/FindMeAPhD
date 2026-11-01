import os
import json
from typing import Dict, Any
from core.llm_router import LLMRouter

REF_DOC_PATH = os.path.join(os.path.dirname(__file__), '..', 'db', 'reference_document.json')

class OfferingEvaluator:
    """
    Evaluates candidate PhD offerings against the user's specific reference document.
    Outputs structured numerical scores (Geography, Academic Fit, Financials) and detailed reasoning.
    """
    
    def __init__(self, ref_doc_path: str = REF_DOC_PATH):
        if not os.path.exists(ref_doc_path):
            raise FileNotFoundError(f"Reference document not found at {ref_doc_path}")
        with open(ref_doc_path, 'r', encoding='utf-8') as f:
            self.ref_doc = json.load(f)

    def evaluate(self, offering: Dict[str, Any]) -> Dict[str, Any]:
        """
        Runs single-swoop evaluation on an offering using the LLM router.
        """
        prompt = f"""
You are an expert academic advisor evaluating a PhD vacancy for a specific candidate.

CANDIDATE PROFILE:
{json.dumps(self.ref_doc, indent=2)}

VACANCY DETAILS:
- Title: {offering.get('title')}
- Institution: {offering.get('institution')}
- Location / Regions: {offering.get('location')} | {offering.get('regions')}
- ArXiv Categories: {offering.get('arxiv_categories')}
- Application Deadline: {offering.get('deadline')}
- URL: {offering.get('url')}
- Description:
{offering.get('description')[:4000]}

SCORING RULES (Strict 0.0 - 10.0 scale):
1. Geography (score_geography):
   - AUTOMATIC DISQUALIFICATION (0.0): United States, China, India, Middle East, Latin America.
   - TOP PRIORITY (9.5 - 10.0): Scandinavia (Sweden, Denmark, Norway, Finland).
   - VERY HIGH (8.5 - 9.4): Switzerland, Germany, Netherlands, France, Austria, other EU/EEA nations (candidate has Spanish/EU citizenship, so no visa barriers).
   - ACCEPTABLE (7.0 - 8.4): Canada, Australia, South Africa.
   - OTHERS: < 5.0.

2. Academic Fit (score_academic):
   - PERFECT/DIRECT FIT (9.0 - 10.0): Quantum computation / information applied to particle physics / QCD, or QCD phenomenology (Lund string model, hadronization, parton showers, quantum algorithms/witness circuits).
   - STRONG FIT (8.0 - 8.9): Theoretical quantum information / quantum computing, or theoretical particle physics (hep-ph, hep-th, hadron physics). Computational or analytical is great.
   - MODERATE FIT (6.0 - 7.9): General theoretical physics, astroparticle/neutrino physics, or experimental particle physics with heavy simulation/algorithm development.
   - LOW FIT (< 6.0): Unrelated experimental work or outside quantum/particle theory.

3. Financials (score_financial):
   - Candidate requires minimum stipend > 2,000 EUR/month net (or equivalent) in the EU.
   - Scandinavia, Switzerland, Netherlands, Germany, Austria, Belgium typically guarantee salaries well above this (€2,500 - €4,500/month equivalent). Score 8.5 - 10.0.
   - If description states a stipend under €2,000/month, score < 6.0.
   - If funding is unknown or standard EU, score 7.0 - 8.0.

4. Total Score (total_score):
   - Weighted: (0.45 * score_academic) + (0.35 * score_geography) + (0.20 * score_financial).
   - If disqualified, total_score must be 0.0.

OUTPUT FORMAT:
Respond strictly with a single valid JSON object with these exact keys:
{{
  "score_geography": float,
  "score_academic": float,
  "score_financial": float,
  "total_score": float,
  "disqualified": bool,
  "disqualification_reason": string or null,
  "topics_mentioned": list of strings,
  "compensation_detected": string or null,
  "evaluation_summary": string
}}
"""
        response = LLMRouter.get_completion(
            prompt=prompt,
            system_prompt="You are a concise academic evaluator. Keep internal reasoning under 150 words and output ONLY the valid JSON object.",
            task_type="fast",
            json_mode=True,
            max_tokens=3500
        )
        
        try:
            cleaned = response.strip()
            if "```json" in cleaned:
                cleaned = cleaned.split("```json", 1)[1].split("```", 1)[0]
            elif "```" in cleaned:
                cleaned = cleaned.split("```", 1)[1].split("```", 1)[0]
            elif "{" in cleaned and "}" in cleaned:
                start = cleaned.find("{")
                end = cleaned.rfind("}") + 1
                cleaned = cleaned[start:end]
            data = json.loads(cleaned.strip())
            return data
        except Exception as e:
            print(f"[Evaluator] Failed to parse evaluation JSON: {e}\nRaw response:\n{response}")
            return {
                "score_geography": 0.0,
                "score_academic": 0.0,
                "score_financial": 0.0,
                "total_score": 0.0,
                "disqualified": False,
                "disqualification_reason": f"Parsing error: {e}",
                "topics_mentioned": [],
                "compensation_detected": None,
                "evaluation_summary": "Evaluation parsing failed."
            }
