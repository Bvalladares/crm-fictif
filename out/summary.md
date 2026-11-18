# Résumé CRM Atelier Nova

- **Date de référence (as_of)** : 2026-11-18
- **Graine aléatoire** : 42
- **Mode public** : non

## Volumes

| Objet | Nombre |
| --- | --- |
| Entreprises | 220 |
| Contacts | 427 |
| Deals (total) | 260 |
| Deals ouverts | 70 |
| Deals gagnés | 70 |
| Deals perdus | 120 |
| Activités | 4082 |

## Répartition par étape (deals ouverts)

| Étape | Nombre |
| --- | --- |
| decouverte | 12 |
| qualification | 25 |
| demo | 7 |
| proposition | 12 |
| negociation | 14 |

## Répartition par AE

| AE | Ouverts | Gagnés | Perdus |
| --- | --- | --- | --- |
| ae1 | 19 | 38 | 24 |
| ae2 | 13 | 8 | 20 |
| ae3 | 15 | 6 | 19 |
| ae4 | 11 | 6 | 47 |
| ae5 | 12 | 12 | 10 |

## Anomalies plantées (38 signaler)

| Deal | Code | Preuve |
| --- | --- | --- |
| D-0013 | A1 | En Qualification depuis 49 j (normale 14 j) |
| D-0015 | A1 | En Négociation depuis 82 j (normale 30 j) |
| D-0020 | A1 | En Qualification depuis 52 j (normale 14 j) |
| D-0027 | A1 | En Qualification depuis 45 j (normale 14 j) |
| D-0046 | A1 | En Qualification depuis 46 j (normale 14 j) |
| D-0047 | A1 | En Qualification depuis 42 j (normale 14 j) |
| D-0051 | A1 | En Négociation depuis 82 j (normale 30 j) |
| D-0057 | A1 | En Qualification depuis 54 j (normale 14 j) |
| D-0015 | A2 | Aucune tâche ni réunion à venir |
| D-0026 | A2 | Aucune tâche ni réunion à venir |
| D-0046 | A2 | Aucune tâche ni réunion à venir |
| D-0047 | A2 | Aucune tâche ni réunion à venir |
| D-0051 | A2 | Aucune tâche ni réunion à venir |
| D-0057 | A2 | Aucune tâche ni réunion à venir |
| D-0065 | A2 | Aucune tâche ni réunion à venir |
| D-0002 | A3 | Date de clôture dépassée : 2026-11-03 (il y a 15 j) |
| D-0023 | A3 | Date de clôture dépassée : 2026-11-09 (il y a 9 j) |
| D-0031 | A3 | Date de clôture dépassée : 2026-11-06 (il y a 12 j) |
| D-0032 | A3 | Date de clôture dépassée : 2026-09-30 (il y a 49 j) |
| D-0066 | A3 | Date de clôture dépassée : 2026-10-27 (il y a 22 j) |
| D-0068 | A3 | Date de clôture dépassée : 2026-11-07 (il y a 11 j) |
| D-0009 | A4 | Deal de 30000€ sans activité depuis 28 j |
| D-0017 | A4 | Deal de 30000€ sans activité depuis 37 j |
| D-0038 | A4 | Deal de 25000€ sans activité depuis 31 j |
| D-0067 | A4 | Deal de 45000€ sans activité depuis 42 j |
| D-0007 | A5 | Montant manquant en Négociation |
| D-0029 | A5 | Montant manquant en Négociation |
| D-0063 | A5 | Montant manquant en Proposition envoyée |
| D-0016 | A6 | Clôture en 2026-11 mais étape Qualification |
| D-0021 | A6 | Clôture en 2026-11 mais étape Qualification |
| D-0070 | A6 | Clôture en 2026-11 mais étape Qualification |
| D-0041 | A7 | Deal 53500€ en Négociation avec 1 seul interlocuteur |
| D-0042 | A7 | Deal 25000€ en Négociation avec 1 seul interlocuteur |
| D-0055 | A7 | Deal 38500€ en Négociation avec 1 seul interlocuteur |
| D-0011 | A8 | En Négociation sans réunion de démo dans l'historique |
| D-0056 | A8 | En Négociation sans réunion de démo dans l'historique |
| D-0005 | A9 | Doublon : même entreprise C-0134, noms quasi identiques |
| D-0064 | A9 | Doublon : même entreprise C-0134, noms quasi identiques |

## Leurres (6 ignorer)

| Deal | Code | Preuve |
| --- | --- | --- |
| D-0012 | L1 | Long en Qualification mais RDV calé le 2026-11-27 |
| D-0036 | L2 | Long en Négociation mais RDV calé le 2026-11-30 |
| D-0039 | L3 | Deal 25000€ mais dernière activité il y a 20 j (seuil 21 j) |
| D-0059 | L4 | Deal 25000€ mais dernière activité il y a 20 j (seuil 21 j) |
| D-0030 | L5 | Négociation 1 contact mais montant 15 000€ (seuil A7 = 20 000€) |
| D-0043 | L6 | Date de clôture = as_of (2026-11-18), pas encore dépassée |

## TODOs

- TODO: Vérifier les plages téléphoniques réservées à la fiction par l'Arcep. Actuellement en 01 99 00 XX XX.
- TODO: Phase 2 — import.py vers HubSpot, reset.py, tick.py.
- TODO: Ajouter de la saisonnalité (creux août, pics juin/décembre).
