"""Small local demo cases for the Scientific Triage Assistant MVP."""

EMPTY_CASE = ""

PHI_HEAVY_CASE = (
    "Patient Jane Doe, DOB 01/02/1980, MRN 1234567, phone 555-010-2211. "
    "Newly diagnosed lung adenocarcinoma. EGFR L858R detected on tumor panel."
)

GENE_ONLY_CASE = (
    "Metastatic breast cancer with HER2 amplification and progression after "
    "trastuzumab-based therapy. Summarize evidence and trial options."
)

VARIANT_CASE = (
    "62-year-old with metastatic non-small cell lung cancer and EGFR L858R mutation, "
    "progression after osimertinib, new dyspnea and weight loss over 4 weeks, mild cough, "
    "elevated CRP, HR 112, SpO2 93%. De-identified summary."
)

NO_VARIANT_CASE = (
    "Metastatic melanoma cancer with high tumor mutational burden. "
    "No molecular alteration was provided in the referral note."
)
