
import json
import re
import html
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
import feedparser
from bs4 import BeautifulSoup

OUTPUT = Path("actualites_sources.json")

MAX_PAR_FLUX = 15
MAX_CARACTERES = 12000
TIMEOUT = 12

FEEDS = [
    (
        "Location courte durée",
        "https://news.google.com/rss/search?q=location+courte+dur%C3%A9e+Montpellier&hl=fr&gl=FR&ceid=FR:fr"
    ),
    (
        "Réglementation",
        "https://news.google.com/rss/search?q=meubl%C3%A9s+de+tourisme+r%C3%A9glementation&hl=fr&gl=FR&ceid=FR:fr"
    ),
    (
        "Fiscalité",
        "https://news.google.com/rss/search?q=fiscalit%C3%A9+location+saisonni%C3%A8re&hl=fr&gl=FR&ceid=FR:fr"
    ),
    (
        "Marché immobilier",
        "https://news.google.com/rss/search?q=march%C3%A9+immobilier+Montpellier&hl=fr&gl=FR&ceid=FR:fr"
    ),
    (
        "Tourisme",
        "https://news.google.com/rss/search?q=tourisme+Montpellier+H%C3%A9rault&hl=fr&gl=FR&ceid=FR:fr"
    )
]

SOURCES_OFFICIELLES = [
    (
        "Service-Public",
        "https://www.service-public.fr/particuliers/actualites/rss"
    )
]

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (compatible; MC34Blog/3.0; "
        "+https://maconciergerie34.fr/)"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9"
})


def nettoyer(texte):
    if not texte:
        return ""

    texte = html.unescape(str(texte))
    texte = re.sub(r"<[^>]+>", " ", texte)
    texte = re.sub(r"\s+", " ", texte)

    return texte.strip()


def extraire_article(url):
    """
    Récupère uniquement le texte accessible
    publiquement dans la page HTML.

    Ne contourne pas les abonnements,
    protections ou restrictions d'accès.
    """

    try:
        response = SESSION.get(
            url,
            timeout=TIMEOUT,
            allow_redirects=True
        )

        response.raise_for_status()

        type_contenu = response.headers.get(
            "Content-Type", ""
        ).lower()

        if "text/html" not in type_contenu:
            return "", response.url

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        for element in soup([
            "script",
            "style",
            "nav",
            "footer",
            "header",
            "aside",
            "form"
        ]):
            element.decompose()

        conteneur = (
            soup.find("article")
            or soup.find("main")
        )

        if conteneur is None:
            return "", response.url

        paragraphes = []

        for p in conteneur.find_all("p"):
            texte = nettoyer(p.get_text(" ", strip=True))

            if len(texte) >= 60:
                paragraphes.append(texte)

        contenu = "\n\n".join(paragraphes)

        return contenu[:MAX_CARACTERES], response.url

    except requests.RequestException as erreur:
        print(f"Lecture impossible : {erreur}")
        return "", url
    except Exception as erreur:
        print(f"Extraction ignorée : {erreur}")
        return "", url


def collecter_flux(categorie, url):
    actualites = []

    try:
        response = SESSION.get(
            url,
            timeout=20
        )

        response.raise_for_status()

        flux = feedparser.parse(
            response.content
        )

        for entree in flux.entries[:MAX_PAR_FLUX]:

            titre = nettoyer(
                entree.get("title", "")
            )

            lien = entree.get(
                "link", ""
            ).strip()

            if not titre or not lien:
                continue

            resume = nettoyer(
                entree.get("summary", "")
            )

            source = entree.get(
                "source", {}
            )

            if isinstance(source, dict):
                nom_source = source.get(
                    "title", ""
                )
            else:
                nom_source = ""

            contenu, lien_final = extraire_article(
                lien
            )

            if contenu:
                print(
                    f"Contenu récupéré : "
                    f"{titre[:60]}"
                )

            actualites.append({
                "category": categorie,
                "title": titre,
                "source_url": lien,
                "resolved_url": lien_final,
                "source_name": nom_source,
                "published": entree.get(
                    "published", ""
                ),
                "summary": resume,
                "article_text": contenu,
                "content_available": bool(contenu)
            })

            time.sleep(0.2)

    except requests.RequestException as erreur:
        print(
            f"Erreur flux {categorie}: "
            f"{erreur}"
        )

    return actualites


def main():
    actualites = []
    liens_vus = set()

    for categorie, url in FEEDS:
        print(f"Collecte : {categorie}")

        resultats = collecter_flux(
            categorie, url
        )

        for item in resultats:
            lien = item["source_url"]

            if lien in liens_vus:
                continue

            liens_vus.add(lien)
            actualites.append(item)

    resultat = {
        "updated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "sources": actualites
    }

    OUTPUT.write_text(
        json.dumps(
            resultat,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    disponibles = sum(
        1 for item in actualites
        if item["content_available"]
    )

    print(
        f"{len(actualites)} actualités collectées."
    )

    print(
        f"{disponibles} contenus détaillés récupérés."
    )


if __name__ == "__main__":
    main()
