import sys
import time
import random
import unicodedata
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

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
COLOR_RED = (220, 50, 50)
COLOR_DISABLED_BG = (44, 44, 44)
COLOR_BLUE = (33, 103, 187)

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
# FONCTIONS LOGGING & FORMATAGE
# ==============================================================================
def log_step(step_title: str) -> None:
    print("\n" + "=" * 80)
    print(f"  {step_title}")
    print("=" * 80)

def log_substep(substep_title: str) -> None:
    print(f"\n--- [{substep_title}] ---")

def log_info(msg: str) -> None:
    print(f"[INFO] {msg}")

def log_warn(msg: str) -> None:
    print(f"[WARN] {msg}")

def log_err(msg: str) -> None:
    print(f"[ERROR] {msg}")


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
            log_info(f"Navigation détectée : {previous_url} -> {driver.current_url}")
            return

        if any(page_contains_text(driver, marker) for marker in markers):
            log_info("Page dynamique prête (marqueurs trouvés).")
            return

        try:
            if driver.find_elements(By.XPATH, "//button[contains(@class, 'btn-horaires')]"):
                log_info("Boutons .btn-horaires détectés dans le DOM.")
                return
        except Exception:
            pass

        time.sleep(0.5)

    log_warn("Timeout lors de l'attente de la page dynamique.")


def submit_login_form(driver: webdriver.Chrome, login_element, password_element) -> None:
    submit_buttons = driver.find_elements(
        By.XPATH,
        "//button[@type='submit'] | //input[@type='submit'] | //button[contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'connexion')]"
    )

    if submit_buttons:
        log_info("Soumission du formulaire via clic sur le bouton Connexion.")
        submit_buttons[0].click()
    else:
        log_info("Bouton de connexion non trouvé, soumission via touche Entrée.")
        password_element.send_keys(Keys.ENTER)


def close_popup_if_present(driver: webdriver.Chrome, timeout: int = 5) -> None:
    try:
        close_button = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, "//button[@type='button' and @class='close' and @data-dismiss='modal']"))
        )
        close_button.click()
        log_info("Popup d'information fermée.")
    except Exception:
        log_info("Aucune popup à fermer.")


def click_reservation_div_if_present(driver: webdriver.Chrome, timeout: int = 2) -> None:
    try:
        reservation_div = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, "//div[.//a[contains(@href, \"javascript:myLoad('/prereservation.asp')\")]]"))
        )
        reservation_div.click()
        log_info("Onglet/Conteneur 'Réserver' cliqué.")
    except Exception:
        log_warn("Conteneur 'Réserver' non trouvé.")


def click_back_div_if_present(driver: webdriver.Chrome, timeout: int = 10) -> None:
    try:
        driver.execute_script("if (window.myLoad) { window.myLoad('/prereservation.asp'); }")
        log_info("Retour à l'accueil préréservation via myLoad.")
    except Exception as e:
        log_err(f"Erreur lors de la réinitialisation de la vue retour : {e}")


def click_reservation_double_if_present(driver: webdriver.Chrome, timeout: int = 10) -> None:
    try:
        driver.execute_script("if (window.myLoad) { window.myLoad('/reservation_capsule.asp?id_sport=2'); }")
        log_info("Accès aux Terrains DOUBLES (id_sport=2).")
    except Exception as e:
        log_err(f"Erreur navigation Terrains Doubles : {e}")


def click_reservation_single_if_present(driver: webdriver.Chrome, timeout: int = 10) -> None:
    try:
        driver.execute_script("if (window.myLoad) { window.myLoad('/reservation_capsule.asp?id_sport=7'); }")
        log_info("Accès au Terrain SIMPLE (id_sport=7).")
    except Exception as e:
        log_err(f"Erreur navigation Terrain Simple : {e}")


def get_choosepop_buttons_status(driver: webdriver.Chrome, timeout: int = 2) -> list[dict[str, str]]:
    results = []
    try:
        buttons = WebDriverWait(driver, timeout).until(
            lambda d: d.find_elements(By.XPATH, "//button[contains(@class, 'btn-horaires')]")
        )
    except Exception:
        log_warn("Aucun bouton .btn-horaires trouvé dans la page.")
        return results

    log_info(f"Nombre total de créneaux bruts détectés dans le DOM : {len(buttons)}")

    for button in buttons:
        raw_label = (button.text or "").replace("\xa0", " ").strip()
        label = "\n".join(raw_label.splitlines()[:1]).strip()
        is_enabled = button.is_enabled()
        status = "available" if is_enabled else "unavailable"
        
        print(f"   ↳ [RAW SELENIUM] Horaire: '{label}' | IsEnabled: {is_enabled} -> Status: {status}")
        results.append({"LABEL": label, "STATUS": status})

    return results


def click_tomorrow_time_element(driver: webdriver.Chrome) -> bool:
    log_substep("NAVIGATION VERs DEMAIN")
    try:
        xpath = "//time[contains(@class, 'icon') and not(contains(@class, 'active')) and not(contains(@class, 'iconWhite'))]"
        tomorrow_elements = driver.find_elements(By.XPATH, xpath)

        if not tomorrow_elements:
            log_err("Impossible de localiser le sélecteur pour Demain.")
            return False

        target_el = tomorrow_elements[0]
        onclick_attr = target_el.get_attribute("onclick") or ""
        log_info(f"Bloc Demain trouvé : texte='{target_el.text.strip()}' | onclick='{onclick_attr}'")

        if "viewD" in onclick_attr:
            driver.execute_script(onclick_attr)
            log_info("Basculement sur l'onglet Demain effectué via JavaScript viewD.")
            return True
        else:
            driver.execute_script("arguments[0].click();", target_el)
            log_info("Basculement sur Demain effectué via clic classique.")
            return True

    except Exception as exc:
        log_err(f"Exception lors du basculement sur la journée de Demain : {exc}")
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
        log_step("ÉTAPE 1/5 : CONNEXION ET NAVIGATION INITIALE")
        log_info(f"Ouverture de l'URL : {url}")
        driver.get(url)
        time.sleep(2)

        login_fields = driver.find_elements(By.NAME, "email")
        password_fields = driver.find_elements(By.NAME, "mot_de_passe")

        if not login_fields or not password_fields:
            raise RuntimeError("Formulaire de connexion inaccessible ou non trouvé.")

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
        # Scraping : DOUBLES
        # ----------------------------------------------------------------------
        log_step("ÉTAPE 2/5 : SCRAPING - TERRAINS DOUBLES")
        
        log_substep("DOUBLES - Passage 1 : Aujourd'hui")
        click_reservation_double_if_present(driver)
        wait_for_dynamic_page(driver, timeout=3, markers=["nouvelle reservation", "reserver", "btn-horaires"])
        
        raw_double_day1 = get_choosepop_buttons_status(driver)
        filtered_double_day1 = [item for item in raw_double_day1 if item["LABEL"] in DAY1_ALLOWED_HOURS]
        data_double.extend(filtered_double_day1)
        log_info(f"DOUBLES Jour 1 -> Reçus: {len(raw_double_day1)} | Conservés: {len(filtered_double_day1)}")

        log_substep("DOUBLES - Passage 2 : Demain Matin")
        if click_tomorrow_time_element(driver):
            time.sleep(2.0)
            raw_double_day2 = get_choosepop_buttons_status(driver)
            filtered_double_day2 = [item for item in raw_double_day2 if item["LABEL"] in DAY2_ALLOWED_HOURS]
            data_double.extend(filtered_double_day2)
            log_info(f"DOUBLES Jour 2 -> Reçus: {len(raw_double_day2)} | Conservés: {len(filtered_double_day2)}")
        else:
            log_err("Échec de la récupération pour le lendemain (DOUBLES).")

        click_back_div_if_present(driver)
        time.sleep(0.5)

        # ----------------------------------------------------------------------
        # Scraping : SINGLE
        # ----------------------------------------------------------------------
        log_step("ÉTAPE 3/5 : SCRAPING - TERRAIN SIMPLE")
        
        log_substep("SIMPLE - Passage 1 : Aujourd'hui")
        click_reservation_single_if_present(driver)
        wait_for_dynamic_page(driver, timeout=4, markers=["nouvelle reservation", "reserver", "btn-horaires"])
        
        raw_single_day1 = get_choosepop_buttons_status(driver)
        filtered_single_day1 = [item for item in raw_single_day1 if item["LABEL"] in DAY1_ALLOWED_HOURS]
        data_single.extend(filtered_single_day1)
        log_info(f"SIMPLE Jour 1 -> Reçus: {len(raw_single_day1)} | Conservés: {len(filtered_single_day1)}")

        log_substep("SIMPLE - Passage 2 : Demain Matin")
        if click_tomorrow_time_element(driver):
            time.sleep(2.0)
            raw_single_day2 = get_choosepop_buttons_status(driver)
            filtered_single_day2 = [item for item in raw_single_day2 if item["LABEL"] in DAY2_ALLOWED_HOURS]
            data_single.extend(filtered_single_day2)
            log_info(f"SIMPLE Jour 2 -> Reçus: {len(raw_single_day2)} | Conservés: {len(filtered_single_day2)}")
        else:
            log_err("Échec de la récupération pour le lendemain (SIMPLE).")

    finally:
        driver.quit()
        log_info(f"Fermeture du navigateur. Temps total de scraping : {time.perf_counter() - t0:.2f}s")

    return data_double, data_single


# ==============================================================================
# MAPPING DE LA GRILLE & GENERATION PILLOW
# ==============================================================================
def load_best_font(font_names: list[str], size: int) -> ImageFont.FreeTypeFont:
    for name in font_names:
        font_path = FNT_FOLDER / name
        if font_path.exists():
            try:
                return ImageFont.truetype(str(font_path), size)
            except Exception:
                pass
    return ImageFont.load_default()


def update_schedule_items(
    base_schedule: list[tuple[str, str]], dynamic_data: list[dict[str, str]]
) -> list[tuple[str, str]]:
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


def draw_slot_pill(
    draw: ImageDraw.ImageDraw,
    x: float,
    y: float,
    width: float,
    height: float,
    text: str,
    status: str,
    font: ImageFont.FreeTypeFont,
) -> None:
    radius = height / 2.0
    rect = [x, y, x + width, y + height]

    if status == "DISPONIBLE":
        bg_color = COLOR_GOLD
        text_color = COLOR_BLACK
    else:
        bg_color = COLOR_DISABLED_BG
        text_color = COLOR_WHITE

    draw.rounded_rectangle(rect, radius=radius, fill=bg_color)

    if status == "INDISPONIBLE":
        inner_margin = 3.0
        inner_rect = [x + inner_margin, y + inner_margin, x + width - inner_margin, y + height - inner_margin]
        inner_radius = max(1.0, radius - inner_margin)
        draw.rounded_rectangle(inner_rect, radius=inner_radius, outline=COLOR_RED, width=3)

    bbox = font.getbbox(text)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    tx = x + (width - text_w) / 2.0 - bbox[0]
    ty = y + (height - text_h) / 2.0 - bbox[1]
    draw.text((tx, ty), text, fill=text_color, font=font)


def render_schedule_image(
    background_path: Path,
    schedule_items: list[tuple[str, str]],
    output_path: Path,
    bottom_title_text: str = "TERRAINS DOUBLES",
) -> None:
    log_substep(f"RENDU VISUEL : {bottom_title_text}")
    log_info(f"Fond sélectionné : {background_path.name}")
    log_info(f"Fichier de sortie : {output_path.name}")

    if not background_path.exists():
        log_err(f"Image d'arrière-plan introuvable : {background_path}")
        return

    base_img = Image.open(background_path).convert("RGBA")
    W, H = base_img.size

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font_label = load_best_font(PREFERRED_FONTS, 32)
    font_slot = load_best_font(PREFERRED_FONTS, 28)
    font_title = load_best_font(PREFERRED_FONTS, 58)

    pad_x = 40.0
    gap_x = 20.0
    col_width = (W - (2 * pad_x) - (3 * gap_x)) / 4.0

    pill_w = col_width
    pill_h = 42.0
    row_gap = 12.0
    header_h = 100.0
    start_y = 175.0

    # Colonnes Header
    for c_idx in range(4):
        cx = pad_x + c_idx * (col_width + gap_x)
        icon_name = COLUMN_ICONS[c_idx]
        icon_path = IMG_FOLDER / icon_name
        
        if icon_path.exists():
            icon_img = Image.open(icon_path).convert("RGBA")
            target_h = 42
            aspect = icon_img.width / icon_img.height
            target_w = int(target_h * aspect)
            icon_resized = icon_img.resize((target_w, target_h), Image.LANCZOS)

            ix = int(cx + (col_width - target_w) / 2.0)
            iy = int(start_y)
            overlay.paste(icon_resized, (ix, iy), icon_resized)

        lbl = COLUMN_LABELS[c_idx]
        bbox = font_label.getbbox(lbl)
        lw = bbox[2] - bbox[0]
        lx = cx + (col_width - lw) / 2.0 - bbox[0]
        ly = start_y + 48.0
        draw.text((lx, ly), lbl, fill=COLOR_WHITE, font=font_label)

    grid_y = start_y + header_h

    # Grille des créneaux
    for idx, (hour, status) in enumerate(schedule_items):
        r_idx = idx % 6
        c_idx = idx // 6

        if c_idx >= 4:
            break

        if status == "ABSENT" or not hour:
            continue

        cx = pad_x + c_idx * (col_width + gap_x)
        cy = grid_y + r_idx * (pill_h + row_gap)

        draw_slot_pill(draw, cx, cy, pill_w, pill_h, hour, status, font_slot)

    # Titre Bas
    title_bbox = font_title.getbbox(bottom_title_text)
    tw = title_bbox[2] - title_bbox[0]
    tx = (W - tw) / 2.0 - title_bbox[0]
    ty = H - 140.0
    draw.text((tx, ty), bottom_title_text, fill=COLOR_WHITE, font=font_title)

    final_img = Image.alpha_composite(base_img, overlay)
    RES_FOLDER.mkdir(parents=True, exist_ok=True)
    final_img.convert("RGB").save(output_path, quality=95)
    log_info(f"Image enregistrée avec succès -> {output_path}")


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

    # Scraping des données via Selenium
    data_double, data_single = launch_and_fill(url, login_value, password_value)

    # Grille Modèle (Template)
    template_items_single = [
        ("11:00", ""), ("12:00", ""),
        ("13:00", ""), ("14:00", ""),
        ("15:00", ""), ("16:00", ""),
        ("17:00", ""), ("18:00", ""), 
        ("19:00", ""), ("20:00", ""), ("21:00", ""),
        ("22:00", ""), ("23:00", ""), 
        ("06:00", ""), ("07:00", ""), 
        ("08:00", ""), ("09:00", ""),   ("10:00", ""), 
    ]

    template_items_double = [
        ("10:30", ""), ("11:00", ""), ("12:00", ""),
        ("12:30", ""), ("13:30", ""), ("14:00", ""),
        ("15:00", ""), ("16:30", ""),
        ("17:00", ""), ("18:00", ""), ("18:30", ""),
        ("19:30", ""), ("20:00", ""), ("21:00", ""),
        ("21:30", ""), ("22:30", ""), ("23:00", ""),
        ("06:00", ""), ("06:30", ""), ("07:30", ""),
        ("08:00", ""), ("09:00", ""), ("09:30", ""),
    ]

    log_step("ÉTAPE 4/5 : COMPILATION ET STRUCTURATION DES DONNÉES")
    
    # Injection des statuts scrapés dans le template
    schedule_items_double = update_schedule_items(template_items_double, data_double)
    schedule_items_single = update_schedule_items(template_items_single, data_single)

    log_substep("DONNÉES FINALES INJECTÉES - TERRAINS DOUBLES")
    for hour, status in schedule_items_double:
        print(f"   [{hour}] -> {status}")

    log_substep("DONNÉES FINALES INJECTÉES - TERRAIN SIMPLE")
    for hour, status in schedule_items_single:
        print(f"   [{hour}] -> {status}")

    # Choix de 2 fonds distincts aléatoirement
    log_step("ÉTAPE 5/5 : SÉLECTION DES FONDS ET GÉNÉRATION D'IMAGES")
    bck_images = list(BCK_FOLDER.glob("*.jpg")) + list(BCK_FOLDER.glob("*.png"))
    
    if len(bck_images) >= 2:
        bg_double, bg_single = random.sample(bck_images, 2)
        log_info(f"Deux images de fond distinctes tirées au sort : '{bg_double.name}' et '{bg_single.name}'")
    elif len(bck_images) == 1:
        bg_double = bg_single = bck_images[0]
        log_warn(f"Une seule image trouvée dans {BCK_FOLDER}. Utilisation du même fond.")
    else:
        bg_double = bg_single = BCK_FOLDER / "default.png"
        log_warn("Aucune image de fond trouvée dans le dossier. Mode secours par défaut.")

    # Génération des 2 visuels
    render_schedule_image(
        background_path=bg_double,
        schedule_items=schedule_items_double,
        output_path=RES_FOLDER / "schedule_double.jpg",
        bottom_title_text="TERRAINS DOUBLES",
    )

    render_schedule_image(
        background_path=bg_single,
        schedule_items=schedule_items_single,
        output_path=RES_FOLDER / "schedule_single.jpg",
        bottom_title_text="TERRAIN SIMPLE",
    )

    log_step("TRAITEMENT TERMINÉ AVEC SUCCÈS")


if __name__ == "__main__":
    main()