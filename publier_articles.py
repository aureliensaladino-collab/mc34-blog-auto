
import json
import re
import html
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse
from difflib import SequenceMatcher

SOURCE = Path("articles_candidats.json")
ACTUALITES = Path("actualites_sources.json")
OUTPUT = Path("articles.json")

MAX_NOUVEAUX = 5
MAX_TOTAL = 60

IMAGES = {
    "Réglementation": "https://images.unsplash.com/photo-1589829545856-d10d557cf95f?w=1200&q=85",
    "Fiscalité": "https://images.unsplash.com/photo-1554224155-6726b3ff858f?w=1200&q=85",
    "Marché immobilier": "https://images.unsplash.com/photo-1560518883-ce09059eeffa?w=1200&q=85",
    "Tourisme": "https://images.unsplash.com/photo-1488646953014-85cb44e25828?w=1200&q=85",
    "Location courte durée": "https://images.unsplash.com/photo-1600607687920-4e2a09cf159d?w=1200&q=85"
}

def nettoyer(valeur):
    if not valeur:
        return ""
    texte = html.unescape(str(valeur))
    texte = re.sub(r"<[^>]*>", " ", texte)
    return re.sub(r"\s+", " ", texte).strip()

def normaliser(texte):
    return re.sub(
        r"[^a-z0-9]+", " ",
        nettoyer(texte).lower()
    ).strip()

def lire_json(chemin):
    if not chemin.exists():
        return []

    try:
        data = json.loads(
            chemin.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return []

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for cle in ("articles", "sources", "actualites"):
            if isinstance(data.get(cle), list):
                return data[cle]

    return []

def url_source(article):
    return nettoyer(
        article.get("resolved_url")
        or article.get("source_url")
        or ""
    )

def cle_url(article):
    return nettoyer(article.get("source_url", ""))

def titre_court(titre):
    titre = nettoyer(titre)

    titre = re.sub(
        r"\s+[-|]\s+[^-|]{2,45}$",
        "",
        titre
    )

    if len(titre) <= 95:
        return titre

    morceaux = re.split(r"\s*[:;]\s*", titre)
    if 25 <= len(morceaux[0]) <= 95:
        return morceaux[0]

    mots = titre.split()
    resultat = ""

    for mot in mots:
        essai = (resultat + " " + mot).strip()
        if len(essai) > 90:
            break
        resultat = essai

    return resultat.rstrip(" ,;:-") + "…"

def image_article(categorie):
    return IMAGES.get(
        categorie,
        IMAGES["Marché immobilier"]
    )

def identifier(article):
    base = (
        cle_url(article)
        or url_source(article)
        or article.get("title", "")
    )

    return hashlib.sha256(
        str(base).encode("utf-8")
    ).hexdigest()[:16]

def correspondance(a, b):
    ua = cle_url(a)
    ub = cle_url(b)

    if ua and ub and ua == ub:
        return True

    ra = url_source(a)
    rb = url_source(b)

    if ra and rb and ra == rb:
        return True

    ta = normaliser(a.get("title", ""))
    tb = normaliser(b.get("title", ""))

    if len(ta) < 18 or len(tb) < 18:
        return False

    return SequenceMatcher(
        None, ta, tb
    ).ratio() >= 0.92

def recuperer_source(article, sources):
    for source in sources:
        if correspondance(article, source):
            return source

    return None

def decouper_phrases(texte):
    texte = nettoyer(texte)

    return [
        p.strip()
        for p in re.split(
            r"(?<=[.!?])\s+(?=[A-ZÀ-ÖØ-Þ0-9«])",
            texte
        )
        if len(p.strip()) >= 45
    ]

def faits_courts(texte, maximum=4):
    """
    Sélectionne de courts éléments informatifs.
    Ne reproduit pas de longs passages de presse.
    """
    resultat = []
    deja_vus = set()

    for phrase in decouper_phrases(texte):
        if len(phrase) > 190:
            continue

        cle = normaliser(phrase)[:90]

        if cle in deja_vus:
            continue

        deja_vus.add(cle)
        resultat.append(phrase)

        if len(resultat) >= maximum:
            break

    return resultat

def introduction_article(article, source):
    resume = nettoyer(
        source.get("summary", "")
        or article.get("summary", "")
    )

    titre = titre_court(
        source.get("title")
        or article.get("title", "")
    )

    # Évite les anciens résumés automatiques
    # qui ajoutent artificiellement Montpellier.
    marqueurs = [
        "cette actualité concerne le domaine",
        "peut intéresser les propriétaires",
        "le document consulté présente"
    ]

    if any(m in resume.lower() for m in marqueurs):
        resume = ""

    if resume and normaliser(resume) != normaliser(titre):
        return resume[:220]

    return titre

def construire_contenu(article, source):
    texte = nettoyer(source.get("article_text", ""))
    introduction = introduction_article(article, source)

    sections = []

    if len(texte) >= 350:
        faits = faits_courts(texte)

        if faits:
            sections.append({
                "title": "Les faits à retenir",
                "paragraphs": faits[:2]
            })

            if len(faits) > 2:
                sections.append({
                    "title": "Les précisions apportées par la source",
                    "paragraphs": faits[2:]
                })

    if not sections:
        sections.append({
            "title": "Ce que l'on sait",
            "paragraphs": [
                introduction,
                "Les informations détaillées de cette "
                "publication ne sont pas disponibles "
                "dans notre collecte. Consultez la "
                "source originale pour en savoir plus."
            ]
        })

    categorie = article.get(
        "category",
        source.get("category", "Actualités")
    )

    conseils = {
        "Réglementation":
            "Vérifier les textes officiels, leur date "
            "d'application et les règles de la commune concernée.",

        "Fiscalité":
            "Vérifier le régime fiscal applicable, "
            "les dates et les éventuelles exceptions.",

        "Marché immobilier":
            "Comparer les informations avec les "
            "données du marché immobilier local.",

        "Tourisme":
            "Vérifier les chiffres de fréquentation "
            "et leur périmètre géographique.",

        "Location courte durée":
            "Examiner les conséquences éventuelles "
            "pour la gestion et les réservations."
    }

    sections.append({
        "title": "À vérifier avant de prendre une décision",
        "paragraphs": [
            conseils.get(
                categorie,
                "Vérifier les informations dans "
                "la publication originale."
            )
        ]
    })

    return introduction, sections

def creer_article(candidat, sources):
    source = recuperer_source(candidat, sources) or candidat

    categorie = candidat.get(
        "category",
        source.get("category", "Actualités")
    )

    introduction, sections = construire_contenu(
        candidat, source
    )

    maintenant = datetime.now(
        timezone.utc
    ).isoformat()

    url = url_source(source) or url_source(candidat)

    nom_source = (
        source.get("source_name")
        or candidat.get("source_name")
        or urlparse(url).hostname
        or "Source originale"
    )

    titre = titre_court(
        candidat.get("title")
        or source.get("title", "")
    )

    return {
        "id": identifier(candidat),
        "title": titre,
        "category": categorie,
        "date": candidat.get("published") or maintenant,
        "published": candidat.get("published") or maintenant,
        "excerpt": introduction,
        "summary": introduction,
        "description": introduction,
        "image": image_article(categorie),
        "image_url": image_article(categorie),
        "source_name": nom_source,
        "source_url": url,
        "sections": sections,

        # Format attendu par Lodgify V4 :
        # une liste de sections et de paragraphes.
        "content": sections,

        "sources": [
            {
                "title": nom_source,
                "url": url
            }
        ] if url.startswith(("https://", "http://")) else [],

        "status": "published",
        "created_at": maintenant,
        "content_available": len(
            nettoyer(source.get("article_text", ""))
        ) >= 350
    }

def conserver_article(ancien, nouveau):
    ancien_id = ancien.get("id")
    ancienne_image = ancien.get("image")
    ancienne_creation = ancien.get("created_at")

    ancien.update(nouveau)

    if ancien_id:
        ancien["id"] = ancien_id

    if ancienne_image:
        ancien["image"] = ancienne_image
        ancien["image_url"] = ancienne_image

    if ancienne_creation:
        ancien["created_at"] = ancienne_creation

def enrichir_anciens(anciens, sources):
    nombre = 0

    for ancien in anciens:
        source = recuperer_source(ancien, sources)

        if source is None:
            continue

        if len(nettoyer(
            source.get("article_text", "")
        )) < 350:
            continue

        nouveau = creer_article(ancien, sources)
        conserver_article(ancien, nouveau)
        nombre += 1

    return nombre

def main():
    candidats = [
        a for a in lire_json(SOURCE)
        if isinstance(a, dict)
    ]

    sources = [
        a for a in lire_json(ACTUALITES)
        if isinstance(a, dict)
    ]

    anciens = [
        a for a in lire_json(OUTPUT)
        if isinstance(a, dict)
    ]

    print(f"{len(candidats)} candidats disponibles.")
    print(f"{len(sources)} sources collectées.")
    print(f"{len(anciens)} anciens articles conservés.")

    actualises = enrichir_anciens(anciens, sources)

    nouveaux = []

    for candidat in candidats:
        if len(nouveaux) >= MAX_NOUVEAUX:
            break

        deja_present = any(
            correspondance(candidat, ancien)
            for ancien in anciens + nouveaux
        )

        if deja_present:
            continue

        article = creer_article(candidat, sources)

        if not article["title"]:
            continue

        nouveaux.append(article)

    # Corrige aussi les anciens contenus déjà
    # structurés, sans supprimer leur texte.
    for ancien in anciens:
        if not ancien.get("image"):
            ancien["image"] = image_article(
                ancien.get("category", "")
            )

        if not ancien.get("image_url"):
            ancien["image_url"] = ancien["image"]

        contenu = ancien.get("content")

        if isinstance(contenu, str):
            sections = ancien.get("sections")

            if isinstance(sections, list) and sections:
                ancien["content"] = sections

            elif contenu.strip():
                ancien["content"] = [{
                    "title": "L'article",
                    "paragraphs": [
                        p.strip()
                        for p in contenu.split("\n\n")
                        if p.strip()
                    ]
                }]

        if not ancien.get("sources"):
            url = ancien.get("source_url", "")

            if url.startswith(("https://", "http://")):
                ancien["sources"] = [{
                    "title": ancien.get(
                        "source_name", "Source originale"
                    ),
                    "url": url
                }]

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
    print("Publication terminée.")

if __name__ == "__main__":
    main()
