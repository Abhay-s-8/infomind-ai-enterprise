"""Synthetic labeled-document generator. The data is template-based and therefore much easier than real documents:
metrics measured on it demonstrate the pipeline, not real-world accuracy."""
import random

import pandas as pd

CATEGORIES = [
    "Technical Documentation", "Research and Reports", "Administration", "Policies and Procedures",
    "Finance and Procurement", "Training and Education", "General Correspondence",
]

_VOCAB: dict[str, dict[str, list[str]]] = {
    "Technical Documentation": {
        "subj": ["The API gateway", "The deployment module", "The configuration service", "The database driver",
                 "The firmware update", "The network switch", "The build pipeline", "The logging subsystem"],
        "verb": ["exposes", "requires", "validates", "initialises", "retries", "serialises", "caches", "monitors"],
        "obj": ["the REST endpoint parameters", "a configuration schema", "the installation prerequisites",
                "version compatibility checks", "the error codes and stack traces", "the system architecture diagram",
                "a command line interface", "timeout and latency settings"],
    },
    "Research and Reports": {
        "subj": ["The study", "Our analysis", "The experiment", "This survey", "The literature review",
                 "The field investigation", "The pilot trial", "The statistical model"],
        "verb": ["indicates", "suggests", "compares", "hypothesises", "measures", "demonstrates", "summarises",
                 "evaluates"],
        "obj": ["a significant correlation between the variables", "findings from the sample population",
                "the methodology and limitations", "results across three experimental conditions",
                "evidence supporting the research hypothesis", "trends observed over the reporting period",
                "the conclusions and recommendations", "an abstract of the main contributions"],
    },
    "Administration": {
        "subj": ["The office manager", "The front desk", "Human resources", "The facilities team",
                 "The scheduling coordinator", "The records clerk", "The department secretary", "Administrative staff"],
        "verb": ["schedules", "updates", "files", "coordinates", "distributes", "approves", "archives", "arranges"],
        "obj": ["the weekly meeting agenda", "staff leave requests", "office supply orders", "the visitor register",
                "room bookings and calendars", "employee onboarding paperwork", "the shared filing system",
                "the minutes of the committee meeting"],
    },
    "Policies and Procedures": {
        "subj": ["This policy", "All employees", "The standard operating procedure", "Section four",
                 "The compliance office", "Each department", "The code of conduct", "The escalation procedure"],
        "verb": ["mandates", "prohibits", "must follow", "enforces", "defines", "requires adherence to", "governs",
                 "outlines"],
        "obj": ["the data retention requirements", "acceptable use of company resources",
                "mandatory reporting obligations", "disciplinary measures for violations",
                "the approval and review process", "conflict of interest disclosures", "safety and compliance rules",
                "the scope and applicability of this policy"],
    },
    "Finance and Procurement": {
        "subj": ["The purchasing department", "The finance team", "This invoice", "The vendor", "The budget office",
                 "The procurement officer", "The quarterly forecast", "The accounts payable clerk"],
        "verb": ["issues", "reconciles", "allocates", "quotes", "pays", "audits", "negotiates", "forecasts"],
        "obj": ["the purchase order and unit price", "invoice totals and payment terms",
                "the annual budget and expenditure", "a tender and contract award",
                "supplier quotations in dollars", "the general ledger balance", "tax and cost centre allocations",
                "the procurement approval threshold"],
    },
    "Training and Education": {
        "subj": ["This course", "The instructor", "The workshop", "Each learner", "The curriculum",
                 "The training module", "The tutorial", "The certification programme"],
        "verb": ["teaches", "introduces", "assesses", "covers", "guides students through", "provides exercises on",
                 "prepares participants for", "reviews"],
        "obj": ["the learning objectives and syllabus", "a hands-on practice lab", "fundamentals for beginners",
                "quiz questions and grading rubrics", "lesson plans and lecture slides",
                "skills development and competency", "an end-of-course examination", "homework assignments"],
    },
    "General Correspondence": {
        "subj": ["I", "We", "Our team", "The sender", "Thank you for your message and", "Please note that we",
                 "As discussed, I", "Kind regards from the team who"],
        "verb": ["wanted to follow up on", "appreciate", "look forward to", "am writing regarding",
                 "hope you are well and", "would like to thank you for", "am happy to confirm", "regret to inform you of"],
        "obj": ["our conversation last week", "your recent email", "the upcoming visit", "a quick question",
                "the greetings and best wishes", "your kind invitation", "the change of plans", "a brief reminder"],
    },
}

_NOISE = ["Please see the attached document for details.", "This was reviewed last month.",
          "Contact the relevant team for further information.", "The details are summarised below.",
          "Several items remain open.", "A copy was sent to all parties."]


def generate(n_per_class: int = 60, seed: int = 42) -> pd.DataFrame:
    rng = random.Random(seed)
    rows, seen = [], set()
    for category, v in _VOCAB.items():
        made, attempts = 0, 0
        while made < n_per_class and attempts < n_per_class * 50:
            attempts += 1
            sentences = [f"{rng.choice(v['subj'])} {rng.choice(v['verb'])} {rng.choice(v['obj'])}."
                         for _ in range(rng.randint(3, 6))]
            if rng.random() < 0.7:  # cross-category noise keeps the task from being trivially separable
                other = _VOCAB[rng.choice([c for c in _VOCAB if c != category])]
                sentences.insert(rng.randrange(len(sentences) + 1),
                                 f"{rng.choice(other['subj'])} {rng.choice(other['verb'])} {rng.choice(other['obj'])}.")
            sentences.insert(rng.randrange(len(sentences) + 1), rng.choice(_NOISE))
            text = " ".join(sentences)
            if text in seen:  # exact-duplicate guard against train/test leakage
                continue
            seen.add(text)
            rows.append({"text": text, "label": category})
            made += 1
    df = pd.DataFrame(rows)
    return df.sample(frac=1.0, random_state=seed).reset_index(drop=True)
