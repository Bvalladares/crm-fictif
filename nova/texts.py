"""
French text templates for CRM activities.
Commercial style: short, abbreviated, occasional typos.
"""

# Subject templates by activity type
SUBJECTS = {
    "appel": [
        "Appel de suivi",
        "Relance téléphonique",
        "Point rapide",
        "Appel de qualification",
        "Prise de contact",
        "Appel de suivi projet",
        "Relance offre",
        "Appel découverte",
        "Point avancement",
        "Appel bilan",
    ],
    "email": [
        "Envoi proposition commerciale",
        "Suite à notre échange",
        "Relance devis",
        "Envoi documentation",
        "Confirmation RDV",
        "Résumé appel",
        "Envoi contrat pour signature",
        "Mise à jour tarifs",
        "Réponse questions techniques",
        "Suivi demande",
    ],
    "reunion": [
        "Réunion de démo",
        "Présentation solution",
        "RDV découverte",
        "Réunion de négociation",
        "Point projet",
        "Démo plateforme Nova",
        "Réunion bilan",
        "Présentation équipe",
        "RDV technique",
        "Réunion de closing",
    ],
    "note": [
        "Note de suivi",
        "CR appel",
        "Mémo important",
        "Note interne",
        "Observation",
        "Point situation",
        "Résumé échange",
        "Alerte",
        "Info client",
        "Contexte deal",
    ],
    "tache": [
        "Envoyer la proposition",
        "Rappeler le contact",
        "Préparer la démo",
        "Finaliser le contrat",
        "Vérifier les specs",
        "Relancer par email",
        "Contacter le service technique",
        "Préparer les slides",
        "Envoyer le recap",
        "Faire signer",
    ],
}

# Body templates by activity type
BODIES = {
    "appel": [
        "Bon échange, le client est intéressé par la gestion des interventions. Besoin confirmé.",
        "RDV pris pour présenter la solution. Contact disponible la semaine prochaine.",
        "Pas joignable, laisser un msg. Rappeler demain.",
        "Échange rapide, confirme son intérêt. Envoie la docu ce soir.",
        "Client veut voir une démo avant de s'engager. OK pour la semaine prochaine.",
        "Point fait sur les besoins. Equipe de 15 techniciens à gérer. Bon potentiel.",
        "Rappel suite à envoi de la prop. Pas encore lu, à relancer.",
        "Bonne discussion, le DG valide le projet. Reste à arbitrer le budget.",
        "Interlocuteur en congés jusque fin du mois. Rappeler le 2.",
        "Échange technique avec le responsable IT. Intégration ERP possible.",
        "Objection prix. A comparer avec concurrent. Préparer argumentaire.",
        "Client pressé, veut signer avant fin trimestre. Accélérer le process.",
        "Pas de décision avant le prochain CODIR, dans 3 semaines.",
        "Bon feeling, projet bien cadré. Deal assez sûr.",
        "Besoin confirmé, budget validé côté client. Plus qu'à formaliser.",
    ],
    "email": [
        "Bonjour, suite à notre échange, je vous transmets notre proposition commerciale en PJ.",
        "Comme convenu, voici la documentation technique de la plateforme Nova.",
        "Je me permets de revenir vers vous concernant notre offre. Avez-vous eu le temps de l'examiner ?",
        "Ci-joint le contrat pour signature électronique. N'hésitez pas si des questions.",
        "Suite à notre démo de la semaine dernière, voici le résumé et les prochaines étapes.",
        "Je vous confirme notre rendez-vous de démo pour le [date]. Accès en visio joint.",
        "Comme discuté, je vous adresse une version révisée de la proposition avec la remise convenue.",
        "Merci pour votre retour. Je reviens vers vous avec les éléments demandés.",
        "Bonjour, je fais suite à mon appel de ce matin. Voici la doc que vous avez demandée.",
        "Voici le récapitulatif de notre échange et les prochaines étapes. Bonne journée.",
    ],
    "reunion": [
        "Démo réalisée. Client très intéressé par le module planification. Suite : envoyer offre.",
        "Réunion de découverte. 3 participants côté client. Besoin bien cadré.",
        "Présentation complète de la plateforme. Questions sur l'API et l'intégration. RDV suivi fixé.",
        "Négociation avancée. Client demande remise de 10%. On peut aller à 7%.",
        "RDV technique avec DSI. Validation architecture. Go pour la suite.",
        "Réunion de closing, derniers points contractuels réglés. Signature imminente.",
        "Point projet, planning de déploiement validé. Équipe projet constituée.",
        "Présentation à l'équipe direction. Retours positifs. Budget validé.",
        "Démo produit, focus sur le reporting. Impact fort pour le responsable exploitation.",
        "RDV de suivi, deal toujours chaud. Concurrence mentionnée (SFR Business).",
    ],
    "note": [
        "Client en attente d'arbitrage budget. Pas de news avant le CODIR du 15.",
        "Contact principal est en congés jusqu'au 5 janvier, RDV calé au retour.",
        "Attention : concurrent sur le dossier (Synchroteam). Surveiller.",
        "Deal stratégique, à suivre en priorité. Bon potentiel de upsell.",
        "Dossier complexe, plusieurs interlocuteurs. Cartographier les décideurs.",
        "Client a des doutes sur la migration des données. Prévoir PoC.",
        "Budget validé mais signature bloquée par le juriste. Relancer DG.",
        "RDV calé après les vacances. Client très chaud, pas d'urgence.",
        "Interlocuteur change de poste. Identifier le nouveau responsable.",
        "Projet mis en pause (réorg interne). Recontacter dans 2 mois.",
        "Client en congés jusqu'au 5/01, RDV calé. Pas d'inquiétude.",
        "Dossier suivi, échange la semaine dernière, tout va bien.",
        "Bon feeling, client fidèle. Pas de risque de perte.",
        "Note de contexte : le client a changé d'interlocuteur principal.",
        "Suivi OK, prochaine étape clairement définie.",
    ],
    "tache": [
        "Envoyer la proposition révisée avant vendredi.",
        "Rappeler le contact pour confirmer la date de signature.",
        "Préparer la démo personnalisée pour ce client.",
        "Finaliser les clauses du contrat avec le service juridique.",
        "Relancer par email si pas de réponse d'ici lundi.",
        "Préparer le dossier technique pour l'appel d'offres.",
        "Envoyer les références clients demandées.",
        "Contacter le service technique pour validation de l'intégration.",
        "Préparer la présentation pour le CODIR.",
        "Vérifier la faisabilité de la remise demandée.",
    ],
}


def pick_subject(rng, activity_type):
    """Pick a random subject for the given activity type."""
    templates = SUBJECTS.get(activity_type, SUBJECTS["note"])
    return rng.choice(templates)


def pick_body(rng, activity_type):
    """Pick a random body for the given activity type."""
    templates = BODIES.get(activity_type, BODIES["note"])
    return rng.choice(templates)
