# Résumé CRM Atelier Nova

- **Date de référence (as_of)** : 2026-11-18
- **Graine aléatoire** : 42
- **Mode public** : non

## Volumes

| Objet | Nombre |
| --- | --- |
| Entreprises | 220 |
| Contacts | 427 |
| Deals (total) | 300 |
| Deals ouverts | 110 |
| Deals gagnés | 70 |
| Deals perdus | 120 |
| Activités | 4839 |

## Répartition par étape (deals ouverts)

| Étape | Nombre |
| --- | --- |
| decouverte | 24 |
| qualification | 33 |
| demo | 17 |
| proposition | 16 |
| negociation | 20 |

## Répartition par AE

| AE | Ouverts | Gagnés | Perdus |
| --- | --- | --- | --- |
| ae1 | 29 | 34 | 23 |
| ae2 | 14 | 10 | 23 |
| ae3 | 23 | 8 | 18 |
| ae4 | 17 | 5 | 45 |
| ae5 | 27 | 13 | 11 |

## Anomalies plantées (38 signaler)

| Deal | Code | Preuve |
| --- | --- | --- |
| D-0001 | A1 | En Démo depuis 63 j (normale 21 j) |
| D-0007 | A1 | En Qualification depuis 41 j (normale 14 j) |
| D-0015 | A1 | En Négociation depuis 88 j (normale 30 j) |
| D-0023 | A1 | En Découverte depuis 45 j (normale 14 j) |
| D-0045 | A1 | En Qualification depuis 54 j (normale 14 j) |
| D-0057 | A1 | En Qualification depuis 53 j (normale 14 j) |
| D-0075 | A1 | En Qualification depuis 43 j (normale 14 j) |
| D-0096 | A1 | En Proposition envoyée depuis 65 j (normale 21 j) |
| D-0001 | A2 | Aucune tâche ni réunion à venir |
| D-0023 | A2 | Aucune tâche ni réunion à venir |
| D-0045 | A2 | Aucune tâche ni réunion à venir |
| D-0063 | A2 | Aucune tâche ni réunion à venir |
| D-0065 | A2 | Aucune tâche ni réunion à venir |
| D-0075 | A2 | Aucune tâche ni réunion à venir |
| D-0096 | A2 | Aucune tâche ni réunion à venir |
| D-0040 | A3 | Date de clôture dépassée : 2026-10-21 (il y a 28 j) |
| D-0043 | A3 | Date de clôture dépassée : 2026-10-24 (il y a 25 j) |
| D-0055 | A3 | Date de clôture dépassée : 2026-10-10 (il y a 39 j) |
| D-0068 | A3 | Date de clôture dépassée : 2026-09-30 (il y a 49 j) |
| D-0070 | A3 | Date de clôture dépassée : 2026-10-13 (il y a 36 j) |
| D-0094 | A3 | Date de clôture dépassée : 2026-11-06 (il y a 12 j) |
| D-0034 | A4 | Deal de 30000€ sans activité depuis 30 j |
| D-0061 | A4 | Deal de 30000€ sans activité depuis 33 j |
| D-0072 | A4 | Deal de 40000€ sans activité depuis 43 j |
| D-0078 | A4 | Deal de 45000€ sans activité depuis 35 j |
| D-0005 | A5 | Montant manquant en Négociation |
| D-0029 | A5 | Montant manquant en Négociation |
| D-0046 | A5 | Montant manquant en Proposition envoyée |
| D-0022 | A6 | Clôture en 2026-11 mais étape Qualification |
| D-0025 | A6 | Clôture en 2026-11 mais étape Qualification |
| D-0038 | A6 | Clôture en 2026-11 mais étape Découverte |
| D-0014 | A7 | Deal 25000€ en Négociation avec 1 seul interlocuteur |
| D-0049 | A7 | Deal 35000€ en Négociation avec 1 seul interlocuteur |
| D-0089 | A7 | Deal 20000€ en Négociation avec 1 seul interlocuteur |
| D-0087 | A8 | En Négociation sans réunion de démo dans l'historique |
| D-0110 | A8 | En Négociation sans réunion de démo dans l'historique |
| D-0006 | A9 | Doublon : même entreprise C-0121, noms quasi identiques |
| D-0106 | A9 | Doublon : même entreprise C-0121, noms quasi identiques |

## Leurres (6 ignorer)

| Deal | Code | Preuve |
| --- | --- | --- |
| D-0004 | L1 | Long en Démo mais RDV calé le 2026-11-28 |
| D-0048 | L2 | Long en Proposition envoyée mais RDV calé le 2026-12-07 |
| D-0095 | L3 | Deal 35000€ mais dernière activité il y a 20 j (seuil 21 j) |
| D-0107 | L4 | Deal 25000€ mais dernière activité il y a 20 j (seuil 21 j) |
| D-0012 | L5 | Négociation 1 contact mais montant 15 000€ (seuil A7 = 20 000€) |
| D-0051 | L6 | Date de clôture = as_of (2026-11-18), pas encore dépassée |

## TODOs

- TODO: Vérifier les plages téléphoniques réservées à la fiction par l'Arcep. Actuellement en 01 99 00 XX XX.
- TODO: Phase 2 — import.py vers HubSpot, reset.py, tick.py.
- TODO: Ajouter de la saisonnalité (creux août, pics juin/décembre).
