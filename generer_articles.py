
import json
import re
import unicodedata
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from difflib import SequenceMatcher

SOURCE = Path("actualites_sources.json")
OUTPUT = Path("articles_candidats.json")

MAX_CANDIDATS = 15
AGE_MAX_JOURS = 45

MOTS_IMPORTANTS = {
    "montpellier": 5,
    "herault": 4,
    "location courte duree": 5,
    "location saisonniere": 5,
    "meuble de tourisme": 5,
    "airbnb": 3,
    "reglementation": 5,
    "fiscalite": 5,
    "loi": 3,
    "decret": 4,
    "autorisation": 5,
    "changement d usage": 5,
    "taxe de sejour": 5,
    "copropriete": 4,
    "tourisme": 2,
    "proprietaire": 2,
    "rentabilite": 3,
    "interdiction": 4,
}

def normaliser(texte):
    texte = unicodedata.normalize(
        "NFKD", str(texte or "").lower()
    )
    texte = "".join(
        c for c in texte
        if not unicodedata.combining(c)
    )
    texte = re.sub(r"[^a-z0-9]+", " ", texte)
    return re.sub(r"\s+", " ", texte).strip()


def calculer_score(titre, categorie):
    texte = normaliser(titre)
    score = sum(
        points
        for mot, points in MOTS_IMPORTANTS.items()
        if normaliser(mot) in texte
    )

    if "montpellier" in texte:
        score += 3

    return score


def date_valide(valeur):
    try:
        date = parsedate_to_datetime(valeur)
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        return date.astimezone(timezone.utc)
    except (TypeError, ValueError, IndexError):
        return None


def est_doublon(titre, candidats):
    titre_normalise = normaliser(titre)

    for candidat in candidats:
        autre = normaliser(candidat["title"])

        similarite = SequenceMatcher(
            None, titre_normalise, autre
        ).ratio()

        if similarite >= 0.76:
            return True

    return False


def main():
    if not SOURCE.exists():
        raise FileNotFoundError(
            "actualites_sources.json introuvable"
        )

    donnees = json.loads(
        SOURCE.read_text(encoding="utf-8")
    )

    maintenant = datetime.now(timezone.utc)
    limite = maintenant - timedelta(
        days=AGE_MAX_JOURS
    )

    selection = []
    liens_vus = set()

    for item in donnees.get("sources", []):
        titre = item.get("title", "").strip()
        lien = item.get("source_url", "").strip()
        categorie = item.get("category", "")
        publication = item.get("published", "")

        if not titre or not lien.startswith("https://"):
            continue

        if lien in liens_vus:
            continue

        date = date_valide(publication)

        if date is None or date < limite:
            continue

        if date > maintenant + timedelta(days=1):
            continue

        score = calculer_score(
            titre, categorie
        )

        if score < 7:
            continue

        liens_vus.add(lien)

        selection.append({
            "title": titre,
            "category": categorie,
            "summary": item.get("summary", ""),
            "source_name": item.get(
                "source_name", ""
            ),
            "source_url": lien,
            "published": publication,
            "importance_score": score,
            "status": "a_verifier"
        })

    selection.sort(
        key=lambda x: x["importance_score"],
        reverse=True
    )

    candidats = []

    for item in selection:
        if est_doublon(item["title"], candidats):
            continue

        candidats.append(item)

        if len(candidats) >= MAX_CANDIDATS:
            break

    resultat = {
        "updated_at": maintenant.isoformat(),
        "candidats": candidats
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
        f"{len(candidats)} actualités sélectionnées."
    )


if __name__ == "__main__":
    main()
