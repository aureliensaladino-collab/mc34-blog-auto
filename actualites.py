
import json
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import requests

# Flux RSS de recherche d'actualités
FEEDS = [
    (
        "Location courte durée",
        "https://news.google.com/rss/search?q="
        "location+courte+dur%C3%A9e+Montpellier"
        "&hl=fr&gl=FR&ceid=FR:fr"
    ),
    (
        "Réglementation",
        "https://news.google.com/rss/search?q="
        "meubl%C3%A9s+de+tourisme+r%C3%A9glementation"
        "&hl=fr&gl=FR&ceid=FR:fr"
    ),
    (
        "Fiscalité",
        "https://news.google.com/rss/search?q="
        "fiscalit%C3%A9+location+saisonni%C3%A8re"
        "&hl=fr&gl=FR&ceid=FR:fr"
    )
]

OUTPUT = Path("actualites_sources.json")


def collecter():
    actualites = []
    liens_vus = set()

    for categorie, url in FEEDS:
        try:
            response = requests.get(
                url,
                timeout=20,
                headers={
                    "User-Agent": "MC34Blog/1.0"
                }
            )
            response.raise_for_status()

            flux = feedparser.parse(response.content)

            for entree in flux.entries[:10]:
                titre = entree.get("title", "").strip()
                lien = entree.get("link", "").strip()

                if not titre or not lien:
                    continue

                if lien in liens_vus:
                    continue

                liens_vus.add(lien)

                actualites.append({
                    "category": categorie,
                    "title": titre,
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
        f"{len(donnees['sources'])} "
        "actualités collectées."
    )


if __name__ == "__main__":
    main()
