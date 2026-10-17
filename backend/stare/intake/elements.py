"""Legal elements per statute and theory: the knowledge the planner and the offline Research Agent use.

Each theory lists its elements (what the plaintiff must show) and search queries per element. The
queries are written the way courts phrase the rule, so lexical and dense search both find the
controlling passages. Leading authorities are *not* listed here on purpose: the agents must find
and verify authority through retrieval and the Citation Firewall, never from a hard-coded list.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from stare.schemas import Statute


@dataclass(frozen=True)
class Element:
    name: str
    queries: tuple[str, ...]


@dataclass(frozen=True)
class Theory:
    statute: Statute
    key: str
    label: str
    issue: str
    elements: tuple[Element, ...]
    adverse_queries: tuple[str, ...] = field(default_factory=tuple)


STATUTE_LABEL: dict[str, str] = {
    "title_vii": "Title VII of the Civil Rights Act of 1964",
    "ada": "Americans with Disabilities Act",
    "adea": "Age Discrimination in Employment Act",
}

STATUTE_CITE: dict[str, str] = {
    "title_vii": "42 U.S.C. § 2000e et seq.",
    "ada": "42 U.S.C. § 12101 et seq.",
    "adea": "29 U.S.C. § 621 et seq.",
}

THEORIES: dict[tuple[str, str], Theory] = {}


def _t(theory: Theory) -> None:
    THEORIES[(theory.statute, theory.key)] = theory


# --------------------------------------------------------------------------- Title VII
_t(Theory("title_vii", "disparate_treatment", "Disparate treatment",
    "Elements and proof of a Title VII disparate-treatment claim",
    (
        Element("Prima facie case under the McDonnell Douglas burden-shifting framework", (
            "prima facie case of discrimination protected class qualified adverse employment action",
            "McDonnell Douglas burden-shifting framework Title VII disparate treatment",
        )),
        Element("Adverse employment action affecting terms or conditions of employment", (
            "adverse employment action terms conditions or privileges of employment discrimination",
            "some harm respecting an identifiable term or condition of employment transfer",
        )),
        Element("Legitimate nondiscriminatory reason and pretext", (
            "legitimate nondiscriminatory reason burden of production pretext for discrimination",
            "plaintiff's prima facie case combined with sufficient evidence to find employer's justification false",
        )),
        Element("Similarly situated comparators", (
            "similarly situated employees outside the protected class treated more favorably comparator",
        )),
    ),
    adverse_queries=(
        "employer entitled to judgment no rational factfinder could conclude action was discriminatory",
        "stray remarks insufficient evidence of discriminatory intent",
        "same actor inference hired and fired by same person",
    ),
))
_t(Theory("title_vii", "retaliation", "Retaliation",
    "Elements of a Title VII retaliation claim under 42 U.S.C. § 2000e-3(a)",
    (
        Element("Protected activity (opposition or participation)", (
            "opposed any practice made an unlawful employment practice protected activity retaliation",
            "participation clause made a charge testified assisted or participated in investigation",
        )),
        Element("Materially adverse action that might dissuade a reasonable worker", (
            "materially adverse action might well have dissuaded a reasonable worker from making or supporting a charge",
            "anti-retaliation provision not limited to discriminatory actions that affect terms and conditions",
        )),
        Element("But-for causation between protected activity and adverse action", (
            "retaliation claims must be proved according to traditional principles of but-for causation",
            "temporal proximity between employer's knowledge of protected activity and adverse action very close",
        )),
    ),
    adverse_queries=(
        "temporal proximity alone insufficient causation retaliation months",
        "no reasonable person could have believed the conduct violated Title VII opposition",
        "petty slights minor annoyances not materially adverse",
    ),
))
_t(Theory("title_vii", "hostile_work_environment", "Hostile work environment",
    "Elements of a Title VII hostile-work-environment claim and employer liability",
    (
        Element("Unwelcome harassment based on a protected characteristic", (
            "hostile work environment harassment because of sex race unwelcome conduct",
            "workplace permeated with discriminatory intimidation ridicule and insult",
        )),
        Element("Severe or pervasive enough to alter the conditions of employment", (
            "sufficiently severe or pervasive to alter the conditions of the victim's employment abusive working environment",
            "totality of circumstances frequency severity physically threatening or humiliating interferes with work performance",
        )),
        Element("Employer liability: supervisor (Faragher/Ellerth defense) or co-worker (negligence)", (
            "employer vicariously liable supervisor tangible employment action affirmative defense reasonable care",
            "supervisor empowered to take tangible employment actions against the victim",
            "employer negligent in controlling working conditions co-worker harassment",
        )),
    ),
    adverse_queries=(
        "isolated incidents unless extremely serious do not amount to discriminatory changes",
        "employee unreasonably failed to take advantage of preventive or corrective opportunities",
        "ordinary tribulations of the workplace sporadic use of abusive language",
    ),
))
_t(Theory("title_vii", "religious_accommodation", "Religious accommodation",
    "Title VII duty to accommodate religious practice and undue hardship",
    (
        Element("Religious practice and employer's motive", (
            "religious accommodation employer may not make applicant's religious practice a factor in employment decisions",
        )),
        Element("Undue hardship", (
            "undue hardship substantial increased costs in relation to the conduct of its particular business",
            "reasonably accommodate an employee's religious observance or practice without undue hardship",
        )),
    ),
    adverse_queries=("accommodation would impose undue hardship on the conduct of the employer's business",),
))
_t(Theory("title_vii", "pregnancy", "Pregnancy discrimination",
    "Pregnancy Discrimination Act claims under Title VII",
    (
        Element("Pregnancy Discrimination Act accommodation comparison", (
            "Pregnancy Discrimination Act treated the same for all employment-related purposes as other persons similar in ability or inability to work",
            "employer's policies impose significant burden on pregnant workers legitimate nondiscriminatory reasons",
        )),
    ),
))

# --------------------------------------------------------------------------- ADA
_t(Theory("ada", "disparate_treatment", "Disability discrimination",
    "Elements of an ADA Title I disability-discrimination claim",
    (
        Element("Disability: actual, record of, or regarded as (broad construction after the ADAAA)", (
            "disability physical or mental impairment that substantially limits one or more major life activities",
            "definition of disability shall be construed in favor of broad coverage ADA Amendments Act",
            "regarded as having such an impairment",
        )),
        Element("Qualified individual able to perform essential functions", (
            "qualified individual with or without reasonable accommodation can perform the essential functions",
            "essential functions of the employment position employer's judgment written description",
        )),
        Element("Adverse action because of disability", (
            "discriminate against a qualified individual on the basis of disability",
            "ADA causation discharge because of disability",
        )),
    ),
    adverse_queries=(
        "direct threat to the health or safety of the individual or others",
        "plaintiff not a qualified individual unable to perform essential functions attendance",
    ),
))
_t(Theory("ada", "failure_to_accommodate", "Failure to accommodate",
    "Elements of an ADA failure-to-accommodate claim and the interactive process",
    (
        Element("Employer knew of the disability and the limitation", (
            "not making reasonable accommodations to the known physical or mental limitations",
        )),
        Element("A reasonable accommodation would allow performance of essential functions", (
            "reasonable accommodation may include job restructuring part-time or modified work schedules reassignment to a vacant position",
            "accommodation reasonable on its face ordinary run of cases",
        )),
        Element("Interactive process", (
            "informal interactive process with the individual with a disability precise limitations",
        )),
        Element("Undue hardship defense", (
            "undue hardship action requiring significant difficulty or expense",
        )),
    ),
    adverse_queries=(
        "seniority system ordinarily trumps reassignment accommodation",
        "employee responsible for breakdown of interactive process",
        "indefinite leave not a reasonable accommodation",
    ),
))
_t(Theory("ada", "retaliation", "ADA retaliation",
    "Elements of an ADA retaliation claim under 42 U.S.C. § 12203",
    (
        Element("Protected activity under the ADA, including requesting accommodation", (
            "no person shall discriminate against any individual because such individual has opposed any act or practice made unlawful by this chapter",
        )),
        Element("Materially adverse action and causation", (
            "materially adverse action retaliation causal connection",
        )),
    ),
))

# --------------------------------------------------------------------------- ADEA
_t(Theory("adea", "disparate_treatment", "Age discrimination",
    "Elements of an ADEA age-discrimination claim",
    (
        Element("Protected age (40 and over)", (
            "prohibitions shall be limited to individuals who are at least 40 years of age",
        )),
        Element("But-for causation: age was the reason for the decision", (
            "plaintiff must prove that age was the but-for cause of the employer's adverse decision",
            "ADEA does not authorize a mixed-motives age discrimination claim",
        )),
        Element("Prima facie case and replacement by a substantially younger person", (
            "replaced by someone substantially younger inference of age discrimination",
            "prima facie case age discrimination replaced by person outside protected class",
        )),
        Element("Pretext", (
            "trier of fact may infer the ultimate fact of discrimination from the falsity of the employer's explanation",
        )),
    ),
    adverse_queries=(
        "decision based on factor correlated with age such as pension status not age discrimination",
        "reasonable factors other than age",
    ),
))
_t(Theory("adea", "disparate_impact", "Age disparate impact",
    "Disparate-impact liability under the ADEA",
    (
        Element("Disparate impact is cognizable under the ADEA", (
            "disparate impact claims cognizable under the ADEA specific test or practice",
        )),
        Element("Reasonable factors other than age", (
            "reasonable factors other than age defense disparate impact",
        )),
    ),
))
_t(Theory("adea", "retaliation", "ADEA retaliation",
    "Elements of an ADEA retaliation claim under 29 U.S.C. § 623(d)",
    (
        Element("Protected activity and causation", (
            "unlawful for an employer to discriminate against any employee because such individual has opposed any practice made unlawful by this section",
        )),
    ),
))

PROCEDURAL = {
    "title_vii": Element("Timeliness of the EEOC charge and right-to-sue requirements", (
        "charge shall be filed within one hundred and eighty days after the alleged unlawful employment practice occurred three hundred days",
        "discrete discriminatory act occurred on the day that it happened hostile environment continuing",
        "charge-filing requirement is a nonjurisdictional claim-processing rule",
        "within ninety days after the giving of such notice a civil action may be brought",
    )),
    "ada": Element("ADA exhaustion: Title VII procedures apply to Title I claims", (
        "powers remedies and procedures set forth in sections 2000e-4 2000e-5 2000e-8 2000e-9",
        "charge shall be filed within one hundred and eighty days three hundred days",
    )),
    "adea": Element("ADEA charge timing and the 60-day waiting period", (
        "no civil action may be commenced until 60 days after a charge alleging unlawful discrimination has been filed",
        "charge filed within 180 days or 300 days ADEA",
    )),
}

THEORY_ALIASES = {
    "disparate treatment": "disparate_treatment",
    "discrimination": "disparate_treatment",
    "discriminatory discharge": "disparate_treatment",
    "wrongful termination": "disparate_treatment",
    "retaliation": "retaliation",
    "retaliatory": "retaliation",
    "hostile work environment": "hostile_work_environment",
    "harassment": "hostile_work_environment",
    "sexual harassment": "hostile_work_environment",
    "failure to accommodate": "failure_to_accommodate",
    "reasonable accommodation": "failure_to_accommodate",
    "religious accommodation": "religious_accommodation",
    "pregnancy": "pregnancy",
    "disparate impact": "disparate_impact",
}


def theory_for(statute: str, theory: str) -> Theory | None:
    key = THEORY_ALIASES.get(theory.replace("_", " ").lower(), theory)
    return THEORIES.get((statute, key)) or THEORIES.get((statute, "disparate_treatment"))
