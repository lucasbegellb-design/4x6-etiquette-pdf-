"""Vérifie les PDF produits par l'application (tests/e2e.cjs les enregistre).

Usage : python3 tests/verifier_sortie.py <dossier_sortie>

- chaque page fait exactement 288 x 432 pt ;
- le contenu est VECTORIEL : aucune image dans le fichier, du texte extractible ;
- l'étiquette est dans la zone utile (marge de 4 pt) et bien orientée
  (repère noir en haut à gauche de l'étiquette d'origine) ;
- la page /Rotate 90 donne le même rendu que la page paysage d'origine.
"""
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter
from pypdf import PdfReader

OUT = Path(sys.argv[1])
fails = 0


def check(cond, msg):
    global fails
    print(("  ✔ " if cond else "  ✘ ") + msg)
    fails += 0 if cond else 1


def render(pdf, page=1, dpi=72):
    base = OUT / f"_rendu_{pdf.stem}_{page}"
    subprocess.run(["pdftoppm", "-r", str(dpi), "-f", str(page), "-l", str(page), "-png", "-singlefile", str(pdf), str(base)], check=True)
    return Image.open(f"{base}.png").convert("L")


def dark_bbox(img, thr=128):
    return img.point(lambda v: 255 if v < thr else 0).getbbox()


def has_images(reader):
    for page in reader.pages:
        stack = [page.get("/Resources")]
        while stack:
            res = stack.pop()
            if res is None:
                continue
            res = res.get_object()
            xobjs = res.get("/XObject")
            if not xobjs:
                continue
            for _, ref in xobjs.get_object().items():
                xo = ref.get_object()
                if xo.get("/Subtype") == "/Image":
                    return True
                if xo.get("/Subtype") == "/Form":
                    stack.append(xo.get("/Resources"))
    return False


EXPECT_TEXT = {
    "etiquette_colissimo_france_MUNBYN_4x6.pdf": ("Jeanne Martin", 1, "haut-gauche"),
    "etiquette_colissimo_rotate90_MUNBYN_4x6.pdf": ("Jeanne Martin", 1, "haut-gauche"),
    "etiquette_fedex_colissimo_international_MUNBYN_4x6.pdf": ("FedEx", 3, "haut-gauche"),
    "etiquette_ups_MUNBYN_4x6.pdf": ("JOHN SMITH", 1, "haut-droite"),      # étiquette paysage tournée de 90° horaire
    "etiquette_dhl_MUNBYN_4x6.pdf": ("Hans Muster", 1, "haut-gauche"),
    "etiquette_sans_cadre_MUNBYN_4x6.pdf": ("Paul Durand", 1, None),
    "etiquette_page_vide_MUNBYN_4x6.pdf": (None, 1, None),
}

for name, (text, npages, corner) in EXPECT_TEXT.items():
    pdf = OUT / name
    print(name)
    r = PdfReader(str(pdf))
    check(len(r.pages) == npages, f"{len(r.pages)} page(s) (attendu {npages})")
    sizes = {(float(p.mediabox.width), float(p.mediabox.height)) for p in r.pages}
    check(sizes == {(288.0, 432.0)}, f"format des pages : {sizes}")
    check(not has_images(r), "aucune image : contenu vectoriel")
    if text:
        extracted = subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True).stdout
        check(text in extracted, f"texte vectoriel extractible (« {text} »)")
    img = render(pdf, 1, dpi=72)          # 1 px = 1 pt
    bb = dark_bbox(img)
    if bb:
        inside = bb[0] >= 3 and bb[1] >= 3 and bb[2] <= 288 - 3 and bb[3] <= 432 - 3
        check(inside, f"contenu dans la zone utile 280 x 424 (boîte {bb})")
    if corner:
        # Repère : bandeau noir plein en haut à gauche de l'étiquette d'origine. L'érosion (filtre max 13 pt)
        # efface traits, texte, codes-barres et cellules de DataMatrix : il ne reste que les grands aplats noirs.
        blob = dark_bbox(img.filter(ImageFilter.MaxFilter(13)), thr=100)
        where = None
        if blob:
            cx, cy = (blob[0] + blob[2]) / 2, (blob[1] + blob[3]) / 2
            if cy < img.size[1] / 3:
                where = "haut-gauche" if cx < img.size[0] / 2 else "haut-droite"
        check(where == corner, f"orientation : repère noir en {where} (attendu {corner})")

print("Rotation /Rotate 90 vs page paysage")
a = render(OUT / "etiquette_colissimo_france_MUNBYN_4x6.pdf", 1, dpi=100)
b = render(OUT / "etiquette_colissimo_rotate90_MUNBYN_4x6.pdf", 1, dpi=100)
diff = ImageChops.difference(a, b)
ndiff = sum(1 for v in diff.tobytes() if v > 64)
check(ndiff < 0.002 * a.size[0] * a.size[1], f"rendus identiques ({ndiff} pixels différents)")

for f in OUT.glob("_rendu_*.png"):
    f.unlink()
print("\nOK : toutes les vérifications de sortie sont passées." if not fails else f"\n{fails} échec(s)")
sys.exit(1 if fails else 0)
