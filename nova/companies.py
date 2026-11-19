"""
Company data loading from cache.
Phase 1: cache only (no API calls needed as cache is pre-populated).
"""

import json
import os
import random
import re as _re

CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "companies_cache.json")

# INSEE tranche_effectif_salarie codes:
# 12=20-49, 21=50-99, 22=100-199, 31=200-249, 32=250-499 → PME (20-499 sal.)
# 41=500-999, 42=1000-1999, 51=2000-4999, 52=5000-9999, 53=10000+ → Stratégiques
# Code 54 n'existe pas dans la nomenclature INSEE.
TRANCHES_PME = {"12", "21", "22", "31", "32"}
TRANCHES_STRAT = {"41", "42", "51", "52", "53"}


_LOWER_CONN = {"et", "de", "du", "des", "le", "la", "les", "en", "au",
               "aux", "sur", "par", "pour", "&", "d'", "l'"}


def _make_display_name(name: str) -> str:
    """
    Convert an uppercase registry name to readable mixed-case.
    Rules:
    - Drop parenthetical aliases like "(ORANO DEM)".
    - Words where w.isupper() and len(w) <= 4  → keep uppercase (acronyms: EDF, SNCF, T&S).
    - Words containing digits                  → keep as-is (ERA 94, A2, 3M).
    - Connector words (de, du, et, …)          → lowercase, except if first word.
    - Everything else                          → capitalize().
    """
    name = _re.sub(r'\s*\([^)]*\)', '', name).strip()
    words = name.split()
    result = []
    for i, w in enumerate(words):
        if _re.search(r'\d', w):
            result.append(w)
        elif w.isupper() and len(w) <= 4:
            result.append(w)
        elif w.lower() in _LOWER_CONN and i > 0:
            result.append(w.lower())
        else:
            result.append(w.capitalize())
    return " ".join(result)


def load_cache():
    """
    Load companies from cache file.
    Raises RuntimeError with a clear message if cache is missing or empty.
    """
    cache_path = os.path.normpath(CACHE_PATH)
    if not os.path.exists(cache_path):
        raise RuntimeError(
            "data/companies_cache.json introuvable.\n"
            "Lancez : python3 fetch_companies.py"
        )
    with open(cache_path, encoding="utf-8") as f:
        data = json.load(f)
    companies = data.get("companies", [])
    if len(companies) < 100:
        raise RuntimeError(
            f"data/companies_cache.json incomplet ({len(companies)} entrées).\n"
            "Lancez : python3 fetch_companies.py"
        )
    return companies


def classify_company(c):
    """Return segment based on tranche_effectif."""
    t = c.get("tranche_effectif", "")
    if t in TRANCHES_STRAT:
        return "strategique"
    return "pme"


def get_size_band(c):
    """Return human-readable size band."""
    t = c.get("tranche_effectif", "")
    bands = {
        "12": "20-49",
        "21": "50-99",
        "22": "100-199",
        "31": "200-249",
        "32": "250-499",
        "41": "500-999",
        "42": "1000-1999",
        "51": "2000-4999",
        "52": "5000-9999",
        "53": "10000+",
    }
    return bands.get(t, "inconnu")


def select_companies(rng, target=220):
    """
    Select ~target companies from cache with ~1/3 strategic, ~2/3 PME.
    Returns list of company dicts with added segment/size_band fields.
    """
    all_companies = load_cache()
    # Filter out individual companies (nature_juridique 1000)
    all_companies = [c for c in all_companies if str(c.get("nature_juridique", "")) != "1000"]

    pme_pool = [c for c in all_companies if c.get("tranche_effectif", "") in TRANCHES_PME]
    strat_pool = [c for c in all_companies if c.get("tranche_effectif", "") in TRANCHES_STRAT]

    # Sort for determinism
    pme_pool.sort(key=lambda x: x["siren"])
    strat_pool.sort(key=lambda x: x["siren"])

    n_strat = round(target / 3)
    n_pme = target - n_strat

    n_strat = min(n_strat, len(strat_pool))
    n_pme = min(n_pme, len(pme_pool))

    selected_strat = rng.sample(strat_pool, n_strat)
    selected_pme = rng.sample(pme_pool, n_pme)

    result = []
    for c in sorted(selected_strat + selected_pme, key=lambda x: x["siren"]):
        segment = classify_company(c)
        size_band = get_size_band(c)
        nom = c["nom"]
        result.append({
            "siren": c["siren"],
            "name": nom,
            "display_name": _make_display_name(nom),
            "naf": c["naf"],
            "size_band": size_band,
            "city": c["ville"],
            "segment": segment,
        })

    return result


def make_public_companies(rng, companies):
    """
    Replace all company data with invented equivalents for --public mode.
    SIRENs start with 999.
    """
    public_names = [
        "NOVA TECH SOLUTIONS", "ALPHA SERVICES", "BETA MAINTENANCE", "GAMMA INDUSTRIE",
        "DELTA FACILITIES", "EPSILON INGENIERIE", "ZETA CONSTRUCTIONS", "ETA ELECTRONIQUE",
        "THETA PLOMBERIE", "IOTA CLIMATISATION", "KAPPA ETUDES", "LAMBDA MULTISERVICES",
        "MU AUTOMATISATION", "NU ROBOTIQUE", "XI BUREAUTIQUE", "OMICRON LOGISTIQUE",
        "PI CONSULTING", "RHO ENERGIE", "SIGMA BATIMENT", "TAU RENOVATION",
        "UPSILON EQUIPEMENTS", "PHI CONTROLES", "CHI PROCESS", "PSI SYSTEMES",
        "OMEGA RESEAUX", "ACIER SERVICES", "BETON SOLUTIONS", "CABLE INDUSTRIES",
        "DIESEL MAINTENANCE", "ELECTRA FRANCE", "FERRO TECHNIQUE", "GESTION PROPRE",
        "HYDRO CONCEPT", "INFRA BUILD", "JATO SYSTEMES", "KODEX MAINTENANCE",
        "LUMEN ELECTRIQUE", "METRO SERVICES", "NANO INDUSTRIES", "OPTIMA FACILITIES",
    ]
    public_cities = [
        ("VILLENOUVELLE", "31"), ("MONTCHATEL", "69"), ("SAINTEMARIE", "13"),
        ("BEAUCHAMP", "95"), ("RIVIERE-SUR-MER", "17"), ("PONTNEUF", "75"),
        ("HAUTEFONTAINE", "60"), ("BOISLECOMTE", "78"), ("CLAIRVAL", "38"),
        ("ROCHEBLANCHE", "84"),
    ]

    result = []
    siren_counter = [1]

    for i, c in enumerate(companies):
        siren = f"999{siren_counter[0]:06d}"
        siren_counter[0] += 1
        name = public_names[i % len(public_names)] + f" {i+1}"
        city, dept = public_cities[i % len(public_cities)]
        result.append({
            "siren": siren,
            "name": name,
            "display_name": name,   # already invented, no transformation needed
            "naf": c["naf"],
            "size_band": c["size_band"],
            "city": city,
            "segment": c["segment"],
        })

    return result
