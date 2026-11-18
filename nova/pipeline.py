"""
Pipeline stages, durations, and probabilities for Atelier Nova CRM.
"""

# Ordered list of active stages
STAGES = [
    "decouverte",
    "qualification",
    "demo",
    "proposition",
    "negociation",
]

TERMINAL_STAGES = ["gagne", "perdu"]

# Stage metadata: label, win probability at this stage, normal duration in days
STAGE_META = {
    "decouverte":   {"label": "Découverte",          "proba": 0.10, "normal_days": 14},
    "qualification":{"label": "Qualification",        "proba": 0.20, "normal_days": 14},
    "demo":         {"label": "Démo",                 "proba": 0.40, "normal_days": 21},
    "proposition":  {"label": "Proposition envoyée",  "proba": 0.60, "normal_days": 21},
    "negociation":  {"label": "Négociation",          "proba": 0.80, "normal_days": 30},
    "gagne":        {"label": "Gagné",                "proba": 1.00, "normal_days": None},
    "perdu":        {"label": "Perdu",                "proba": 0.00, "normal_days": None},
}

LOST_REASONS = [
    "prix",
    "timing_budget",
    "concurrent",
    "pas_de_decision",
    "produit_inadapte",
    "contact_perdu",
]

# Owner definitions
OWNERS = [
    {"id": "dirco", "name": "Directeur Commercial", "email": "bernard+dirco@flaks.app", "role": "dirco"},
    {"id": "ae1",   "name": "Alice Moreau",          "email": "bernard+ae1@flaks.app",   "role": "ae"},
    {"id": "ae2",   "name": "Bruno Petit",            "email": "bernard+ae2@flaks.app",   "role": "ae"},
    {"id": "ae3",   "name": "Claire Durand",          "email": "bernard+ae3@flaks.app",   "role": "ae"},
    {"id": "ae4",   "name": "David Leroy",            "email": "bernard+ae4@flaks.app",   "role": "ae"},
    {"id": "ae5",   "name": "Emma Bernard",           "email": "bernard+ae5@flaks.app",   "role": "ae"},
    {"id": "sdr1",  "name": "Fabien Simon",           "email": "bernard+sdr1@flaks.app",  "role": "sdr"},
    {"id": "sdr2",  "name": "Gaëlle Martin",          "email": "bernard+sdr2@flaks.app",  "role": "sdr"},
]

AE_IDS = ["ae1", "ae2", "ae3", "ae4", "ae5"]
SDR_IDS = ["sdr1", "sdr2"]
