# Résumé CRM Atelier Nova

- **Date de référence (as_of)** : 2026-11-18
- **Graine aléatoire** : 42
- **Mode public** : non

## Volumes

| Objet | Nombre |
| --- | --- |
| Entreprises | 220 |
| Contacts | 438 |
| Deals (total) | 300 |
| Deals ouverts | 110 |
| Deals gagnés | 70 |
| Deals perdus | 120 |
| Activités | 4958 |

## Répartition par étape (deals ouverts)

| Étape | Nombre |
| --- | --- |
| decouverte | 31 |
| qualification | 24 |
| demo | 18 |
| proposition | 22 |
| negociation | 15 |

## Répartition par AE

| AE | Ouverts | Gagnés | Perdus |
| --- | --- | --- | --- |
| ae1 | 38 | 34 | 33 |
| ae2 | 24 | 12 | 22 |
| ae3 | 18 | 8 | 16 |
| ae4 | 17 | 5 | 40 |
| ae5 | 13 | 11 | 9 |

## Anomalies plantées (38 signaler)

| Deal | Code | Preuve |
| --- | --- | --- |
| D-0029 | A1 | En Découverte depuis 48 j (normale 14 j) |
| D-0030 | A1 | En Proposition envoyée depuis 59 j (normale 21 j) |
| D-0039 | A1 | En Qualification depuis 40 j (normale 14 j) |
| D-0044 | A1 | En Proposition envoyée depuis 64 j (normale 21 j) |
| D-0047 | A1 | En Qualification depuis 52 j (normale 14 j) |
| D-0051 | A1 | En Démo depuis 66 j (normale 21 j) |
| D-0083 | A1 | En Négociation depuis 94 j (normale 30 j) |
| D-0098 | A1 | En Proposition envoyée depuis 69 j (normale 21 j) |
| D-0039 | A2 | Aucune tâche ni réunion à venir |
| D-0044 | A2 | Aucune tâche ni réunion à venir |
| D-0047 | A2 | Aucune tâche ni réunion à venir |
| D-0068 | A2 | Aucune tâche ni réunion à venir |
| D-0078 | A2 | Aucune tâche ni réunion à venir |
| D-0083 | A2 | Aucune tâche ni réunion à venir |
| D-0098 | A2 | Aucune tâche ni réunion à venir |
| D-0004 | A3 | Date de clôture dépassée : 2026-09-26 (il y a 53 j) |
| D-0024 | A3 | Date de clôture dépassée : 2026-10-25 (il y a 24 j) |
| D-0049 | A3 | Date de clôture dépassée : 2026-09-19 (il y a 60 j) |
| D-0062 | A3 | Date de clôture dépassée : 2026-10-29 (il y a 20 j) |
| D-0086 | A3 | Date de clôture dépassée : 2026-09-22 (il y a 57 j) |
| D-0101 | A3 | Date de clôture dépassée : 2026-10-31 (il y a 18 j) |
| D-0011 | A4 | Deal de 30000€ sans activité depuis 36 j |
| D-0027 | A4 | Deal de 50000€ sans activité depuis 35 j |
| D-0092 | A4 | Deal de 50000€ sans activité depuis 32 j |
| D-0094 | A4 | Deal de 25000€ sans activité depuis 30 j |
| D-0018 | A5 | Montant manquant en Proposition envoyée |
| D-0056 | A5 | Montant manquant en Négociation |
| D-0104 | A5 | Montant manquant en Proposition envoyée |
| D-0037 | A6 | Clôture en 2026-11 mais étape Découverte |
| D-0059 | A6 | Clôture en 2026-11 mais étape Qualification |
| D-0080 | A6 | Clôture en 2026-11 mais étape Qualification |
| D-0038 | A7 | Deal 20000€ en Négociation avec 1 seul interlocuteur |
| D-0089 | A7 | Deal 32000€ en Négociation avec 1 seul interlocuteur |
| D-0090 | A7 | Deal 43500€ en Négociation avec 1 seul interlocuteur |
| D-0050 | A8 | En Négociation sans réunion de démo dans l'historique |
| D-0095 | A8 | En Négociation sans réunion de démo dans l'historique |
| D-0021 | A9 | Doublon : même entreprise C-0155, noms quasi identiques |
| D-0043 | A9 | Doublon : même entreprise C-0155, noms quasi identiques |

## Leurres (6 ignorer)

| Deal | Code | Preuve |
| --- | --- | --- |
| D-0025 | L1 | Long en Qualification mais RDV calé le 2026-11-28 |
| D-0110 | L2 | Long en Découverte mais RDV calé le 2026-12-05 |
| D-0099 | L3 | Deal 35000€ mais dernière activité il y a 20 j (seuil 21 j) |
| D-0035 | L4 | Deal 25000€ mais dernière activité il y a 20 j (seuil 21 j) |
| D-0012 | L5 | Négociation 1 contact mais montant 15 000€ (seuil A7 = 20 000€) |
| D-0070 | L6 | Date de clôture = as_of (2026-11-18), pas encore dépassée |

## TODOs

- TODO: Vérifier les plages téléphoniques réservées à la fiction par l'Arcep. Actuellement en 01 99 00 XX XX.
- TODO: Phase 2 — import.py vers HubSpot, reset.py, tick.py.
- TODO: Ajouter de la saisonnalité (creux août, pics juin/décembre).
