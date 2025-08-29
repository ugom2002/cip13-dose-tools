# data
```markdown
# cip13-dose-tools

Outils pour **normaliser les présentations CIP13** à partir du fichier public **CIP/UCD** (ANSM / e-santé).  
Le pipeline extrait, quand c’est possible :

- `nb_unites_par_boite` (ex. 14 comprimés)  
- `forme` (comprimé, gélule, solution, injection, etc.)  
- `dose_par_unite_mg` (convertie en **mg** si l’unité le permet)  
- `dose_totale_boite_mg` (mono-molécule uniquement)  
- `conc_mg_per_ml` et `unit_volume_ml` (pour les formes liquides)  
- Détection des **combinaisons** (ex. “80 mg / 12,5 mg”) + table **explosée par composant**  

Sorties **Parquet-first** (CSV en fallback si `pyarrow` indisponible).

---

## 📦 Données d’entrée

- **Source officielle** : https://smt.esante.gouv.fr/terminologie-cip_ucd/  
  > Sur le portail, récupérez la **Terminologie CIP/UCD**. Dans l’archive téléchargée, le fichier cible se trouve généralement sous **`dat/`** et s’appelle **`CIP_UCD.csv`** (encodage **UTF-16**, séparateur `;`, avec une ou deux lignes de titre avant l’en-tête).

- **Confidentialité** : ne commitez **aucune** donnée SNDS dans ce dépôt.

Par convention, placez le fichier ici :
```

data/CIP\_UCD.csv

````

---

## 🚀 Installation

```bash
# Python >= 3.10 recommandé
python -m venv .venv
source .venv/bin/activate      # Windows: .\.venv\Scripts\activate
python -m pip install -U pip

# Installer le package en mode dev
pip install -e .

# Outils dev (optionnel)
pip install -U ruff black pytest pre-commit
pre-commit install
````

---

## ✨ Utilisation

### 1) Ligne de commande (CLI)

```bash
# Exemple si le fichier est dans ./data/
cipdose --cipucd "data/CIP_UCD.csv" --outdir "./out"
```

**Sorties :**

* `out/cip13_norm.parquet`  → 1 ligne **par CIP13**
* `out/cip13_components.parquet` → 1 ligne **par composant** (utile pour les combinaisons)

> Si `pyarrow`/`fastparquet` n’est pas installé, le script écrit `cip13_norm.csv` et `cip13_components.csv`.

**Windows PowerShell :**

```powershell
cipdose --cipucd "C:\chemin\CIP_UCD.csv" --outdir "C:\chemin\out"
```

### 2) API Python

```python
from cipdose.normalize import homogenize_cip13

norm_df, comp_df = homogenize_cip13("data/CIP_UCD.csv", outdir="out")
print(norm_df.head())
print(comp_df.head())
```

---

## 🧠 Logique & règles de parsing

* **Identifiants** : `CIP13`, `CIP7`, `UCD13`, `UCD7` sont **normalisés** (zéros de tête préservés, nettoyage des caractères non numériques).
* **Forme** : détection par tokens du libellé (`CPR`, `GEL`, `COLLYRE`, `SOL`, `INJ`, `FL`, etc.).
* **Nombre d’unités/boîte** : priorité à la colonne `Qte` ; à défaut, fallback sur le **dernier entier** du libellé (ex. “… CPR 14” → 14).
* **Dose par unité (mg)** :

  * formes **solides** : première teneur repérée (ex. `20 MG`, `1000 MCG` → 1 mg).
  * **liquides** : si **concentration** `X MG/ML` **et** **volume unitaire** “`… / Y ML`” sont présents, alors `dose_par_unite_mg = X × Y`.
* **Combinaisons** : si le libellé contient `A MG / B MG`, on stocke deux valeurs `[A, B]` (non sommées) et on génère une table **explosée** (1 ligne par composant).
* **Dose totale par boîte (mg)** : calculée **uniquement** pour les **mono-molécules** = `nb_unites_par_boite × dose_par_unite_mg`.

---

## 📤 Schéma des sorties

### `cip13_norm.parquet` (niveau **présentation**)

| Colonne                          | Description                                                                |
| -------------------------------- | -------------------------------------------------------------------------- |
| `CIP13`, `CIP7`, `UCD13`, `UCD7` | Identifiants normalisés                                                    |
| `LABO`, `EPHMRA`                 | Métadonnées source                                                         |
| `LIB_UCD` / `LIB_CIP`            | Libellé d’origine                                                          |
| `forme`                          | Forme pharmaceutique                                                       |
| `nb_unites_par_boite`            | Nombre d’unités (priorité `Qte`, sinon fallback libellé)                   |
| `dose_par_unite_mg`              | Dose unitaire convertie en mg (si possible)                                |
| `dose_totale_boite_mg`           | Dose totale (mono-molécule uniquement)                                     |
| `conc_mg_per_ml`                 | Concentration mg/mL (si détectée)                                          |
| `unit_volume_ml`                 | Volume par unité en mL (si détecté)                                        |
| `combo_a_mg`, `combo_b_mg`       | Doses unitaires des 2 composants (si combinaison)                          |
| `DOSE`                           | Représentation lisible : ex. `20.00 mg × 14` ou `80.00 mg + 12.50 mg × 30` |

### `cip13_components.parquet` (niveau **composant**)

| Colonne                          | Description                               |
| -------------------------------- | ----------------------------------------- |
| Identifiants & libellés          | mêmes que ci-dessus                       |
| `forme`, `nb_unites_par_boite`   | idem                                      |
| `component_index`                | 1, 2, … (un enregistrement par composant) |
| `dose_par_unite_mg_component`    | Dose unitaire **du composant** (mg)       |
| `dose_totale_boite_mg_component` | Dose totale **du composant** (mg)         |

---

## 🧪 Tests rapides

```bash
pytest -q
```

Cas couverts (exemples) :

* `ESOMEPRAZOLE 20 MG CPR … 14` → 20 mg × 14
* `AVONEX 30 MCG/0,5 ML … 4/0,5 ML` → \~0,015 mg/unité (30 mcg × 0,5 mL)
* `VALSARTAN/HYDROCHLOROTHIAZIDE 80 MG/12,5 MG CPR 30` → combo `[80, 12.5]` mg × 30

---

## ⚠️ Limites & bonnes pratiques

* Le parsing repose sur les **libellés** ; certains cas atypiques (formes exotiques, libellés incomplets) peuvent nécessiter une **vérification manuelle** ou un référentiel complémentaire (ex. BDPM `CIS_COMPO` pour la composition exacte des combinaisons).
* Pour les **liquides** sans volume unitaire explicite, seule `conc_mg_per_ml` est fournie.
* Les **combinaisons** ne sont **jamais additionnées** : utilisez `cip13_components.parquet` si vous devez agréger par **molécule** composante.
* Le projet ne traite pas l’ATC (par design, pour rester autonome vis-à-vis d’autres tables).

---

## 🤝 Contribuer

1. Fork → branche `feat/...`
2. `ruff check . && black . && pytest`
3. Ouvrez une PR avec description claire + échantillon de cas si possible.
   Voir aussi : `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`.

---

## 🔐 Sécurité & confidentialité

* Ne commitez **aucune** donnée SNDS.
* `CIP_UCD.csv` est public mais soumis aux conditions d’utilisation de la plateforme e-santé / ANSM — respectez-les.

---

## 🧾 Licence

Apache-2.0 (voir `LICENSE`).

---

## 📣 Référence

* **Terminologie CIP/UCD** : [https://smt.esante.gouv.fr/terminologie-cip\_ucd/](https://smt.esante.gouv.fr/terminologie-cip_ucd/)
  *(dans l’archive, le fichier cible se trouve généralement sous `dat/` et s’appelle `CIP_UCD.csv` — encodage UTF-16, séparateur `;`)*

```
```
