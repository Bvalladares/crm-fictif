# BRIEF — `tick.py` : faire vivre le CRM semaine après semaine

Le CRM Atelier Nova est figé à `--as-of 2026-11-18`. Pour tester la revue sur plusieurs semaines consécutives
(critère : 3 revues de suite qui passent l'évaluation), le CRM doit évoluer comme un vrai pipe.

Contraintes inchangées : Python 3, bibliothèque standard uniquement, aucun appel réseau, unittest,
corriger seul jusqu'au vert, commit à la fin (ne pas pousser). Lire d'abord BRIEF.md et BRIEF-AGENT.md.

## Usage

```
python3 tick.py --seed 42            # avance d'une semaine : as_of + 7 jours
python3 tick.py --seed 42 --weeks 3  # avance de 3 semaines, une par une
```

- Lit `out/crm.json` et `out/truth.csv`, écrit les nouvelles versions au même endroit.
- Archive l'état précédent dans `out/history/<as_of>/` (crm.json, truth.csv, facts.json si présent).
- Déterministe : même graine + même état de départ = même résultat. La graine de la semaine = seed + numéro de semaine.

## Ce qui se passe pendant une semaine simulée

Chaque événement est daté entre l'ancien et le nouveau `as_of`, et respecte les profils d'AE de BRIEF.md
(ae1 star, ae4 en difficulté, ae5 logue peu).

| Événement | Volume indicatif par semaine |
|---|---|
| Nouveaux deals en Découverte (créés par les SDR) | 4 à 7 |
| Deals qui avancent d'une étape | 8 à 12 |
| Deals gagnés (depuis Négociation) | 1 à 3 |
| Deals perdus (avec motif) | 2 à 4 |
| Nouvelles activités, cohérentes avec l'étape (mêmes règles que le générateur) | 60 à 100 |
| Tâches et réunions futures créées (prochaines étapes) | 10 à 20 |

## Les anomalies évoluent comme dans la réalité

- **Certaines se résolvent** : environ 30 % des anomalies ouvertes sont corrigées chaque semaine (une tâche est planifiée, le montant est saisi, la date de clôture est mise à jour, le deal avance ou est perdu).
- **D'autres apparaissent naturellement** du simple passage du temps : un deal sans activité franchit le seuil des 21 jours, une date de clôture devient dépassée.
- **De nouvelles sont plantées** : 3 à 6 par semaine, réparties sur les 9 codes, pour garder un volume stable (entre 25 et 45 lignes « signaler »).
- **Les leurres** : à chaque semaine, retirer les leurres devenus obsolètes et en planter de nouveaux pour toujours en avoir 6, construits comme dans BRIEF.md (même règles, dates cohérentes avec le nouvel as_of).
- **La vérité terrain est recalculée** à chaque semaine : `truth.csv` doit correspondre exactement à `rules.py` appliqué au nouveau CRM, comme pour la génération initiale (aucune anomalie accidentelle non listée).

## Journal de la semaine

Écrire `out/history/<nouvel_as_of>/changes.md` : deals créés, avancés, gagnés, perdus ; anomalies résolues, apparues, plantées.
Sert à vérifier à l'œil et à nourrir les posts de build in public (« cette semaine, 4 problèmes réglés, 3 nouveaux »).

## Tests

1. Après 1 tick et après 3 ticks : `rules.py` sur `crm.json` retrouve exactement les lignes « signaler » de `truth.csv`, aucun leurre signalé.
2. Cohérence temporelle : aucune activité datée après le nouvel as_of sauf tâches et réunions futures ; aucune activité après la close_date d'un deal clos (hors note de clôture) ; stage_history croissant.
3. Les deals clos ne bougent plus.
4. Volumes dans les fourchettes du tableau ; nombre de lignes « signaler » entre 25 et 45 ; exactement 6 leurres.
5. Reproductibilité : deux exécutions depuis le même état donnent des fichiers identiques.
6. La chaîne complète passe après chaque tick : `review.facts`, `review.render_raw`, `review.evaluate` avec pass = true.
7. Tous les tests existants restent verts.

## Rendu

Compte rendu court, extrait du `changes.md` de la première semaine simulée, score de la revue brute après 1 et 3 ticks, commit (sans push).
