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
| Activités | 3981 |

## Répartition par étape (deals ouverts)

| Étape | Nombre |
| --- | --- |
| decouverte | 14 |
| qualification | 15 |
| demo | 17 |
| proposition | 9 |
| negociation | 15 |

## Répartition par AE

| AE | Ouverts | Gagnés | Perdus |
| --- | --- | --- | --- |
| ae1 | 22 | 38 | 26 |
| ae2 | 15 | 8 | 18 |
| ae3 | 11 | 11 | 16 |
| ae4 | 10 | 5 | 49 |
| ae5 | 12 | 8 | 11 |

## Anomalies plantées (38 signaler)

| Deal | Code | Preuve |
| --- | --- | --- |
| D-0007 | A1 | En Proposition envoyée depuis 61 j (normale 21 j) |
| D-0009 | A1 | En Qualification depuis 55 j (normale 14 j) |
| D-0013 | A1 | En Démo depuis 66 j (normale 21 j) |
| D-0015 | A1 | En Négociation depuis 83 j (normale 30 j) |
| D-0021 | A1 | En Démo depuis 67 j (normale 21 j) |
| D-0024 | A1 | En Qualification depuis 48 j (normale 14 j) |
| D-0066 | A1 | En Négociation depuis 93 j (normale 30 j) |
| D-0068 | A1 | En Découverte depuis 46 j (normale 14 j) |
| D-0007 | A2 | Aucune tâche ni réunion à venir |
| D-0009 | A2 | Aucune tâche ni réunion à venir |
| D-0013 | A2 | Aucune tâche ni réunion à venir |
| D-0015 | A2 | Aucune tâche ni réunion à venir |
| D-0024 | A2 | Aucune tâche ni réunion à venir |
| D-0050 | A2 | Aucune tâche ni réunion à venir |
| D-0051 | A2 | Aucune tâche ni réunion à venir |
| D-0008 | A3 | Date de clôture dépassée : 2026-11-07 (il y a 11 j) |
| D-0041 | A3 | Date de clôture dépassée : 2026-10-08 (il y a 41 j) |
| D-0044 | A3 | Date de clôture dépassée : 2026-09-30 (il y a 49 j) |
| D-0045 | A3 | Date de clôture dépassée : 2026-11-10 (il y a 8 j) |
| D-0064 | A3 | Date de clôture dépassée : 2026-10-31 (il y a 18 j) |
| D-0069 | A3 | Date de clôture dépassée : 2026-10-05 (il y a 44 j) |
| D-0025 | A4 | Deal de 50000€ sans activité depuis 42 j |
| D-0047 | A4 | Deal de 40000€ sans activité depuis 45 j |
| D-0049 | A4 | Deal de 45000€ sans activité depuis 24 j |
| D-0053 | A4 | Deal de 50000€ sans activité depuis 41 j |
| D-0034 | A5 | Montant manquant en Négociation |
| D-0048 | A5 | Montant manquant en Négociation |
| D-0056 | A5 | Montant manquant en Négociation |
| D-0011 | A6 | Clôture en 2026-11 mais étape Découverte |
| D-0020 | A6 | Clôture en 2026-11 mais étape Qualification |
| D-0060 | A6 | Clôture en 2026-11 mais étape Découverte |
| D-0019 | A7 | Deal 25000€ en Négociation avec 1 seul interlocuteur |
| D-0022 | A7 | Deal 30000€ en Négociation avec 1 seul interlocuteur |
| D-0065 | A7 | Deal 25000€ en Négociation avec 1 seul interlocuteur |
| D-0005 | A8 | En Négociation sans réunion de démo dans l'historique |
| D-0028 | A8 | En Négociation sans réunion de démo dans l'historique |
| D-0003 | A9 | Doublon : même entreprise C-0045, noms quasi identiques |
| D-0023 | A9 | Doublon : même entreprise C-0045, noms quasi identiques |

## Leurres (6 ignorer)

| Deal | Code | Preuve |
| --- | --- | --- |
| D-0037 | L1 | Long en Démo mais RDV calé le 2026-11-23 |
| D-0010 | L2 | Long en Découverte mais RDV calé le 2026-11-29 |
| D-0012 | L3 | Deal 30000€ mais dernière activité il y a 20 j (seuil 21 j) |
| D-0004 | L4 | Deal 30000€ mais dernière activité il y a 20 j (seuil 21 j) |
| D-0054 | L5 | Négociation 1 contact mais montant 15 000€ (seuil A7 = 20 000€) |
| D-0042 | L6 | Date de clôture = as_of (2026-11-18), pas encore dépassée |

## TODOs

- TODO: Vérifier les plages téléphoniques réservées à la fiction par l'Arcep. Actuellement en 01 99 00 XX XX.
- TODO: Phase 2 — import.py vers HubSpot, reset.py, tick.py.
- TODO: Ajouter de la saisonnalité (creux août, pics juin/décembre).
