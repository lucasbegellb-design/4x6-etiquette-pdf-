"""Génère des PDF de test qui imitent les mises en page réelles des étiquettes.

Usage : python3 tests/generer_pdf_test.py [dossier_sortie]   (défaut : tests/pdf)

Chaque PDF contient : un cadre extérieur en pointillés (« ruban adhésif »),
le rectangle de l'étiquette à trait PLEIN, des faux codes-barres, du texte.
Les zones attendues sont écrites dans attendu.json (coordonnées « visuelles »
en points, origine en bas à gauche de la page telle qu'affichée).
"""
import json
import random
import sys
from pathlib import Path

from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent / "pdf")
OUT.mkdir(parents=True, exist_ok=True)
A4P = A4                      # 595.28 x 841.89
A4L = landscape(A4)           # 841.89 x 595.28
expected = {}


def barcode(c, x0, y0, x1, y1, seed):
    """Faux code-barres 1D : barres verticales pleines de largeur variable."""
    rnd = random.Random(seed)
    x = x0
    while x < x1:
        w = rnd.choice([0.8, 1.2, 1.8, 2.6])
        if x + w > x1:
            break
        c.rect(x, y0, w, y1 - y0, stroke=0, fill=1)
        x += w + rnd.choice([0.8, 1.2, 1.8, 2.6])


def matrix_code(c, x, y, size, seed, n=16):
    """Faux code 2D (DataMatrix)."""
    rnd = random.Random(seed)
    cell = size / n
    for i in range(n):
        for j in range(n):
            if i == 0 or j == 0 or rnd.random() < 0.45:
                c.rect(x + i * cell, y + j * cell, cell, cell, stroke=0, fill=1)


def dashed_frame(c, x0, y0, x1, y1, dash=(6, 3), text="Collez ici le ruban adhésif"):
    c.saveState()
    c.setDash(*dash)
    c.setLineWidth(1)
    c.rect(x0, y0, x1 - x0, y1 - y0, stroke=1, fill=0)
    c.restoreState()
    if text:
        c.setFont("Helvetica-Oblique", 8)
        c.drawCentredString((x0 + x1) / 2, y1 - 12, text)
        c.drawCentredString((x0 + x1) / 2, y0 + 5, text)


def address_block(c, x, y, lines, size=9):
    c.setFont("Helvetica", size)
    for i, line in enumerate(lines):
        c.drawString(x, y - i * (size + 2), line)


def colissimo_label(c, x0, y0, x1, y1, intl=False, lw=1.0):
    """Étiquette Colissimo : rectangle plein + contenu."""
    c.setLineWidth(lw)
    c.rect(x0, y0, x1 - x0, y1 - y0, stroke=1, fill=0)
    # bandeau noir en haut à gauche (repère d'orientation)
    c.rect(x0 + 4, y1 - 28, 92, 24, stroke=0, fill=1)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(x0 + 10, y1 - 22, "colissimo")
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(x1 - 8, y1 - 20, "INTERNATIONAL" if intl else "FRANCE")
    # séparateurs internes (forment des rectangles plus petits)
    c.setLineWidth(0.8)
    c.line(x0, y1 - 34, x1, y1 - 34)
    c.line(x0, y1 - 120, x1, y1 - 120)
    c.line(x0 + (x1 - x0) / 2, y1 - 120, x0 + (x1 - x0) / 2, y1 - 34)
    address_block(c, x0 + 8, y1 - 48, ["EXPÉDITEUR", "Boutique Test", "12 rue des Lilas", "75011 PARIS"], 8)
    address_block(c, x0 + (x1 - x0) / 2 + 6, y1 - 48, ["DESTINATAIRE", "Jeanne Martin", "5 avenue Fictive", "69003 LYON"], 8)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(x0 + 10, y1 - 145, "6A 123 456 789 0")
    barcode(c, x0 + 14, y1 - 230, x1 - 14, y1 - 160, seed=x0 + y0)
    matrix_code(c, x0 + 12, y0 + 12, 60, seed=7)
    c.setFont("Helvetica", 8)
    c.drawString(x0 + 84, y0 + 60, "Poids : 0,75 kg")
    c.drawString(x0 + 84, y0 + 48, "Date de dépôt : 05/11/2026")
    if intl:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x0 + 84, y0 + 30, "FedEx International Connect Plus")
        barcode(c, x0 + 14, y0 + 90, x1 - 14, y0 + 150, seed=99)


def instructions_right(c, x, y, title="Mode d'emploi"):
    c.setFont("Helvetica-Bold", 14)
    c.drawString(x, y, title)
    c.setFont("Helvetica", 9)
    for i, t in enumerate([
        "1. Imprimez cette page en A4.",
        "2. Découpez l'étiquette en suivant les pointillés.",
        "3. Collez-la sur le colis avec du ruban adhésif transparent.",
        "4. Déposez le colis en bureau de poste ou en point relais.",
    ]):
        c.drawString(x, y - 22 - i * 14, t)


# 1. Colissimo France (étiquette « courte »)
c = canvas.Canvas(str(OUT / "colissimo_france.pdf"), pagesize=A4L)
dashed_frame(c, 30, 136, 368, 532)
colissimo_label(c, 54, 160, 344, 508)
instructions_right(c, 430, 520)
c.setLineWidth(1)
c.rect(420, 300, 380, 150, stroke=1, fill=0)          # encadré « preuve de dépôt », plus petit
c.setFont("Helvetica", 9)
c.drawString(430, 430, "Preuve de dépôt - à conserver")
barcode(c, 440, 330, 700, 380, seed=3)
c.save()
expected["colissimo_france.pdf"] = {"pages": 1, "customs": False,
                                    "boxes": {"0": {"box": [54, 160, 344, 508], "source": "rect"}}}

# 2. Colissimo / FedEx international (étiquette « haute ») + CN23 + facture
c = canvas.Canvas(str(OUT / "fedex_colissimo_international.pdf"), pagesize=A4L)
dashed_frame(c, 30, 51, 368, 531, dash=(3, 1))          # pointillés serrés : cas difficile
colissimo_label(c, 54, 75, 344, 507, intl=True)
instructions_right(c, 430, 520)
c.showPage()
c.setPageSize(A4P)
# page 2 : déclaration CN23 (formulaire tableau en haut de page)
c.setLineWidth(1)
c.rect(29, 372, 539, 440, stroke=1, fill=0)
c.setFont("Helvetica-Bold", 13)
c.drawString(40, 790, "DÉCLARATION EN DOUANE                 CN 23")
c.setLineWidth(0.6)
for y in (770, 700, 640, 560, 480, 420):
    c.line(29, y, 568, y)
for x in (300, 420, 500):
    c.line(x, 420, x, 560)
c.line(300, 700, 300, 770)
address_block(c, 40, 755, ["De : Boutique Test", "12 rue des Lilas", "75011 PARIS - FRANCE"], 8)
address_block(c, 310, 755, ["À : John Smith", "1 Example Street", "NEW YORK NY 10001 - USA"], 8)
address_block(c, 40, 545, ["Description détaillée du contenu", "T-shirt coton x2", "Carte postale x1"], 8)
address_block(c, 310, 545, ["Quantité", "2", "1"], 8)
address_block(c, 430, 545, ["Poids (kg)", "0,40", "0,02"], 8)
address_block(c, 510, 545, ["Valeur", "30,00", "2,00"], 8)
c.setFont("Helvetica", 7)
c.drawString(40, 400, "Je certifie que les renseignements donnés dans la présente déclaration sont exacts.")
c.setFont("Helvetica", 9)
c.drawString(40, 330, "Exemplaire à remettre avec le colis (3 exemplaires).")
c.showPage()
c.setPageSize(A4P)
# page 3 : facture commerciale, sans cadre (repli boîte englobante)
c.setFont("Helvetica-Bold", 16)
c.drawString(60, 770, "FACTURE COMMERCIALE / COMMERCIAL INVOICE")
address_block(c, 60, 740, ["Vendeur : Boutique Test, 12 rue des Lilas, 75011 Paris", "Acheteur : John Smith, 1 Example Street, New York",
                           "N° d'envoi : CA123456789FR", "", "Article             Qté   Prix unitaire   Total",
                           "T-shirt coton        2        15,00 EUR     30,00 EUR",
                           "Carte postale        1         2,00 EUR      2,00 EUR", "", "Total : 32,00 EUR",
                           "Motif de l'export : vente", "Signature :"], 10)
c.save()
expected["fedex_colissimo_international.pdf"] = {
    "pages": 3, "customs": True,
    "boxes": {"0": {"box": [54, 75, 344, 507], "source": "rect"},
              "1": {"box": [29, 372, 568, 812], "source": "rect"},
              "2": {"box": [60, 617, 458, 782], "source": "bbox", "loose": True}}}

# 3. UPS : page A4 portrait, étiquette en paysage dans la moitié haute
c = canvas.Canvas(str(OUT / "ups.pdf"), pagesize=A4P)
c.setLineWidth(1.5)
c.rect(32, 466, 424, 299, stroke=1, fill=0)
c.rect(36, 735, 60, 26, stroke=0, fill=1)                    # repère haut-gauche
c.setFillColorRGB(1, 1, 1)
c.setFont("Helvetica-Bold", 16)
c.drawString(44, 742, "UPS")
c.setFillColorRGB(0, 0, 0)
c.setLineWidth(0.8)
c.line(32, 690, 456, 690)
c.line(32, 560, 456, 560)
address_block(c, 110, 755, ["BOUTIQUE TEST  +33 1 23 45 67 89", "12 RUE DES LILAS", "75011 PARIS FRANCE"], 8)
address_block(c, 50, 675, ["SHIP TO:", "JOHN SMITH", "1 EXAMPLE STREET", "NEW YORK NY 10001", "UNITED STATES"], 10)
matrix_code(c, 370, 600, 70, seed=11)
c.setFont("Helvetica-Bold", 15)
c.drawString(44, 572, "UPS EXPRESS SAVER   1Z 999 AA1 01 2345 6784")
barcode(c, 60, 480, 430, 550, seed=5)
c.saveState()
c.setDash(4, 4)
c.line(20, 430, 575, 430)                                    # ligne de pliage en pointillés
c.restoreState()
c.setFont("Helvetica", 8)
c.drawString(30, 418, "Pliez la feuille en suivant cette ligne. Ne pas photocopier l'étiquette.")
instructions_right(c, 40, 380, title="Instructions UPS")
c.save()
expected["ups.pdf"] = {"pages": 1, "customs": False, "boxes": {"0": {"box": [32, 466, 456, 765], "source": "rect"}}}

# 4. DHL « Créer une expédition » : A4 paysage, trait fin (0,5 pt), x entiers (trait à cheval sur 2 pixels)
c = canvas.Canvas(str(OUT / "dhl.pdf"), pagesize=A4L)
c.setLineWidth(0.5)
c.rect(92, 61.3, 268, 495.4, stroke=1, fill=0)
c.rect(97, 525, 70, 28, stroke=0, fill=1)                    # repère haut-gauche
c.setFillColorRGB(1, 1, 1)
c.setFont("Helvetica-Bold", 18)
c.drawString(104, 532, "DHL")
c.setFillColorRGB(0, 0, 0)
c.line(92, 515, 360, 515)
c.line(92, 400, 360, 400)
address_block(c, 100, 500, ["From: Boutique Test", "12 rue des Lilas 75011 Paris"], 8)
address_block(c, 100, 470, ["To: Hans Muster", "Beispielstrasse 1", "8000 ZÜRICH", "SWITZERLAND"], 11)
c.setFont("Helvetica-Bold", 14)
c.drawString(100, 380, "WPX  ·  CH-ZRH-ZRH")
barcode(c, 105, 300, 345, 360, seed=8)
barcode(c, 105, 110, 345, 180, seed=9)
c.setFont("Helvetica", 9)
c.drawString(105, 95, "WAYBILL 12 3456 7890")
dashed_frame(c, 80, 49, 372, 569, dash=(5, 2), text="")
c.setFont("Helvetica-Bold", 14)
c.drawString(430, 540, "Récapitulatif de l'expédition")
address_block(c, 430, 515, ["Référence : 2026-1105-01", "Service : DHL Express Worldwide", "Poids : 1,2 kg",
                            "Contenu : vêtements", "Merci d'avoir choisi DHL."], 10)
c.save()
expected["dhl.pdf"] = {"pages": 1, "customs": False, "boxes": {"0": {"box": [92, 61, 360, 557], "source": "rect"}}}

# 5. Page sans cadre : repli sur la boîte englobante des pixels sombres
c = canvas.Canvas(str(OUT / "sans_cadre.pdf"), pagesize=A4P)
c.setFont("Helvetica-Bold", 22)
c.drawString(100, 700, "ÉTIQUETTE SANS CADRE")
barcode(c, 100, 560, 400, 660, seed=21)
address_block(c, 100, 530, ["Destinataire : Paul Durand", "8 impasse du Test", "33000 BORDEAUX"], 12)
c.save()
expected["sans_cadre.pdf"] = {"pages": 1, "customs": False,
                              "boxes": {"0": {"box": [100, 504, 400, 717], "source": "bbox", "loose": True}}}

# 6. Page blanche A4 paysage : détection incohérente -> préréglage le plus proche
c = canvas.Canvas(str(OUT / "page_vide.pdf"), pagesize=A4L)
c.setFont("Helvetica", 1)
c.drawString(-100, -100, " ")
c.showPage()
c.save()
expected["page_vide.pdf"] = {"pages": 1, "customs": False,
                             "boxes": {"0": {"box": [54, 160, 344, 508], "source": "preset"}}}

# 7. Même étiquette Colissimo, mais page PORTRAIT avec /Rotate 90 (affichée en paysage).
#    Le contenu est transformé pour que l'affichage soit identique au n° 1 :
#    (X, Y) affiché -> (u, v) = (W - Y, X) dans l'espace utilisateur portrait.
from pypdf import PageObject, PdfReader, PdfWriter, Transformation
W, H = A4P
src = PdfReader(str(OUT / "colissimo_france.pdf")).pages[0]
page = PageObject.create_blank_page(width=W, height=H)
page.merge_transformed_page(src, Transformation((0, 1, -1, 0, W, 0)))
page.rotate(90)
w = PdfWriter()
w.add_page(page)
with open(OUT / "colissimo_rotate90.pdf", "wb") as fh:
    w.write(fh)
expected["colissimo_rotate90.pdf"] = {"pages": 1, "customs": False,
                                      "boxes": {"0": {"box": [54, 160, 344, 508], "source": "rect"}}}

(OUT / "attendu.json").write_text(json.dumps(expected, indent=2, ensure_ascii=False))
print("PDF générés dans", OUT)
