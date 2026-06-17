#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Curation PV — génère une page HTML statique à partir de 4 flux RSS.
- 1 article (le plus récent) par source.
- Affiche le résumé natif du flux S'IL EXISTE ; sinon titre + lien seulement.
- Ne fabrique jamais de résumé manquant.
- Cite obligatoirement : source, date, auteur (si dispo), lien vers l'article.
"""
import html, re, datetime, sys
import feedparser

# --- Sources validées (flux RSS testés) -----------------------------------
SOURCES = [
    {"nom": "L'Écho du Solaire", "url": "https://www.lechodusolaire.fr/feed/"},
    {"nom": "les-energies-renouvelables.eu", "url": "https://www.les-energies-renouvelables.eu/feed/"},
    {"nom": "INES", "url": "https://www.ines-solaire.org/feed/"},
    {"nom": "Enerplan", "url": "https://www.enerplan.asso.fr/feed/"},
]

# Filtre thématique optionnel : True = prend le dernier article contenant
# un mot-clé PV ; False = prend simplement le plus récent (choix par défaut).
THEME_FILTER = False
MOTS_CLES = ["photovolta", "solaire", "autoconsommation", "panneau", "agrivolta", "tarif"]

RESUME_MAX = 280  # caractères max du résumé affiché (teaser)

def texte(t):
    t = re.sub(r"<[^>]+>", " ", t or "")
    t = html.unescape(t)
    return re.sub(r"\s+", " ", t).strip()

def nettoie_resume(e):
    """Retourne un résumé exploitable ou '' (jamais inventé)."""
    brut = texte(getattr(e, "summary", ""))
    # Retire le boilerplate WordPress de fin de flux
    brut = re.sub(r"The post .*? appeared first on .*?\.?$", "", brut).strip()
    if len(brut) < 40:            # trop court / vide => pas de résumé fiable
        return ""
    if len(brut) > RESUME_MAX:    # tronque proprement sur une frontière de mot
        coupe = brut[:RESUME_MAX].rsplit(" ", 1)[0]
        brut = coupe.rstrip(".,;:") + " […]"
    return brut

def date_fr(e):
    st = getattr(e, "published_parsed", None) or getattr(e, "updated_parsed", None)
    if not st:
        return ""
    mois = ["janv.","févr.","mars","avr.","mai","juin","juil.","août","sept.","oct.","nov.","déc."]
    return f"{st.tm_mday} {mois[st.tm_mon-1]} {st.tm_year}"

def choisir_article(entries):
    if not entries:
        return None
    if THEME_FILTER:
        for e in entries:  # entries déjà triées du plus récent au plus ancien
            blob = (getattr(e,"title","") + " " + getattr(e,"summary","")).lower()
            if any(m in blob for m in MOTS_CLES):
                return e
    return entries[0]

def collecte():
    items = []
    for s in SOURCES:
        d = feedparser.parse(s["url"])
        e = choisir_article(d.entries)
        if not e:
            print(f"  ! {s['nom']} : aucune entrée", file=sys.stderr)
            continue
        items.append({
            "source": s["nom"],
            "titre":  texte(getattr(e, "title", "Sans titre")),
            "lien":   getattr(e, "link", "#").split("?utm")[0],
            "date":   date_fr(e),
            "auteur": texte(getattr(e, "author", "")),
            "resume": nettoie_resume(e),
        })
    return items

# --- Gabarit (charte : papier chaud / terracotta / Fraunces+Hanken) --------
def carte(a):
    meta = a["source"]
    if a["date"]:   meta += f" · {a['date']}"
    if a["auteur"]: meta += f" · {a['auteur']}"
    resume_html = f'<p class="resume">{html.escape(a["resume"])}</p>' if a["resume"] else \
                  '<p class="resume vide">Résumé non fourni par la source — consultez l’article original.</p>'
    return f"""      <article class="carte">
        <div class="src">{html.escape(a["source"])}</div>
        <h2><a href="{html.escape(a["lien"])}" target="_blank" rel="noopener nofollow">{html.escape(a["titre"])}</a></h2>
        <div class="meta">{html.escape(meta)}</div>
        {resume_html}
        <a class="lire" href="{html.escape(a["lien"])}" target="_blank" rel="noopener nofollow">Lire l’article complet ↗</a>
      </article>"""

def page(items):
    cartes = "\n".join(carte(a) for a in items)
    maj = datetime.date.today().strftime("%d/%m/%Y")
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Veille photovoltaïque</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Hanken+Grotesk:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root{{
    --papier:#F6F0E6; --papier2:#FBF7F0; --encre:#2C2620;
    --terra:#C0613E; --terra-fonce:#9E4A2C; --trait:#E4D9C8; --gris:#7A7064;
  }}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--papier);color:var(--encre);
    font-family:"Hanken Grotesk",system-ui,sans-serif;line-height:1.55;padding:18px}}
  .entete{{max-width:920px;margin:0 auto 6px}}
  .entete h1{{font-family:"Fraunces",Georgia,serif;font-weight:600;font-size:1.7rem;margin:.2rem 0}}
  .entete .sous{{color:var(--gris);font-size:.9rem;margin:0}}
  .grille{{max-width:920px;margin:18px auto 0;display:grid;gap:16px;
    grid-template-columns:repeat(auto-fill,minmax(280px,1fr))}}
  .carte{{background:var(--papier2);border:1px solid var(--trait);border-radius:14px;
    padding:18px 18px 16px;display:flex;flex-direction:column}}
  .src{{display:inline-block;align-self:flex-start;font-size:.72rem;font-weight:600;
    letter-spacing:.04em;text-transform:uppercase;color:var(--terra-fonce);
    background:rgba(192,97,62,.10);border-radius:20px;padding:3px 10px;margin-bottom:10px}}
  .carte h2{{font-family:"Fraunces",Georgia,serif;font-weight:600;font-size:1.12rem;
    line-height:1.3;margin:0 0 6px}}
  .carte h2 a{{color:var(--encre);text-decoration:none}}
  .carte h2 a:hover{{color:var(--terra-fonce);text-decoration:underline}}
  .meta{{font-size:.78rem;color:var(--gris);margin-bottom:10px}}
  .resume{{font-size:.92rem;margin:0 0 14px}}
  .resume.vide{{font-style:italic;color:var(--gris)}}
  .lire{{margin-top:auto;align-self:flex-start;font-size:.85rem;font-weight:600;
    color:#fff;background:var(--terra);text-decoration:none;border-radius:8px;padding:8px 14px}}
  .lire:hover{{background:var(--terra-fonce)}}
  .pied{{max-width:920px;margin:24px auto 0;font-size:.74rem;color:var(--gris);
    border-top:1px solid var(--trait);padding-top:12px}}
  .pied a{{color:var(--terra-fonce)}}
</style>
</head>
<body>
  <header class="entete">
    <h1>Veille photovoltaïque</h1>
    <p class="sous">Sélection d’articles issus de sources spécialisées — mise à jour le {maj}.</p>
  </header>
  <main class="grille">
{cartes}
  </main>
  <footer class="pied">
    Curation automatique. Les titres, extraits et liens renvoient vers les sites éditeurs,
    seuls détenteurs des droits sur leurs contenus. Aucun article n’est reproduit en intégralité.
    Sources : L’Écho du Solaire, les-energies-renouvelables.eu, INES, Enerplan.
  </footer>
</body>
</html>
"""

if __name__ == "__main__":
    items = collecte()
    out = "veille-pv.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(page(items))
    print(f"OK — {len(items)} articles écrits dans {out}")
