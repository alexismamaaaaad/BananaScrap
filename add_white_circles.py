from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

# ==============================================================================
# CONFIGURATION ET CONSTANTES
# ==============================================================================
# Couleurs au format RGB
COLOR_WHITE = (255, 255, 255)
COLOR_BLACK = (0, 0, 0)
COLOR_GOLD = (255, 215, 0)
COLOR_GREEN = (0, 180, 0)
COLOR_RED = (220, 50, 50)
COLOR_DISABLED_BG = (200, 200, 200)

# Noms de colonnes pour les créneaux horaires
COLUMN_LABELS = ["MIDI", "APRES-MIDI", "SOIREE", "DEM. MATIN"]

# Polices de caractères prioritaires
PREFERRED_FONTS = [
    "Montserrat-Bold.ttf",
    "MontserratAlternates-Bold.ttf",
    "Montserrat-Regular.ttf",
    "MontserratAlternates-Regular.ttf",
    "Montserrat.ttf",
    "montserrat.ttf",
    "arial.ttf",
]


# ==============================================================================
# FONCTIONS UTILITAIRES
# ==============================================================================
def find_single_jpg(path: Path) -> Path:
    """Recherche l'image template source dans le dossier spécifié."""
    jpg_files = sorted(path.glob("template_story_creneaux.jpg"))
    candidate_files = [p for p in jpg_files if "_with_" not in p.stem.lower()]

    if len(candidate_files) == 1:
        return candidate_files[0]
    if len(jpg_files) == 1:
        return jpg_files[0]

    raise FileNotFoundError(f"Fichier .jpg source introuvable dans {path}")


def load_font(name: str | None, size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """
    Charge une police Truetype par nom spécifique ou via la liste de secours.
    Retourne la police par défaut de PIL si aucune police n'est disponible.
    """
    # 1. Tentative de chargement par nom spécifique s'il est fourni
    if name:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass

    # 2. Recherche dans la liste de polices prioritaires
    candidates = PREFERRED_FONTS if bold else reversed(PREFERRED_FONTS)
    for font_name in candidates:
        try:
            return ImageFont.truetype(font_name, size)
        except Exception:
            continue

    # 3. Fallback sur la police PIL par défaut
    return ImageFont.load_default()


def calculate_grid_metrics(width: int, height: int, rows: int = 6, cols: int = 4) -> dict:
    """
    Calcule toutes les métriques géométriques pour la grille de créneaux.
    Permet d'éviter la redondance des formules dans les fonctions de dessin.
    """
    top_margin = height * 0.31
    bottom_margin = height * 0.08
    left_margin = width * 0.07
    right_margin = width * 0.07

    usable_width = width - left_margin - right_margin
    usable_height = (height - top_margin - bottom_margin) * 0.92

    cell_width = usable_width / cols
    cell_height = usable_height / rows

    return {
        "top_margin": top_margin,
        "left_margin": left_margin,
        "usable_height": usable_height,
        "cell_width": cell_width,
        "cell_height": cell_height,
        "size_w": cell_width * 0.88,
        "size_h": cell_height * 0.89,
        "rows": rows,
        "cols": cols,
    }


# ==============================================================================
# COMPOSANTS VISUELS (EN-TÊTE, GRILLE, PIED DE PAGE)
# ==============================================================================
def add_header_logo(image: Image.Image, logo_path: Path) -> None:
    """Superpose le logo et dessine les titres en haut de l'image (modifie l'image en place)."""
    if not logo_path.exists():
        print(f"Fichier Logo introuvable : {logo_path}")
        return

    # Redimensionnement et collage du logo
    logo = Image.open(logo_path).convert("RGBA")
    max_height = int(image.height * 0.17)
    logo = ImageOps.contain(logo, (image.width, max_height))

    x_logo = (image.width - logo.width) // 2
    y_logo = int(image.height * 0.005)
    image.paste(logo, (x_logo, y_logo), logo)

    # Configuration des textes de l'en-tête
    draw = ImageDraw.Draw(image)
    font_title = load_font("JandaManateeSolid.ttf", max(24, int(image.height * 0.036)))

    title_text = "NOS CRENEAUX DISPONIBLES"
    sub_text = "TERRAINS DOUBLES"

    # Dessin du titre principal
    bbox_title = draw.textbbox((0, 0), title_text, font=font_title)
    draw.text(
        ((image.width - (bbox_title[2] - bbox_title[0])) // 2, logo.height * 1.05),
        title_text,
        fill=COLOR_GOLD,
        font=font_title,
    )

    # Dessin du sous-titre
    bbox_sub = draw.textbbox((0, 0), sub_text, font=font_title)
    draw.text(
        ((image.width - (bbox_sub[2] - bbox_sub[0])) // 2, logo.height * 1.35),
        sub_text,
        fill=COLOR_BLACK,
        font=font_title,
    )


def draw_schedule_grid(image: Image.Image, schedule_items: list[tuple[str, str]]) -> None:
    """Dessine la grille complète : séparateurs, arrière-plans (squircles), en-têtes et textes (modifie l'image en place)."""
    draw = ImageDraw.Draw(image)
    metrics = calculate_grid_metrics(image.width, image.height)

    cols, rows = metrics["cols"], metrics["rows"]
    cell_w, cell_h = metrics["cell_width"], metrics["cell_height"]
    size_w, size_h = metrics["size_w"], metrics["size_h"]
    top_margin, left_margin = metrics["top_margin"], metrics["left_margin"]

    # 1. Dessin des lignes séparatrices verticales entre colonnes
    separator_width = max(2, int(image.width * 0.006))
    for col in range(1, cols):
        sep_x = left_margin + col * cell_w
        draw.line(
            (sep_x, top_margin, sep_x, top_margin + metrics["usable_height"]),
            fill=COLOR_GOLD,
            width=separator_width,
        )

    # 2. Dessin des cartes d'arrière-plan (squircles/rounded rectangles)
    radius = int(min(size_w, size_h) * 0.24)
    for row in range(rows):
        for col in range(cols):
            idx = col * rows + row
            status = schedule_items[idx][1] if idx < len(schedule_items) else "Disponible"
            is_available = status.lower().startswith("disponible")
            fill_color = COLOR_WHITE if is_available else COLOR_DISABLED_BG

            x_center = left_margin + (col + 0.5) * cell_w
            y_center = top_margin + (row + 0.5) * cell_h

            draw.rounded_rectangle(
                (x_center - size_w / 2, y_center - size_h / 2, x_center + size_w / 2, y_center + size_h / 2),
                radius=radius,
                fill=fill_color,
                outline=COLOR_WHITE,
            )

    # 3. Dessin des en-têtes de colonnes (MIDI, APRES-MIDI, etc.)
    font_header = load_font(None, max(12, int(cell_w * 0.14)), bold=True)
    for col, label in enumerate(COLUMN_LABELS):
        x_center = left_margin + (col + 0.5) * cell_w
        y_pos = top_margin - int(image.height * 0.02)
        bbox = draw.textbbox((0, 0), label, font=font_header)
        text_w = bbox[2] - bbox[0]
        draw.text((x_center - text_w / 2, y_pos), label, fill=COLOR_WHITE, font=font_header)

    # 4. Dessin du contenu des cellules (Horaires et Statuts/Croix)
    time_font = load_font(None, max(16, int(min(size_w, size_h) * 0.32)), bold=True)
    status_font = load_font(None, max(12, int(min(size_w, size_h) * 0.18)), bold=False)

    for idx, (time_text, status_text) in enumerate(schedule_items[: rows * cols]):
        col = idx // rows
        row = idx % rows
        x_center = left_margin + (col + 0.5) * cell_w
        y_center = top_margin + (row + 0.5) * cell_h

        # Dessin du texte de l'heure
        t_bbox = draw.textbbox((0, 0), time_text, font=time_font)
        t_w, t_h = t_bbox[2] - t_bbox[0], t_bbox[3] - t_bbox[1]
        draw.text(
            (x_center - t_w / 2, y_center - t_h / 2 - int(size_h * 0.2)),
            time_text,
            fill=COLOR_BLACK,
            font=time_font,
        )

        # Dessin du statut ("Disponible" ou Croix d'indisponibilité)
        if status_text.lower().startswith("disponible"):
            s_bbox = draw.textbbox((0, 0), status_text, font=status_font)
            s_w, s_h = s_bbox[2] - s_bbox[0], s_bbox[3] - s_bbox[1]
            draw.text(
                (x_center - s_w / 2, y_center + int(size_h * 0.2) - s_h / 2),
                status_text,
                fill=COLOR_GREEN,
                font=status_font,
            )
        else:
            cross_size = int(min(size_w, size_h) * 0.18)
            thickness = max(2, int(cross_size * 0.18))
            cx, cy = x_center, y_center + int(size_h * 0.2)

            draw.line((cx - cross_size / 2, cy - cross_size / 2, cx + cross_size / 2, cy + cross_size / 2), fill=COLOR_RED, width=thickness)
            draw.line((cx - cross_size / 2, cy + cross_size / 2, cx + cross_size / 2, cy - cross_size / 2), fill=COLOR_RED, width=thickness)


def add_footer(image: Image.Image, footer_path: Path) -> None:
    """Superpose le bandeau de bas de page et ses textes de réassurance (modifie l'image en place)."""
    if not footer_path.exists():
        print(f"Fichier Footer introuvable : {footer_path}")
        return

    # Intégration de l'image de fond du footer
    footer = Image.open(footer_path).convert("RGBA")
    footer = ImageOps.contain(footer, (int(image.width * 1.0), int(image.height * 0.16)))

    x_footer = (image.width - footer.width) // 2
    y_footer = image.height - footer.height
    image.paste(footer, (x_footer, y_footer), footer)

    # Configuration et dessin des textes d'appel à l'action
    draw = ImageDraw.Draw(image)
    main_font = load_font("JandaManateeSolid.ttf", max(20, int(image.height * 0.035)))
    sub_font = load_font(None, max(16, int(image.height * 0.02)), bold=False)

    text_main = "Réservez votre créneau en ligne !"
    text_sub = "Apple Store, Google Play ou site internet en bio !"

    # Texte principal (doré)
    bbox_m = draw.textbbox((0, 0), text_main, font=main_font)
    text_y = image.height - int(image.height * 0.081)
    draw.text(((image.width - (bbox_m[2] - bbox_m[0])) // 2, text_y), text_main, fill=COLOR_GOLD, font=main_font)

    # Texte secondaire (blanc)
    bbox_s = draw.textbbox((0, 0), text_sub, font=sub_font)
    draw.text(
        ((image.width - (bbox_s[2] - bbox_s[0])) // 2, text_y + int(image.height * 0.05)),
        text_sub,
        fill=COLOR_WHITE,
        font=sub_font,
    )


# ==============================================================================
# PIPELINE PRINCIPAL
# ==============================================================================
def main() -> None:
    folder = Path.cwd()
    image_path = find_single_jpg(folder)

    # Ouverture de l'image de base en RGBA unique pour tout le pipeline
    canvas = Image.open(image_path).convert("RGBA")

    # Données des créneaux
    schedule_items = [
        ("10h30", "Disponible"), ("11h00", "Disponible"), ("12h00", "Disponible"),
        ("12h30", "Disponible"), ("13h30", "Indisponible"), ("14h00", "Indisponible"),
        ("14h30", "Disponible"), ("15h00", "Disponible"), ("16h30", "Indisponible"),
        ("17h00", "Disponible"), ("18h00", "Disponible"), ("18h30", "Indisponible"),
        ("19h30", "Indisponible"), ("20h00", "Indisponible"), ("21h00", "Disponible"),
        ("21h30", "Disponible"), ("22h30", "Disponible"), ("23h00", "Indisponible"),
        ("06h00", "Disponible"), ("06h30", "Disponible"), ("07h30", "Indisponible"),
        ("08h00", "Disponible"), ("09h00", "Disponible"), ("09h30", "Disponible"),
    ]

    # Application séquentielle des éléments
    draw_schedule_grid(canvas, schedule_items)
    add_footer(canvas, folder / "Footer.png")
    add_header_logo(canvas, folder / "LogoBananaPadel.png")

    # Conversion finale en RGB pour le format JPG et sauvegarde
    final_image = canvas.convert("RGB")
    output_path = image_path.with_name(f"{image_path.stem}_with_squircles_and_footer_and_logo.jpg")
    final_image.save(output_path, quality=95)
    print(f"Image enregistrée avec succès : {output_path}")


if __name__ == "__main__":
    main()