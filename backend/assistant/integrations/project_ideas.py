"""Five sourced engineering proposals and a deterministic two-project shortlist."""

import re
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .errors import ConfigError, ProviderError

Text = Annotated[str, Field(min_length=1, max_length=2000)]
Score = Annotated[int, Field(ge=1, le=5)]


class ProjectIdea(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Annotated[str, Field(min_length=3, max_length=160)]
    target_users: Text
    problem: Annotated[str, Field(min_length=1, max_length=2000, pattern=r"^[^0-9%]*$")]
    mvp: Text
    architecture: Text
    production_features: list[Text] = Field(min_length=3, max_length=6)
    implementation_plan: list[Text] = Field(min_length=3, max_length=6)
    risks_and_validation: Text
    business_value: Score
    feasibility: Score
    engineering_depth: Score
    novelty: Score
    evidence_indices: list[int] = Field(max_length=5)


class ProjectBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ideas: list[ProjectIdea] = Field(min_length=5, max_length=5)


def title_key(value):
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def select_shortlist(ideas, gateway):
    ordered = sorted(ideas, key=lambda idea: (-idea["score"], idea["number"]))
    chosen, reason = ordered[:2], "Selected by the two highest heuristic totals."
    cutoff = chosen[-1]["score"]
    tied = [idea for idea in ideas if idea["score"] == cutoff]
    required = {idea["number"] for idea in ideas if idea["score"] > cutoff}
    if len(tied) > 2 - len(required):
        try:
            fields = ("number", "title", "target_users", "problem", "mvp", "score")
            decision = gateway.choose_shortlist([{key: idea[key] for key in fields} for idea in ideas])
            numbers, criteria = decision.get("numbers"), decision.get("criteria")
            if (not isinstance(numbers, list) or len(numbers) != 2 or any(type(n) is not int for n in numbers)
                    or len(set(numbers)) != 2 or not required.issubset(numbers)
                    or not set(numbers).issubset({idea["number"] for idea in ideas if idea["score"] >= cutoff})
                    or not isinstance(criteria, list) or not 1 <= len(criteria) <= 3
                    or any(not isinstance(item, str) or item not in {"MVP scope", "data availability", "integration complexity", "problem diversity"} for item in criteria)):
                raise ValueError("Invalid shortlist decision")
            chosen = [next(idea for idea in ideas if idea["number"] == number) for number in numbers]
            reason = "Scores tied at the cutoff. Model heuristic criteria: " + ", ".join(dict.fromkeys(criteria)) + ". Validate MVP scope and data/integration access before choosing a project."
        except (ConfigError, ProviderError, ValueError, TypeError, AttributeError):
            reason = "Scores tied at the cutoff; comparative assessment was unavailable. Original idea order breaks the tie and does not establish that these projects are better."
    return chosen, reason


def add_project_ideas(report, gateway, recent_titles=()):
    findings = report.get("key_findings", [])
    recent = {title_key(name) for name in recent_titles}
    for attempt in range(2):
        raw = gateway.propose_projects(report["title"], findings, list(recent_titles),
                                       ProjectBatch.model_json_schema(), revise=bool(attempt))
        try:
            batch = ProjectBatch.model_validate(raw)
            keys = [title_key(idea.title) for idea in batch.ideas]
            if any(re.search(r"\bpercent(?:age)?s?\b", idea.problem, re.I) for idea in batch.ideas):
                raise ValueError("Problem hypotheses must not contain quantitative market claims.")
            if not all(keys) or len(set(keys)) != 5 or set(keys) & recent:
                raise ValueError("Project titles must be distinct from this batch and recent reports.")
            if any(type(index) is not int or not 0 <= index < len(findings)
                   for idea in batch.ideas for index in idea.evidence_indices):
                raise ValueError("Unknown evidence index.")
            break
        except (ValidationError, ValueError):
            if attempt:
                raise ProviderError("Project planning did not produce five distinct, valid ideas. Retry this report.") from None
    ideas = []
    for number, idea in enumerate(batch.ideas, 1):
        item = idea.model_dump()
        item["number"] = number
        item["score"] = (3 * idea.business_value + 3 * idea.feasibility
                         + 2 * idea.engineering_depth + 2 * idea.novelty)
        item["source_urls"] = list(dict.fromkeys(url for index in idea.evidence_indices
                                                  for url in findings[index].get("source_urls", [])))
        item["evidence_status"] = ("Includes corroborated evidence; proposal still requires validation."
                                   if any(findings[index].get("verified") for index in idea.evidence_indices)
                                   else "Unverified motivation; independently validate before building.")
        ideas.append(item)
    shortlist, shortlist_reason = select_shortlist(ideas, gateway)
    return {**report, "report_kind": "project_ideas", "project_ideas": ideas,
            "shortlisted_projects": [item["number"] for item in shortlist],
            "shortlist_reason": shortlist_reason,
            "ranking_method": "Heuristic score /50: business value ×3, feasibility ×3, engineering depth ×2, novelty ×2. Each input is a model estimate from 1–5, not a measured business outcome.",
            "executive_summary": "Five enterprise project proposals, narrowed to two for detailed implementation planning.\n"
                                 + "\n".join(f"{idea['number']}. {idea['title']} — {idea['score']}/50" for idea in ideas)
                                 + "\nShortlist: " + "; ".join(item["title"] for item in shortlist)
                                 + "\nProposals, architectures and scores are engineering suggestions. Factual evidence retains its verification labels.",
            "next_steps": ["Review the two shortlisted projects and validate access to users, data and integrations.",
                           "Choose one MVP before expanding to the proposed production features."]}


def project_blocks(report):
    ideas = report.get("project_ideas", [])
    if not ideas:
        return []
    blocks = [("Selection method", report.get("ranking_method", "") + "\n" + report.get("shortlist_reason", "") + "\nThese are prototype proposals. Regulatory coverage and access to private training data have not been validated.")]
    for idea in ideas:
        text = (f"Target users: {idea['target_users']}\nProblem hypothesis: {idea['problem']}\n"
                f"MVP: {idea['mvp']}\nHeuristic score: {idea['score']}/50\n"
                f"Evidence: {idea['evidence_status']}\n" + "\n".join(idea["source_urls"]))
        blocks.append((f"Idea {idea['number']}: {idea['title']}", text))
    for rank, number in enumerate(report.get("shortlisted_projects", []), 1):
        idea = next(item for item in ideas if item["number"] == number)
        text = (f"Why shortlisted: business value {idea['business_value']}/5; feasibility {idea['feasibility']}/5; "
                f"engineering depth {idea['engineering_depth']}/5; novelty {idea['novelty']}/5.\n"
                f"Suggested architecture: {idea['architecture']}\nProduction features:\n"
                + "\n".join("• " + item for item in idea["production_features"])
                + "\nImplementation plan:\n"
                + "\n".join(f"{index}. {item}" for index, item in enumerate(idea["implementation_plan"], 1))
                + "\nRisks and validation: " + idea["risks_and_validation"])
        blocks.append((f"Shortlist {rank}: {idea['title']}", text))
    return blocks
