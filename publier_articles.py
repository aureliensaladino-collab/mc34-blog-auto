
import json
import re
import html
import hashlib
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

def nettoyer(valeur):
    if not valeur:
        return ""
    soup = BeautifulSoup(
        html.unescape(str(valeur)), "html.parser"
    )
    return re.sub(
        r"\s+", " ", soup.get_text(" ", strip=True)
    ).strip()

def titre_court(titre):
    titre = nettoyer(titre)
    titre = re.sub(
        r"\s+[-|]\s+(BFM Immo|Le Figaro|Figaro Immobilier|"
        r"Capital|Ouest-France|Franceinfo)$",
        "", titre, flags=re.I
    )
    if len(titre) <= 100:
        return titre

    debut = re.split(r"\s+[:;]\s+", titre)[0]
    if 35 <= len(debut) <= 100:
        return debut

    mots = titre.split()
    resultat = ""
    for mot in mots:
        essai = (resultat + " " + mot).strip()
        if len(essai) > 95:
            break
        resultat = essai

    return resultat.rstrip(" ,;:-") + "…"

def phrases(texte):
    texte = nettoyer(texte)
    return [
        p.strip()
        for p in re.split(
            r"(?<=[.!?])\s+(?=[A-ZÀ-ÖØ-Þ0-9«])",
            texte
        )
        if len(p.strip()) >= 55
    ]

def faits_distincts(texte, maximum=5):
    resultat = []
    vus = set()

    for phrase in phrases(texte):
        if len(phrase) > 350:
            continue

        cle = re.sub(r"\W+", "", phrase.lower())[:90]
        if cle in vus:
            continue

        vus.add(cle)
        resultat.append(phrase)

        if len(resultat) >= maximum:
            break

    return resultat

def identifiant(article):
    base = (
        article.get("resolved_url")
        or article.get("source_url")
        or article.get("title", "")
    )
    return hashlib.sha256(
        str(base).encode("utf-8")
    ).hexdigest()[:16]

def source_article(article):
    return (
        article.get("resolved_url")
        or article.get("source_url")
        or ""
    )

def image_article(categorie):
    return IMAGES.get(
        categorie, IMAGES["Marché immobilier"]
    )

def contenu_article(article):
    titre = nettoyer(article.get("title", ""))
    resume = nettoyer(article.get("summary", ""))
    texte = nettoyer(article.get("article_text", ""))
    categorie = article.get("category", "Actualités")
    source = nettoyer(article.get("source_name", ""))
    url = source_article(article)

    if not source and url:
        source = urlparse(url).hostname or "Source originale"

    disponible = len(texte) >= 350
    sections = []

    if disponible:
        faits = faits_distincts(texte)

        if faits:
            introduction = faits[0][:240]

            sections.append({
                "title": "Les faits essentiels",
                "paragraphs": faits[:3]
            })

            if len(faits) > 3:
                sections.append({
                    "title": "Les autres informations",
                    "paragraphs": faits[3:5]
                })
        else:
            introduction = resume[:240] or titre
            sections.append({
                "title": "Ce que rapporte la source",
                "paragraphs": [introduction]
            })

    else:
        introduction = resume[:240] or titre
        sections.append({
            "title": "Les informations disponibles",
            "paragraphs": [
                resume[:450] if resume else titre,
                "Le texte intégral de la source n'a pas "
                "pu être récupéré automatiquement. "
                "Aucune information supplémentaire "
                "n'est donc présentée comme vérifiée."
            ]
        })

    conseils = {
        "Réglementation": (
            "Vérifier si les mesures évoquées sont "
            "déjà applicables et dans quelles communes."
        ),
        "Fiscalité": (
            "Vérifier l'année fiscale concernée, "
            "le régime applicable et les textes officiels."
        ),
        "Marché immobilier": (
            "Comparer les données avec celles du marché "
            "local avant de prendre une décision."
        ),
        "Tourisme": (
            "Examiner les chiffres de fréquentation "
            "et leur évolution selon les saisons."
        ),
        "Location courte durée": (
            "Examiner les conséquences éventuelles "
            "sur les réservations, les revenus "
            "et la gestion du logement."
        )
    }

    sections.append({
        "title": "Ce qu'il faut vérifier",
        "paragraphs": [
            conseils.get(
                categorie,
                "Consulter la publication originale "
                "avant toute décision."
            )
        ]
    })

    sections.append({
        "title": "Source et références",
        "paragraphs": [
            "Publication : " + (source or "Source originale"),
            "Adresse : " + url,
            "Cette synthèse automatique ne remplace "
            "pas la consultation de l'article original."
        ]
    })

    contenu = "\n\n".join(
        section["title"] + "\n\n"
        + "\n\n".join(section["paragraphs"])
        for section in sections
    )

    return introduction, sections, contenu

def creer_article(candidat):
    categorie = candidat.get("category", "Actualités")
    introduction, sections, contenu = contenu_article(candidat)
    maintenant = datetime.now(timezone.utc).isoformat()

    return {
        "id": identifiant(candidat),
        "title": titre_court(candidat.get("title", "")),
        "category": categorie,
        "date": candidat.get("published") or maintenant,
        "published": candidat.get("published") or maintenant,
        "excerpt": introduction,
        "summary": introduction,
        "description": introduction,
        "image": image_article(categorie),
        "image_url": image_article(categorie),
        "source_name": candidat.get("source_name", ""),
        "source_url": source_article(candidat),
        "sections": sections,
        "content": contenu,
        "body": contenu,
        "status": "published",
        "created_at": maintenant
    }

def lire_json(chemin):
    if not chemin.exists():
        return []
    try:
        donnees = json.loads(
            chemin.read_text(encoding="utf-8")
        )
        if isinstance(donnees, dict):
            donnees = donnees.get("articles", [])
        return donnees if isinstance(donnees, list) else []
    except (OSError, json.JSONDecodeError):
        return []

def main():
    candidats = lire_json(SOURCE)
    anciens = [
        a for a in lire_json(OUTPUT)
        if isinstance(a, dict)
    ]

    par_url = {
        a.get("source_url"): a
        for a in anciens
        if a.get("source_url")
    }

    par_id = {
        str(a.get("id")): a
        for a in anciens
        if a.get("id")
    }

    nouveaux = []
    actualises = 0

    for candidat in candidats:
        if not isinstance(candidat, dict):
            continue

        article = creer_article(candidat)
        url = article["source_url"]

        ancien = (
            par_url.get(url)
            or par_id.get(article["id"])
        )

        if ancien is not None:
            # Préserver les identifiants et les images.
            if candidat.get("content_available") and len(
                nettoyer(candidat.get("article_text", ""))
            ) >= 350:
                ancien_id = ancien.get("id")
                ancienne_image = ancien.get("image")
                ancienne_creation = ancien.get("created_at")

                ancien.update(article)

                if ancien_id:
                    ancien["id"] = ancien_id
                if ancienne_image:
                    ancien["image"] = ancienne_image
                    ancien["image_url"] = ancienne_image
                if ancienne_creation:
                    ancien["created_at"] = ancienne_creation

                actualises += 1

            continue

        if len(nouveaux) >= MAX_NOUVEAUX:
            continue

        nouveaux.append(article)
        par_id[article["id"]] = article
        if url:
            par_url[url] = article

    # Garder les anciens articles, même si leurs
    # sources ne figurent plus parmi les candidats.
    for article in anciens:
        categorie = article.get(
            "category", "Marché immobilier"
        )

        if not article.get("image"):
            article["image"] = image_article(categorie)

        if not article.get("image_url"):
            article["image_url"] = article["image"]

    articles = (nouveaux + anciens)[:MAX_TOTAL]

    OUTPUT.write_text(
        json.dumps(
            articles,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    print(f"{len(nouveaux)} nouveaux articles publiés.")
    print(f"{actualises} anciens articles enrichis.")
    print(f"{len(articles)} articles au total.")

if __name__ == "__main__":
    main()
