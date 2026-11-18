"""
Fake contact generation for Atelier Nova CRM.
French first names, last names, professional titles.
"""

import re

# French first names (male and female combined)
FIRST_NAMES = [
    "Alexandre", "Alice", "Antoine", "Aurelie", "Baptiste",
    "Benjamin", "Bruno", "Camille", "Caroline", "Catherine",
    "Cedric", "Charlotte", "Christophe", "Claire", "Clement",
    "Coline", "Cyrille", "David", "Delphine", "Denis",
    "Didier", "Dominique", "Edouard", "Elise", "Emilie",
    "Emma", "Eric", "Estelle", "Etienne", "Fabien",
    "Fabrice", "Florence", "Francois", "Frederic", "Gaelle",
    "Guillaume", "Helene", "Hugo", "Isabelle", "Jacques",
    "Jean", "Jerome", "Julien", "Julie", "Kevin",
    "Laetitia", "Laurent", "Lea", "Lionel", "Lucie",
    "Ludovic", "Manon", "Marc", "Marie", "Mathieu",
    "Mathilde", "Maxime", "Michel", "Mohamed", "Nathalie",
    "Nicolas", "Noemie", "Olivier", "Pauline", "Philippe",
    "Pierre", "Raphael", "Remi", "Romain", "Sandrine",
    "Sebastien", "Serge", "Simon", "Sophie", "Stephane",
    "Sylvie", "Thomas", "Thibault", "Valerie", "Vanessa",
    "Victor", "Vincent", "Virginie", "Xavier", "Yann",
    "Yannick", "Zoé", "Adrien", "Agnes", "Alexis",
    "Amelie", "Anaïs", "Arnaud", "Audrey", "Axel",
    "Ayoub", "Bastien", "Benoit", "Bertrand", "Boris",
    "Brice", "Chloé", "Corentin", "Damien", "Daniel",
    "Dylan", "Elsa", "Enora", "Florian", "Franck",
]

LAST_NAMES = [
    "Martin", "Bernard", "Thomas", "Petit", "Robert",
    "Richard", "Durand", "Dubois", "Moreau", "Laurent",
    "Simon", "Michel", "Lefebvre", "Leroy", "Roux",
    "David", "Bertrand", "Morel", "Fournier", "Girard",
    "Bonnet", "Dupont", "Lambert", "Fontaine", "Rousseau",
    "Vincent", "Muller", "Lefevre", "Faure", "Andre",
    "Mercier", "Blanc", "Guerin", "Boyer", "Garnier",
    "Chevalier", "Francois", "Legrand", "Gauthier", "Garcia",
    "Perrin", "Robin", "Clement", "Morin", "Nicolas",
    "Henry", "Roussel", "Mathieu", "Gautier", "Masson",
    "Marchand", "Duval", "Denis", "Dumont", "Marie",
    "Lemaire", "Noel", "Meyer", "Dufour", "Meunier",
    "Brun", "Blanchard", "Giraud", "Joly", "Riviere",
    "Lucas", "Brunet", "Gaillard", "Barbier", "Arnaud",
    "Martinez", "Gerard", "Remy", "Picard", "Rolland",
    "Colin", "Vidal", "Bourgeois", "Renard", "Lemoine",
    "Arnoux", "Aubry", "Carre", "Charpentier", "Collet",
    "Couturier", "Delorme", "Dupuis", "Ferrand", "Fleury",
    "Gosselin", "Hubert", "Lacroix", "Leclercq", "Maillard",
    "Navarro", "Ollivier", "Pasquier", "Pérez", "Renaud",
    "Rousseau", "Schmitt", "Tessier", "Thibault", "Valentin",
    "Vasseur", "Villain", "Wagner", "Willaume", "Zimmermann",
]

# Titles by segment
TITLES_PME = ["DAF", "Directeur technique", "Responsable d'exploitation",
              "Responsable maintenance", "DG", "Acheteur"]
TITLES_STRAT = ["DAF", "Directeur technique", "Responsable d'exploitation",
                "Responsable maintenance", "Acheteur"]


def slugify(name):
    """Convert company name to email slug."""
    s = name.lower()
    # Replace accented chars
    replacements = {
        'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
        'à': 'a', 'â': 'a', 'ä': 'a',
        'î': 'i', 'ï': 'i',
        'ô': 'o', 'ö': 'o',
        'ù': 'u', 'û': 'u', 'ü': 'u',
        'ç': 'c', 'ñ': 'n',
        'œ': 'oe', 'æ': 'ae',
    }
    for k, v in replacements.items():
        s = s.replace(k, v)
    # Keep only alphanumeric and hyphens
    s = re.sub(r'[^a-z0-9]+', '-', s)
    s = s.strip('-')
    return s


def gen_contacts(rng, companies):
    """
    Generate 1-3 contacts per company, targeting ~450 total for 220 companies.
    (220 companies × avg 2.05 = ~450 contacts)
    Returns list of contact dicts.
    Phone is left empty (see summary.md TODO for Arcep ranges).
    """
    contacts = []
    for company in companies:
        # Weights: 1 contact=25%, 2 contacts=50%, 3 contacts=25%
        # 220 companies × avg 2.0 = ~440 contacts (within ±15% of 450)
        n_contacts = rng.choices([1, 2, 3], weights=[25, 50, 25], k=1)[0]
        segment = company["segment"]
        titles = TITLES_PME if segment == "pme" else TITLES_STRAT

        # Pick unique titles for this company
        available_titles = list(titles)
        rng.shuffle(available_titles)
        selected_titles = available_titles[:n_contacts]

        company_slug = slugify(company["name"])

        for title in selected_titles:
            first = rng.choice(FIRST_NAMES)
            last = rng.choice(LAST_NAMES)
            # Normalize for email
            first_slug = slugify(first)
            last_slug = slugify(last)
            email = f"{first_slug}.{last_slug}@{company_slug}.exemple.invalid"
            contacts.append({
                "company_id": company["id"],
                "first_name": first,
                "last_name": last,
                "title": title,
                "email": email,
                "phone": "",
            })

    return contacts
