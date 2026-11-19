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
| Activités | 4908 |

## Répartition par étape (deals ouverts)

| Étape | Nombre |
| --- | --- |
| decouverte | 30 |
| qualification | 32 |
| demo | 16 |
| proposition | 18 |
| negociation | 14 |

## Répartition par AE

| AE | Ouverts | Gagnés | Perdus |
| --- | --- | --- | --- |
| ae1 | 38 | 34 | 33 |
| ae2 | 24 | 12 | 22 |
| ae3 | 16 | 8 | 16 |
| ae4 | 19 | 5 | 40 |
| ae5 | 13 | 11 | 9 |

## Anomalies plantées (38 signaler)

| Deal | Code | Preuve |
| --- | --- | --- |
| D-0001 | A1 | En Découverte depuis 41 j (normale 14 j) |
| D-0010 | A1 | En Démo depuis 60 j (normale 21 j) |
| D-0023 | A1 | En Qualification depuis 50 j (normale 14 j) |
| D-0030 | A1 | En Proposition envoyée depuis 70 j (normale 21 j) |
| D-0045 | A1 | En Démo depuis 64 j (normale 21 j) |
| D-0050 | A1 | En Qualification depuis 51 j (normale 14 j) |
| D-0068 | A1 | En Qualification depuis 55 j (normale 14 j) |
| D-0110 | A1 | En Découverte depuis 55 j (normale 14 j) |
| D-0001 | A2 | Aucune tâche ni réunion à venir |
| D-0010 | A2 | Aucune tâche ni réunion à venir |
| D-0023 | A2 | Aucune tâche ni réunion à venir |
| D-0048 | A2 | Aucune tâche ni réunion à venir |
| D-0050 | A2 | Aucune tâche ni réunion à venir |
| D-0100 | A2 | Aucune tâche ni réunion à venir |
| D-0110 | A2 | Aucune tâche ni réunion à venir |
| D-0007 | A3 | Date de clôture dépassée : 2026-10-27 (il y a 22 j) |
| D-0014 | A3 | Date de clôture dépassée : 2026-11-04 (il y a 14 j) |
| D-0049 | A3 | Date de clôture dépassée : 2026-10-21 (il y a 28 j) |
| D-0071 | A3 | Date de clôture dépassée : 2026-09-24 (il y a 55 j) |
| D-0080 | A3 | Date de clôture dépassée : 2026-10-14 (il y a 35 j) |
| D-0108 | A3 | Date de clôture dépassée : 2026-09-29 (il y a 50 j) |
| D-0028 | A4 | Deal de 45000€ sans activité depuis 23 j |
| D-0046 | A4 | Deal de 50000€ sans activité depuis 43 j |
| D-0059 | A4 | Deal de 25000€ sans activité depuis 42 j |
| D-0098 | A4 | Deal de 35000€ sans activité depuis 31 j |
| D-0034 | A5 | Montant manquant en Négociation |
| D-0077 | A5 | Montant manquant en Négociation |
| D-0102 | A5 | Montant manquant en Proposition envoyée |
| D-0022 | A6 | Clôture en 2026-11 mais étape Qualification |
| D-0038 | A6 | Clôture en 2026-11 mais étape Découverte |
| D-0074 | A6 | Clôture en 2026-11 mais étape Qualification |
| D-0029 | A7 | Deal 35000€ en Négociation avec 1 seul interlocuteur |
| D-0044 | A7 | Deal 34000€ en Négociation avec 1 seul interlocuteur |
| D-0064 | A7 | Deal 51500€ en Négociation avec 1 seul interlocuteur |
| D-0092 | A8 | En Négociation sans réunion de démo dans l'historique |
| D-0103 | A8 | En Négociation sans réunion de démo dans l'historique |
| D-0016 | A9 | Doublon : même entreprise C-0107, noms quasi identiques |
| D-0097 | A9 | Doublon : même entreprise C-0107, noms quasi identiques |

## Leurres (6 ignorer)

| Deal | Code | Preuve |
| --- | --- | --- |
| D-0057 | L1 | Long en Qualification mais RDV calé le 2026-11-28 |
| D-0095 | L2 | Long en Qualification mais RDV calé le 2026-12-07 |
| D-0054 | L3 | Deal 35000€ mais dernière activité il y a 20 j (seuil 21 j) |
| D-0024 | L4 | Deal 25000€ mais dernière activité il y a 20 j (seuil 21 j) |
| D-0083 | L5 | Négociation 1 contact mais montant 15 000€ (seuil A7 = 20 000€) |
| D-0005 | L6 | Date de clôture = as_of (2026-11-18), pas encore dépassée |

## TODOs

- TODO: Vérifier les plages téléphoniques réservées à la fiction par l'Arcep. Actuellement en 01 99 00 XX XX.
- TODO: Phase 2 — import.py vers HubSpot, reset.py, tick.py.
- TODO: Ajouter de la saisonnalité (creux août, pics juin/décembre).
