# BRIEF — Agent de revue de pipeline, partie locale (v1)

Le faux CRM est prêt (`out/crm.json`, `out/truth.csv`, `nova/rules.py`).
On construit maintenant l'agent qui produit la revue de pipeline du lundi.

## Principe : le code calcule, le LLM rédige

1. **`review/facts.py`** (code, sans LLM) lit `crm.json`, applique `nova/rules.py` et produit `out/facts.json` : tout ce que la revue a le droit de dire, chiffres déjà calculés.
2. **La synthèse** est rédigée par un LLM **à partir de `facts.json` uniquement**. Dans cette v1, c'est Hermes qui rédigera (sur le VPS, hors de ce repo). Ce repo fournit seulement le prompt et les garde-fous.
3. **`review/render_raw.py`** (code, sans LLM) produit une revue brute lisible à partir de `facts.json`. C'est le secours si le LLM tombe, et la référence de comparaison.
4. **`review/evaluate.py`** note n'importe quelle revue (brute ou rédigée par un LLM) contre `truth.csv` et `facts.json`.

Contraintes inchangées : Python 3, bibliothèque standard uniquement, aucun appel réseau, tests avec unittest, corriger seul jusqu'au vert, commit à la fin.

## `out/facts.json`

```json
{
  "as_of": "2026-11-18",
  "team": "Atelier Nova",
  "totals": {"open_deals": 70, "open_amount": 1234000, "flagged_deals": 30, "flagged_amount": 456000},
  "priorities": ["D-0142", "D-0087", "D-0031"],
  "by_owner": [
    {"owner_id": "ae3", "owner_name": "...", "open_deals": 14, "open_amount": 210000,
     "flagged": [
       {"deal_id": "D-0142", "deal_name": "...", "company": "...", "stage": "Démo", "amount": 32000,
        "codes": ["A1", "A2"],
        "facts": ["En Démo depuis 47 jours (durée normale 21 jours)", "Aucune tâche ni réunion à venir"],
        "last_activity": {"date": "2026-10-02", "type": "appel", "summary": "..."}}
     ]}
  ],
  "excused": [
    {"deal_id": "D-0187", "deal_name": "...", "owner_id": "ae1",
     "why": "En Démo depuis 52 jours, mais note du 2026-11-15 et RDV prévu le 2026-12-08"}
  ],
  "allowed_numbers": ["47", "21", "32 000", "..."]
}
```

Règles :
- `facts` = phrases factuelles courtes en français, chiffres inclus. Jamais d'interprétation (« le client se désintéresse »), seulement des constats.
- `priorities` = les 3 deals signalés les plus importants, calculés par du code : score = montant × poids des anomalies (A4, A7 = 3 ; A1, A2, A3 = 2 ; autres = 1). Égalité départagée par le montant.
- `excused` = deals qui dépassent un seuil mais que l'exception de `rules.py` écarte (note récente + RDV à venir). L'agent n'a jamais accès à `truth.csv` : il ne sait pas ce qu'est un leurre, il applique les règles.
- `allowed_numbers` = tous les nombres (montants, jours, dates, comptes) présents dans `facts.json`, sous leurs formes écrites usuelles (32000, 32 000, 32 000 €, 32 k€, 2026-12-08, 8/12, 8 décembre). Sert au contrôle anti-invention.
- Un deal avec plusieurs anomalies apparaît une seule fois, avec tous ses codes.

## `review/prompt.md`

Le prompt que Hermes utilisera pour rédiger la revue à partir de `facts.json` :
- Destinataire : le directeur commercial, lundi 8 h, dans Slack. Lisible en 2 minutes.
- Structure : 2 lignes d'ouverture (combien de deals à regarder, pour quel montant) → les 3 priorités → un bloc court par AE (seulement ceux qui ont des deals signalés) → une ligne « vus mais pas inquiétants » reprenant `excused`.
- Environ 300 mots plus les blocs AE. Ton direct, factuel, sans jugement sur les personnes.
- **Interdit** : tout nombre, date ou nom absent de `facts.json` ; toute supposition sur les intentions du client ; toute recommandation de management (« recadrer ae4 »).
- Chaque deal cité l'est par son nom de deal, exactement comme dans `facts.json`.

## `review/render_raw.py`

Même structure que le prompt, rédigée par gabarits, sans LLM. Sortie : `out/review_raw.md`.

## `review/evaluate.py`

Usage : `python3 -m review.evaluate out/review_raw.md` (ou tout autre fichier de revue).
Sortie : un score lisible + `out/eval_<nom>.json`.

| mesure | méthode | seuil de réussite |
| --- | --- | --- |
| Rappel | deals de truth.csv « signaler » cités dans la revue (par nom de deal) | ≥ 90 % (35/38 lignes, en comptant un deal multi-anomalies comme couvrant toutes ses lignes s'il est cité) |
| Leurres signalés à tort | deals « ignorer » cités ailleurs que dans la ligne « vus mais pas inquiétants » | ≤ 1 |
| Chiffres inventés | nombres de la revue absents de `allowed_numbers` | 0 |
| Longueur | mots hors blocs AE | ≤ 350 |

La revue brute (`render_raw.py`) doit obtenir le score parfait : c'est le test de cohérence de toute la chaîne.

## Tests

1. `facts.json` : chaque deal signalé correspond exactement aux lignes « signaler » de truth.csv ; les leurres sont dans `excused` ou absents, jamais dans `flagged`.
2. `priorities` : calcul reproductible et conforme à la formule.
3. `allowed_numbers` contient bien les formes écrites de chaque nombre de `facts`.
4. `render_raw.py` obtient le score parfait avec `evaluate.py`.
5. `evaluate.py` détecte bien les erreurs : sur une revue piégée écrite à la main dans les tests (un chiffre inventé, un leurre signalé, 5 deals oubliés), chaque erreur est comptée.

## Rendu

Compte rendu court + commit. Ensuite viendra la partie Hermes (skill sur le VPS : générer facts.json, rédiger avec prompt.md, poster dans Slack, évaluer et poster le score).
