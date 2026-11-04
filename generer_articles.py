
import json
import re
import unicodedata
from pathlib import Path
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from difflib import SequenceMatcher

SOURCE = Path("actualites_sources.json")
OUTPUT = Path("articles_candidats.json")

MAX_ARTICLES = 15
AGE_MAX_JOURS = 45

MOTS_IMPORTANTS = {
    "montpellier": 8,
    "herault": 7,
    "location courte duree": 7,
    "meuble de tourisme": 7,
    "location saisonniere": 7,
    "reglementation": 6,
    "fiscalite": 6,
    "airbnb": 6,
    "proprietaire": 5,
    "tourisme": 4,
    "immobilier": 4,
    "logement": 3,
    "location": 3,
    "taxe": 3,
    "copropriete": 3,
    "rentabilite": 3
}

MOTS_EXCLUS = [
    "football",
    "rugby",
    "basket",
    "mercato",
    "accident mortel",
    "fait divers",
    "horoscope",
    "recette de cuisine"
]


def normaliser(texte):
    texte = unicodedata.normalize(
        "NFKD",
        str(texte or "").lower()
    )

    texte = "".join(
        caractere
        for caractere in texte
        if not unicodedata.combining(caractere)
    )

    return re.sub(r"\s+", " ", texte).strip()


def date_publication(valeur):
    if not valeur:
        return None

    try:
        date = parsedate_to_datetime(valeur)
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        return date.astimezone(timezone.utc)
    except (TypeError, ValueError, IndexError):
        pass

    try:
        date = datetime.fromisoformat(
            valeur.replace("Z", "+00:00")
        )
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        return date.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def calculer_score(actualite):
    titre = normaliser(
        actualite.get("title", "")
    )

    resume = normaliser(
        actualite.get("summary", "")
    )

    texte = titre + " " + resume

    if any(mot in titre for mot in MOTS_EXCLUS):
        return -100

    score = 0

    for mot, poids in MOTS_IMPORTANTS.items():
        if mot in titre:
            score += poids
        elif mot in resume:
            score += max(1, poids // 2)

    if actualite.get("content_available"):
        score += 5

    if len(actualite.get("article_text", "")) >= 1000:
        score += 3

    if len(actualite.get("summary", "")) >= 200:
        score += 2

    if actualite.get("source_name") == "Service-Public":
        score += 3

    return score


def est_doublon(titre, titres_existants):
    titre = normaliser(titre)

    for ancien in titres_existants:
        similarite = SequenceMatcher(
            None,
            titre,
            normaliser(ancien)
        ).ratio()

        if similarite >= 0.76:
            return True

    return False


def main():
    if not SOURCE.exists():
        print("Aucune source disponible.")
        OUTPUT.write_text(
            "[]",
            encoding="utf-8"
        )
        return

    donnees = json.loads(
        SOURCE.read_text(encoding="utf-8")
    )

    actualites = donnees.get("sources", [])

    maintenant = datetime.now(timezone.utc)
    limite = maintenant - timedelta(
        days=AGE_MAX_JOURS
    )

    candidats = []

    for actualite in actualites:
        titre = actualite.get("title", "").strip()
        url = actualite.get("source_url", "").strip()

        if not titre or not url:
            continue

        date = date_publication(
            actualite.get("published", "")
        )

        if date and (
            date < limite
            or date > maintenant + timedelta(days=1)
        ):
            continue

        score = calculer_score(actualite)

        if score < 4:
            continue

        candidats.append({
            "title": titre,
            "category": actualite.get(
                "category",
                "Actualités"
            ),
            "summary": actualite.get(
                "summary",
                ""
            ),
            "article_text": actualite.get(
                "article_text",
                ""
            ),
            "content_available": bool(
                actualite.get(
                    "content_available",
                    False
                )
            ),
            "source_name": actualite.get(
                "source_name",
                ""
            ),
            "source_url": url,
            "resolved_url": actualite.get(
                "resolved_url",
                url
            ),
            "published": actualite.get(
                "published",
                ""
            ),
            "importance_score": score,
            "status": "a_verifier"
        })

    candidats.sort(
        key=lambda item: (
            item["importance_score"],
            bool(item["content_available"]),
            item["published"]
        ),
        reverse=True
    )

    selection = []
    titres_vus = []
    liens_vus = set()

    for candidat in candidats:
        if len(selection) >= MAX_ARTICLES:
            break

        if candidat["source_url"] in liens_vus:
            continue

        if est_doublon(
            candidat["title"],
            titres_vus
        ):
            continue

        selection.append(candidat)
        titres_vus.append(
            candidat["title"]
        )
        liens_vus.add(
            candidat["source_url"]
        )

    OUTPUT.write_text(
        json.dumps(
            selection,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    print(
        f"{len(actualites)} actualités analysées."
    )

    print(
        f"{len(selection)} actualités sélectionnées."
    )

    print(
        sum(
            1 for article in selection
            if article["content_available"]
        ),
        "articles sélectionnés avec contenu détaillé."
    )


if __name__ == "__main__":
    main()
