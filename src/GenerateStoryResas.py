from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps,ImageFilter
# ==============================================================================
# CONFIGURATION ET CONSTANTES
# ==============================================================================

# Folders for ressources 
SRC_FOLDER = Path.cwd()
RES_FOLDER = Path.cwd().parent / "results/"
FNT_FOLDER = Path.cwd().parent / "fonts/"
BCK_FOLDER = Path.cwd().parent / "backgrounds/"
IMG_FOLDER = Path.cwd().parent / "img/"

# Couleurs au format RGB
COLOR_WHITE = (255, 255, 255)
COLOR_BLACK = (0, 0, 0)
COLOR_GOLD = (253, 202, 55)
COLOR_GREEN = (0, 180, 0)
COLOR_RED = (220, 50, 50)
COLOR_DISABLED_BG = (44, 44, 44)
COLOR_BLUE = (33, 103, 187)

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

COLUMN_ICONS = [
    "midday.png",
    "afternoon.png",
    "moon.png",
    "morning.png",
]

# ==============================================================================
# FONCTIONS UTILITAIRES
# ==============================================================================
def find_single_jpg(path: Path) -> Path:
    """Recherche l'image template source dans le dossier spécifié."""
    jpg_files = sorted(path.glob("template_story_creneaux.jpg"))

    if len(jpg_files) == 1:
        return jpg_files[0]

    raise FileNotFoundError(f"Fichier .jpg source introuvable dans {path}")


def load_font(
    name: str | None, size: int, bold: bool = False
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """
    Charge une police Truetype par nom spécifique ou via la liste de secours.
    Retourne la police par défaut de PIL si aucune police n'est disponible.
    """
    # 1. Tentative de chargement par nom spécifique s'il est fourni

   
    if name:
        try:
            return ImageFont.truetype(FNT_FOLDER / name, size)
        except Exception:
            pass

    # 2. Recherche dans la liste de polices prioritaires
    candidates = PREFERRED_FONTS if bold else reversed(PREFERRED_FONTS)
    for font_name in candidates:
        try:
            return ImageFont.truetype(FNT_FOLDER / font_name, size)
        except Exception:
            continue

    # 3. Fallback sur la police PIL par défaut
    return ImageFont.load_default()


def calculate_grid_metrics(
    width: int, height: int, rows: int = 6, cols: int = 4
) -> dict:
    """
    Calcule toutes les métriques géométriques pour la grille de créneaux.
    Permet d'éviter la redondance des formules dans les fonctions de dessin.
    """
    top_margin = height * 0.45
    bottom_margin = height * 0.08
    left_margin = width * 0.07
    right_margin = width * 0.07

    usable_width = width - left_margin - right_margin
    usable_height = (height - top_margin - bottom_margin) * 0.80

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
def add_header_logo(image: Image.Image, logo_path: Path, Title : str) -> None:
    """Superpose le logo et dessine les titres en haut de l'image (modifie l'image en place)."""
    if not logo_path.exists():
        print(f"Fichier Logo introuvable : {logo_path}")
        return

    # Redimensionnement et collage du logo
    logo = Image.open(logo_path).convert("RGBA")
    max_height = int(image.height * 0.20)
    logo = ImageOps.contain(logo, (image.width, max_height))

    x_logo = (image.width - logo.width) // 2
    y_logo = int(image.height * 0.02)
    image.paste(logo, (x_logo, y_logo), logo)

    # Configuration des textes de l'en-tête
    draw = ImageDraw.Draw(image)
    font_title = load_font("JandaManateeSolid.ttf", max(24, int(image.height * 0.036)))
    font_subtitle = load_font("JandaManateeSolid.ttf", max(24, int(image.height * 0.05)))

    title_text = "NOS CRENEAUX DISPONIBLES"

    # Dessin du titre principal
    bbox_title = draw.textbbox((0, 0), title_text, font=font_title)
    draw.text(
        ((image.width - (bbox_title[2] - bbox_title[0])) // 2, logo.height * 1.2),
        title_text,
        fill=COLOR_GOLD,
        font=font_title,
    )

    # Dessin du sous-titre
    bbox_sub = draw.textbbox((0, 0), Title, font=font_subtitle)
    draw.text(
        ((image.width - (bbox_sub[2] - bbox_sub[0])) // 2, logo.height * 1.45),
        Title,
        fill=COLOR_BLACK,
        font=font_subtitle,
    )


def draw_schedule_grid(
    image: Image.Image, schedule_items: list[tuple[str, str]], rows: int, cols: int
) -> None:
    """Dessine la grille complète : séparateurs, arrière-plans (squircles), en-têtes et textes (modifie l'image en place)."""
    draw = ImageDraw.Draw(image)
    metrics = calculate_grid_metrics(image.width, image.height, rows, cols)

    cols, rows = metrics["cols"], metrics["rows"]
    cell_w, cell_h = metrics["cell_width"], metrics["cell_height"]
    size_w, size_h = metrics["size_w"], metrics["size_h"]
    top_margin, left_margin = metrics["top_margin"], metrics["left_margin"]

    # 1. Dessin des lignes séparatrices verticales entre colonnes
    #separator_width = max(2, int(image.width * 0.006))
    #for col in range(1, cols):
    #    sep_x = left_margin + col * cell_w
    #    draw.line(
    #        (sep_x, top_margin, sep_x, top_margin + metrics["usable_height"]),
    #        fill=COLOR_GOLD,
    #        width=separator_width,
    #    )

    # 2. Dessin des cartes d'arrière-plan (squircles/rounded rectangles)
    radius = int(min(size_w, size_h) * 0.48)
    for row in range(rows):
        for col in range(cols):
            idx = col * rows + row
            status = (
                schedule_items[idx][1] if idx < len(schedule_items) else "DISPONIBLE"
            )
            is_available = status.lower().startswith("disponible")
            fill_color = COLOR_WHITE if is_available else COLOR_DISABLED_BG
            outline_color = COLOR_BLUE if is_available else COLOR_WHITE
        
            x_center = left_margin + (col + 0.5) * cell_w
            y_center = top_margin + (row + 0.5) * cell_h

            if schedule_items[idx][1] != "ABSENT":
                draw.rounded_rectangle(
                    (
                        x_center - size_w / 2,
                        y_center - size_h / 2,
                        x_center + size_w / 2,
                        y_center + size_h / 2,
                    ),
                    radius=radius,
                    fill=fill_color,
                    outline=outline_color,
                    width=3

                )

    # 3. Dessin des icônes + en-têtes de colonnes
    font_header = load_font(None, max(12, int(cell_w * 0.14)), bold=True)

    icon_width = int(cell_w * 0.35)          # largeur identique pour les 4 icônes
    icon_text_gap = int(image.height * 0.008)

    for col, (label, icon_name) in enumerate(zip(COLUMN_LABELS, COLUMN_ICONS)):
        x_center = left_margin + (col + 0.5) * cell_w

        # Chargement de l'icône
        icon_path = Path.cwd().parent / "img" / icon_name
        if icon_path.exists():

            icon = Image.open(icon_path).convert("RGBA")

            ratio = icon.height / icon.width
            icon = ImageOps.contain(
                icon,
                (icon_width, int(icon_width * ratio))
            )

            icon_x = int(x_center - icon.width / 2)
            icon_y = int(top_margin - image.height * 0.075)

            alpha = icon.getchannel("A")

            # ---------- Contour noir (extérieur) ----------
            black_alpha = alpha.filter(ImageFilter.MaxFilter(3))
            black_outline = Image.new("RGBA", icon.size, (0, 0, 0, 0))
            black_outline.putalpha(black_alpha)

            # ---------- Contour blanc (intérieur) ----------
            white_alpha = alpha.filter(ImageFilter.MaxFilter(5))
            white_outline = Image.new("RGBA", icon.size, (255, 255, 255, 0))
            white_outline.putalpha(white_alpha)

            # Dessin dans l'ordre
            #image.paste(white_outline, (icon_x, icon_y), white_outline)
            image.paste(black_outline, (icon_x, icon_y), black_outline)
            image.paste(icon, (icon_x, icon_y), icon)

            text_y = icon_y + icon.height + icon_text_gap
        else:
            text_y = top_margin - int(image.height * 0.02)

        bbox = draw.textbbox((0, 0), label, font=font_header)
        text_w = bbox[2] - bbox[0]

        draw.text(
            (x_center - text_w / 2, text_y),
            label,
            fill=COLOR_WHITE,
            font=font_header,
        )

    # 4. Dessin du contenu des cellules (Horaires et Statuts/Croix)
    time_font = load_font(
        "Montserrat-Regular.ttf",
        int(cell_w * 0.25),
        bold=False,
    )
    
    status_font = load_font(None, int(cell_w * 0.095), bold=True)

    for idx, (time_text, status_text) in enumerate(schedule_items[: rows * cols]):
        col = idx // rows
        row = idx % rows
        x_center = left_margin + (col + 0.5) * cell_w
        y_center = top_margin + (row + 0.45) * cell_h

        # Dessin du texte de l'heure
        t_bbox = draw.textbbox((0, 0), time_text, font=time_font)
        t_w, t_h = t_bbox[2] - t_bbox[0], t_bbox[3] - t_bbox[1]
        if status_text.lower().startswith("disponible"):
            colorHour = COLOR_BLACK
        else:
            colorHour = COLOR_WHITE

        draw.text(
            (x_center - t_w / 2, y_center - t_h / 2 - int(size_h * 0.2)),
            time_text,
            fill=colorHour,
            font=time_font,
        )

        # Dessin du statut ("Disponible" ou Croix d'indisponibilité)
        if status_text.lower().startswith("disponible"):
            s_bbox = draw.textbbox((0, 0), status_text, font=status_font)
            s_w, s_h = s_bbox[2] - s_bbox[0], s_bbox[3] - s_bbox[1]
            draw.text(
                (x_center - s_w / 2, y_center + int(size_h * 0.25) - s_h / 2),
                status_text,
                fill=COLOR_BLUE,
                font=status_font,
            )
        elif status_text.lower().startswith("absent"):
            toto="test"
        else:
            cross_size = int(min(size_w, size_h) * 0.18)
            thickness = max(2, int(cross_size * 0.30))
            cx, cy = x_center, y_center + int(size_h * 0.3)

            draw.line(
                (
                    cx - cross_size / 2,
                    cy - cross_size / 2,
                    cx + cross_size / 2,
                    cy + cross_size / 2,
                ),
                fill=COLOR_RED,
                width=thickness,
            )
            draw.line(
                (
                    cx - cross_size / 2,
                    cy + cross_size / 2,
                    cx + cross_size / 2,
                    cy - cross_size / 2,
                ),
                fill=COLOR_RED,
                width=thickness,
            )


def add_footer(image: Image.Image, footer_path: Path) -> None:
    """Superpose le bandeau de bas de page et ses textes de réassurance (modifie l'image en place)."""
    if not footer_path.exists():
        print(f"Fichier Footer introuvable : {footer_path}")
        return

    # Intégration de l'image de fond du footer
    footer = Image.open(footer_path).convert("RGBA")
    footer = ImageOps.contain(
        footer, (int(image.width * 1.0), int(image.height * 0.16))
    )

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
    draw.text(
        ((image.width - (bbox_m[2] - bbox_m[0])) // 2, text_y),
        text_main,
        fill=COLOR_GOLD,
        font=main_font,
    )

    # Texte secondaire (blanc)
    bbox_s = draw.textbbox((0, 0), text_sub, font=sub_font)
    draw.text(
        (
            (image.width - (bbox_s[2] - bbox_s[0])) // 2,
            text_y + int(image.height * 0.05),
        ),
        text_sub,
        fill=COLOR_WHITE,
        font=sub_font,
    )


# ==============================================================================
# PIPELINE PRINCIPAL
# ==============================================================================
def main() -> None:

    image_path = find_single_jpg(BCK_FOLDER)

    # **************************************************************************** #
    # DOUBLES                                                                      #
    # **************************************************************************** #

    # Données des créneaux
    schedule_items_double = [
        ("10:30", "INDISPONIBLE"),
        ("11:00", "INDISPONIBLE"),
        ("12:00", "DISPONIBLE"),
        ("12:30", "DISPONIBLE"),
        ("13:30", "DISPONIBLE"),
        ("14:00", "DISPONIBLE"),
        ("14:30", "DISPONIBLE"),
        ("15:00", "DISPONIBLE"),
        ("16:30", "DISPONIBLE"),
        ("17:00", "INDISPONIBLE"),
        ("18:00", "DISPONIBLE"),
        ("18:30", "DISPONIBLE"),
        ("19:30", "DISPONIBLE"),
        ("20:00", "DISPONIBLE"),
        ("21:00", "INDISPONIBLE"),
        ("21:30", "DISPONIBLE"),
        ("22:30", "DISPONIBLE"),
        ("23:00", "INDISPONIBLE"),
        ("06:00", "INDISPONIBLE"),
        ("06:30", "DISPONIBLE"),
        ("07:30", "DISPONIBLE"),
        ("08:00", "DISPONIBLE"),
        ("09:00", "DISPONIBLE"),
        ("09:30", "DISPONIBLE"),
    ]

    # Ouverture de l'image de base en RGBA unique pour tout le pipeline
    canvas = Image.open(image_path).convert("RGBA")

    # Application séquentielle des éléments
    draw_schedule_grid(canvas, schedule_items_double, 6,4)
    add_footer(canvas, IMG_FOLDER / "Footer.png")
    add_header_logo(canvas, IMG_FOLDER / "LogoBananaPadel.png", "TERRAINS DOUBLES")

    # Conversion finale en RGB pour le format JPG et sauvegarde
    final_image = canvas.convert("RGB")
    output_path = RES_FOLDER / "planning_double.jpg"
    final_image.save(output_path, quality=95)
    print(f"Image enregistrée avec succès : {output_path}")

    # **************************************************************************** #
    # SINGLE                                                                       #
    # **************************************************************************** #

    schedule_items_simple = [
            ("11:00", "INDISPONIBLE"),
            ("12:00", "DISPONIBLE"),
            ("13:00", "DISPONIBLE"),
            ("14:00", "DISPONIBLE"),
            ("", "ABSENT"),
            ("15:00", "DISPONIBLE"),
            ("16:00", "DISPONIBLE"),
            ("17:00", "DISPONIBLE"),
            ("18:00", "DISPONIBLE"),
            ("", "ABSENT"),
            ("19:00", "DISPONIBLE"),
            ("20:00", "DISPONIBLE"),
            ("21:00", "DISPONIBLE"),
            ("22:00", "DISPONIBLE"),
            ("23:00", "DISPONIBLE"),
            ("06:00", "DISPONIBLE"),
            ("07:00", "DISPONIBLE"),
            ("08:00", "DISPONIBLE"),
            ("09:00", "DISPONIBLE"),
            ("10:00", "DISPONIBLE"),
        ]
    
    # Ouverture de l'image de base en RGBA unique pour tout le pipeline
    canvas = Image.open(image_path).convert("RGBA")

    # Application séquentielle des éléments
    draw_schedule_grid(canvas, schedule_items_simple, 5,4)
    add_footer(canvas, IMG_FOLDER / "Footer.png")
    add_header_logo(canvas, IMG_FOLDER / "LogoBananaPadel.png", "TERRAIN SIMPLE")

    # Conversion finale en RGB pour le format JPG et sauvegarde
    final_image = canvas.convert("RGB")
    output_path = RES_FOLDER / "planning_simple.jpg"
    final_image.save(output_path, quality=95)
    print(f"Image enregistrée avec succès : {output_path}")


if __name__ == "__main__":
    main()
