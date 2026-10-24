"""Provider-independent research planning, evidence judging and report assembly."""
from .errors import ProviderError
from ..prompt_templates import SYSTEM as SYSTEM, task_prompt

def _topic(topic):
    if not isinstance(topic, str) or not topic.strip() or len(topic) > 2000:
        raise ValueError("Research topic must contain 1 to 2000 characters.")
    return topic.strip()


class ResearchPlanningMixin:
    def choose_shortlist(self, ideas):
        schema = {"type": "object", "properties": {
            "numbers": {"type": "array", "items": {"type": "integer", "minimum": 1, "maximum": 5}, "minItems": 2, "maxItems": 2},
            "criteria": {"type": "array", "items": {"type": "string", "enum": ["MVP scope", "data availability", "integration complexity", "problem diversity"]}, "minItems": 1, "maxItems": 3}}, "required": ["numbers", "criteria"]}
        return self._json(task_prompt("shortlist", {"ideas": ideas}), schema, max_output_tokens=512)

    def plan_research(self, topic: str) -> list[str]:
        topic = _topic(topic)
        result = self._json(task_prompt("research_plan", {"topic": topic}),
                            {"type": "object", "properties": {"queries": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 3}}, "required": ["queries"]})
        queries = result.get("queries")
        if not isinstance(queries, list) or not 1 <= len(queries) <= 3 or any(not isinstance(q, str) or not q.strip() or len(q) > 500 for q in queries):
            raise ProviderError("The model returned invalid research queries.")
        return queries

    def verify_evidence(self, claim: str, evidence: list[dict]) -> list[dict]:
        schema = {"type": "object", "properties": {"results": {"type": "array", "items": {"type": "object", "properties": {
            "url": {"type": "string"}, "supports": {"type": "boolean"}, "quote": {"type": "string"}}, "required": ["url", "supports", "quote"]}}}, "required": ["results"]}
        prompt = task_prompt("verify_evidence", {"claim": claim, "untrusted_evidence": evidence})
        result = self._json(prompt, schema).get("results", [])
        if not isinstance(result, list):
            raise ProviderError("The model returned invalid evidence verification.")
        return [item for item in result[:20] if isinstance(item, dict) and isinstance(item.get("supports"), bool)
                and isinstance(item.get("quote"), str) and isinstance(item.get("url"), str)]

    def propose_projects(self, topic, findings, recent_titles, schema, revise=False):
        prompt = task_prompt("project_ideas", {"focus": _topic(topic), "revise": revise,
            "recent_project_titles": recent_titles[:70],
            "untrusted_findings": [{"index": i, "text": f["text"][:700], "verified": f.get("verified", False)}
                                   for i, f in enumerate(findings[:20])]})
        return self._json(prompt, schema, max_output_tokens=10000)

    def write_report(self, topic: str, findings: list[dict]) -> dict:
        # The model selects existing finding IDs. All factual prose and citations
        # are then copied from those findings, so writing cannot fabricate either.
        if not findings:
            return {"executive_summary": "No supported findings were retrieved.", "key_findings": [], "next_steps": ["Try a more specific research question."]}
        schema = {"type": "object", "properties": {"summary_indices": {"type": "array", "items": {"type": "integer"}, "maxItems": 4}}, "required": ["summary_indices"]}
        result = self._json(task_prompt("report_summary", {"topic": _topic(topic),
            "findings": [{"index": i, "text": f["text"][:700], "verified": f.get("verified", False)}
                         for i, f in enumerate(findings[:30])]}), schema)
        indices = result.get("summary_indices", [])
        if not isinstance(indices, list) or any(type(i) is not int or not 0 <= i < len(findings) for i in indices):
            raise ProviderError("The model returned invalid report finding indices.")
        selected = [findings[i] for i in dict.fromkeys(indices[:4])]
        summary = "\n\n".join(("" if f.get("verified") else "Unverified: ") + f["text"] for f in selected)
        return {"executive_summary": summary or "See the findings and evidence below.", "key_findings": findings,
                "next_steps": ["Review the linked evidence and resolve findings marked unverified before acting."]}
