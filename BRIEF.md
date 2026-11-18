# BRIEF — Générateur du CRM fictif « Atelier Nova » (phase 1)

Ce repo produit un faux CRM réaliste, avec des anomalies plantées et connues d'avance (la « vérité terrain »).
Il sert à évaluer des agents IA de revue de pipeline, à faire des démos et à nourrir une plateforme démo publique.

**Phase 1 = générer les fichiers et prouver qu'ils sont justes. Aucun appel à HubSpot dans cette phase.**

## Contraintes techniques

- Python 3, **bibliothèque standard uniquement** (urllib, json, csv, random, datetime, unittest). Aucun `pip install`.
- Graine aléatoire fixe : `python3 generate.py --seed 42` doit produire des fichiers identiques octet pour octet à chaque exécution.
- Paramètre `--as-of AAAA-MM-JJ` (défaut : aujourd'hui) = la date « du jour » du CRM. Tout l'historique est calculé par rapport à elle.
- Paramètre `--public` : remplace toutes les entreprises réelles par des entreprises inventées (noms, villes, SIREN fictifs commençant par 999).
- Une seule commande de vérification : `python3 -m unittest discover tests`. La lancer et corriger seul jusqu'au vert avant de rendre la main.

## Structure attendue

```
crm-fictif/
  BRIEF.md
  generate.py          # point d'entrée
  nova/
    companies.py       # récupération + cache des entreprises réelles
    people.py          # noms, fonctions, e-mails, téléphones fictifs
    pipeline.py        # étapes, durées, probabilités (constantes)
    deals.py           # génération des deals et de leur historique
    activities.py      # appels, e-mails, réunions, notes, tâches
    anomalies.py       # plantation des anomalies et des leurres
    rules.py           # règles de détection déterministes (référence)
    texts.py           # modèles de notes et d'e-mails en français
  data/
    companies_cache.json   # réponses de l'API mises en cache (versionné)
  out/
    crm.json
    truth.csv
    summary.md         # résumé lisible : volumes, répartition, anomalies
  tests/
```

## L'entreprise fictive

Atelier Nova, éditeur SaaS français de planification et de suivi des interventions terrain.
Clients : PME et ETI de maintenance, BTP et services techniques. Abonnement annuel.

- Panier : loi log-normale, médiane 12 000 €, bornes 3 000 à 60 000 €, arrondi à 500 €.
- Segment « comptes stratégiques » (≈ 1/3 des entreprises, les plus grosses) : deals de 30 000 à 60 000 €.
- Cycle de vente : 45 à 90 jours. Historique : du 2025-05-01 à `--as-of`.
- Saisonnalité : creux en août, pics de signatures en juin et décembre.

### Équipe (owners, tous fictifs)

| id | rôle | profil |
| --- | --- | --- |
| dirco | Directeur commercial | Ne porte pas de deals |
| ae1 | AE | Star : 1,5 × plus de deals gagnés |
| ae2, ae3 | AE | Solides |
| ae4 | AE | En difficulté : taux de transformation faible, deals qui traînent |
| ae5 | AE | Logue peu : 3 × moins d'activités pour un volume normal |
| sdr1, sdr2 | SDR | Créent les deals en Découverte, les passent aux AE |

E-mails des owners : `bernard+<id>@flaks.app`.

## Pipeline

| clé | étape | proba | durée normale (jours) |
| --- | --- | --- | --- |
| decouverte | Découverte | 0.10 | 14 |
| qualification | Qualification | 0.20 | 14 |
| demo | Démo | 0.40 | 21 |
| proposition | Proposition envoyée | 0.60 | 21 |
| negociation | Négociation | 0.80 | 30 |
| gagne | Gagné | 1.00 | — |
| perdu | Perdu | 0.00 | — |

Motifs de perte : prix, timing_budget, concurrent, pas_de_decision, produit_inadapte, contact_perdu.

## Volumes

| objet | volume |
| --- | --- |
| entreprises | ~220 |
| contacts | ~450 (1 à 4 par entreprise) |
| deals ouverts | ~70 (plus nombreux en début de pipe) |
| deals gagnés | ~70 |
| deals perdus | ~120 (avec motif) |
| activités | ~4 000 (5 à 25 par deal, plus denses en Démo et Négociation) |

## Entreprises réelles

Source : API publique Recherche d'entreprises (`https://recherche-entreprises.api.gouv.fr/search`).
Vérifier les noms exacts des paramètres dans la documentation de l'API avant de coder.

- Codes NAF ciblés (à ajuster si un code renvoie trop peu de résultats) : 43.21A, 43.22A, 43.22B, 43.29A, 33.12Z, 33.14Z, 81.10Z, 71.12B.
- PME : 20 à 499 salariés. Comptes stratégiques : 500 salariés et plus (ce sont les entreprises « connues »).
- Uniquement des entreprises actives, **jamais d'entreprise individuelle** (nature juridique 1000) : leur nom est une donnée personnelle.
- Champs gardés : SIREN, nom, NAF, tranche d'effectif, ville, département. **Aucun nom de dirigeant.**
- Respecter la limite de débit de l'API (pause entre les appels), mettre toutes les réponses en cache dans `data/companies_cache.json`. Si le cache existe, ne pas rappeler l'API.

## Contacts fictifs

- Prénoms et noms générés, fonctions plausibles : DAF, directeur technique, responsable d'exploitation, responsable maintenance, DG (PME uniquement), acheteur.
- E-mails : `prenom.nom@<slug-entreprise>.exemple.invalid` (domaine non routable, rien ne peut partir).
- Téléphones : plages réservées à la fiction par l'Arcep. Si tu ne peux pas confirmer ces plages, utilise `01 99 00 XX XX` et ajoute un TODO dans summary.md.

## Activités et textes

- Types : appel, e-mail, réunion, note, tâche. Chacune horodatée et associée à un deal, un contact et un owner.
- Tâches et réunions peuvent être **à venir** (après `--as-of`) : c'est ce qui définit « une prochaine étape ».
- Textes en français, style commercial réel : courts, abrégés, parfois incomplets, quelques fautes de frappe.
- Les textes ne parlent que du besoin et du projet. **Jamais de fait inventé sur l'entreprise réelle** (CA, difficultés, dirigeants, actualité).
- v1 : modèles de phrases combinés aléatoirement, sans LLM.

## Format de sortie `out/crm.json`

Format commun, indépendant de HubSpot (l'agent ne lira que ce format) :

```json
{
  "meta": {"as_of": "2026-11-18", "seed": 42, "public": false},
  "owners": [{"id": "ae1", "name": "...", "email": "...", "role": "ae"}],
  "companies": [{"id": "C-0001", "siren": "...", "name": "...", "naf": "...", "size_band": "...", "city": "...", "segment": "pme|strategique"}],
  "contacts": [{"id": "P-0001", "company_id": "C-0001", "first_name": "...", "last_name": "...", "title": "...", "email": "...", "phone": "..."}],
  "deals": [{"id": "D-0001", "company_id": "...", "contact_ids": ["..."], "owner_id": "ae1", "name": "...", "amount": 12000,
             "stage": "demo", "stage_entered_at": "2026-10-02", "created_at": "...", "close_date": "...",
             "lost_reason": null, "stage_history": [{"stage": "decouverte", "entered_at": "..."}]}],
  "activities": [{"id": "A-0001", "deal_id": "...", "contact_id": "...", "owner_id": "...", "type": "meeting",
                  "at": "2026-11-20T10:00:00", "subject": "...", "body": "..."}]
}
```

`stage_entered_at` deviendra la propriété personnalisée `date_entree_etape` dans HubSpot (l'historique natif ne peut pas être antidaté).

## Anomalies plantées (deals ouverts uniquement)

| code | anomalie | règle | nombre |
| --- | --- | --- | --- |
| A1 | Stagnant | jours dans l'étape > 2 × durée normale | 8 |
| A2 | Pas de prochaine étape | aucune tâche ni réunion à venir | 7 |
| A3 | Clôture dépassée | close_date < as_of | 6 |
| A4 | Gros deal silencieux | amount ≥ 25 000 et dernière activité passée il y a > 21 jours | 4 |
| A5 | Montant manquant | amount nul ou vide à partir de proposition | 3 |
| A6 | Prévision irréaliste | close_date dans le mois de as_of mais étape decouverte ou qualification | 3 |
| A7 | Un seul interlocuteur | amount ≥ 20 000, étape negociation, un seul contact | 3 |
| A8 | Saut d'étape | étape negociation sans aucune réunion de démo dans l'historique | 2 |
| A9 | Doublon | même entreprise, deux deals ouverts au nom quasi identique | 2 |

Total : 38 anomalies. Un deal peut en porter deux (par exemple A1 + A2), comme dans la réalité.
**Tous les autres deals ouverts doivent être « propres » au regard des 9 règles** : aucune anomalie accidentelle.

### 6 leurres (doivent être ignorés)

| leurre | construction |
| --- | --- |
| L1, L2 | Longs dans l'étape (dépassent A1) MAIS note de moins de 7 jours expliquant le délai (« client en congés jusqu'au 5/01, RDV calé ») ET réunion à venir |
| L3, L4 | amount ≥ 25 000, dernière activité il y a exactement 20 jours (juste sous le seuil A4) |
| L5 | négociation, un seul contact, amount 15 000 (sous le seuil A7) |
| L6 | close_date = as_of (pas encore dépassée) |

Attention : L1 et L2 dépassent techniquement la règle A1. `rules.py` doit donc implémenter l'exception : un deal n'est pas stagnant s'il a une note récente (< 7 jours) ET une réunion à venir.

## Vérité terrain `out/truth.csv`

```
deal_id,code,attendu,preuve,owner
D-0142,A1,signaler,"En Démo depuis 47 j (normale 21 j)",ae3
D-0187,L1,ignorer,"Long en Démo mais RDV calé le 2026-12-02",ae1
```

Une ligne par anomalie et par leurre. `preuve` contient les chiffres exacts calculés.

## Tests (tous dans `tests/`, unittest)

1. **Cohérence** : `rules.py` appliqué à `crm.json` retrouve exactement les lignes `signaler` de `truth.csv`, ni plus ni moins, et ne signale aucun leurre.
2. **Reproductibilité** : deux générations avec la même graine donnent des fichiers identiques.
3. **Volumes** : chaque volume est à ± 15 % de la cible ; 38 anomalies et 6 leurres exactement.
4. **Vraisemblance** : dates dans l'ordre (création ≤ entrées d'étape ≤ as_of pour l'historique), montants dans les bornes, gagnés/perdus avec close_date passée, perdus avec motif.
5. **Sécurité des données** : aucun e-mail de contact hors `.exemple.invalid`, aucune entreprise individuelle, aucun champ dirigeant.
6. **Mode public** : avec `--public`, aucun SIREN ni nom issu du cache des entreprises réelles.

## Rendu attendu

- `out/summary.md` : volumes, répartition par étape et par AE, liste des anomalies et leurres avec leur deal.
- Un court compte rendu : ce qui a été fait, les choix faits seul, les TODO restants.

Phase 2 (plus tard, pas maintenant) : `import.py` vers un compte de test HubSpot, `reset.py`, `tick.py` (semaine suivante).
