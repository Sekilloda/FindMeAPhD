import re
import urllib.parse
from difflib import SequenceMatcher
from typing import Dict, Any, List, Optional, Tuple

class DuplicateDetector:
    """
    Intelligent cross-source deduplication and comparison engine.
    Detects whether an academic opportunity found on one portal (e.g. CERN, DESY, Varbi, Quantiki)
    is identical to an offering already ingested from another feed (e.g. InspireHEP).
    """

    TITLE_NOISE_PATTERNS = [
        r'\bphd\s+(?:position|student|fellowship|candidate|opportunity|project|scholarship|programme|studies|positions)\s+(?:in|on|for|at)?\b',
        r'\bdoctoral\s+(?:student|position|candidate|fellowship|researcher|positions)\s+(?:in|on|for|at)?\b',
        r'\bpostdoctoral\s+(?:position|fellowship|researcher|positions)\b',
        r'\(m/f/d\)', r'\(w/m/d\)', r'\(f/m/d\)', r'\(all genders\)',
        r'\[quant-ph\]', r'\[hep-ph\]', r'\[hep-th\]', r'\[physics\]',
        r'ref\.\s*no\.?:\s*[\w\d\-\/]+',
        r'\bjob\s*id:?\s*[\w\d\-]+',
        r'\bcall\s*for\s*applications:?\b',
        r'\(2\+1\s*years\)', r'\(3\s*years\)', r'\(4\s*years\)'
    ]

    STOPWORDS = {"in", "on", "at", "for", "of", "the", "with", "and", "a", "an", "to", "by", "as"}

    INSTITUTION_SYNONYMS = {
        "stockholm": ["stockholm university", "stockholms universitet", "su"],
        "lund": ["lund university", "lunds universitet", "lu"],
        "uppsala": ["uppsala university", "uppsala universitet", "uu"],
        "kth": ["kth royal institute of technology", "kth", "kungliga tekniska hogskolan"],
        "cern": ["cern", "european organization for nuclear research", "organisation europeenne pour la recherche nucleaire"],
        "desy": ["desy", "deutsches elektronen-synchrotron", "helmholtz"],
        "copenhagen": ["university of copenhagen", "kobenhavns universitet", "ku", "nbi", "niels bohr institute"],
        "chalmers": ["chalmers university of technology", "chalmers tekniska hogskola"],
        "zagreb": ["boskovic inst", "rudjer boskovic", "irb"]
    }

    def __init__(self, existing_offerings: List[Dict[str, Any]]):
        """
        Takes a list of existing offerings from db (dict representation of rows).
        """
        self.existing_offerings = existing_offerings or []
        self._index_records()

    def _canonicalize_url(self, url: Optional[str]) -> str:
        if not url:
            return ""
        parsed = urllib.parse.urlparse(url.strip())
        query_params = urllib.parse.parse_qs(parsed.query)
        filtered_params = {k: v for k, v in query_params.items() if not k.startswith("utm_") and k not in ("ref", "source")}
        new_query = urllib.parse.urlencode(filtered_params, doseq=True)
        netloc = parsed.netloc.lower().replace("www.", "")
        path = parsed.path.rstrip("/")
        return f"{parsed.scheme}://{netloc}{path}{'?' + new_query if new_query else ''}"

    def normalize_title(self, title: str) -> str:
        if not title:
            return ""
        # 1. Strip parenthetical codes containing numbers e.g. (EP-FCC-2026-166-GRAP)
        text = re.sub(r'\([^)]*\d[^)]*\)', ' ', title)
        # 2. Strip standalone reference codes with letters and digits e.g. FSDO020/2026
        text = re.sub(r'\b[A-Za-z]{2,}\d+[\w\-\/]*\b', ' ', text)
        text = re.sub(r'\b[A-Za-z]+-\d+[\w\-]*\b', ' ', text)

        # 3. Replace slashes and colons with spaces
        text = text.replace(":", " ").replace("/", " ").replace("-", " ")
        text = text.lower()

        # 4. Remove noise patterns
        for pattern in self.TITLE_NOISE_PATTERNS:
            text = re.sub(pattern, ' ', text, flags=re.IGNORECASE)

        # 5. Clean non-alphanumeric and strip stopwords
        text = re.sub(r'[^a-z0-9\s]', ' ', text)
        tokens = [w for w in text.split() if w not in self.STOPWORDS]
        return " ".join(tokens)

    def normalize_institution(self, inst: str) -> str:
        if not inst:
            return ""
        inst_clean = inst.lower().strip()
        for canonical, aliases in self.INSTITUTION_SYNONYMS.items():
            for alias in aliases:
                if alias in inst_clean:
                    return canonical
        inst_clean = re.sub(r'\b(university|universitet|institute|dept|department|main|the)\b', ' ', inst_clean)
        return re.sub(r'[^a-z0-9\s]', ' ', inst_clean).strip()

    def _index_records(self):
        self.url_map = {}
        for r in self.existing_offerings:
            canon_url = self._canonicalize_url(r.get("url"))
            if canon_url:
                self.url_map[canon_url] = r
            
            # Also index external apply url if available
            ext_url = self._canonicalize_url(r.get("external_url") or r.get("application_url"))
            if ext_url:
                self.url_map[ext_url] = r

    def find_duplicate(self, candidate: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        Checks whether candidate offering is a duplicate of any existing record.
        Returns: (is_duplicate: bool, matched_record: dict | None, reason: str)
        """
        cand_url = self._canonicalize_url(candidate.get("url"))
        cand_ext_url = self._canonicalize_url(candidate.get("external_url") or candidate.get("application_url"))
        
        # 1. Direct URL or External URL Match
        if cand_url and cand_url in self.url_map:
            match = self.url_map[cand_url]
            return True, match, f"Exact URL match with ID #{match.get('id')}"
        if cand_ext_url and cand_ext_url in self.url_map:
            match = self.url_map[cand_ext_url]
            return True, match, f"External Application Link match with ID #{match.get('id')}"

        cand_title_norm = self.normalize_title(candidate.get("title", ""))
        cand_inst_norm = self.normalize_institution(candidate.get("institution", ""))
        cand_deadline = (candidate.get("deadline") or "").strip()

        if not cand_title_norm:
            return False, None, "No title to compare"

        # 2. Cross-Source Title + Institution / Deadline Fuzzy Matching
        best_ratio = 0.0
        best_match = None
        match_reason = ""

        for existing in self.existing_offerings:
            exist_title_norm = self.normalize_title(existing.get("title", ""))
            if not exist_title_norm:
                continue

            # Exact normalized title match
            if cand_title_norm == exist_title_norm:
                return True, existing, f"Identical normalized title with ID #{existing.get('id')}"

            # SequenceMatcher similarity ratio
            ratio = SequenceMatcher(None, cand_title_norm, exist_title_norm).ratio()
            
            # Check token overlap & subset containment
            cand_tokens = set(cand_title_norm.split())
            exist_tokens = set(exist_title_norm.split())
            jaccard = len(cand_tokens & exist_tokens) / max(1, len(cand_tokens | exist_tokens))
            is_subset = len(cand_tokens & exist_tokens) >= 3 and (cand_tokens.issubset(exist_tokens) or exist_tokens.issubset(cand_tokens))

            exist_inst_norm = self.normalize_institution(existing.get("institution", ""))
            inst_matches = (cand_inst_norm and exist_inst_norm and (
                cand_inst_norm in exist_inst_norm or exist_inst_norm in cand_inst_norm
            ))

            exist_deadline = (existing.get("deadline") or "").strip()
            deadline_matches = (cand_deadline and exist_deadline and cand_deadline == exist_deadline)

            # High confidence threshold matches
            if (ratio >= 0.82 or is_subset or jaccard >= 0.75) and inst_matches:
                return True, existing, f"High title similarity ({ratio:.1%}, jaccard: {jaccard:.1%}) & matching institution ({cand_inst_norm}) with ID #{existing.get('id')}"

            if (ratio >= 0.88 or is_subset) and deadline_matches:
                return True, existing, f"High title similarity ({ratio:.1%}) & identical deadline ({cand_deadline}) with ID #{existing.get('id')}"

            if ratio >= 0.93:
                return True, existing, f"Near-identical title similarity ({ratio:.1%}) with ID #{existing.get('id')}"

            if ratio > best_ratio:
                best_ratio = ratio
                best_match = existing

        return False, None, f"No match found (best similarity: {best_ratio:.1%})"
