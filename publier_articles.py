
import json
import re
import hashlib
from datetime import datetime, timezone
from pathlib import Path

SOURCE = Path("articles_candidats.json")
OUTPUT = Path("articles.json")

MAX_ARTICLES = 60


def lire_json(chemin, defaut):
    if not chemin.exists():
        return defaut

    try:
        return json.loads(
            chemin.read_text(encoding="utf-8")
        )
    except (ValueError, OSError):
        return defaut


def creer_id(url):
    return hashlib.sha256(
        url.encode("utf-8")
    ).hexdigest()[:16]


def nettoyer_titre(titre):
    titre = re.sub(r"\s+", " ", titre).strip()

    # Certains flux ajoutent le nom du média
    if " - " in titre:
        titre = titre.rsplit(" - ", 1)[0].strip()

    return titre


def creer_article(candidat):
    titre = nettoyer_titre(
        candidat.get("title", "")
    )
    url = candidat.get("source_url", "")
    categorie = candidat.get(
        "category", "Actualités"
    )

    if not titre or not url.startswith("https://"):
        return None

    identifiant = creer_id(url)

    return {
        "id": identifiant,
        "category": categorie,
        "title": titre,
        "excerpt": (
            "Une actualité à suivre pour les "
            "propriétaires et professionnels "
            "de la location courte durée."
        ),
        "date": datetime.now(
            timezone.utc
        ).strftime("%d/%m/%Y"),
        "minutes": 2,
        "image": "",
        "content": [
            {
                "heading": "L'actualité",
                "text": (
                    "Cette information a été repérée "
                    "dans notre veille immobilière. "
                    "Le titre et la source sont "
                    "présentés à titre informatif."
                )
            },
            {
                "heading": "Pourquoi suivre ce sujet ?",
                "text": (
                    "Les évolutions du marché, "
                    "de la fiscalité et de la "
                    "réglementation peuvent "
                    "concerner les propriétaires "
                    "de locations saisonnières."
                )
            },
            {
                "heading": "À vérifier",
                "text": (
                    "Consultez la publication "
                    "d'origine et les sources "
                    "officielles avant de prendre "
                    "une décision concernant "
                    "votre logement."
                )
            }
        ],
        "sources": [
            {
                "title": "Consulter l'actualité d'origine",
                "url": url
            }
        ]
    }


def main():
    donnees = lire_json(
        SOURCE, {"candidats": []}
    )
    existant = lire_json(
        OUTPUT, {"articles": []}
    )

    articles = existant.get("articles", [])
    if not isinstance(articles, list):
        articles = []

    ids = {
        a.get("id")
        for a in articles
        if isinstance(a, dict)
    }

    nouveaux = []

    for candidat in donnees.get("candidats", []):
        if candidat.get("status") != "a_verifier":
            continue

        article = creer_article(candidat)

        if not article:
            continue

        if article["id"] in ids:
            continue

        ids.add(article["id"])
        nouveaux.append(article)

    resultat = {
        "articles": (
            nouveaux + articles
        )[:MAX_ARTICLES]
    }

    OUTPUT.write_text(
        json.dumps(
            resultat,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    print(
        f"{len(nouveaux)} nouveaux articles créés."
    )
    print(
        f"{len(resultat['articles'])} articles au total."
    )


if __name__ == "__main__":
    main()
