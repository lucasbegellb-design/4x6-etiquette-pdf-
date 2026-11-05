# Étiquettes PDF → MUNBYN 4×6

Convertit les étiquettes d'expédition PDF (Colissimo, FedEx via Colissimo, UPS, DHL) au format de
l'imprimante thermique MUNBYN : **4×6 pouces (100 × 150 mm), page de 288 × 432 pt**.

👉 **https://lucasbegellb-design.github.io/4x6-etiquette-pdf-/**

## Utilisation

1. Glissez-déposez un ou plusieurs PDF (ou bouton « Choisir des PDF »).
2. La zone de l'étiquette est détectée automatiquement sur chaque page (cadre rouge sur les miniatures).
3. Seule la page 1 (l'étiquette) est cochée ; cochez d'autres pages si besoin (ex. déclaration CN23).
4. Vérifiez l'aperçu 4×6 ; si la détection s'est trompée, déplacez le cadre ou ses poignées
   (ou choisissez un préréglage : Colissimo courte/haute, CN23, UPS, DHL, page entière).
5. **Télécharger** → `etiquette_<nom-original>_MUNBYN_4x6.pdf`, ou **Imprimer** → ouvre le PDF dans un nouvel onglet.

Envoi hors UE : si le PDF contient une CN23 ou une facture commerciale, l'app le signale
(« imprime aussi les papiers de douane en A4 ») et propose de les ouvrir en A4.

## ⚠️ Impression

**Imprimer en 4×6, échelle 100 % (pas « ajuster à la page »).**
Dans la boîte d'impression : papier 4×6 / 100 × 150 mm, échelle 100 % (ou « taille réelle »), marges par défaut.

## Confidentialité

Tout se passe dans le navigateur : aucun fichier n'est envoyé (les étiquettes contiennent des adresses).
Les seules requêtes réseau chargent pdf-lib 1.17.1 et pdf.js 3.11.174 depuis jsDelivr (versions figées,
contrôle d'intégrité SRI) ; la page interdit toute autre connexion (Content-Security-Policy).

## Fonctionnement

- Le PDF produit reste **vectoriel** : la zone est découpée avec `embedPage(page, boundingBox)` de pdf-lib,
  puis posée avec `drawPage` (marge 4 pt, centrée, proportions conservées, rotation de 90° horaire si la
  zone est plus large que haute). Rien n'est rasterisé.
- Détection : rendu de la page avec pdf.js, recherche du plus grand rectangle à trait **plein**
  (les pointillés « Collez ici le ruban adhésif » sont ignorés), sinon boîte englobante du contenu,
  sinon préréglage selon le format de page.

## Tests

```bash
python3 tests/generer_pdf_test.py tests/pdf          # PDF factices + zones attendues
node tests/e2e.cjs tests/pdf tests/sortie            # Chromium/Playwright : glisser-déposer, détection, téléchargement…
python3 tests/verifier_sortie.py tests/sortie        # 288×432 pt, texte vectoriel, aucune image, orientation
```
