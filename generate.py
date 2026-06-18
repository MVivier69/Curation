#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Veille PV — agrège des flux RSS, conserve un historique glissant et publie
les articles des N derniers jours, groupés par date. Charte Index_Panneau.

Paramètres pilotés par config.json (sources, mots-clés, rétention, filtre…),
avec valeurs par défaut intégrées si le fichier manque ou est invalide.
"""
import json, os, re, html, time, sys, unicodedata, datetime
import requests, feedparser

HIST_FICHIER = "historique.json"
SORTIE_HTML  = "veille-pv.html"
CONFIG       = "config.json"

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124 Safari/537.36"}

# ─── Configuration par défaut (utilisée si config.json absent/invalide) ───
DEFAUT = {
  "retention_jours": 10,
  "theme_filter": True,
  "affichage_max": 150,
  "resume_max": 280,
  "mots_cles": ["photovolta", "panneau", "solaire", "autoconsommation", "batterie",
                "stockage", "onduleur", "agrivolta", "kwc", "tarif de rachat",
                "arrete", "s21", "renouvelable", "transition energetique"],
  "sources": [
    {"nom": "pv magazine France",            "url": "https://www.pv-magazine.fr/feed/"},
    {"nom": "L'Écho du Solaire",             "url": "https://www.lechodusolaire.fr/feed/"},
    {"nom": "PV Tech",                       "url": "https://www.pv-tech.org/feed/"},
    {"nom": "pv magazine",                   "url": "https://www.pv-magazine.com/feed/"},
    {"nom": "INES",                          "url": "https://www.ines-solaire.org/feed/"},
    {"nom": "Enerplan",                      "url": "https://www.enerplan.asso.fr/feed/"},
    {"nom": "les-energies-renouvelables.eu", "url": "https://www.les-energies-renouvelables.eu/feed/"},
    {"nom": "Energy-Storage.news",           "url": "https://www.energy-storage.news/feed/"},
    {"nom": "Révolution Énergétique",        "url": "https://www.revolution-energetique.com/feed/"},
    {"nom": "Connaissance des Énergies",     "url": "https://www.connaissancedesenergies.org/rss.xml"},
    {"nom": "Enerzine",                      "url": "https://www.enerzine.com/feed"},
    {"nom": "Transitions & Énergies",        "url": "https://www.transitionsenergies.com/feed/"},
    {"nom": "L'EnerGeek",                    "url": "https://lenergeek.com/feed/"},
    {"nom": "GreenUnivers",                  "url": "https://www.greenunivers.com/feed/"},
    {"nom": "CLER",                          "url": "https://www.cler.org/feed/"},
    {"nom": "négaWatt",                      "url": "https://negawatt.org/spip.php?page=backend"},
    {"nom": "CleanTechnica",                 "url": "https://cleantechnica.com/feed/"},
    {"nom": "Actu-Environnement",            "url": "https://www.actu-environnement.com/ae/news/archives/rss.php4"},
    {"nom": "Futura Sciences",               "url": "https://www.futura-sciences.com/rss/actualites.xml"},
    {"nom": "Batiactu",                      "url": "https://www.batiactu.com/accueil.rss"},
  ],
}

def charge_config():
    cfg = json.loads(json.dumps(DEFAUT))          # copie profonde
    if os.path.exists(CONFIG):
        try:
            u = json.load(open(CONFIG, encoding="utf-8"))
            for k in DEFAUT:
                if k in u:
                    cfg[k] = u[k]
            print(f"config.json chargé ({len(cfg['sources'])} sources, "
                  f"{len(cfg['mots_cles'])} mots-clés).")
        except Exception as ex:
            print(f"! config.json invalide ({ex}) — valeurs par défaut utilisées.", file=sys.stderr)
    else:
        print("config.json absent — valeurs par défaut utilisées.")
    return cfg

MOIS = ["janv.","févr.","mars","avr.","mai","juin","juil.","août","sept.","oct.","nov.","déc."]
MOIS_LONG = ["janvier","février","mars","avril","mai","juin","juillet","août",
             "septembre","octobre","novembre","décembre"]

def norm(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")

def texte(t):
    t = re.sub(r"<[^>]+>", " ", t or "")
    return re.sub(r"\s+", " ", html.unescape(t)).strip()

def nettoie_resume(e, cfg):
    brut = texte(getattr(e, "summary", ""))
    brut = re.sub(r"The post .*? appeared first on .*?\.?$", "", brut).strip()
    if len(brut) < 40:
        return ""
    if len(brut) > cfg["resume_max"]:
        brut = brut[:cfg["resume_max"]].rsplit(" ", 1)[0].rstrip(".,;:") + " […]"
    return brut

def thematique(titre, resume, cfg):
    if not cfg["theme_filter"]:
        return True
    blob = norm(titre + " " + resume)
    return any(norm(m) in blob for m in cfg["mots_cles"])

def fetch(url, essais=2):
    last = "?"
    for i in range(essais):
        try:
            r = requests.get(url, headers=UA, timeout=25)
            if r.status_code == 200:
                return feedparser.parse(r.content)
            last = f"HTTP {r.status_code}"
        except Exception as ex:
            last = type(ex).__name__
        time.sleep(1.5)
    print(f"  ! flux KO : {url} ({last})", file=sys.stderr)
    return None

def collecte_jour(cfg):
    vus, ok, ko = [], 0, []
    auj = datetime.date.today().isoformat()
    for s in cfg["sources"]:
        d = fetch(s["url"])
        if not d or not getattr(d, "entries", None):
            ko.append(s["nom"]); continue
        ok += 1
        for e in d.entries:
            titre = texte(getattr(e, "title", ""))
            lien  = getattr(e, "link", "").split("?utm")[0].split("#")[0]
            if not titre or not lien:
                continue
            resume = nettoie_resume(e, cfg)
            if not thematique(titre, resume, cfg):
                continue
            st = getattr(e, "published_parsed", None) or getattr(e, "updated_parsed", None)
            vus.append({
                "source": s["nom"], "titre": titre, "lien": lien,
                "auteur": texte(getattr(e, "author", "")), "resume": resume,
                "pub": time.strftime("%Y-%m-%d", st) if st else None,
                "ts": time.mktime(st) if st else None, "vu": auj,
            })
    print(f"Flux interrogés : {len(cfg['sources'])} | OK : {ok} | KO : {len(ko)}"
          + (f" ({', '.join(ko)})" if ko else ""))
    return vus, ok, ko

def charge_hist():
    if os.path.exists(HIST_FICHIER):
        try:
            return json.load(open(HIST_FICHIER, encoding="utf-8"))
        except Exception as ex:
            print(f"! historique.json illisible ({ex}) — réinitialisé.", file=sys.stderr)
    return []

def date_effective(a):
    return a["pub"] or a["vu"]

def fusion_purge(hist, nouveaux, cfg):
    index = {a["lien"]: a for a in hist}
    for a in nouveaux:
        if a["lien"] in index:
            a["vu"] = index[a["lien"]].get("vu", a["vu"])
        index[a["lien"]] = a
    basse = (datetime.date.today() - datetime.timedelta(days=cfg["retention_jours"])).isoformat()
    garde = [a for a in index.values() if date_effective(a) >= basse]   # futurs conservés
    garde.sort(key=lambda a: (a["ts"] or time.mktime(
        datetime.datetime.strptime(a["vu"], "%Y-%m-%d").timetuple())), reverse=True)
    return garde

# ─── Rendu (charte Index_Panneau) ───────────────────────────────────────
SUN = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
       'stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2'
       'M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>')

def jour_label(iso):
    d = datetime.date.fromisoformat(iso); auj = datetime.date.today()
    if d == auj: return "Aujourd’hui"
    if d == auj - datetime.timedelta(days=1): return "Hier"
    return f"{d.day} {MOIS_LONG[d.month-1]} {d.year}"

def carte(a):
    meta = a["source"]
    if a["pub"]:
        d = datetime.date.fromisoformat(a["pub"]); meta += f" · {d.day} {MOIS[d.month-1]} {d.year}"
    if a["auteur"]: meta += f" · {a['auteur']}"
    resume = (f'<p class="resume">{html.escape(a["resume"])}</p>' if a["resume"]
              else '<p class="resume vide">Résumé non fourni par la source — voir l’article original.</p>')
    return f"""        <article class="article">
          <span class="src">{html.escape(a["source"])}</span>
          <h2><a href="{html.escape(a["lien"])}" target="_blank" rel="noopener nofollow">{html.escape(a["titre"])}</a></h2>
          <div class="meta">{html.escape(meta)}</div>
          {resume}
          <a class="lire" href="{html.escape(a["lien"])}" target="_blank" rel="noopener nofollow">Lire l’article complet ↗</a>
        </article>"""

def groupes_html(articles):
    blocs, courant, cle = [], [], None
    for a in articles:
        k = date_effective(a)
        if k != cle:
            if courant: blocs.append((cle, courant)); courant = []
            cle = k
        courant.append(a)
    if courant: blocs.append((cle, courant))
    out = []
    for k, items in blocs:
        cartes = "\n".join(carte(a) for a in items)
        out.append(f'      <h2 class="jour">{jour_label(k)} '
                   f'<span class="jcount">{len(items)} article{"s" if len(items)>1 else ""}</span></h2>\n'
                   f'      <div class="grid">\n{cartes}\n      </div>')
    return "\n".join(out)

def page(articles, cfg):
    maj = datetime.date.today().strftime("%d/%m/%Y")
    nb_sources = len({a["source"] for a in articles})
    corps = groupes_html(articles) if articles else \
            '<p class="lead">Aucun article thématique sur la période.</p>'
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Veille photovoltaïque</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&family=Hanken+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root{{
    --paper:#FBFAF7; --paper-2:#F4F1EA; --ink:#1C1917; --ink-soft:#57534E; --ink-faint:#8A8178;
    --line:#E7E2D8; --line-strong:#D8D1C4; --card:#FFFFFF;
    --accent:#C2410C; --accent-2:#EA8A3E; --accent-soft:#FBEAD9; --accent-ink:#7C2D12;
    --slate:#64748B; --good:#15803D; --bad:#B91C1C;
    --shadow:0 1px 2px rgba(28,25,23,.04), 0 14px 30px -18px rgba(28,25,23,.18);
    --radius:16px;
    --font-display:"Fraunces", Georgia, "Times New Roman", serif;
    --font-body:"Hanken Grotesk", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  }}
  *{{box-sizing:border-box}}
  body{{margin:0;font-family:var(--font-body);color:var(--ink);
    background:
      radial-gradient(1100px 480px at 78% -8%, var(--accent-soft) 0%, transparent 60%),
      linear-gradient(180deg, var(--paper) 0%, var(--paper) 70%, var(--paper-2) 100%);
    background-attachment:fixed;line-height:1.5;font-variant-numeric:tabular-nums}}
  .wrap{{max-width:1120px;margin:0 auto;padding:0 22px 60px}}
  .masthead{{padding:46px 0 24px;border-bottom:1px solid var(--line);margin-bottom:8px}}
  .kicker{{display:flex;align-items:center;gap:12px;margin-bottom:18px;flex-wrap:wrap}}
  .badge{{display:inline-flex;align-items:center;gap:8px;padding:6px 12px;border-radius:999px;
    background:var(--accent-soft);color:var(--accent-ink);border:1px solid #F1D8C2;
    font-size:12.5px;font-weight:600;letter-spacing:.02em}}
  .badge svg{{width:15px;height:15px}}
  .eyebrow{{font-size:12px;font-weight:600;letter-spacing:.22em;text-transform:uppercase;color:var(--ink-faint)}}
  h1{{font-family:var(--font-display);font-weight:500;font-size:clamp(30px,5vw,46px);
    line-height:1.05;letter-spacing:-.015em;margin:0}}
  h1 em{{font-style:italic;color:var(--accent)}}
  .lead{{margin:14px 0 0;max-width:60ch;color:var(--ink-soft);font-size:16px}}
  .jour{{font-family:var(--font-display);font-weight:500;font-size:22px;letter-spacing:-.01em;
    margin:38px 0 14px;display:flex;align-items:baseline;gap:12px}}
  .jour .jcount{{font-family:var(--font-body);font-size:12.5px;font-weight:600;color:var(--ink-faint);
    text-transform:uppercase;letter-spacing:.06em}}
  .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:16px}}
  .article{{position:relative;display:flex;flex-direction:column;background:var(--card);
    border:1px solid var(--line);border-radius:var(--radius);padding:22px 20px 20px;
    box-shadow:var(--shadow);overflow:hidden}}
  .article::before{{content:"";position:absolute;top:0;left:0;right:0;height:3px;background:var(--accent)}}
  .src{{display:inline-flex;align-self:flex-start;align-items:center;padding:5px 11px;border-radius:999px;
    background:var(--accent-soft);color:var(--accent-ink);border:1px solid #F1D8C2;
    font-size:11.5px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;margin-bottom:12px}}
  .article h2{{font-family:var(--font-display);font-weight:500;font-size:18px;line-height:1.25;
    letter-spacing:-.01em;margin:0 0 6px}}
  .article h2 a{{color:var(--ink);text-decoration:none}}
  .article h2 a:hover{{color:var(--accent)}}
  .meta{{font-size:12px;color:var(--ink-faint);margin-bottom:12px}}
  .resume{{font-size:14px;color:var(--ink-soft);margin:0 0 18px}}
  .resume.vide{{font-style:italic;color:var(--ink-faint)}}
  .lire{{margin-top:auto;align-self:flex-start;font-family:var(--font-body);font-size:13px;font-weight:600;
    color:#fff;background:var(--ink);border-radius:11px;padding:9px 16px;text-decoration:none;
    box-shadow:var(--shadow);transition:transform .12s ease, background .2s ease}}
  .lire:hover{{background:#000;transform:translateY(-1px)}}
  .note{{display:flex;gap:14px;margin-top:34px;padding:16px 18px;background:var(--card);
    border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:12px;
    box-shadow:var(--shadow);font-size:13px;color:var(--ink-soft)}}
  .note strong{{color:var(--ink)}}
</style>
</head>
<body>
  <div class="wrap">
    <header class="masthead">
      <div class="kicker">
        <span class="badge">{SUN} Veille quotidienne</span>
        <span class="eyebrow">Photovoltaïque · {cfg['retention_jours']} jours</span>
      </div>
      <h1>Veille <em>photovoltaïque</em></h1>
      <p class="lead">{len(articles)} articles sur les {cfg['retention_jours']} derniers jours,
      issus de {nb_sources} sources — mise à jour le {maj}.</p>
    </header>

{corps}

    <div class="note">
      <div>Curation automatique. Les titres, extraits et liens renvoient vers les sites éditeurs,
      <strong>seuls détenteurs des droits</strong> sur leurs contenus ; aucun article n’est reproduit en intégralité.</div>
    </div>
  </div>
</body>
</html>
"""

if __name__ == "__main__":
    cfg = charge_config()
    hist = charge_hist()
    nouveaux, ok, ko = collecte_jour(cfg)
    articles = fusion_purge(hist, nouveaux, cfg)
    json.dump(articles, open(HIST_FICHIER, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    auj = datetime.date.today().isoformat()
    affiches = [a for a in articles if date_effective(a) <= auj][:cfg["affichage_max"]]
    open(SORTIE_HTML, "w", encoding="utf-8").write(page(affiches, cfg))
    print(f"OK — collectés:{len(nouveaux)} | historique:{len(articles)} | affichés:{len(affiches)}")
