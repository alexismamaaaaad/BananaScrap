import calendar
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from selenium.webdriver.common.keys import Keys
import pandas as pd
import resend
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options

URL = "https://gestion.livexperience.fr/"

load_dotenv()
resend.api_key = os.getenv("RESEND_API_KEY")
LOGIN = os.getenv("APP_LOG")
PASSWORD = os.getenv("APP_PWD")

OUTPUT_XLSX_PATH = Path(__file__).resolve().parents[1] / "results" / "DailyStats.xlsx"
OUTPUT_TEMPLATE_HTML_PATH = Path(__file__).resolve().parents[1] / "results" / "template_daily_result.html"

STATS_HEADERS = [
    "Date yyyymmdd",
    "Total Payé",
    "Total Frais",
    "Total Club",
    "Total Payé Mois",
    "Total Frais Mois",
    "Total Club Mois",
    "Inscriptions",
    "Réservations",
    "Créneaux joués",
    "Joué Double 1",
    "Joué Double 2",
    "Joué Simple",
    "Annulations",
    "Détail annulations",
]


def log_step(step_name: str):
    """Affiche une bannière claire dans les logs GitHub Actions pour suivre la progression."""
    print(f"\n==================================================")
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] 🚀 ÉTAPE : {step_name}")
    print(f"==================================================")


def capture_debug_artifacts(driver: webdriver.Chrome, prefix: str = "debug_error"):
    """Prend une capture d'écran et sauvegarde le HTML de la page actuelle."""
    try:
        results_dir = Path(__file__).resolve().parents[1] / "results"
        results_dir.mkdir(exist_ok=True, parents=True)
        
        timestamp = datetime.now(timezone.utc).strftime("%H%M%S")
        img_path = results_dir / f"{prefix}_{timestamp}.png"
        html_path = results_dir / f"{prefix}_{timestamp}.html"

        driver.save_screenshot(str(img_path))
        html_path.write_text(driver.page_source, encoding="utf-8")

        print(f"📸 DEBUG Artifacts sauvegardés :")
        print(f"   - Image : {img_path}")
        print(f"   - HTML  : {html_path}")
        print(f"📍 URL courante : {driver.current_url}")
    except Exception as e:
        print(f"⚠️ Impossible de capturer les artefacts : {e}")


def build_driver() -> webdriver.Chrome:
    log_step("Initialisation du driver Chrome")
    options = Options()
        
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    options.add_argument(f"user-agent={user_agent}")

    driver = webdriver.Chrome(options=options)
    print("✅ Driver Chrome créé avec succès.")
    return driver


def wait_for_element(driver: webdriver.Chrome, by: str, value: str, timeout: int = 20):
    print(f"⏳ Attente présence élément : ({by} = '{value}') [Timeout={timeout}s]")
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((by, value))
    )


def wait_for_interactable(driver: webdriver.Chrome, by: str, value: str, timeout: int = 20):
    print(f"⏳ Attente élément cliquable : ({by} = '{value}') [Timeout={timeout}s]")
    return WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((by, value))
    )


def find_clickable_link(driver: webdriver.Chrome, text: str):
    print(f"🔍 Recherche du lien cliquable contenant le texte : '{text}'")
    normalized_text = text.lower()
    candidates = [
        f"//a[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{normalized_text}')]",
        f"//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{normalized_text}')]",
        f"//span[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{normalized_text}')]",
    ]

    for xpath in candidates:
        try:
            elem = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, xpath))
            )
            print(f"✅ Trouvé via XPath : {xpath}")
            return elem
        except Exception:
            continue

    print(f"❌ Échec de recherche du texte : '{text}'")
    raise TimeoutError(f"Unable to find clickable element containing text: {text}")


def save_to_excel(row: list[str]) -> None:
    log_step("Sauvegarde des données dans le fichier Excel")
    OUTPUT_XLSX_PATH.parent.mkdir(exist_ok=True)

    if OUTPUT_XLSX_PATH.exists():
        df = pd.read_excel(OUTPUT_XLSX_PATH)
    else:
        df = pd.DataFrame(columns=STATS_HEADERS)

    if "Date yyyymmdd" not in df.columns:
        df = pd.DataFrame(columns=STATS_HEADERS)

    new_row = pd.DataFrame([row], columns=STATS_HEADERS)
    date_column = "Date yyyymmdd"

    def normalize_date(value) -> str:
        text = str(value).strip()
        if not text:
            return ""
        if text.replace(".", "", 1).isdigit():
            return str(int(float(text)))
        return text

    if date_column in df.columns:
        df[date_column] = df[date_column].apply(normalize_date)

    if date_column in new_row.columns:
        new_row[date_column] = new_row[date_column].apply(normalize_date)

    for column in [
        date_column,
        "Total Payé",
        "Total Frais",
        "Total Club",
        "Total Payé Mois",
        "Total Frais Mois",
        "Total Club Mois",
        "Inscriptions",
        "Réservations",
        "Créneaux joués",
        "Joué Double 1",
        "Joué Double 2",
        "Joué Simple",
        "Annulations",
    ]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
        if column in new_row.columns:
            new_row[column] = pd.to_numeric(new_row[column], errors="coerce")

    date_value = normalize_date(row[0])
    existing_match = None

    if date_column in df.columns:
        for idx, existing_value in enumerate(df[date_column].astype(str).str.strip().tolist()):
            if normalize_date(existing_value) == date_value:
                existing_match = idx
                break

    if existing_match is not None:
        for column in STATS_HEADERS:
            if column in df.columns and column in new_row.columns:
                df.at[existing_match, column] = new_row.iloc[0][column]
    else:
        df = pd.concat([df, new_row], ignore_index=True)

    df.to_excel(OUTPUT_XLSX_PATH, index=False)
    print("✅ Excel sauvegardé.")


def extract_numeric_value(value: str):
    import re
    if value is None:
        return ""

    cleaned = re.sub(r"\s+", "", str(value))
    cleaned = re.sub(r"[^0-9,.-]", "", cleaned)

    if not cleaned:
        return ""

    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")

    try:
        return float(cleaned)
    except ValueError:
        return ""
    

def get_month_progress_days() -> float:
    today = datetime.now(timezone.utc)
    total_days = calendar.monthrange(today.year, today.month)[1]
    return (today.day / total_days) * 100


def build_daily_stats_email_html(stats_row: list[str]) -> str:
    if not OUTPUT_TEMPLATE_HTML_PATH.exists():
        raise FileNotFoundError(f"Template HTML introuvable : {OUTPUT_TEMPLATE_HTML_PATH}")

    html = OUTPUT_TEMPLATE_HTML_PATH.read_text(encoding="utf-8")

    date_value = stats_row[0] if len(stats_row) > 0 else datetime.now(timezone.utc).strftime("%Y%m%d")
    try:
        parsed_date = datetime.strptime(date_value, "%Y%m%d")
        human_date = parsed_date.strftime("%A %d %B %Y")
        human_date = human_date.replace("Monday", "Lundi").replace("Tuesday", "Mardi").replace("Wednesday", "Mercredi").replace("Thursday", "Jeudi").replace("Friday", "Vendredi").replace("Saturday", "Samedi").replace("Sunday", "Dimanche")
        human_date = human_date.replace("January", "janvier").replace("February", "février").replace("March", "mars").replace("April", "avril").replace("May", "mai").replace("June", "juin").replace("July", "juillet").replace("August", "août").replace("September", "septembre").replace("October", "octobre").replace("November", "novembre").replace("December", "décembre")
    except ValueError:
        human_date = date_value

    daily_goal = 240

    def to_number(val, default: float = 0.0) -> float:
        try:
            if val is None or val == "":
                return float(default)
            return float(val)
        except Exception:
            return float(default)

    ca_day = to_number(stats_row[1]) if len(stats_row) > 1 else 0.0
    frais_day = to_number(stats_row[2]) if len(stats_row) > 2 else 0.0
    real_day = to_number(stats_row[3]) if len(stats_row) > 3 else 0.0

    try:
        percent_goal = (ca_day / daily_goal) * 100 - 100
    except Exception:
        percent_goal = 0.0

    month_goal = 7200
    ca_month = to_number(stats_row[4]) if len(stats_row) > 4 else 0.0
    frais_month = to_number(stats_row[5]) if len(stats_row) > 5 else 0.0
    real_month = to_number(stats_row[6]) if len(stats_row) > 6 else 0.0
    percent_of_month_done = get_month_progress_days()
    try:
        goal_today_month = month_goal * percent_of_month_done  / 100
    except Exception:
        goal_today_month = 0.0

    try:
        percent_month_goal = (real_month / goal_today_month) * 100 - 100 if goal_today_month else 0.0
    except Exception:
        percent_month_goal = 0.0

    if percent_goal >= 0:
        DAY_GOAL_STYLE = "background-color:#F0FDF4;border:2px solid #22C55E;"
        DAY_GOAL_TITLE_STYLE = "color:#15803D;"
        DAY_GOAL_VALUE_STYLE = "color:#16A34A;"
    else:
        DAY_GOAL_STYLE = "background-color:#FFF2F2;border:2px solid #E53E3E;"
        DAY_GOAL_TITLE_STYLE = "color:#9B2C2C;"
        DAY_GOAL_VALUE_STYLE = "color:#E53E3E;"

    if percent_month_goal >= 0:
        MONTH_GOAL_STYLE = "background-color:#F0FDF4;border:2px solid #22C55E;"
        MONTH_GOAL_TITLE_STYLE = "color:#15803D;"
        MONTH_GOAL_VALUE_STYLE = "color:#16A34A;"
    else:
        MONTH_GOAL_STYLE = "background-color:#FFF2F2;border:2px solid #E53E3E;"
        MONTH_GOAL_TITLE_STYLE = "color:#9B2C2C;"
        MONTH_GOAL_VALUE_STYLE = "color:#E53E3E;"

    replacements = {
        "{{DATE_DAY}}": human_date,
        "{{CA_DAY}}": str(ca_day) +" €" if len(stats_row) > 1 else "0",
        "{{FRAIS_DAY}}": str(frais_day) +" €" if len(stats_row) > 2 else "0",
        "{{REAL_DAY}}": str(real_day) if len(stats_row) > 3 else "0",
        "{{GOAL_DAY}}": ("✅ +" if ca_day >= daily_goal else "❌ ") + str(round(percent_goal, 2)) + "%",
        "{{CLASS_DAY_GOAL}}": " capsulesuccess " if ca_day >= daily_goal else " capsuleerror ",
        "{{DOUBLE_1}}": str(stats_row[10]) if len(stats_row) > 10 else "0",
        "{{DOUBLE_2}}": str(stats_row[11]) if len(stats_row) > 11 else "0",
        "{{SIMPLE}}": str(stats_row[12]) if len(stats_row) > 12 else "0",
        "{{GOAL_RESA}}": "9",
        "{{GOAL_ANNU}}": "0",
        "{{RESERVATIONS}}": str(stats_row[8]) if len(stats_row) > 8 else "0",
        "{{MATCHS_JOUES}}": str(stats_row[9]) if len(stats_row) > 9 else "0",
        "{{ANNULATIONS}}": str(stats_row[13]) if len(stats_row) > 13 else "0",
        "{{DETAIL_ANNULATIONS}}": (stats_row[14] if len(stats_row) > 14 else "Aucun").replace("\n", "<br>"),
        "{{COMPTES_CREES}}":  str(stats_row[7]) if len(stats_row) > 7 else "0",
        "{{CA_MONTH}}": str(ca_month)+" €"  if len(stats_row) > 4 else "0",
        "{{FRAIS_MONTH}}": str(frais_month)+" €" if len(stats_row) > 5 else "0",
        "{{REAL_MONTH}}": str(real_month)+" €" if len(stats_row) > 6 else "0",
        "{{GOAL_MONTH}}": ("✅ +" if percent_month_goal > 0 else "❌ ") + str(round(percent_month_goal, 2)) + "%",
        "{{CLASS_MONTH_GOAL}}": " capsulesuccess " if percent_month_goal > 0 else " capsuleerror ",
        "{{MONTH_TO_DATE}}": str(round(goal_today_month, 0)),
        "{{DAY_GOAL_STYLE}}": DAY_GOAL_STYLE,
        "{{DAY_GOAL_TITLE_STYLE}}": DAY_GOAL_TITLE_STYLE,
        "{{DAY_GOAL_VALUE_STYLE}}": DAY_GOAL_VALUE_STYLE,
        "{{MONTH_GOAL_STYLE}}": MONTH_GOAL_STYLE,
        "{{MONTH_GOAL_TITLE_STYLE}}": MONTH_GOAL_TITLE_STYLE,
        "{{MONTH_GOAL_VALUE_STYLE}}": MONTH_GOAL_VALUE_STYLE,
    }

    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)

    return html


def save_daily_stats_html(stats_row: list[str]) -> None:
    try:
        html_body = build_daily_stats_email_html(stats_row)
        date_value = stats_row[0] if len(stats_row) > 0 else datetime.now(timezone.utc).strftime("%Y%m%d")
        output_html_path = Path(__file__).resolve().parents[1] / "results" / f"daily_result_{date_value}.html"
        output_html_path.write_text(html_body, encoding="utf-8")
        print(f"✅ HTML enregistré : {output_html_path}")
    except Exception as exc:
        print(f"⚠️ Échec de la génération du fichier HTML : {exc}")


def count_slots_by_resource_id(driver: webdriver.Chrome):
    print("📊 Comptage des créneaux dans le planning...")
    counts = {"DOUBLE 1": 0, "DOUBLE 2": 0, "Simple": 0}
    events = driver.find_elements(By.CSS_SELECTOR, ".fc-time-grid-event")

    if not events:
        print("ℹ️ Aucun événement trouvé dans .fc-time-grid-event")
        return counts

    headers = []
    for label in ["DOUBLE 1", "DOUBLE 2", "Simple"]:
        try:
            header = driver.find_element(
                By.XPATH,
                (
                    "//*[contains(@class, 'fc-resource-cell') or contains(@class, 'fc-col-header-cell')]"
                    f"[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{label.lower()}')]"
                ),
            )
            headers.append((label, header))
        except Exception:
            continue

    if headers:
        for event in events:
            try:
                event_center = event.location["x"] + event.size["width"] / 2
            except Exception:
                continue

            matched = False
            for label, header in sorted(headers, key=lambda item: item[1].location["x"]):
                try:
                    left = header.location["x"]
                    right = left + header.size["width"]
                except Exception:
                    continue

                if left <= event_center <= right:
                    counts[label] += 1
                    matched = True
                    break

            if not matched:
                counts["Simple"] += 1

        return counts

    for event in events:
        text = " ".join(
            filter(
                None,
                [
                    event.text,
                    event.get_attribute("innerText") or "",
                    event.get_attribute("title") or "",
                    event.get_attribute("data-resource-id") or "",
                ],
            )
        ).lower()

        if "double 2" in text or "double2" in text or ("double" in text and "2" in text):
            counts["DOUBLE 2"] += 1
        elif "double 1" in text or "double1" in text or ("double" in text and "1" in text):
            counts["DOUBLE 1"] += 1
        elif "simple" in text or "single" in text:
            counts["Simple"] += 1
        else:
            counts["Simple"] += 1

    return counts
    

def main() -> None:
    log_step("Vérification des Variables d'Environnement")
    
    def mask_secret(val: str) -> str:
        if not val:
            return "NON DÉFINI / VIDE"
        val_clean = val.strip()
        if len(val_clean) <= 2:
            return f"'{val_clean[0]}*' (longueur: {len(val)})"
        return f"'{val_clean[0]}{'*' * (len(val_clean) - 2)}{val_clean[-1]}' (longueur brute: {len(val)}, nettoyée: {len(val_clean)})"

    print(f"  APP_LOG : {(LOGIN)}")
    print(f"  APP_PWD : {(PASSWORD)}")
    
    if not LOGIN or not PASSWORD:
        raise ValueError("❌ APP_LOG ou APP_PWD est manquant dans les secrets GitHub !")

    driver = build_driver()
    try:
        log_step("Accès à l'URL LiveXperience")
        print(f"Naviguer vers : {URL}")
        driver.get(URL)
        print(f"📍 URL chargée : {driver.current_url}")
        
        today = datetime.now(timezone.utc).strftime("%d/%m/%Y")

        log_step("Connexion au Formulaire")
        
        # Nettoyage des éventuels espaces/sauts de ligne invisibles dans GitHub Secrets
        clean_login = LOGIN.strip()
        clean_pwd = PASSWORD.strip()

        login_input = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='login'], input[name='mot_de_passe'], input[type='text'], input[type='email']"))
        )
        login_input.clear()
        login_input.send_keys(clean_login)
        print(f"✅ Identifiant injecté dans le champ (valeur injectée: {clean_login[:2]}***{clean_login[-1] if len(clean_login)>1 else ''})")

        pwd_input = driver.find_element(By.CSS_SELECTOR, "input[name='mot_de_passe'], input[name='password'], input[type='password']")
        pwd_input.clear()
        pwd_input.send_keys(clean_pwd)
        print(f"✅ Mot de passe injecté dans le champ (valeur injectée: {clean_pwd[:1]}***{clean_pwd[-1] if len(clean_pwd)>1 else ''})")

        # Soumission explicite du formulaire
        try:
            form = pwd_input.find_element(By.XPATH, "./ancestor::form")
            driver.execute_script("arguments[0].submit();", form)
            print("🚀 Formulaire soumis via JS (form.submit()).")
        except Exception:
            pwd_input.send_keys(Keys.RETURN)
            print("⌨️ Soumission effectuée via la touche ENTRÉE.")

        time.sleep(3)

        # Masquage/attente du loader #wait
        try:
            print("⏳ Attente de la fin du chargement (#wait)...")
            WebDriverWait(driver, 15).until(
                EC.invisibility_of_element_located((By.ID, "wait"))
            )
            print("✅ Loader #wait disparu.")
        except Exception:
            print("⚠️ Le spinner #wait ne s'est pas masqué automatiquement. Masquage JS forcé.")
            driver.execute_script("var w = document.getElementById('wait'); if(w) w.style.display='none';")

        print(f"📍 URL après tentative de login : {driver.current_url}")

        log_step("Validation du Dashboard & Navigation 'PAIEMENTS EN LIGNE'")
        try:
            menu_link = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'PAIEMENTS EN LIGNE')]"))
            )
            print("✅ Menu 'PAIEMENTS EN LIGNE' détecté !")
        except Exception as e:
            print("❌ Échec de détection du tableau de bord.")
            capture_debug_artifacts(driver, "login_failed")
            raise e

        # Essayer de lire le nombre de créneaux joués du jour
        try:
            wait_for_element(driver, By.XPATH, "//*[contains(normalize-space(.), 'DOUBLE 1')]", timeout=10)
            time.sleep(2)
            slot_counts = count_slots_by_resource_id(driver)
            played_slots = sum(slot_counts.values())
            double1_slots = slot_counts["DOUBLE 1"]
            double2_slots = slot_counts["DOUBLE 2"]
            simple_slots = slot_counts["Simple"]
        except Exception as exc:
            played_slots = 0
            double1_slots = 0
            double2_slots = 0
            simple_slots = 0
            print(f"⚠️ Impossible de compter les créneaux joués : {exc}")

        print("📊 Stats Créneaux Joués :")
        print("  - Total :", played_slots)
        print("  - DOUBLE 1 :", double1_slots)
        print("  - DOUBLE 2 :", double2_slots)
        print("  - Simple :", simple_slots)

        log_step("Navigation vers Suivi des Paiements")
        try:
            time.sleep(2)
            menu_link = find_clickable_link(driver, "PAIEMENTS EN LIGNE")
            driver.execute_script("arguments[0].click();", menu_link)
            time.sleep(2)

            payment_link = find_clickable_link(driver, "suivi des paiements")
            driver.execute_script("arguments[0].click();", payment_link)
            time.sleep(3)
        except Exception as exc:
            print(f"❌ Navigation vers paiements impossible : {exc}")
            capture_debug_artifacts(driver, "nav_payments_failed")
            raise

        wait_for_element(driver, By.XPATH, "//*[contains(normalize-space(.), 'Liste des paiements web')]")
        print("✅ Page 'Liste des paiements web' atteinte.")

        date_input = wait_for_interactable(driver, By.ID, "date")
        date_input.clear()
        date_input.send_keys(today)
        print(f"📅 Date appliquée : {today}")

        filter_button = wait_for_interactable(driver, By.XPATH, "//button[contains(normalize-space(.), 'Filtrer')]")
        filter_button.click()
        print("🔍 Filtrage appliqué.")
        time.sleep(2)

        rows = driver.find_elements(By.ID, "tr_encaisse")
        texts: list[str] = [row.get_attribute("innerText").strip() or row.text.strip() for row in rows if (row.get_attribute("innerText") or row.text or "").strip()]

        print("📊 Lignes 'Encaisse' Journée :", len(texts))
        for text in texts:
            print("  -> " + text)

        total_paye = extract_numeric_value(texts[0].replace(" ","")) if len(texts) > 0 else ""
        total_frais = extract_numeric_value(texts[1].replace(" ","")) if len(texts) > 1 else ""
        total_club = extract_numeric_value(texts[2].replace(" ","")) if len(texts) > 2 else ""

        log_step("Récupération du Récapitulatif Mensuel")
        recap_button = wait_for_interactable(driver, By.XPATH, "//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'récap mensuel')]")
        recap_button.click()
        time.sleep(2)

        wait_for_element(driver, By.XPATH, "//*[contains(normalize-space(.), 'Liste des paiements web')]")

        rows = driver.find_elements(By.ID, "tr_encaisse")
        texts = [row.get_attribute("innerText").strip() or row.text.strip() for row in rows if (row.get_attribute("innerText") or row.text or "").strip()]

        print("📊 Lignes 'Encaisse' Mois :", len(texts))
        for text in texts:
            print("  -> " + text)

        total_paye_mois = extract_numeric_value(texts[0].replace(" ","")) if len(texts) > 0 else ""
        total_frais_mois = extract_numeric_value(texts[1].replace(" ","")) if len(texts) > 1 else ""
        total_club_mois = extract_numeric_value(texts[2].replace(" ","")) if len(texts) > 2 else ""

        log_step("Récupération des Badges (Inscriptions & Réservations)")
        try:
            inscrit_badge = driver.find_element(
                By.XPATH,
                "//i[@class='fa fa-user']/following-sibling::span[contains(@class, 'badge-warning')][1]"
            )
            inscriptions = inscrit_badge.get_attribute("innerText").strip() or "0"
        except Exception:
            inscriptions = "0"

        try:
            reserved_badge = driver.find_element(
                By.XPATH,
                "//i[@class='fa fa-calendar']/following-sibling::span[contains(@class, 'badge-warning')][1]"
            )
            reservations = reserved_badge.get_attribute("innerText").strip() or "0"
        except Exception:
            reservations = "0"

        print("👤 Inscrits du jour :", inscriptions)
        print("📅 Créneaux réservés :", reservations)

        log_step("Navigation vers Suivi des Annulations")
        try:
            menu_link = find_clickable_link(driver, "RESERVATIONS")
            driver.execute_script("arguments[0].click();", menu_link)
            time.sleep(2)

            payment_link = find_clickable_link(driver, "SUIVI DES ANNULATIONS")
            driver.execute_script("arguments[0].click();", payment_link)
            time.sleep(3)
        except Exception as exc:
            print(f"❌ Navigation vers annulations impossible : {exc}")
            capture_debug_artifacts(driver, "nav_annulations_failed")
            raise

        date_input = wait_for_interactable(driver, By.ID, "date_annulation")
        date_input.clear()
        date_input.send_keys(today)

        filter_button = wait_for_interactable(driver, By.XPATH, "//button[contains(normalize-space(.), 'Filtrer')]")
        filter_button.click()

        wait_for_element(driver, By.XPATH, "//table[contains(@class, 'table-striped')]")

        rows = driver.find_elements(By.CSS_SELECTOR, "table.table-striped tbody tr")
        cancellation_details: list[str] = []
        for index, row in enumerate(rows, start=1):
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) < 8:
                continue

            cancellation_slot = cells[1].get_attribute("innerText").strip()
            client = cells[4].get_attribute("innerText").strip()
            terrain = cells[5].get_attribute("innerText").strip()
            tarif = cells[6].get_attribute("innerText").strip()
            moyen_annulation = cells[8].get_attribute("innerText").strip()

            detail = f"{cancellation_slot} | {client} | {terrain} | {tarif} | {moyen_annulation}"
            cancellation_details.append(detail)
            print(f"  ❌ Créneau annulé #{index}: {detail}")

        stats_row = [
            str(datetime.now(timezone.utc).strftime("%Y%m%d")),
            total_paye,
            total_frais,
            total_club,
            total_paye_mois,
            total_frais_mois,
            total_club_mois,
            inscriptions,
            reservations,
            str(played_slots),
            str(double1_slots),
            str(double2_slots),
            str(simple_slots),
            str(len(cancellation_details)),
            "\n".join(cancellation_details),
        ]

        log_step("Sauvegarde et Génération du Rapport Final")
        save_to_excel(stats_row)
        save_daily_stats_html(stats_row)
        print("🎉 TRAITEMENT TERMINÉ AVEC SUCCÈS !")

    except Exception as global_exc:
        log_step("ERREUR CRITIQUE DÉTECTÉE")
        print(f"💥 Exception : {global_exc}")
        capture_debug_artifacts(driver, "unhandled_exception")
        raise global_exc

    finally:
        driver.quit()
        print("🚪 Navigateur Chrome fermé.")


if __name__ == "__main__":
    main()