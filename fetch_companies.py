#!/usr/bin/env python3
"""
Fetches French companies from API Recherche d'Entreprises and writes
data/companies_cache.json.

Usage: python3 fetch_companies.py

API : https://recherche-entreprises.api.gouv.fr/search
Paramètres vérifiés sur openapi.json (v1.0.0) :
  - activite_principale : code NAF/APE de l'unité légale
  - tranche_effectif_salarie : tranche(s), séparées par virgule
  - etat_administratif : "A" = active uniquement
  - per_page : 25 max
  - page : 1-indexé
Champs réponse : siren, nom_complet, activite_principale,
  tranche_effectif_salarie, nature_juridique,
  siege.libelle_commune, siege.departement

Règles :
  - Jamais nature_juridique == "1000" (entreprise individuelle)
  - Jamais de champ dirigeant conservé
  - Pause ≥ 0.15 s entre les appels (< 7 req/s)
  - Si le cache existe déjà, propose de l'écraser (ou lire --force)
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API_BASE = "https://recherche-entreprises.api.gouv.fr/search"
PAUSE = 0.20          # secondes entre appels (< 7 req/s)
MAX_PER_NAF = 500     # résultats max par combinaison NAF × tranche
PER_PAGE = 25         # max autorisé par l'API

NAF_CODES = ["43.21A", "43.22A", "43.22B", "43.29A",
             "33.12Z", "33.14Z", "81.10Z", "71.12B"]

# Tranches PME : 20-499 salariés (codes INSEE 12-32)
# 12=20-49, 21=50-99, 22=100-199, 31=200-249, 32=250-499
TRANCHES_PME = "12,21,22,31,32"
# Tranches stratégiques : 500+ salariés (codes INSEE 41-53)
# 41=500-999, 42=1000-1999, 51=2000-4999, 52=5000-9999, 53=10000+
# Note : le code 54 n'existe pas dans la nomenclature INSEE, il provoque HTTP 400.
TRANCHES_STRAT = "41,42,51,52,53"

CACHE_PATH = os.path.join(os.path.dirname(__file__), "data", "companies_cache.json")


def fetch_page(naf, tranches, page):
    """
    Appel paginé à l'API.
    Retourne le dict JSON ou lève urllib.error.URLError / HTTPError.
    En cas d'erreur HTTP, affiche l'URL complète et le corps de la réponse.
    """
    params = {
        "activite_principale": naf,
        "tranche_effectif_salarie": tranches,
        "etat_administratif": "A",
        "page": str(page),
        "per_page": str(PER_PAGE),
    }
    url = API_BASE + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "crm-fictif/1.0 (outil de démo non-diffusé)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        print(f"\n  URL appelée : {url}")
        print(f"  Réponse API : {body[:500]}")
        raise


def parse_company(r):
    """
    Extrait les champs utiles d'un résultat API.
    Retourne None si l'entrée doit être exclue.
    Aucun champ dirigeant n'est conservé.
    """
    # Exclure entreprises individuelles (nature_juridique 1000)
    nature = str(r.get("nature_juridique", ""))
    if nature == "1000":
        return None

    siren = r.get("siren", "")
    if not siren:
        return None

    nom = r.get("nom_complet") or r.get("nom_raison_sociale") or ""
    if not nom or nom.strip().startswith("[NON-DIFFUSIBLE]"):
        return None

    naf = r.get("activite_principale", "")
    tranche = r.get("tranche_effectif_salarie", "")
    siege = r.get("siege") or {}
    ville = siege.get("libelle_commune", "")
    departement = siege.get("departement", "")

    return {
        "siren": siren,
        "nom": nom.strip(),
        "naf": naf,
        "tranche_effectif": tranche,
        "ville": ville,
        "departement": departement,
        "nature_juridique": nature,
        # Aucun champ dirigeant : nom_personne n'est pas inclus
    }


def fetch_segment(naf, tranches, label):
    """Récupère toutes les pages pour un code NAF et une tranche donnés."""
    companies = []
    page = 1
    while True:
        print(f"    {label} NAF={naf} page={page}…", end=" ", flush=True)
        try:
            data = fetch_page(naf, tranches, page)
        except urllib.error.URLError as e:
            print(f"ERREUR réseau : {e}")
            break
        except Exception as e:
            print(f"ERREUR inattendue : {e}")
            break

        results = data.get("results", [])
        total = data.get("total_results", 0)

        for r in results:
            c = parse_company(r)
            if c:
                companies.append(c)

        fetched_so_far = (page - 1) * PER_PAGE + len(results)
        print(f"{len(results)} rés. (total API : {total})")

        if not results or fetched_so_far >= min(total, MAX_PER_NAF):
            break

        page += 1
        time.sleep(PAUSE)

    return companies


def main():
    force = "--force" in sys.argv
    _only_idx = sys.argv.index("--only") if "--only" in sys.argv else -1
    only_strat = (_only_idx >= 0 and _only_idx + 1 < len(sys.argv)
                  and sys.argv[_only_idx + 1] == "strat")

    if only_strat:
        # Merge mode: load existing cache, re-fetch only STRAT, write back.
        existing_companies = {}
        if os.path.exists(CACHE_PATH):
            with open(CACHE_PATH, encoding="utf-8") as f:
                existing = json.load(f)
            for c in existing.get("companies", []):
                existing_companies[c["siren"]] = c
            n = len(existing_companies)
            print(f"Cache existant chargé : {n} entreprises (PME conservées, STRAT à refaire)")
        else:
            print("Aucun cache existant, création depuis zéro (uniquement STRAT).")

        print("=== Récupération des entreprises STRAT (API Recherche d'Entreprises) ===")
        print(f"Tranches : {TRANCHES_STRAT}  (codes INSEE 41-53, soit 500+ salariés)")
        print(f"Codes NAF : {', '.join(NAF_CODES)}")
        print()

        # Remove existing STRAT entries so we fetch fresh ones
        strat_codes = set(TRANCHES_STRAT.split(","))
        existing_companies = {
            siren: c for siren, c in existing_companies.items()
            if c.get("tranche_effectif", "") not in strat_codes
        }
        print(f"  Entrées STRAT supprimées du cache (seront remplacées).")

        new_companies = dict(existing_companies)
        for naf in NAF_CODES:
            print(f"  NAF {naf} :")
            for c in fetch_segment(naf, TRANCHES_STRAT, "STRAT"):
                new_companies[c["siren"]] = c
            time.sleep(PAUSE)

        companies = list(new_companies.values())

    else:
        if os.path.exists(CACHE_PATH) and not force:
            with open(CACHE_PATH, encoding="utf-8") as f:
                existing = json.load(f)
            n = len(existing.get("companies", []))
            if n > 0:
                print(f"Le cache existe déjà ({n} entreprises).")
                print("Utilisez --force pour le remplacer, ou --only strat pour ne refaire que les grandes entreprises.")
                print("  python3 fetch_companies.py --force")
                print("  python3 fetch_companies.py --only strat")
                sys.exit(0)

        print("=== Récupération des entreprises (API Recherche d'Entreprises) ===")
        print(f"Codes NAF : {', '.join(NAF_CODES)}")
        print()

        all_companies = {}  # Dédupliqué par SIREN

        for naf in NAF_CODES:
            print(f"  NAF {naf} :")
            for c in fetch_segment(naf, TRANCHES_PME, "PME"):
                all_companies[c["siren"]] = c
            time.sleep(PAUSE)
            for c in fetch_segment(naf, TRANCHES_STRAT, "STRAT"):
                all_companies[c["siren"]] = c
            time.sleep(PAUSE)

        companies = list(all_companies.values())

    pme_codes = set(TRANCHES_PME.split(","))
    strat_codes = set(TRANCHES_STRAT.split(","))
    pme = sum(1 for c in companies if c["tranche_effectif"] in pme_codes)
    strat = sum(1 for c in companies if c["tranche_effectif"] in strat_codes)
    indiv = sum(1 for c in companies if c.get("nature_juridique") == "1000")

    print(f"\nTotal : {len(companies)} entreprises uniques")
    print(f"  PME (20-499 sal., codes 12-32)   : {pme}")
    print(f"  Stratégiques (500+ sal., codes 41-53) : {strat}")
    print(f"  Individuelles (exclues dans generate.py) : {indiv}")

    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump({"companies": companies}, f, ensure_ascii=False, indent=2)

    print(f"\nCache écrit : {CACHE_PATH}")
    print("Lancez ensuite : python3 generate.py --seed 42 --as-of 2026-11-18")


if __name__ == "__main__":
    main()
