
import json
import re
import hashlib
import html
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from difflib import SequenceMatcher

SOURCE = Path("articles_candidats.json")
OUTPUT = Path("articles.json")

MAX_ARTICLES = 60
MAX_NOUVEAUX = 5

IMAGES = {
    "Réglementation":
        "https://images.unsplash.com/photo-1589829545856-d10d557cf95f?w=1200",
    "Fiscalité":
        "https://images.unsplash.com/photo-1554224155-6726b3ff858f?w=1200",
    "Marché immobilier":
        "https://images.unsplash.com/photo-1560518883-ce09059eeffa?w=1200",
    "Location courte durée":
        "https://images.unsplash.com/photo-1600607687920-4e2a09cf159d?w=1200",
    "Conseils propriétaires":
        "https://images.unsplash.com/photo-1600566753190-17f0baa2a6c3?w=1200"
}

IMAGE_DEFAUT = (
    "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?w=1200"
)


def lire_json(chemin, defaut):
    try:
        return json.loads(
            chemin.read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return defaut


def nettoyer(texte):
    texte = html.unescape(str(texte or ""))
    texte = re.sub(r"<[^>]+>", " ", texte)
    return re.sub(r"\s+", " ", texte).strip()


def titre_propre(titre):
    titre = nettoyer(titre)
    if " - " in titre:
        titre = titre.rsplit(" - ", 1)[0]
    return titre.strip()


def identifiant(url):
    return hashlib.sha256(
        url.encode("utf-8")
    ).hexdigest()[:16]


def date_publication(valeur):
    try:
        date = parsedate_to_datetime(valeur)
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        return date.strftime("%d/%m/%Y")
    except (TypeError, ValueError, IndexError):
        return ""


def texte_normalise(texte):
    return re.sub(
        r"[^a-z0-9]+", " ",
        nettoyer(texte).lower()
    ).strip()


def resume_exploitable(resume, titre):
    resume = nettoyer(resume)
    titre = nettoyer(titre)

    if not resume or len(resume) < 100:
        return ""

    if SequenceMatcher(
        None,
        texte_normalise(resume),
        texte_normalise(titre)
    ).ratio() > 0.65:
        return ""

    return resume[:650]


def creer_article(item):
    titre = titre_propre(item.get("title", ""))
    lien = item.get("source_url", "")
    categorie = item.get("category", "Actualités")
    media = nettoyer(item.get("source_name", ""))
    date = date_publication(item.get("published", ""))

    if not titre or not lien.startswith("https://"):
        return None

    resume = resume_exploitable(
        item.get("summary", ""),
        titre
    )

    introduction = (
        resume if resume else
        "Cette actualité a été identifiée dans "
        "notre veille consacrée à la location "
        "courte durée et au marché immobilier."
    )

    contenu = [
        {
            "heading": "Ce qu'il faut retenir",
            "text": introduction
        },
        {
            "heading": "Le contexte",
            "text": (
                "Cette publication concerne le thème "
                f"« {categorie} ». Elle fait partie "
                "des sujets suivis par Ma Conciergerie 34 "
                "pour informer les propriétaires de "
                "Montpellier et de l'Hérault."
            )
        },
        {
            "heading": "Ce que les propriétaires peuvent vérifier",
            "text": (
                "Avant d'agir, il est recommandé "
                "de consulter la publication originale, "
                "de vérifier sa date et de déterminer "
                "si les informations concernent "
                "effectivement le logement."
            )
        }
    ]

    if media:
        contenu.append({
            "heading": "La source de l'information",
            "text": (
                f"Cette actualité a été relayée par "
                f"{media}. Le lien vers la publication "
                "d'origine est disponible ci-dessous."
            )
        })

    return {
        "id": identifiant(lien),
        "category": categorie,
        "title": titre,
        "excerpt": (
            resume[:180] if resume else
            "Actualité immobilière et location "
            "courte durée : les informations "
            "à connaître."
        ),
        "date": date,
        "minutes": 2,
        "image": IMAGES.get(
            categorie, IMAGE_DEFAUT
        ),
        "content": contenu,
        "sources": [
            {
                "title": media or "Source originale",
                "url": lien
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

    for item in donnees.get("candidats", []):
        if len(nouveaux) >= MAX_NOUVEAUX:
            break

        article = creer_article(item)

        if not article:
            continue

        if article["id"] in ids:
            continue

        ids.add(article["id"])
        nouveaux.append(article)

    resultat = {
        "updated_at": datetime.now(
            timezone.utc
        ).isoformat(),
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
        f"{len(nouveaux)} nouveaux articles."
    )
    print(
        f"{len(resultat['articles'])} articles au total."
    )


if __name__ == "__main__":
    main()
