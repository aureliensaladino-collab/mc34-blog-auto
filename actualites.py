
import json
import re
import html
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import requests

FEEDS = [
    (
        "Location courte durée",
        "location courte durée Montpellier"
    ),
    (
        "Réglementation",
        "meublés de tourisme réglementation"
    ),
    (
        "Fiscalité",
        "fiscalité location saisonnière"
    ),
    (
        "Marché immobilier",
        "tourisme immobilier Montpellier Hérault"
    ),
    (
        "Conseils propriétaires",
        "location saisonnière propriétaires conseils"
    )
]

OUTPUT = Path("actualites_sources.json")


def nettoyer(texte):
    texte = re.sub(
        r"<[^>]+>", " ", str(texte or "")
    )
    texte = html.unescape(texte)
    return re.sub(r"\s+", " ", texte).strip()


def collecter():
    actualites = []
    liens_vus = set()

    for categorie, recherche in FEEDS:
        try:
            response = requests.get(
                "https://news.google.com/rss/search",
                params={
                    "q": recherche,
                    "hl": "fr",
                    "gl": "FR",
                    "ceid": "FR:fr"
                },
                timeout=20,
                headers={
                    "User-Agent": "Mozilla/5.0"
                }
            )

            response.raise_for_status()
            flux = feedparser.parse(response.content)

            for entree in flux.entries[:15]:
                titre = nettoyer(
                    entree.get("title", "")
                )
                lien = entree.get("link", "")

                if not titre or not lien:
                    continue

                if lien in liens_vus:
                    continue

                liens_vus.add(lien)

                source = entree.get("source", {})
                if not isinstance(source, dict):
                    source = {}

                resume = nettoyer(
                    entree.get("summary", "")
                )

                # Google News peut fournir un
                # résumé contenant seulement
                # des liens et des titres.
                actualites.append({
                    "category": categorie,
                    "title": titre,
                    "summary": resume[:1500],
                    "source_name": nettoyer(
                        source.get("title", "")
                    ),
                    "source_url": lien,
                    "published": entree.get(
                        "published", ""
                    )
                })

        except Exception as erreur:
            print(
                f"Erreur flux {categorie}: {erreur}"
            )

    return actualites


def main():
    donnees = {
        "updated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "sources": collecter()
    }

    OUTPUT.write_text(
        json.dumps(
            donnees,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    print(
        f"{len(donnees['sources'])} actualités collectées."
    )


if __name__ == "__main__":
    main()
