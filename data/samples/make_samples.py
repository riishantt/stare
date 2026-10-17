"""Generate the synthetic STARE intake samples (all people, numbers and companies are fictional).

Run:  backend/.venv/bin/python data/samples/make_samples.py
Writes next to this file:
  complaint_ndtex_title7_retaliation.pdf   text-layer PDF (N.D. Tex.)
  complaint_ndcal_ada_title7_scanned.pdf   image-only PDF (N.D. Cal.), exercises OCR
  complaint_adea.txt                       short ADEA complaint (S.D.N.Y.)
  pii_seeded/NN_*.json                     snippets + the PII strings that must disappear
"""

from __future__ import annotations

import json
from pathlib import Path

import pymupdf

OUT = Path(__file__).parent

# ------------------------------------------------------------------------------------------------
# Complaint texts
# ------------------------------------------------------------------------------------------------

NDTEX = """UNITED STATES DISTRICT COURT
FOR THE NORTHERN DISTRICT OF TEXAS
DALLAS DIVISION

MARIA ELENA RIVERA,
Plaintiff,

v.

ACME LOGISTICS, INC.,
Defendant.

Civil Action No. 3:26-cv-00871-N

COMPLAINT AND JURY DEMAND

Plaintiff Maria Elena Rivera ("Plaintiff"), by and through undersigned counsel, files this Complaint against Defendant Acme Logistics, Inc. ("Acme" or "Defendant") and alleges as follows.

NATURE OF THE ACTION

1. This is an action under Title VII of the Civil Rights Act of 1964, 42 U.S.C. § 2000e et seq., to redress race discrimination and retaliation. Plaintiff was fired after she complained that Black and Hispanic warehouse associates were disciplined more harshly than white associates.

JURISDICTION AND VENUE

2. This Court has subject-matter jurisdiction under 28 U.S.C. §§ 1331 and 1343 and 42 U.S.C. § 2000e-5(f)(3). Venue is proper in the Northern District of Texas because the unlawful employment practices were committed in Dallas, Texas.

PARTIES

3. Plaintiff is an individual who resides at 4417 Willow Creek Lane, Plano, Texas 75024. Her date of birth is March 14, 1983. Her email address is maria.rivera83@examplemail.com and her telephone number is (214) 555-0142. Her Social Security number is 123-45-6789 and her Acme employee ID was EMP-48213.

4. Defendant Acme Logistics, Inc. is a Delaware corporation that operates a distribution center at 9100 Commerce Street, Dallas, Texas 75207 and employs more than 500 persons.

EXHAUSTION OF ADMINISTRATIVE REMEDIES

5. Plaintiff filed a timely charge of discrimination with the Equal Employment Opportunity Commission ("EEOC") on September 12, 2025. The EEOC issued a Notice of Right to Sue on February 10, 2026. Plaintiff files this action within ninety days of receipt of that notice.

FACTUAL ALLEGATIONS

6. Acme hired Plaintiff on June 7, 2021 as a warehouse associate. She was promoted to warehouse supervisor in 2023 and consistently received satisfactory or better performance reviews.

7. Ms. Rivera supervised a shift of approximately forty associates. Her direct manager was Gregory Haldane, the operations director.

8. Throughout early 2025, Mr. Haldane assigned the least desirable shifts to Black and Hispanic associates and issued written warnings to them for conduct that white associates were not disciplined for.

9. On May 19, 2025, Plaintiff complained in writing to Acme's Human Resources department that the discipline practices were racially discriminatory. She asked HR to investigate. Ms. Rivera received no response.

10. Within days of her complaint, Mr. Haldane removed Plaintiff from the shift-planning team, excluded her from supervisor meetings and placed her on a performance improvement plan for the first time in her career.

11. On July 22, 2025, Acme terminated Plaintiff's employment, citing alleged performance deficiencies. The stated reasons were pretextual and arose weeks after her protected complaint.

12. Acme did not discipline Mr. Haldane. Acme replaced Plaintiff with a white supervisor with less experience.

COUNT I - Retaliation in Violation of Title VII, 42 U.S.C. § 2000e-3(a)

13. Plaintiff incorporates the preceding paragraphs.

14. Plaintiff engaged in protected activity when she complained of race discrimination on May 19, 2025.

15. Acme took materially adverse action against Plaintiff, including her termination on July 22, 2025, and there is a causal connection between the protected activity and the adverse action.

COUNT II - Race Discrimination (Disparate Treatment) in Violation of Title VII, 42 U.S.C. § 2000e-2(a)

16. Plaintiff incorporates the preceding paragraphs.

17. Plaintiff is a member of a protected class, was qualified for her position, was terminated, and was replaced by a person outside her protected class.

PRAYER FOR RELIEF

WHEREFORE, Plaintiff requests back pay, front pay, compensatory and punitive damages, attorneys' fees and costs, and all other relief the Court deems just.

JURY DEMAND

Plaintiff demands a trial by jury on all issues so triable.

Dated: March 9, 2026

Respectfully submitted,

/s/ Jordan A. Pellegrino
Jordan A. Pellegrino
Counsel for Plaintiff
2200 Ross Avenue, Suite 4500, Dallas, Texas 75201
"""

NDCAL = """UNITED STATES DISTRICT COURT
NORTHERN DISTRICT OF CALIFORNIA
SAN FRANCISCO DIVISION

DANA KOWALSKI-OKAFOR,
Plaintiff,

v.

BRIGHTHARBOR SOFTWARE, INC.,
Defendant.

Case No. 3:26-cv-04412

COMPLAINT FOR RETALIATION AND FAILURE TO ACCOMMODATE; DEMAND FOR JURY TRIAL

Plaintiff Dana Kowalski-Okafor ("Plaintiff") alleges as follows against Defendant Brightharbor Software, Inc. ("Brightharbor").

INTRODUCTION

1. Plaintiff worked as a senior product analyst for Brightharbor. After she requested a reasonable accommodation for a documented disability and reported a manager's discriminatory remarks, Brightharbor terminated her employment. Plaintiff brings claims under Title VII of the Civil Rights Act of 1964, 42 U.S.C. § 2000e-3(a), and the Americans with Disabilities Act, 42 U.S.C. § 12112(b)(5)(A).

JURISDICTION, VENUE AND EXHAUSTION

2. This Court has jurisdiction under 28 U.S.C. § 1331. Venue is proper in the Northern District of California, San Francisco Division, because Brightharbor employed Plaintiff in San Francisco.

3. Plaintiff filed a charge with the Equal Employment Opportunity Commission on May 4, 2026. The EEOC issued a Notice of Right to Sue on August 12, 2026.

PARTIES

4. Plaintiff is an individual who resides in Oakland, California. Her email address is dana.ko@examplemail.com.

5. Defendant Brightharbor Software, Inc. is a corporation headquartered in San Francisco, California.

FACTUAL ALLEGATIONS

6. Brightharbor hired Plaintiff on August 15, 2022. Plaintiff has a chronic autoimmune condition that substantially limits major life activities.

7. On January 12, 2026, Plaintiff asked her supervisor in writing for a modified schedule and remote work two days per week as a reasonable accommodation. Brightharbor never engaged in the interactive process and denied the request without explanation.

8. On February 2, 2026, Plaintiff reported to Human Resources that her manager made sex-based remarks to female team members. That report was protected activity.

9. On March 16, 2026, Brightharbor terminated Plaintiff's employment, citing restructuring. Two male colleagues with similar roles were retained.

COUNT I - Retaliation in Violation of Title VII

10. Plaintiff incorporates the preceding paragraphs. Brightharbor terminated Plaintiff because she opposed practices made unlawful by Title VII.

COUNT II - Failure to Accommodate in Violation of the Americans with Disabilities Act

11. Plaintiff is a qualified individual with a disability. Brightharbor failed to provide a reasonable accommodation and failed to engage in the interactive process.

PRAYER FOR RELIEF

Plaintiff requests back pay, reinstatement or front pay, compensatory and punitive damages, and attorneys' fees.

DEMAND FOR JURY TRIAL

Plaintiff demands a jury trial.

Dated: September 3, 2026
"""

ADEA = """UNITED STATES DISTRICT COURT
SOUTHERN DISTRICT OF NEW YORK

THOMAS J. BRENNAN,
Plaintiff,

v.

NORTHBRIDGE FINANCIAL GROUP, LLC,
Defendant.

Civil Action No. 1:26-cv-02205

COMPLAINT

Plaintiff Thomas J. Brennan alleges as follows.

1. This is an action under the Age Discrimination in Employment Act of 1967, 29 U.S.C. § 621 et seq. ("ADEA"), for age discrimination.

2. Plaintiff, age 61, resides at 88 Harbor View Road, Brooklyn, New York 11201. His email is tbrennan61@examplemail.com.

3. Northbridge Financial Group, LLC hired Plaintiff on April 2, 2012 as a senior compliance officer. His reviews were consistently strong.

4. In November 2025, Plaintiff's supervisor told him the department needed "fresh energy" and asked when he planned to retire.

5. On January 15, 2026, Northbridge terminated Plaintiff's employment and assigned his duties to two employees in their thirties.

6. Plaintiff filed a charge with the EEOC on February 20, 2026 and received a Notice of Right to Sue on May 5, 2026.

COUNT I - Age Discrimination in Violation of the ADEA, 29 U.S.C. § 623(a)

7. Plaintiff was over forty, qualified, discharged, and replaced by substantially younger employees. Age was the but-for cause of the termination.

Dated: July 1, 2026
"""

# ------------------------------------------------------------------------------------------------
# PDF rendering
# ------------------------------------------------------------------------------------------------

FONT, SIZE, LEAD = "helv", 11, 15
MARGIN = 72


def _wrap(text: str, width: float) -> list[str]:
    lines: list[str] = []
    for para in text.split("\n"):
        if not para.strip():
            lines.append("")
            continue
        cur = ""
        for word in para.split(" "):
            trial = f"{cur} {word}".strip()
            if pymupdf.get_text_length(trial, FONT, SIZE) <= width:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


def text_pdf(text: str) -> pymupdf.Document:
    doc = pymupdf.open()
    rect = pymupdf.paper_rect("letter")
    width = rect.width - 2 * MARGIN
    per_page = int((rect.height - 2 * MARGIN) // LEAD)
    lines = _wrap(text, width)
    for i in range(0, len(lines), per_page):
        page = doc.new_page(width=rect.width, height=rect.height)
        chunk = "\n".join(lines[i:i + per_page])
        box = pymupdf.Rect(MARGIN, MARGIN, rect.width - MARGIN, rect.height - MARGIN + 6)
        page.insert_textbox(box, chunk, fontname=FONT, fontsize=SIZE, lineheight=LEAD / SIZE)
    return doc


def image_only_pdf(src: pymupdf.Document, dpi: int = 200) -> pymupdf.Document:
    out = pymupdf.open()
    for page in src:
        pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
        p = out.new_page(width=page.rect.width, height=page.rect.height)
        p.insert_image(p.rect, stream=pix.tobytes("png"))
    return out


# ------------------------------------------------------------------------------------------------
# Seeded PII snippets: every string in "pii" must be absent from redacted output.
# ------------------------------------------------------------------------------------------------

SEEDED = [
    ("ssn_email_phone",
     "Plaintiff Maria Rivera can be reached at maria.rivera@examplemail.com or (214) 555-0142. Her SSN is 123-45-6789.",
     ["Maria Rivera", "maria.rivera@examplemail.com", "(214) 555-0142", "123-45-6789"]),
    ("home_address",
     "Ms. Okafor lives at 221 Maple Grove Avenue, Apt 4B, Oakland, CA 94607 and has worked at the warehouse since 2019.",
     ["Okafor", "221 Maple Grove Avenue", "94607"]),
    ("dob_and_license",
     "Claimant Daniel Whitaker, DOB: 07/19/1964, driver's license no. D1234567, alleges age discrimination.",
     ["Daniel Whitaker", "07/19/1964", "D1234567"]),
    ("employee_id_zip4",
     "Employee ID: 774302. Mr. Whitaker mailed the form to PO Box 1182, Austin, TX 78767-1182 on Friday.",
     ["774302", "Whitaker", "78767-1182"]),
    ("bank_card",
     "Payroll deposits went to account number 004455667788 and he paid the fee with card 4111 1111 1111 1111.",
     ["004455667788", "4111 1111 1111 1111"]),
    ("supervisor_names",
     "Her supervisor Gregory Haldane told her, in front of coworker Priya Venkataraman, that she was too old for the role.",
     ["Gregory Haldane", "Priya Venkataraman"]),
    ("caption_plaintiff",
     "JOSEPHINE A. MARCHETTI, Plaintiff, v. ACME LOGISTICS, INC., Defendant. Josephine Marchetti alleges retaliation.",
     ["JOSEPHINE A. MARCHETTI", "Josephine Marchetti", "MARCHETTI"]),
    ("surname_only_followup",
     "On June 3, Oluwaseun Adebayo reported the incident. Mr. Adebayo was fired on June 20; Adebayo's phone is 312-555-0188.",
     ["Oluwaseun Adebayo", "Adebayo", "312-555-0188"]),
    ("born_email_residence",
     "Plaintiff Linda Chen was born on March 4, 1971, resides in Plano, Texas, and writes from l.chen71@examplemail.com.",
     ["Linda Chen", "March 4, 1971", "l.chen71@examplemail.com"]),
    ("legal_mix",
     "Hon. Reed O'Connor of the Northern District of Texas applied McDonnell Douglas Corp. v. Green, 411 U.S. 792 (1973), "
     "to Roberto Salazar's Title VII claim against Acme Logistics, Inc. before the Equal Employment Opportunity Commission.",
     ["Roberto Salazar"]),
]

# Strings that must survive redaction in the legal_mix snippet (over-redaction guard).
SEEDED_KEEP = {
    "legal_mix": ["Northern District of Texas", "McDonnell Douglas", "411 U.S. 792", "Title VII", "Acme Logistics, Inc.",
                  "Equal Employment Opportunity Commission", "Reed O'Connor"],
}


def main() -> None:
    doc = text_pdf(NDTEX)
    doc.save(OUT / "complaint_ndtex_title7_retaliation.pdf", garbage=3, deflate=True)
    print("ndtex pages:", len(doc))
    doc.close()

    src = text_pdf(NDCAL)
    img = image_only_pdf(src)
    img.save(OUT / "complaint_ndcal_ada_title7_scanned.pdf", garbage=3, deflate=True)
    print("ndcal pages:", len(img))
    src.close()
    img.close()

    (OUT / "complaint_adea.txt").write_text(ADEA, encoding="utf-8")

    d = OUT / "pii_seeded"
    d.mkdir(exist_ok=True)
    for i, (name, text, pii) in enumerate(SEEDED, start=1):
        payload = {"text": text, "pii": pii, "keep": SEEDED_KEEP.get(name, [])}
        (d / f"{i:02d}_{name}.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print("seeded snippets:", len(SEEDED))


if __name__ == "__main__":
    main()
