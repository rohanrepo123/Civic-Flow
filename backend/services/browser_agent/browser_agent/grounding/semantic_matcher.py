"""Rule-based semantic and fuzzy matching for snapshot elements."""

from dataclasses import dataclass
from difflib import SequenceMatcher
import re

from browser_agent.grounding.confidence import ConfidenceScorer, MatchFeatures
from browser_agent.schemas.observation import InteractiveElement

_STOP_WORDS = {
    "a", "an", "the", "for", "to", "of", "on", "in", "at", "with", "where", "s",
    "should", "i", "me", "my", "we", "our", "please", "find", "locate", "identify",
    "look", "looking", "get", "show", "field", "input", "element", "control", "place",
    "enter", "type", "put", "click", "press", "selecting", "select", "choose", "choosing",
    "upload", "attach", "agreeing", "agree", "accept", "accepting", "application",
    "radio", "button",
}
_CANONICAL = {
    "legal": "full", "complete": "full", "candidate": "applicant", "telephone": "phone",
    "mobile": "phone", "cell": "phone", "e-mail": "email", "mail": "email",
    "zip": "postal", "province": "state", "region": "state", "dropdown": "dropdown",
    "select": "dropdown", "checkbox": "checkbox", "check": "checkbox",
    "upload": "file", "attachment": "file", "attach": "file", "document": "file",
    "agreeing": "agree", "accepting": "agree", "terms": "term",
    "declaration": "term",
    "names": "name", "applicants": "applicant", "addresses": "address",
}

_TYPE_ALIASES = {
    "text": "text_input", "input": "text_input", "text input": "text_input", "textbox": "text_input",
    "email": "email", "email input": "email", "email address input": "email", "email_address": "email",
    "tel": "telephone", "phone": "telephone", "telephone": "telephone", "phone input": "telephone", "telephone input": "telephone",
    "number": "number", "number input": "number", "textarea": "textarea",
    "select": "dropdown", "dropdown": "dropdown", "select element": "dropdown",
    "checkbox": "checkbox", "radio": "radio", "radio button": "radio",
    "file": "file_upload", "file upload": "file_upload", "upload": "file_upload",
    "button": "button", "link": "link",
}


def canonical_text(value: str) -> str:
    """Normalize natural language and common field synonyms for comparison."""
    words = re.findall(r"[a-z0-9]+", value.lower().replace("_", " "))
    canonical = [_CANONICAL.get(word, word) for word in words if word not in _STOP_WORDS]
    return " ".join(canonical)


def normalize_element_type(value: str | None) -> str | None:
    """Map common caller-provided type names to supported element categories."""
    if value is None:
        return None
    key = value.strip().lower().replace("-", " ")
    return _TYPE_ALIASES.get(key, key.replace(" ", "_"))


def infer_expected_type(instruction: str) -> str | None:
    """Infer an intended control category when the instruction states one."""
    text = instruction.lower()
    if re.search(r"\b(upload|attach|browse for|choose file|select file)\b", text):
        return "file_upload"
    if re.search(r"\b(link|visit|open)\b", text):
        return "link"
    if re.search(r"\b(checkbox|check box|agree|accept|declaration|terms)\b", text):
        return "checkbox"
    if re.search(r"\b(radio button|radio)\b", text):
        return "radio"
    if re.search(r"\b(dropdown|drop-down|select list|select menu|choose|select)\b", text):
        return "dropdown"
    if re.search(r"\b(submit|click|press|button|continue|save)\b", text):
        return "button"
    if re.search(r"\b(email|e-mail)\b", text):
        return "email"
    if re.search(r"\b(phone|telephone|mobile|cell)\b", text):
        return "telephone"
    if re.search(r"\b(number|amount|quantity)\b", text):
        return "number"
    if re.search(r"\b(text area|textarea|message|comment|description)\b", text):
        return "textarea"
    if re.search(r"\b(enter|type|write|fill)\b", text):
        return "text_input"
    return None


def is_type_compatible(element: InteractiveElement, expected: str | None) -> bool:
    """Check whether the observed element can serve the requested control role."""
    if expected is None:
        return True
    element_type = element.element_type.lower().replace("-", "_")
    input_type = (element.input_type or "").lower()
    role = (element.role or "").lower()
    if expected == "email":
        return input_type == "email" or (element_type == "text_input" and input_type in {"", "text"})
    if expected == "telephone":
        return input_type == "tel" or (element_type == "text_input" and input_type in {"", "text"})
    if expected == "number":
        return input_type == "number" or (element_type == "text_input" and input_type in {"", "text"})
    if expected == "text_input":
        return element_type == "text_input"
    if expected == "file_upload":
        return element_type == "file_upload" or input_type == "file"
    if expected == "dropdown":
        return element_type == "dropdown" or role == "combobox"
    return element_type == expected or role == expected


@dataclass(frozen=True)
class SemanticMatch:
    """A scored page element and the evidence supporting its score."""

    element: InteractiveElement
    confidence: float
    compatible: bool
    explanation: str


class SemanticMatcher:
    """Rank page elements using labels, accessible text, attributes, and type."""

    def __init__(self, scorer: ConfidenceScorer | None = None) -> None:
        self.scorer = scorer or ConfidenceScorer()

    def rank(
        self,
        instruction: str,
        elements: list[InteractiveElement],
        expected_element_type: str | None = None,
    ) -> list[SemanticMatch]:
        """Score all elements, highest first, without using DOM IDs as semantics."""
        query = canonical_text(instruction)
        query_tokens = set(query.split())
        expected = normalize_element_type(expected_element_type) or infer_expected_type(instruction)
        matches: list[SemanticMatch] = []
        for element in elements:
            facets = [
                ("label", element.label),
                ("accessible name", element.aria_label),
                ("placeholder", element.placeholder),
                ("visible text", element.text),
                ("name attribute", element.name),
                ("input type", element.input_type),
                ("role", element.role),
                ("element type", element.element_type),
            ]
            normalized_facets = [(source, canonical_text(value)) for source, value in facets if value]
            all_element_tokens = set().union(*(set(facet.split()) for _, facet in normalized_facets)) if normalized_facets else set()
            compatible = is_type_compatible(element, expected)
            best_precision = best_coverage = best_fuzzy = 0.0
            exact = False
            best_source = "element attributes"
            for source, facet in normalized_facets:
                facet_tokens = set(facet.split())
                precision = len(query_tokens & facet_tokens) / len(query_tokens) if query_tokens else 0.0
                coverage = len(query_tokens & facet_tokens) / len(facet_tokens) if facet_tokens else 0.0
                fuzzy = SequenceMatcher(None, query, facet).ratio() if query and facet else 0.0
                facet_exact = bool(query and query == facet)
                score_tuple = (facet_exact, 0.45 * precision + 0.20 * coverage + 0.35 * fuzzy)
                best_tuple = (exact, 0.45 * best_precision + 0.20 * best_coverage + 0.35 * best_fuzzy)
                if score_tuple > best_tuple:
                    exact = facet_exact
                    best_precision, best_coverage, best_fuzzy = precision, coverage, fuzzy
                    best_source = source
            features = MatchFeatures(
                exact_match=exact,
                query_precision=best_precision,
                candidate_coverage=best_coverage,
                fuzzy_similarity=best_fuzzy,
                compatible_type=compatible,
                all_keywords_match=bool(query_tokens) and query_tokens.issubset(all_element_tokens),
                query_token_count=len(query_tokens),
            )
            confidence = self.scorer.score(features)
            if exact:
                reason = f"Exact normalized match on the {best_source}."
            elif features.all_keywords_match:
                reason = "All instruction keywords occur across the element's semantic labels and attributes."
            elif best_precision > 0:
                reason = f"{best_precision:.0%} of instruction keywords match the {best_source}; fuzzy similarity {best_fuzzy:.0%}."
            else:
                reason = f"Weak fuzzy similarity to the {best_source} ({best_fuzzy:.0%})."
            if expected:
                reason += " Control type is compatible." if compatible else f" Control type conflicts with requested {expected}."
            matches.append(SemanticMatch(element, confidence, compatible, reason))
        return sorted(matches, key=lambda item: item.confidence, reverse=True)
