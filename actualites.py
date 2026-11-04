
import json
import re
import html
import time
import unicodedata
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
import feedparser
from bs4 import BeautifulSoup

OUTPUT = Path("actualites_sources.json")
TIMEOUT = 12
MAX_PAR_FLUX = 12
MAX_TEXTE = 9000

# Flux directs : les liens pointent vers les éditeurs.
# Flux Google News : utiles pour repérer les sujets,
# mais ne donnent pas directement les articles.
FEEDS = [
    (
        "Marché immobilier",
        "https://www.bfmtv.com/rss/immobilier/",
        "BFM Immo",
        True
    ),
    (
        "Marché immobilier",
        "https://www.franceinfo.fr/economie/immobilier.rss",
        "Franceinfo",
        True
    ),
    (
        "Marché immobilier",
        "https://actualites.logic-immo.com/actus-rss.xml",
        "Logic-Immo",
        True
    ),
    (
        "Location courte durée",
        "https://news.google.com/rss/search?q=location+courte+dur%C3%A9e+Montpellier&hl=fr&gl=FR&ceid=FR:fr",
        "Google News",
        False
    ),
    (
        "Réglementation",
        "https://news.google.com/rss/search?q=meubl%C3%A9s+tourisme+r%C3%A9glementation&hl=fr&gl=FR&ceid=FR:fr",
        "Google News",
        False
    ),
    (
        "Fiscalité",
        "https://news.google.com/rss/search?q=fiscalit%C3%A9+location+saisonni%C3%A8re&hl=fr&gl=FR&ceid=FR:fr",
        "Google News",
        False
    ),
    (
        "Tourisme",
        "https://news.google.com/rss/search?q=tourisme+Montpellier+H%C3%A9rault&hl=fr&gl=FR&ceid=FR:fr",
        "Google News",
        False
    )
]

MOTS_CLES = [
    "immobilier", "logement", "location",
    "locatif", "meuble", "tourisme",
    "touristique", "airbnb", "proprietaire",
    "copropriete", "fiscalite", "foncier",
    "hebergement", "montpellier", "herault",
    "loyer", "habitation", "residence",
    "investissement", "taxe", "dpe"
]

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; MC34Blog/5.0)",
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
        r"\s+",
        " ",
        soup.get_text(" ", strip=True)
    ).strip()


def normaliser(texte):
    texte = unicodedata.normalize(
        "NFKD",
        nettoyer(texte).lower()
    )

    return "".join(
        c for c in texte
        if not unicodedata.combining(c)
    )


def est_pertinent(titre, resume):
    contenu = normaliser(titre + " " + resume)

    return any(
        mot in contenu
        for mot in MOTS_CLES
    )


def est_lien_direct(url):
    try:
        domaine = urlparse(url).hostname or ""

        return not (
            domaine == "news.google.com"
            or domaine.endswith(".news.google.com")
        )
    except ValueError:
        return False


def extraire_article(url):
    if not est_lien_direct(url):
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

        conteneur = (
            soup.find("article")
            or soup.find("main")
        )

        if conteneur is None:
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

        if len(contenu) < 350:
            return "", response.url

        return contenu[:MAX_TEXTE], response.url

    except requests.RequestException as erreur:
        print(
            "Page inaccessible :",
            str(erreur)[:120]
        )
        return "", url


def collecter_flux(categorie, url, nom, direct):
    actualites = []

    try:
        response = SESSION.get(
            url,
            timeout=20
        )
        response.raise_for_status()

        flux = feedparser.parse(response.content)

        if not flux.entries:
            print("Flux vide :", nom)

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

            if not titre:
                continue

            if not lien.startswith(
                ("https://", "http://")
            ):
                continue

            if not est_pertinent(titre, resume):
                continue

            contenu = ""
            lien_final = lien

            if direct:
                contenu, lien_final = extraire_article(
                    lien
                )

            source = entree.get("source", {})
            nom_source = nom

            if isinstance(source, dict):
                nom_source = (
                    source.get("title") or nom
                )

            actualites.append({
                "category": categorie,
                "title": titre,
                "source_url": lien,
                "resolved_url": lien_final,
                "source_name": nom_source,
                "published": entree.get(
                    "published",
                    entree.get("updated", "")
                ),
                "summary": resume[:2000],
                "article_text": contenu,
                "content_available": bool(contenu)
            })

            if contenu:
                print(
                    "Contenu détaillé obtenu :",
                    titre[:70]
                )

            time.sleep(0.1)

    except requests.RequestException as erreur:
        print(
            "Erreur de flux :",
            nom,
            str(erreur)[:120]
        )

    return actualites


def main():
    actualites = []
    liens_vus = set()

    for categorie, url, nom, direct in FEEDS:
        print("Collecte :", nom, categorie)

        resultats = collecter_flux(
            categorie,
            url,
            nom,
            direct
        )

        print(
            len(resultats),
            "actualités pertinentes"
        )

        for item in resultats:
            lien = item["resolved_url"]

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
