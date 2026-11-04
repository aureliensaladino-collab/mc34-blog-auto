
import json
import re
import html
import time
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
import feedparser
from bs4 import BeautifulSoup

OUTPUT = Path("actualites_sources.json")

MAX_PAR_FLUX = 15
MAX_TEXTE = 9000
TIMEOUT = 15

# Sources officielles et actualités spécialisées.
# Les flux officiels peuvent aussi contenir
# des sujets sans rapport avec l'immobilier.
FEEDS = [
    (
        "Réglementation",
        "https://www.service-public.fr/abonnements/rss/actu-actualites-particuliers.rss",
        "Service-Public"
    ),
    (
        "Réglementation",
        "https://www.service-public.fr/abonnements/rss/actu-actu-pro.rss",
        "Service-Public"
    ),
    (
        "Location courte durée",
        "https://news.google.com/rss/search?q=location+courte+dur%C3%A9e+Montpellier&hl=fr&gl=FR&ceid=FR:fr",
        "Google News"
    ),
    (
        "Réglementation",
        "https://news.google.com/rss/search?q=meubl%C3%A9s+tourisme+r%C3%A9glementation&hl=fr&gl=FR&ceid=FR:fr",
        "Google News"
    ),
    (
        "Fiscalité",
        "https://news.google.com/rss/search?q=fiscalit%C3%A9+location+saisonni%C3%A8re&hl=fr&gl=FR&ceid=FR:fr",
        "Google News"
    ),
    (
        "Marché immobilier",
        "https://news.google.com/rss/search?q=immobilier+Montpellier&hl=fr&gl=FR&ceid=FR:fr",
        "Google News"
    ),
    (
        "Tourisme",
        "https://news.google.com/rss/search?q=tourisme+Montpellier+H%C3%A9rault&hl=fr&gl=FR&ceid=FR:fr",
        "Google News"
    )
]

MOTS_PERTINENTS = [
    "immobilier",
    "logement",
    "location",
    "locatif",
    "meuble",
    "tourisme",
    "touristique",
    "airbnb",
    "proprietaire",
    "copropriete",
    "fiscalite",
    "foncier",
    "taxe de sejour",
    "hebergement",
    "montpellier",
    "herault",
    "residence secondaire",
    "changement d usage"
]

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 MC34Blog/4.0 "
        "(veille documentaire)"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9"
})


def nettoyer(texte):
    if not texte:
        return ""

    soup = BeautifulSoup(
        html.unescape(str(texte)),
        "html.parser"
    )

    return re.sub(
        r"\s+", " ",
        soup.get_text(" ", strip=True)
    ).strip()


def normaliser(texte):
    import unicodedata

    texte = unicodedata.normalize(
        "NFKD",
        nettoyer(texte).lower()
    )

    return "".join(
        c for c in texte
        if not unicodedata.combining(c)
    )


def pertinent(titre, resume):
    texte = normaliser(titre + " " + resume)

    return any(
        mot in texte
        for mot in MOTS_PERTINENTS
    )


def est_google_news(url):
    try:
        domaine = urlparse(url).hostname or ""
        return (
            domaine == "news.google.com"
            or domaine.endswith(".news.google.com")
        )
    except ValueError:
        return False


def extraire_texte(url):
    # Les liens Google News sont des liens
    # intermédiaires. On ne les considère
    # pas comme des pages d'articles.
    if est_google_news(url):
        return "", url

    try:
        response = SESSION.get(
            url,
            timeout=TIMEOUT,
            allow_redirects=True
        )
        response.raise_for_status()

        if "text/html" not in response.headers.get(
            "Content-Type", ""
        ).lower():
            return "", response.url

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        for element in soup([
            "script", "style", "nav",
            "footer", "header", "aside",
            "form", "noscript"
        ]):
            element.decompose()

        # Privilégier la partie éditoriale.
        conteneur = (
            soup.find("article")
            or soup.find("main")
        )

        if not conteneur:
            return "", response.url

        paragraphes = []
        vus = set()

        for p in conteneur.find_all("p"):
            texte = nettoyer(
                p.get_text(" ", strip=True)
            )

            if len(texte) < 70:
                continue

            if texte in vus:
                continue

            vus.add(texte)
            paragraphes.append(texte)

        contenu = "\n\n".join(paragraphes)

        # Éviter de prendre quelques
        # éléments de navigation pour
        # un véritable contenu.
        if len(contenu) < 350:
            return "", response.url

        return contenu[:MAX_TEXTE], response.url

    except requests.RequestException as erreur:
        print(
            "Lecture impossible :",
            str(erreur)[:150]
        )
        return "", url


def collecter_flux(categorie, url, nom_flux):
    resultats = []

    try:
        response = SESSION.get(
            url,
            timeout=20
        )
        response.raise_for_status()

        flux = feedparser.parse(
            response.content
        )

        if not flux.entries:
            print(
                "Flux vide ou inaccessible :",
                nom_flux
            )

        for entree in flux.entries[:MAX_PAR_FLUX]:
            titre = nettoyer(
                entree.get("title", "")
            )
            lien = str(
                entree.get("link", "")
            ).strip()

            resume = nettoyer(
                entree.get("summary", "")
            )

            if not titre or not lien.startswith(
                "https://"
            ):
                continue

            if not pertinent(titre, resume):
                continue

            source = entree.get("source", {})
            source_name = nom_flux

            if isinstance(source, dict):
                source_name = (
                    source.get("title")
                    or nom_flux
                )

            contenu, lien_final = extraire_texte(
                lien
            )

            resultats.append({
                "category": categorie,
                "title": titre,
                "summary": resume[:2000],
                "source_name": source_name,
                "source_url": lien,
                "resolved_url": lien_final,
                "published": entree.get(
                    "published",
                    entree.get("updated", "")
                ),
                "article_text": contenu,
                "content_available": bool(contenu)
            })

            time.sleep(0.1)

    except requests.RequestException as erreur:
        print(
            "Erreur flux",
            nom_flux,
            str(erreur)[:150]
        )

    return resultats


def main():
    actualites = []
    liens_vus = set()

    for categorie, url, nom_flux in FEEDS:
        print("Collecte :", categorie, nom_flux)

        resultats = collecter_flux(
            categorie,
            url,
            nom_flux
        )

        print(
            len(resultats),
            "actualités pertinentes"
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
        bool(item["content_available"])
        for item in actualites
    )

    print(
        f"{len(actualites)} actualités collectées."
    )
    print(
        f"{disponibles} contenus détaillés récupérés."
    )


if __name__ == "__main__":
    main()
