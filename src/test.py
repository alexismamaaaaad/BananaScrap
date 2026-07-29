import sys
import time
import unicodedata
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
except ImportError:
    raise SystemExit("Selenium n'est pas installé. Exécutez : pip install selenium")

# ==============================================================================
# CONFIGURATION ET CONSTANTES
# ==============================================================================
SRC_FOLDER = Path.cwd()
RES_FOLDER = Path.cwd().parent / "results/"
FNT_FOLDER = Path.cwd().parent / "fonts/"
BCK_FOLDER = Path.cwd().parent / "backgrounds/"
IMG_FOLDER = Path.cwd().parent / "img/"

COLOR_WHITE = (255, 255, 255)
COLOR_BLACK = (0, 0, 0)
COLOR_GOLD = (253, 202, 55)
COLOR_BLUE = (33, 103, 187)
COLOR_RED = (220, 50, 50)
COLOR_DISABLED_BG = (44, 44, 44)

COLUMN_LABELS = ["MIDI", "APRES-MIDI", "SOIREE", "DEM. MATIN"]

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


DAY1_ALLOWED_HOURS = {
    "10h30", "11h00", "12h00", "12h30", "13h00", "13h30", "14h00", 
    "14h30", "15h00",  "16h00",  "16h30", "17h00", "18h00", "18h30",  "19h00",
    "19h30", "20h00", "21h00", "21h30",  "22h00",  "22h30", "23h00",
    
}

DAY2_ALLOWED_HOURS = {
    "06h00", "06h30",  "07h00", "07h30", "08h00", "09h00", "09h30",
    "10h00",
}



# ==============================================================================
# FONCTIONS SELENIUM & NAVIGATION
# ==============================================================================
def normalize_text(text: str) -> str:
    if text is None:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("\xa0", " ")
    text = text.lower()
    text = " ".join(text.split())
    return text


def page_contains_text(driver: webdriver.Chrome, expected_text: str) -> bool:
    expected_text = normalize_text(expected_text)
    try:
        if expected_text in normalize_text(driver.page_source):
            return True
    except Exception:
        pass

    try:
        if expected_text in normalize_text(driver.find_element(By.TAG_NAME, "body").text):
            return True
    except Exception:
        pass

    return False


def wait_for_dynamic_page(driver: webdriver.Chrome, timeout: int = 20, markers: list[str] | None = None) -> None:
    start_time = time.time()
    previous_url = driver.current_url
    markers = markers or ["planning", "reserver", "reservation", "nouvelle reservation", "btn-horaires"]

    while time.time() - start_time < timeout:
        if driver.current_url != previous_url:
            print(f"[DEBUG] Navigation : {previous_url} -> {driver.current_url}")
            return

        if any(page_contains_text(driver, marker) for marker in markers):
            print("[DEBUG] Page dynamique prête.")
            return

        try:
            if driver.find_elements(By.XPATH, "//button[contains(@class, 'btn-horaires')]"):
                print("[DEBUG] Boutons horaires détectés.")
                return
        except Exception:
            pass

        time.sleep(0.5)

    print("[DEBUG] Timeout de l'attente dynamique.")


def submit_login_form(driver: webdriver.Chrome, login_element, password_element) -> None:
    submit_buttons = driver.find_elements(
        By.XPATH,
        "//button[@type='submit'] | //input[@type='submit'] | //button[contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'connexion')]"
    )

    if submit_buttons:
        print("[DEBUG] Clic sur le bouton de connexion.")
        submit_buttons[0].click()
    else:
        print("[DEBUG] Pas de bouton trouvé, touche Entrée.")
        password_element.send_keys(Keys.ENTER)


def close_popup_if_present(driver: webdriver.Chrome, timeout: int = 5) -> None:
    try:
        close_button = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, "//button[@type='button' and @class='close' and @data-dismiss='modal']"))
        )
        close_button.click()
        print("[DEBUG] Popup fermée.")
    except Exception:
        print("[DEBUG] Aucune popup à fermer.")


def click_reservation_div_if_present(driver: webdriver.Chrome, timeout: int = 2) -> None:
    try:
        reservation_div = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, "//div[.//a[contains(@href, \"javascript:myLoad('/prereservation.asp')\")]]"))
        )
        reservation_div.click()
        print("[DEBUG] Conteneur 'Réserver' cliqué.")
    except Exception:
        print("[DEBUG] Conteneur 'Réserver' non trouvé.")


def click_back_div_if_present(driver: webdriver.Chrome, timeout: int = 10) -> None:
    try:
        driver.execute_script("if (window.myLoad) { window.myLoad('/prereservation.asp'); }")
        print("[DEBUG] Back exécuté via myLoad.")
    except Exception as e:
        print(f"[DEBUG] Erreur lors du clic retour : {e}")


def click_reservation_double_if_present(driver: webdriver.Chrome, timeout: int = 10) -> None:
    try:
        driver.execute_script("if (window.myLoad) { window.myLoad('/reservation_capsule.asp?id_sport=2'); }")
        print("[DEBUG] Navigation Terrains Doubles (id_sport=2) exécutée.")
    except Exception as e:
        print(f"[DEBUG] Erreur clic Doubles : {e}")


def click_reservation_single_if_present(driver: webdriver.Chrome, timeout: int = 10) -> None:
    try:
        driver.execute_script("if (window.myLoad) { window.myLoad('/reservation_capsule.asp?id_sport=7'); }")
        print("[DEBUG] Navigation Terrain Simple (id_sport=7) exécutée.")
    except Exception as e:
        print(f"[DEBUG] Erreur clic Simple : {e}")


def get_choosepop_buttons_status(driver: webdriver.Chrome, timeout: int = 2) -> list[dict[str, str]]:
    results = []
    try:
        buttons = WebDriverWait(driver, timeout).until(
            lambda d: d.find_elements(By.XPATH, "//button[contains(@class, 'btn-horaires')]")
        )
    except Exception:
        print("[DEBUG] Aucun bouton .btn-horaires trouvé dans le DOM.")
        return results

    print(f"[DEBUG] Nombre de boutons .btn-horaires trouvés sur la page : {len(buttons)}")

    for button in buttons:
        raw_label = (button.text or "").replace("\xa0", " ").strip()
        label = "\n".join(raw_label.splitlines()[:1]).strip()
        is_enabled = button.is_enabled()
        status = "available" if is_enabled else "unavailable"
        results.append({"LABEL": label, "STATUS": status})

    return results


def click_tomorrow_time_element(driver: webdriver.Chrome) -> bool:
    print("\n--- [DEBUG] RECHERCHE DE L'ÉLÉMENT DEMAIN ---")
    try:
        xpath = "//time[contains(@class, 'icon') and not(contains(@class, 'active')) and not(contains(@class, 'iconWhite'))]"
        tomorrow_elements = driver.find_elements(By.XPATH, xpath)

        if not tomorrow_elements:
            print("[DEBUG ERR] Impossible de trouver le bloc pour Demain.")
            return False

        target_el = tomorrow_elements[0]
        onclick_attr = target_el.get_attribute("onclick") or ""
        print(f"[DEBUG] Élément Demain ciblé : text='{target_el.text.strip()}' | onclick='{onclick_attr}'")

        if "viewD" in onclick_attr:
            driver.execute_script(onclick_attr)
            print(f"[DEBUG] JS viewD exécuté avec succès : {onclick_attr}")
            return True
        else:
            driver.execute_script("arguments[0].click();", target_el)
            print("[DEBUG] Fallback clic JS exécuté.")
            return True

    except Exception as exc:
        print(f"[DEBUG ERR] Erreur lors du basculement sur Demain : {exc}")
        return False


def launch_and_fill(url: str, login_value: str, password_value: str) -> tuple[list[dict], list[dict]]:
    t0 = time.perf_counter()
    options = Options()
    options.add_argument("--start-maximized")

    service = ChromeService()
    driver = webdriver.Chrome(service=service, options=options)

    data_double = []
    data_single = []

    try:
        print("\n--- [DEBUG] CONNEXION ET NAVIGATION INITIALE ---")
        driver.get(url)
        time.sleep(2)

        login_fields = driver.find_elements(By.NAME, "email")
        password_fields = driver.find_elements(By.NAME, "mot_de_passe")

        if not login_fields or not password_fields:
            raise RuntimeError("Champs de connexion introuvables.")

        login_fields[0].clear()
        login_fields[0].send_keys(login_value)
        password_fields[0].clear()
        password_fields[0].send_keys(password_value)

        submit_login_form(driver, login_fields[0], password_fields[0])
        wait_for_dynamic_page(driver, timeout=4)
        close_popup_if_present(driver)
        click_reservation_div_if_present(driver)
        time.sleep(0.5)

        # ----------------------------------------------------------------------
        # Execution 1 : DOUBLE
        # ----------------------------------------------------------------------
        print("\n--- [DEBUG] SCRAPING DOUBLES - PASSAGE 1 (Aujourd'hui) ---")
        click_reservation_double_if_present(driver)
        wait_for_dynamic_page(driver, timeout=3, markers=["nouvelle reservation", "reserver", "btn-horaires"])
        
        raw_day1 = get_choosepop_buttons_status(driver)
        print(f"[DEBUG] Boutons bruts extraits Jour 1 ({len(raw_day1)}) : {[x['LABEL'] for x in raw_day1]}")

        data_double = [item for item in raw_day1 if item["LABEL"] in DAY1_ALLOWED_HOURS]

        print("\n--- [DEBUG] SCRAPING DOUBLES - PASSAGE 2 (Demain) ---")
        if click_tomorrow_time_element(driver):
            time.sleep(2.0)
            raw_day2 = get_choosepop_buttons_status(driver)
            morning_slots_day2 = [item for item in raw_day2 if item["LABEL"] in DAY2_ALLOWED_HOURS]
            data_double.extend(morning_slots_day2)
        else:
            print("[DEBUG ERR] Échec basculement sur Demain pour Doubles.")

        click_back_div_if_present(driver)
        time.sleep(0.5)

        # ----------------------------------------------------------------------
        # Execution 2 : SINGLE
        # ----------------------------------------------------------------------
        print("\n--- [DEBUG] SCRAPING SIMPLE - PASSAGE 1 (Aujourd'hui) ---")
        click_reservation_single_if_present(driver)
        wait_for_dynamic_page(driver, timeout=4, markers=["nouvelle reservation", "reserver", "btn-horaires"])
        
        raw_single_day1 = get_choosepop_buttons_status(driver)
        data_single = [item for item in raw_single_day1 if item["LABEL"] in DAY1_ALLOWED_HOURS]

        print("\n--- [DEBUG] SCRAPING SIMPLE - PASSAGE 2 (Demain) ---")
        if click_tomorrow_time_element(driver):
            time.sleep(2.0)
            raw_single_day2 = get_choosepop_buttons_status(driver)
            morning_slots_single_day2 = [item for item in raw_single_day2 if item["LABEL"] in DAY2_ALLOWED_HOURS]
            data_single.extend(morning_slots_single_day2)
        else:
            print("[DEBUG ERR] Échec basculement sur Demain pour Simple.")

    finally:
        driver.quit()
        print(f"\n[DEBUG] Durée totale navigateur : {time.perf_counter() - t0:.2f}s")

    return data_double, data_single


# ==============================================================================
# FONCTIONS UTILITAIRES & RENDU PILLOW (DE GENERATERESAS)
# ==============================================================================
def find_single_jpg(path: Path) -> Path:
    jpg_files = sorted(path.glob("template_story_creneaux.jpg"))
    if len(jpg_files) == 1:
        return jpg_files[0]
    raise FileNotFoundError(f"Fichier .jpg source introuvable dans {path}")


def load_font(name: str | None, size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if name:
        try:
            return ImageFont.truetype(FNT_FOLDER / name, size)
        except Exception:
            pass

    candidates = PREFERRED_FONTS if bold else reversed(PREFERRED_FONTS)
    for font_name in candidates:
        try:
            return ImageFont.truetype(FNT_FOLDER / font_name, size)
        except Exception:
            continue

    return ImageFont.load_default()


def calculate_grid_metrics(width: int, height: int, rows: int = 6, cols: int = 4) -> dict:
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


def update_schedule_items(base_schedule: list[tuple[str, str]], dynamic_data: list[dict[str, str]]) -> list[tuple[str, str]]:
    status_map = {}
    for item in dynamic_data:
        label = item.get("LABEL", "").replace("h", ":").strip()
        status_map[label] = item.get("STATUS", "unavailable")

    updated_schedule = []
    for hour, status in base_schedule:
        if status == "ABSENT" or not hour:
            updated_schedule.append((hour, "ABSENT"))
        else:
            fetched_status = status_map.get(hour)
            if fetched_status == "available":
                new_status = "DISPONIBLE"
            elif fetched_status == "unavailable":
                new_status = "INDISPONIBLE"
            else:
                new_status = status

            updated_schedule.append((hour, new_status))

    return updated_schedule


def add_header_logo(image: Image.Image, logo_path: Path, Title: str) -> None:
    if not logo_path.exists():
        print(f"Fichier Logo introuvable : {logo_path}")
        return

    logo = Image.open(logo_path).convert("RGBA")
    max_height = int(image.height * 0.20)
    logo = ImageOps.contain(logo, (image.width, max_height))

    x_logo = (image.width - logo.width) // 2
    y_logo = int(image.height * 0.02)
    image.paste(logo, (x_logo, y_logo), logo)

    draw = ImageDraw.Draw(image)
    font_title = load_font("JandaManateeSolid.ttf", max(24, int(image.height * 0.036)))
    font_subtitle = load_font("JandaManateeSolid.ttf", max(24, int(image.height * 0.05)))

    title_text = "NOS CRENEAUX DISPONIBLES"

    bbox_title = draw.textbbox((0, 0), title_text, font=font_title)
    draw.text(
        ((image.width - (bbox_title[2] - bbox_title[0])) // 2, logo.height * 1.2),
        title_text,
        fill=COLOR_GOLD,
        font=font_title,
    )

    bbox_sub = draw.textbbox((0, 0), Title, font=font_subtitle)
    draw.text(
        ((image.width - (bbox_sub[2] - bbox_sub[0])) // 2, logo.height * 1.45),
        Title,
        fill=COLOR_BLACK,
        font=font_subtitle,
    )


def draw_schedule_grid(image: Image.Image, schedule_items: list[tuple[str, str]], rows: int, cols: int) -> None:
    draw = ImageDraw.Draw(image)
    metrics = calculate_grid_metrics(image.width, image.height, rows, cols)

    cols, rows = metrics["cols"], metrics["rows"]
    cell_w, cell_h = metrics["cell_width"], metrics["cell_height"]
    size_w, size_h = metrics["size_w"], metrics["size_h"]
    top_margin, left_margin = metrics["top_margin"], metrics["left_margin"]

    radius = int(min(size_w, size_h) * 0.48)
    for row in range(rows):
        for col in range(cols):
            idx = col * rows + row
            status = schedule_items[idx][1] if idx < len(schedule_items) else "DISPONIBLE"
            is_available = status.lower().startswith("disponible")
            fill_color = COLOR_WHITE if is_available else COLOR_DISABLED_BG
            outline_color = COLOR_BLUE if is_available else COLOR_WHITE
        
            x_center = left_margin + (col + 0.5) * cell_w
            y_center = top_margin + (row + 0.5) * cell_h

            if idx < len(schedule_items) and schedule_items[idx][1] != "ABSENT":
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

    font_header = load_font(None, max(12, int(cell_w * 0.14)), bold=True)
    icon_width = int(cell_w * 0.35)
    icon_text_gap = int(image.height * 0.008)

    for col, (label, icon_name) in enumerate(zip(COLUMN_LABELS, COLUMN_ICONS)):
        x_center = left_margin + (col + 0.5) * cell_w
        icon_path = IMG_FOLDER / icon_name
        
        if icon_path.exists():
            icon = Image.open(icon_path).convert("RGBA")
            ratio = icon.height / icon.width
            icon = ImageOps.contain(icon, (icon_width, int(icon_width * ratio)))

            icon_x = int(x_center - icon.width / 2)
            icon_y = int(top_margin - image.height * 0.075)

            alpha = icon.getchannel("A")
            black_alpha = alpha.filter(ImageFilter.MaxFilter(3))
            black_outline = Image.new("RGBA", icon.size, (0, 0, 0, 0))
            black_outline.putalpha(black_alpha)

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

    time_font = load_font("Montserrat-Regular.ttf", int(cell_w * 0.25), bold=False)
    status_font = load_font(None, int(cell_w * 0.095), bold=True)

    for idx, (time_text, status_text) in enumerate(schedule_items[: rows * cols]):
        col = idx // rows
        row = idx % rows
        x_center = left_margin + (col + 0.5) * cell_w
        y_center = top_margin + (row + 0.45) * cell_h

        if status_text.lower().startswith("disponible"):
            colorHour = COLOR_BLACK
        else:
            colorHour = COLOR_WHITE

        t_bbox = draw.textbbox((0, 0), time_text, font=time_font)
        t_w, t_h = t_bbox[2] - t_bbox[0], t_bbox[3] - t_bbox[1]

        draw.text(
            (x_center - t_w / 2, y_center - t_h / 2 - int(size_h * 0.2)),
            time_text,
            fill=colorHour,
            font=time_font,
        )

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
            pass
        else:
            cross_size = int(min(size_w, size_h) * 0.18)
            thickness = max(2, int(cross_size * 0.30))
            cx, cy = x_center, y_center + int(size_h * 0.3)

            draw.line((cx - cross_size / 2, cy - cross_size / 2, cx + cross_size / 2, cy + cross_size / 2), fill=COLOR_RED, width=thickness)
            draw.line((cx - cross_size / 2, cy + cross_size / 2, cx + cross_size / 2, cy - cross_size / 2), fill=COLOR_RED, width=thickness)


def add_footer(image: Image.Image, footer_path: Path) -> None:
    if not footer_path.exists():
        print(f"Fichier Footer introuvable : {footer_path}")
        return

    footer = Image.open(footer_path).convert("RGBA")
    footer = ImageOps.contain(footer, (int(image.width * 1.0), int(image.height * 0.16)))

    x_footer = (image.width - footer.width) // 2
    y_footer = image.height - footer.height
    image.paste(footer, (x_footer, y_footer), footer)

    draw = ImageDraw.Draw(image)
    main_font = load_font("JandaManateeSolid.ttf", max(20, int(image.height * 0.035)))
    sub_font = load_font(None, max(16, int(image.height * 0.02)), bold=False)

    text_main = "Réservez votre créneau en ligne !"
    text_sub = "Apple Store, Google Play ou site internet en bio !"

    bbox_m = draw.textbbox((0, 0), text_main, font=main_font)
    text_y = image.height - int(image.height * 0.081)
    draw.text(
        ((image.width - (bbox_m[2] - bbox_m[0])) // 2, text_y),
        text_main,
        fill=COLOR_GOLD,
        font=main_font,
    )

    bbox_s = draw.textbbox((0, 0), text_sub, font=sub_font)
    draw.text(
        ((image.width - (bbox_s[2] - bbox_s[0])) // 2, text_y + int(image.height * 0.05)),
        text_sub,
        fill=COLOR_WHITE,
        font=sub_font,
    )


# ==============================================================================
# MAIN EXECUTABLE
# ==============================================================================
def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python script_final.py <login> <mot_de_passe>")
        sys.exit(1)

    url = "https://banana-padel.mymobileapp.fr/"
    login_value = sys.argv[1]
    password_value = sys.argv[2]

    # Scraping des données dynamique via Selenium
    data_double, data_single = launch_and_fill(url, login_value, password_value)

    # Grille Modèle (Template)
    template_items_single = [
        ("11:00", ""), ("12:00", ""),
        ("13:00", ""), ("14:00", ""),  ("", "ABSENT"),
        ("15:00", ""), ("16:00", ""),
        ("17:00", ""), ("18:00", ""), ("", "ABSENT"),
        ("19:00", ""), ("20:00", ""), ("21:00", ""),
        ("22:00", ""), ("23:00", ""), 
        ("06:00", ""), ("07:00", ""), 
        ("08:00", ""), ("09:00", ""),   ("10:00", ""), 
    ]

    template_items_double = [
        ("10:30", ""), ("11:00", ""), ("12:00", ""),
        ("12:30", ""), ("13:30", ""), ("14:00", ""),
        ("15:00", ""), ("15:30", ""), ("16:30", ""),
        ("17:00", ""), ("18:00", ""), ("18:30", ""),
        ("19:30", ""), ("20:00", ""), ("21:00", ""),
        ("21:30", ""), ("22:30", ""), ("23:00", ""),
        ("06:00", ""), ("06:30", ""), ("07:30", ""),
        ("08:00", ""), ("09:00", ""), ("09:30", ""),
    ]

    schedule_items_double = update_schedule_items(template_items_double, data_double)
    schedule_items_single = update_schedule_items(template_items_single, data_single)

    # Recherche du template de fond
    image_path = find_single_jpg(BCK_FOLDER)

    # --------------------------------------------------------------------------
    # GENERATION IMAGE DOUBLES (GRILLE 6x4)
    # --------------------------------------------------------------------------
    canvas_double = Image.open(image_path).convert("RGBA")
    draw_schedule_grid(canvas_double, schedule_items_double, 6, 4)
    add_footer(canvas_double, IMG_FOLDER / "Footer.png")
    add_header_logo(canvas_double, IMG_FOLDER / "LogoBananaPadel.png", "TERRAINS DOUBLES")

    RES_FOLDER.mkdir(parents=True, exist_ok=True)
    out_double = RES_FOLDER / "planning_double.jpg"
    canvas_double.convert("RGB").save(out_double, quality=95)
    print(f"[SUCCÈS] Image enregistrée : {out_double}")

    # --------------------------------------------------------------------------
    # GENERATION IMAGE SIMPLE (GRILLE 5x4)
    # --------------------------------------------------------------------------
    canvas_single = Image.open(image_path).convert("RGBA")
    draw_schedule_grid(canvas_single, schedule_items_single, 5, 4)
    add_footer(canvas_single, IMG_FOLDER / "Footer.png")
    add_header_logo(canvas_single, IMG_FOLDER / "LogoBananaPadel.png", "TERRAIN SIMPLE")

    out_single = RES_FOLDER / "planning_simple.jpg"
    canvas_single.convert("RGB").save(out_single, quality=95)
    print(f"[SUCCÈS] Image enregistrée : {out_single}")


if __name__ == "__main__":
    main()