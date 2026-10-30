
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

SOURCE = Path("actualites_sources.json")
OUTPUT = Path("articles_candidats.json")

MOTS_IMPORTANTS = {
    "réglementation": 5,
    "loi": 4,
    "décret": 4,
    "interdiction": 5,
    "autorisation": 4,
    "changement d'usage": 5,
    "fiscalité": 5,
    "impôt": 4,
    "taxe": 4,
    "airbnb": 2,
    "meublé de tourisme": 4,
    "location saisonnière": 3,
    "montpellier": 4,
    "hérault": 3,
}

def normaliser(texte):
    return re.sub(r"\s+", " ", texte.lower()).strip()

def calculer_score(titre):
    texte = normaliser(titre)
    return sum(
        points
        for mot, points in MOTS_IMPORTANTS.items()
        if mot in texte
    )

def main():
    if not SOURCE.exists():
        raise FileNotFoundError(
            "Le fichier actualites_sources.json est absent."
        )

    donnees = json.loads(
        SOURCE.read_text(encoding="utf-8")
    )

    candidats = []
    deja_vus = set()

    for item in donnees.get("sources", []):
        titre = item.get("title", "").strip()
        lien = item.get("source_url", "").strip()

        if not titre or not lien:
            continue

        cle = normaliser(titre)
        if cle in deja_vus:
            continue

        deja_vus.add(cle)
        score = calculer_score(titre)

        if score < 7:
            continue

        candidats.append({
            "title": titre,
            "category": item.get("category", ""),
            "source_url": lien,
            "published": item.get("published", ""),
            "importance_score": score,
            "status": "a_verifier"
        })

    candidats.sort(
        key=lambda x: x["importance_score"],
        reverse=True
    )

    resultat = {
        "updated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "candidats": candidats[:15]
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
        f"{len(resultat['candidats'])} "
        "actualités candidates détectées."
    )

if __name__ == "__main__":
    main()
