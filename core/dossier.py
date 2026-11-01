import os
import re
import json
from typing import Dict, Any
from core.llm_router import LLMRouter

REF_DOC_PATH = os.path.join(os.path.dirname(__file__), '..', 'db', 'reference_document.json')
APPLICATIONS_DIR = os.path.join(os.path.dirname(__file__), '..', 'applications')

class DossierGenerator:
    """
    For high-scoring PhD positions, stores the complete vacancy description and
    synthesizes a tailored application guide with strategic pointers for the cover letter,
    CV customization, and interview preparation.
    """
    
    def __init__(self, ref_doc_path: str = REF_DOC_PATH, base_dir: str = APPLICATIONS_DIR):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)
        with open(ref_doc_path, 'r', encoding='utf-8') as f:
            self.ref_doc = json.load(f)

    def _slugify(self, text: str) -> str:
        text = text.lower()
        text = re.sub(r'[^a-z0-9]+', '_', text).strip('_')
        return text[:45]

    def generate_dossier(self, offering: Dict[str, Any], evaluation: Dict[str, Any]) -> str:
        offering_id = offering.get("id") or "new"
        title_slug = self._slugify(offering.get("title", "phd_position"))
        folder_name = f"{offering_id}_{title_slug}"
        target_dir = os.path.join(self.base_dir, folder_name)
        os.makedirs(target_dir, exist_ok=True)
        
        # 1. Save description.md
        desc_path = os.path.join(target_dir, "description.md")
        with open(desc_path, 'w', encoding='utf-8') as f:
            f.write(self._format_description_markdown(offering, evaluation))
            
        # 2. Generate application_guide.md
        guide_path = os.path.join(target_dir, "application_guide.md")
        guide_content = self._generate_guide_content(offering, evaluation)
        with open(guide_path, 'w', encoding='utf-8') as f:
            f.write(guide_content)
            
        print(f"[Dossier] Created application dossier at: {target_dir}")
        return guide_path

    def _format_description_markdown(self, offering: Dict[str, Any], evaluation: Dict[str, Any]) -> str:
        return f"""# {offering.get('title')}

- **Institution**: {offering.get('institution')}
- **Location**: {offering.get('location')} ({offering.get('regions')})
- **Application Deadline**: {offering.get('deadline')}
- **Application Link**: [{offering.get('url')}]({offering.get('url')})
- **InspireHEP Record**: [{offering.get('inspire_url', offering.get('url'))}]({offering.get('inspire_url', offering.get('url'))})
- **Categories**: {offering.get('arxiv_categories')}

---

## Evaluation Summary
- **Overall Match Score**: **{evaluation.get('total_score', 0):.1f} / 10.0**
  - Academic Fit: {evaluation.get('score_academic', 0):.1f} / 10.0
  - Geography: {evaluation.get('score_geography', 0):.1f} / 10.0
  - Financials: {evaluation.get('score_financial', 0):.1f} / 10.0
- **Topics Identified**: {', '.join(evaluation.get('topics_mentioned', []))}
- **Compensation**: {evaluation.get('compensation_detected') or 'Standard institution rate'}
- **Evaluator Notes**: {evaluation.get('evaluation_summary')}

---

## Original Vacancy Description

```text
{offering.get('description')}
```
"""

    def _generate_guide_content(self, offering: Dict[str, Any], evaluation: Dict[str, Any]) -> str:
        prompt = f"""
You are an expert academic mentor in Theoretical Physics and Quantum Computing.
Write a comprehensive, highly strategic Application & Cover Letter Guide for the candidate applying to this PhD vacancy.

CANDIDATE BACKGROUND:
{json.dumps(self.ref_doc, indent=2)}
Key candidate facts:
- Master's thesis: QCD phenomenology under the Lund string model, featuring quantum computational design (quantum algorithm for hadronization histories and rank indistinguishability witness circuit).
- Spanish (EU) and Ecuadorian dual citizenship (eligible for domestic EU employment without visa delays).
- Strong computational and analytical background in theoretical particle and quantum physics.

VACANCY DETAILS:
- Title: {offering.get('title')}
- Institution: {offering.get('institution')}
- Location: {offering.get('location')}
- Deadline: {offering.get('deadline')}
- Categories: {offering.get('arxiv_categories')}
- Vacancy Text:
{offering.get('description')[:4000]}

EVALUATION DETAILS:
- Total Score: {evaluation.get('total_score')}
- Evaluator Reasoning: {evaluation.get('evaluation_summary')}

TASK:
Produce an actionable Markdown document with these sections:
1. **Strategic Match & Research Angle**: Analyze the specific overlap between the candidate's thesis and the group's research. Explain how to pitch the combination of QCD phenomenology and quantum computation.
2. **Cover Letter Blueprint**:
   - Provide a section-by-section breakdown (Opening Hook, Scientific Bridge, Technical & Computational Competencies, Administrative Ease & Commitment).
   - Write out sample drafting paragraphs tailored specifically to this vacancy.
3. **CV Tailoring & Emphasis Checklist**:
   - Exactly which skills, methodologies, frameworks (e.g., Python, C++, ROOT, Qiskit/Pennylane, tensor networks, Monte Carlo, QFT), and coursework to place in the spotlight.
4. **Targeted Interview Questions**:
   - 3-4 deep, technically impressive questions the candidate can ask the supervisor about their ongoing work or the future of this project.

Write directly in polished, professional Markdown.
"""
        response = LLMRouter.get_completion(
            prompt=prompt,
            system_prompt="You are a senior theoretical physics academic advisor. Output comprehensive Markdown guidance.",
            task_type="reasoning",
            max_tokens=6500
        )
        if "<thought>" in response and "</thought>" in response:
            response = response.split("</thought>", 1)[1].strip()
        return response
