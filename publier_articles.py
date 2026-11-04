
import json
import re
import hashlib
import html
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse
from bs4 import BeautifulSoup

SOURCE = Path("articles_candidats.json")
OUTPUT = Path("articles.json")

MAX_NOUVEAUX = 5
MAX_TOTAL = 60

IMAGES = {
    "Réglementation": "https://images.unsplash.com/photo-1560518883-ce09059eeffa?w=1200&q=85",
    "Fiscalité": "https://images.unsplash.com/photo-1554224155-6726b3ff858f?w=1200&q=85",
    "Marché immobilier": "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=1200&q=85",
    "Tourisme": "https://images.unsplash.com/photo-1533105079780-92b9be482077?w=1200&q=85",
    "Location courte durée": "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?w=1200&q=85"
}

IMAGE_DEFAUT = IMAGES["Marché immobilier"]


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


def phrases(texte):
    texte = nettoyer(texte)

    return [
        phrase.strip()
        for phrase in re.split(
            r"(?<=[.!?])\s+(?=[A-ZÀ-ÖØ-Þ0-9])",
            texte
        )
        if len(phrase.strip()) >= 45
    ]


def extraire_faits(texte, maximum=8):
    resultat = []
    vus = set()

    for phrase in phrases(texte):
        cle = phrase.lower()

        if cle in vus:
            continue

        if len(phrase) > 500:
            continue

        vus.add(cle)
        resultat.append(phrase)

        if len(resultat) >= maximum:
            break

    return resultat


def image_article(categorie):
    return IMAGES.get(
        categorie,
        IMAGE_DEFAUT
    )


def identifiant(article):
    base = (
        article.get("resolved_url")
        or article.get("source_url")
        or article.get("title", "")
    )

    return hashlib.sha256(
        base.encode("utf-8")
    ).hexdigest()[:16]


def domaine_source(url):
    try:
        return urlparse(url).hostname or ""
    except ValueError:
        return ""


def construire_contenu(article):
    titre = nettoyer(
        article.get("title", "")
    )

    categorie = article.get(
        "category",
        "Actualités"
    )

    resume = nettoyer(
        article.get("summary", "")
    )

    texte = nettoyer(
        article.get("article_text", "")
    )

    nom_source = nettoyer(
        article.get("source_name", "")
    ) or domaine_source(
        article.get("source_url", "")
    )

    url_source = (
        article.get("resolved_url")
        or article.get("source_url", "")
    )

    # On ne transforme pas un simple titre
    # en affirmation détaillée.
    contenu_disponible = (
        len(texte) >= 350
    )

    faits = extraire_faits(
        texte if contenu_disponible else resume,
        maximum=8
    )

    introduction = (
        f"{titre}. Cette actualité concerne "
        f"le domaine « {categorie.lower()} » "
        "et peut intéresser les propriétaires "
        "de logements à Montpellier et "
        "dans l'Hérault."
    )

    sections = []

    if contenu_disponible and faits:
        sections.append({
            "title": "Les informations à retenir",
            "paragraphs": [
                "Le document consulté présente "
                "notamment les éléments suivants."
            ]
        })

        # Extraits courts, sans reproduction
        # intégrale de l'article source.
        for fait in faits[:5]:
            sections[-1]["paragraphs"].append(
                fait[:280]
            )

    elif resume:
        sections.append({
            "title": "Ce que rapporte la source",
            "paragraphs": [
                resume[:700]
            ]
        })

    else:
        sections.append({
            "title": "Ce que l'on sait",
            "paragraphs": [
                "Le titre de cette actualité "
                "a été repéré dans un flux "
                "d'information. Le contenu "
                "détaillé n'a pas pu être "
                "vérifié automatiquement."
            ]
        })

    sections.append({
        "title": "Pourquoi suivre ce sujet ?",
        "paragraphs": [
            "Pour un propriétaire qui loue "
            "un logement en courte durée, "
            "les évolutions du marché, "
            "du tourisme et des règles "
            "applicables peuvent influencer "
            "la gestion de son bien.",
            "Il est utile de distinguer "
            "les annonces, les projets "
            "et les mesures réellement "
            "entrées en vigueur avant "
            "de prendre une décision."
        ]
    })

    if categorie == "Fiscalité":
        conseil = (
            "Vérifier la période fiscale "
            "concernée, le régime applicable "
            "et les textes officiels avant "
            "toute déclaration."
        )
    elif categorie == "Réglementation":
        conseil = (
            "Consulter les règles en vigueur "
            "et les démarches éventuellement "
            "demandées par la commune "
            "où se situe le logement."
        )
    elif categorie == "Tourisme":
        conseil = (
            "Comparer les tendances annoncées "
            "avec la fréquentation réelle, "
            "les réservations et la saisonnalité."
        )
    elif categorie == "Marché immobilier":
        conseil = (
            "Examiner les données locales "
            "et la période étudiée avant "
            "d'en tirer des conclusions "
            "sur la rentabilité d'un bien."
        )
    else:
        conseil = (
            "Vérifier les règles locales, "
            "les conditions de location "
            "et les informations officielles "
            "avant de modifier ses pratiques."
        )

    sections.append({
        "title": "Ce que les propriétaires peuvent vérifier",
        "paragraphs": [conseil]
    })

    sections.append({
        "title": "Source et vérification",
        "paragraphs": [
            f"Source indiquée : {nom_source}.",
            (
                "Lien vers la publication : "
                + url_source
            ),
            (
                "Cet article est une synthèse "
                "automatisée. Il ne remplace "
                "pas la consultation de "
                "la publication originale."
            )
        ]
    })

    contenu = "\n\n".join(
        section["title"] + "\n\n"
        + "\n\n".join(section["paragraphs"])
        for section in sections
    )

    return introduction, sections, contenu


def creer_article(candidat):
    titre = nettoyer(
        candidat.get("title", "")
    )

    categorie = candidat.get(
        "category",
        "Actualités"
    )

    introduction, sections, contenu = (
        construire_contenu(candidat)
    )

    maintenant = datetime.now(
        timezone.utc
    ).isoformat()

    return {
        "id": identifiant(candidat),
        "title": titre,
        "category": categorie,
        "date": candidat.get("published")
        or maintenant,
        "published": candidat.get("published")
        or maintenant,
        "excerpt": introduction,
        "summary": introduction,
        "description": introduction,
        "image": image_article(categorie),
        "image_url": image_article(categorie),
        "source_name": candidat.get(
            "source_name",
            ""
        ),
        "source_url": candidat.get(
            "resolved_url"
        ) or candidat.get(
            "source_url",
            ""
        ),
        "sections": sections,
        "content": contenu,
        "body": contenu,
        "status": "published",
        "created_at": maintenant
    }


def lire_json(chemin, defaut):
    if not chemin.exists():
        return defaut

    try:
        return json.loads(
            chemin.read_text(
                encoding="utf-8"
            )
        )
    except (
        json.JSONDecodeError,
        OSError
    ):
        return defaut


def main():
    candidats = lire_json(
        SOURCE,
        []
    )

    anciens = lire_json(
        OUTPUT,
        []
    )

    if isinstance(anciens, dict):
        anciens = anciens.get(
            "articles",
            []
        )

    if not isinstance(anciens, list):
        anciens = []

    if not isinstance(candidats, list):
        candidats = []

    # Conserver les anciens articles
    # et réparer les images absentes.
    for article in anciens:
        if not isinstance(article, dict):
            continue

        categorie = article.get(
            "category",
            "Marché immobilier"
        )

        if not article.get("image"):
            article["image"] = image_article(
                categorie
            )

        if not article.get("image_url"):
            article["image_url"] = article["image"]

    ids_existants = {
        str(article.get("id", ""))
        for article in anciens
        if isinstance(article, dict)
    }

    urls_existantes = {
        article.get("source_url", "")
        for article in anciens
        if isinstance(article, dict)
        and article.get("source_url")
    }

    nouveaux = []

    for candidat in candidats:
        if len(nouveaux) >= MAX_NOUVEAUX:
            break

        if not isinstance(candidat, dict):
            continue

        nouvel_article = creer_article(
            candidat
        )

        if nouvel_article["id"] in ids_existants:
            continue

        if (
            nouvel_article["source_url"]
            in urls_existantes
        ):
            continue

        nouveaux.append(nouvel_article)

        ids_existants.add(
            nouvel_article["id"]
        )

        urls_existantes.add(
            nouvel_article["source_url"]
        )

    articles = (
        nouveaux + anciens
    )[:MAX_TOTAL]

    OUTPUT.write_text(
        json.dumps(
            articles,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    print(
        f"{len(nouveaux)} nouveaux articles publiés."
    )

    print(
        f"{len(articles)} articles au total."
    )

    print(
        sum(
            1 for candidat in candidats
            if candidat.get("content_available")
        ),
        "candidats avec contenu détaillé."
    )


if __name__ == "__main__":
    main()
