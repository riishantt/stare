"""Builds gold.jsonl: employment-law research questions with the authorities a correct answer must cite.

Expected citations are leading authorities in the seed corpus for each question (Supreme Court holdings
and well-known Fifth and Ninth Circuit decisions). Run: python data/eval/make_gold.py
"""

import json
from pathlib import Path

T7, ADA, ADEA = "title_vii", "ada", "adea"
Q = [
    # --- Title VII retaliation -----------------------------------------------------------------
    ("What causation standard governs a Title VII retaliation claim?", "txnd", T7, "retaliation", ["570 U.S. 338"]),
    ("Is a retaliation plaintiff required to show the protected activity was a but-for cause of the termination?", "cand", T7, "retaliation", ["570 U.S. 338"]),
    ("What counts as a materially adverse action under Title VII's anti-retaliation provision?", "txnd", T7, "retaliation", ["548 U.S. 53"]),
    ("Can reassignment of job duties be retaliation even if pay is unchanged?", "cand", T7, "retaliation", ["548 U.S. 53"]),
    ("Does the anti-retaliation provision reach actions outside the workplace?", "txnd", T7, "retaliation", ["548 U.S. 53"]),
    ("Does the Fifth Circuit still limit retaliation to ultimate employment decisions?", "txnd", T7, "retaliation", ["548 U.S. 53", "104 F.3d 702"]),
    ("Is temporal proximity alone enough to show causation for retaliation?", "txnd", T7, "retaliation", ["532 U.S. 268"]),
    ("How close in time must protected activity and the adverse action be to infer causation?", "cand", T7, "retaliation", ["532 U.S. 268"]),
    ("Is answering questions in an employer's internal harassment investigation protected opposition activity?", "cand", T7, "retaliation", ["555 U.S. 271"]),
    ("Can firing an employee's fiance be retaliation against the employee who filed an EEOC charge?", "txnd", T7, "retaliation", ["562 U.S. 170"]),
    ("Who may sue as a person aggrieved by third-party retaliation under Title VII?", "cand", T7, "retaliation", ["562 U.S. 170"]),
    ("What are the elements of a prima facie case of retaliation in the Fifth Circuit?", "txnd", T7, "retaliation", ["492 F.3d 551", "42 U.S.C. § 2000e-3"]),
    ("Does Title VII prohibit retaliation for opposing an unlawful employment practice?", "txnd", T7, "retaliation", ["42 U.S.C. § 2000e-3"]),
    ("Is placing an employee on paid administrative leave a materially adverse retaliatory action?", "txnd", T7, "retaliation", ["492 F.3d 551", "548 U.S. 53"]),
    ("Can a supervisor's biased report make the employer liable when another manager makes the decision (cat's paw)?", "txnd", T7, "retaliation", ["562 U.S. 411"]),
    ("What causal showing is needed for a retaliation claim in the Ninth Circuit?", "cand", T7, "retaliation", ["570 U.S. 338", "281 F.3d 1054"]),
    ("What adverse employment actions support a retaliation claim in the Ninth Circuit?", "cand", T7, "retaliation", ["217 F.3d 1234", "548 U.S. 53"]),
    ("Does retaliation require the plaintiff to show the employer knew of the protected activity?", "txnd", T7, "retaliation", ["532 U.S. 268"]),
    ("Is the participation clause limited to formal EEOC proceedings?", "cand", T7, "retaliation", ["555 U.S. 271", "42 U.S.C. § 2000e-3"]),
    ("Can a retaliation claim survive summary judgment based on pretext evidence?", "txnd", T7, "retaliation", ["530 U.S. 133", "570 U.S. 338"]),
    # --- Title VII disparate treatment -----------------------------------------------------------
    ("What is the McDonnell Douglas prima facie case for discriminatory refusal to hire?", "txnd", T7, "disparate_treatment", ["411 U.S. 792"]),
    ("Which party bears the burden of persuasion under the McDonnell Douglas framework?", "cand", T7, "disparate_treatment", ["450 U.S. 248", "509 U.S. 502"]),
    ("What must the employer produce to rebut a prima facie case of discrimination?", "txnd", T7, "disparate_treatment", ["450 U.S. 248"]),
    ("Does disbelief of the employer's reason compel judgment for the plaintiff?", "txnd", T7, "disparate_treatment", ["509 U.S. 502"]),
    ("Can a prima facie case plus evidence of pretext be enough to sustain a verdict of discrimination?", "txnd", T7, "disparate_treatment", ["530 U.S. 133"]),
    ("Must an employment discrimination complaint plead a prima facie case to survive a motion to dismiss?", "cand", T7, "disparate_treatment", ["534 U.S. 506"]),
    ("Is direct evidence required for a mixed-motive instruction under Title VII?", "cand", T7, "disparate_treatment", ["539 U.S. 90"]),
    ("What is the motivating-factor standard under Title VII?", "txnd", T7, "disparate_treatment", ["539 U.S. 90", "490 U.S. 228"]),
    ("Does sex stereotyping constitute discrimination because of sex?", "cand", T7, "disparate_treatment", ["490 U.S. 228"]),
    ("Does Title VII protect employees from discrimination for being gay or transgender?", "txnd", T7, "disparate_treatment", ["590 U.S. 644"]),
    ("Must a plaintiff challenging a job transfer show significant harm?", "txnd", T7, "disparate_treatment", ["601 U.S. 346"]),
    ("What harm must a Title VII discrimination plaintiff show from a transfer?", "cand", T7, "disparate_treatment", ["601 U.S. 346"]),
    ("Can a supervisor's use of the word 'boy' be evidence of racial animus?", "txnd", T7, "disparate_treatment", ["546 U.S. 454"]),
    ("How must comparators be similarly situated in the Fifth Circuit?", "txnd", T7, "disparate_treatment", ["574 F.3d 253", "245 F.3d 507"]),
    ("Are comparators required to be nearly identical in the Fifth Circuit?", "txnd", T7, "disparate_treatment", ["574 F.3d 253"]),
    ("What qualifies as an adverse employment action for a discrimination claim in the Fifth Circuit?", "txnd", T7, "disparate_treatment", ["601 U.S. 346", "492 F.3d 551"]),
    ("Can an employer defend a race-conscious decision by fear of disparate-impact liability?", "cand", T7, "disparate_treatment", ["557 U.S. 557"]),
    ("What is the strong-basis-in-evidence standard for race-based action to avoid disparate impact?", "txnd", T7, "disparate_treatment", ["557 U.S. 557"]),
    ("Does Title VII prohibit employment practices with a disparate impact on race?", "txnd", T7, "disparate_treatment", ["401 U.S. 424"]),
    ("Can a single discriminatory comment by a decisionmaker defeat summary judgment in the Ninth Circuit?", "cand", T7, "disparate_treatment", ["424 F.3d 1027"]),
    ("What prima facie showing is needed for Title VII discrimination in the Ninth Circuit?", "cand", T7, "disparate_treatment", ["411 U.S. 792", "349 F.3d 634"]),
    ("Is the Title VII employee-numerosity requirement jurisdictional?", "txnd", T7, "disparate_treatment", ["546 U.S. 500"]),
    ("When is after-acquired evidence of misconduct relevant to remedies in a discrimination case?", "cand", ADEA, "disparate_treatment", ["513 U.S. 352"]),
    ("When are punitive damages available for intentional discrimination under Title VII?", "txnd", T7, "disparate_treatment", ["527 U.S. 526"]),
    # --- Hostile work environment ---------------------------------------------------------------
    ("Is sexual harassment creating a hostile work environment actionable under Title VII?", "txnd", T7, "hostile_work_environment", ["477 U.S. 57"]),
    ("Must a hostile work environment plaintiff show psychological injury?", "cand", T7, "hostile_work_environment", ["510 U.S. 17"]),
    ("What factors determine whether harassment is severe or pervasive?", "txnd", T7, "hostile_work_environment", ["510 U.S. 17"]),
    ("Is same-sex sexual harassment actionable under Title VII?", "txnd", T7, "hostile_work_environment", ["523 U.S. 75"]),
    ("When is an employer vicariously liable for a supervisor's harassment?", "cand", T7, "hostile_work_environment", ["524 U.S. 775", "524 U.S. 742"]),
    ("What is the Faragher-Ellerth affirmative defense?", "txnd", T7, "hostile_work_environment", ["524 U.S. 775", "524 U.S. 742"]),
    ("Who is a supervisor for purposes of vicarious liability under Title VII?", "txnd", T7, "hostile_work_environment", ["570 U.S. 421"]),
    ("Can a constructive discharge be a tangible employment action barring the Ellerth defense?", "cand", T7, "hostile_work_environment", ["542 U.S. 129"]),
    ("Are isolated offhand comments enough for a hostile work environment?", "txnd", T7, "hostile_work_environment", ["524 U.S. 775", "532 U.S. 268"]),
    ("Can harassment of a male employee based on gender stereotypes be actionable in the Fifth Circuit?", "txnd", T7, "hostile_work_environment", ["731 F.3d 444", "523 U.S. 75"]),
    ("What standard does the Ninth Circuit apply to judge whether harassment is severe from the victim's perspective?", "cand", T7, "hostile_work_environment", ["924 F.2d 872"]),
    ("Is a hostile work environment claim timely if one act falls within the filing period?", "cand", T7, "hostile_work_environment", ["536 U.S. 101", "419 F.3d 885"]),
    ("What must a plaintiff show for racial harassment in the Ninth Circuit?", "cand", T7, "hostile_work_environment", ["360 F.3d 1103", "510 U.S. 17"]),
    ("Is an employer liable for co-worker harassment it knew about and failed to stop?", "txnd", T7, "hostile_work_environment", ["570 U.S. 421", "524 U.S. 775"]),
    ("When does a constructive discharge claim accrue for limitations purposes?", "txnd", T7, "hostile_work_environment", ["578 U.S. 547"]),
    ("What is required to prove constructive discharge under Title VII?", "cand", T7, "hostile_work_environment", ["542 U.S. 129", "578 U.S. 547"]),
    # --- Religious accommodation and pregnancy ---------------------------------------------------
    ("What is undue hardship for a religious accommodation under Title VII?", "txnd", T7, "religious_accommodation", ["600 U.S. 447"]),
    ("Does Title VII require an applicant to show the employer had actual knowledge of the need for religious accommodation?", "cand", T7, "religious_accommodation", ["575 U.S. 768"]),
    ("Can an employer refuse to hire someone to avoid accommodating a religious practice?", "txnd", T7, "religious_accommodation", ["575 U.S. 768"]),
    ("When is accommodating an employee's religious objection an undue hardship in the Ninth Circuit?", "cand", T7, "religious_accommodation", ["358 F.3d 599", "600 U.S. 447"]),
    ("How does the Pregnancy Discrimination Act apply to light-duty accommodation policies?", "txnd", T7, "pregnancy", ["575 U.S. 206"]),
    ("Can a pregnant worker show pretext when the employer accommodates others similar in ability to work?", "cand", T7, "pregnancy", ["575 U.S. 206"]),
    # --- Procedure: charge filing ------------------------------------------------------------------
    ("When must an EEOC charge be filed for a discrete discriminatory act?", "txnd", T7, "disparate_treatment", ["536 U.S. 101", "42 U.S.C. § 2000e-5"]),
    ("Is Title VII's charge-filing requirement jurisdictional?", "txnd", T7, "disparate_treatment", ["587 U.S. 541"]),
    ("Can an employer forfeit an exhaustion defense by raising it late?", "cand", T7, "disparate_treatment", ["587 U.S. 541"]),
    ("When does the limitations period for a pay discrimination claim begin after the Ledbetter Act?", "txnd", T7, "disparate_treatment", ["550 U.S. 618"]),
    ("Are untimely discrete acts actionable if related to timely acts?", "cand", T7, "retaliation", ["536 U.S. 101"]),
    ("How long does a plaintiff have to sue after receiving a right-to-sue letter?", "txnd", T7, "disparate_treatment", ["42 U.S.C. § 2000e-5"]),
    ("What document qualifies as an EEOC charge?", "cand", ADEA, "disparate_treatment", ["552 U.S. 389"]),
    # --- ADA -------------------------------------------------------------------------------------------
    ("How is disability defined under the ADA?", "txnd", ADA, "disparate_treatment", ["42 U.S.C. § 12102"]),
    ("Are mitigating measures considered in deciding whether an impairment is a disability?", "cand", ADA, "disparate_treatment", ["527 U.S. 471", "42 U.S.C. § 12102"]),
    ("Is the Toyota v. Williams demanding standard for disability still good law?", "txnd", ADA, "disparate_treatment", ["534 U.S. 184", "42 U.S.C. § 12102"]),
    ("Is asymptomatic HIV a disability under the ADA?", "cand", ADA, "disparate_treatment", ["524 U.S. 624"]),
    ("Who is a qualified individual under ADA Title I?", "txnd", ADA, "disparate_treatment", ["42 U.S.C. § 12111"]),
    ("Can an employer refuse to hire someone whose job would pose a direct threat to their own health?", "cand", ADA, "disparate_treatment", ["536 U.S. 73"]),
    ("Is a neutral no-rehire policy a legitimate reason under the ADA?", "txnd", ADA, "disparate_treatment", ["540 U.S. 44"]),
    ("What must an employer do to reasonably accommodate a disabled employee?", "txnd", ADA, "failure_to_accommodate", ["42 U.S.C. § 12112", "29 C.F.R. § 1630.2"]),
    ("Does a seniority system ordinarily trump a requested reassignment accommodation?", "cand", ADA, "failure_to_accommodate", ["535 U.S. 391"]),
    ("Is an employer required to engage in the interactive process under the ADA?", "txnd", ADA, "failure_to_accommodate", ["570 F.3d 606", "29 C.F.R. § 1630.2"]),
    ("Must a requested accommodation relate to an essential job function?", "txnd", ADA, "failure_to_accommodate", ["730 F.3d 450"]),
    ("What is undue hardship under the ADA?", "cand", ADA, "failure_to_accommodate", ["42 U.S.C. § 12111"]),
    ("Can an ADA plaintiff who claimed total disability for benefits still be a qualified individual?", "txnd", ADA, "disparate_treatment", ["42 U.S.C. § 12111"]),
    ("How does the Ninth Circuit treat safety-based qualification standards under the ADA?", "cand", ADA, "disparate_treatment", ["511 F.3d 974"]),
    ("Does the ADA prohibit retaliation for requesting an accommodation?", "txnd", ADA, "retaliation", ["42 U.S.C. § 12203"]),
    ("What regulation defines reasonable accommodation under the ADA?", "cand", ADA, "failure_to_accommodate", ["29 C.F.R. § 1630.2"]),
    # --- ADEA ----------------------------------------------------------------------------------------------
    ("What causation must an ADEA plaintiff prove?", "txnd", ADEA, "disparate_treatment", ["557 U.S. 167"]),
    ("Is a mixed-motive jury instruction available under the ADEA?", "cand", ADEA, "disparate_treatment", ["557 U.S. 167"]),
    ("Is firing someone to prevent pension vesting age discrimination?", "txnd", ADEA, "disparate_treatment", ["507 U.S. 604"]),
    ("Must an ADEA plaintiff be replaced by someone under 40?", "cand", ADEA, "disparate_treatment", ["517 U.S. 308"]),
    ("Are disparate-impact claims available under the ADEA?", "txnd", ADEA, "disparate_impact", ["544 U.S. 228"]),
    ("Does the ADEA prohibit favoring older workers over younger ones?", "cand", ADEA, "disparate_treatment", ["540 U.S. 581"]),
    ("Is 'other supervisor' evidence admissible in an ADEA case?", "txnd", ADEA, "disparate_treatment", ["552 U.S. 379"]),
    ("Does the ADEA validly abrogate state sovereign immunity?", "cand", ADEA, "disparate_treatment", ["528 U.S. 62"]),
    ("What standard applies to federal-sector age discrimination claims?", "txnd", ADEA, "disparate_treatment", ["589 U.S. 399"]),
    ("How is pretext shown in an ADEA case in the Fifth Circuit?", "txnd", ADEA, "disparate_treatment", ["530 U.S. 133", "309 F.3d 893"]),
    ("Who is protected by the ADEA?", "cand", ADEA, "disparate_treatment", ["29 U.S.C. § 631"]),
]

out = Path(__file__).with_name("gold.jsonl")
with out.open("w") as f:
    for i, (question, court, statute, theory, expected) in enumerate(Q, 1):
        f.write(json.dumps({"id": f"G{i:03d}", "question": question, "court_id": court, "statute": statute,
                            "theory": theory, "expected_citations": expected}) + "\n")
print(f"{len(Q)} questions -> {out}")
