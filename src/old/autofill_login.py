import sys
import time
import unicodedata

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException
except ImportError:
    raise SystemExit("Selenium n'est pas installé. Exécutez : pip install selenium")

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

    for iframe in driver.find_elements(By.TAG_NAME, "iframe"):
        try:
            driver.switch_to.frame(iframe)
            if expected_text in normalize_text(driver.page_source):
                return True
            if expected_text in normalize_text(driver.find_element(By.TAG_NAME, "body").text):
                return True
        except Exception:
            pass
        finally:
            driver.switch_to.default_content()

    return False


def collect_debug_snapshot(driver: webdriver.Chrome) -> str:
    try:
        url = driver.current_url
        title = driver.title
        iframe_count = len(driver.find_elements(By.TAG_NAME, "iframe"))
        body_text = driver.find_element(By.TAG_NAME, "body").text
        snippet = body_text.replace("\n", " ")[:1200]
        return f"URL={url}\nTITLE={title}\nIFRAMES={iframe_count}\nBODY={snippet}"
    except Exception as exc:
        return f"Impossible de lire le snapshot de la page: {exc}"


def wait_for_confirmation(driver: webdriver.Chrome, timeout: int = 45) -> None:
    print("Attente de la page creneaux.asp ou du contenu attendu...")
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: "creneaux.asp" in d.current_url.lower() or page_contains_text(d, "planning")
        )
    except TimeoutException:
        raise RuntimeError(
            "La page n'a pas été détectée dans le délai.\n" + collect_debug_snapshot(driver)
        )

    print(f"URL actuelle : {driver.current_url}")

    if "creneaux.asp" not in driver.current_url.lower():
        print("Attention : l'URL ne contient pas creneaux.asp, mais le contenu attendu peut être présent.")

    expected_texts = ["planning", "le double 2 (+30)", "déconnexion (378)"]
    for expected_text in expected_texts:
        print(f"Recherche du texte : {expected_text}")
        try:
            WebDriverWait(driver, timeout).until(
                lambda d: page_contains_text(d, expected_text)
            )
        except TimeoutException:
            raise RuntimeError(
                f"Texte attendu '{expected_text}' introuvable dans le délai.\n" + collect_debug_snapshot(driver)
            )


def wait_for_dynamic_page(driver: webdriver.Chrome, timeout: int = 20, markers: list[str] | None = None) -> None:
    start_time = time.time()
    previous_url = driver.current_url
    markers = markers or ["planning", "reserver", "reservation", "nouvelle reservation", "btn-horaires"]

    while time.time() - start_time < timeout:
        current_url = driver.current_url
        if current_url != previous_url:
            print(f"Navigation détectée : {previous_url} -> {current_url}")
            return

        if any(page_contains_text(driver, marker) for marker in markers):
            print("Page dynamique prête.")
            return

        try:
            horaire_buttons = driver.find_elements(By.XPATH, "//button[contains(@class, 'btn-horaires')]")
            if horaire_buttons:
                print("Boutons horaires détectés.")
                return
        except Exception:
            pass

        time.sleep(0.5)

    raise TimeoutError(
        "La page dynamique n'a pas atteint un état exploitable dans le délai.\n" + collect_debug_snapshot(driver)
    )


def submit_login_form(driver: webdriver.Chrome, login_element, password_element) -> None:
    form = None
    for element in (login_element, password_element):
        try:
            form = element.find_element(By.XPATH, "ancestor::form")
            if form:
                break
        except Exception:
            form = None

    submit_buttons = []
    if form:
        submit_buttons.extend(
            form.find_elements(
                By.XPATH,
                ".//button[@type='submit'] | .//input[@type='submit'] | .//button[contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'connexion')] | .//button[contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'submit')]"
            )
        )

    if not submit_buttons:
        submit_buttons.extend(
            driver.find_elements(
                By.XPATH,
                "//button[@type='submit'] | //input[@type='submit'] | //button[contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'connexion')] | //button[contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'submit')] | //input[@type='button' and (contains(translate(@value,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'connexion') or contains(translate(@value,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'submit') or contains(translate(@value,'abcdefghijklmnopqrstuvwxyz'),'valider'))]"
            )
        )

    if submit_buttons:
        print("Clic sur le bouton de soumission.")
        submit_buttons[0].click()
        return

    print("Pas de bouton submit trouvé, envoi Enter sur le champ mot de passe.")
    password_element.send_keys(Keys.ENTER)


def close_popup_if_present(driver: webdriver.Chrome, timeout: int = 5) -> None:
    try:
        close_button = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "//button[@type='button' and @class='close' and @data-dismiss='modal' and @aria-label='Close']"
                )
            )
        )
        close_button.click()
        print("Popup détectée et fermée.")
    except Exception:
        print("Aucune popup à fermer.")


def click_reservation_div_if_present(driver: webdriver.Chrome, timeout: int = 2) -> None:
    try:
        reservation_div = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "//div[.//a[contains(@href, \"javascript:myLoad('/prereservation.asp')\")]]"
                )
            )
        )
        reservation_div.click()
        print("Conteneur Réserver cliqué.")
    except Exception:
        print("Conteneur Réserver non trouvé.")

def click_back_div_if_present(driver: webdriver.Chrome, timeout: int = 10) -> None:
    selectors = [
        "//a[contains(@href, \"javascript:myLoad('/prereservation.asp')\")]",
        "//a[contains(@href, '/prereservation.asp')]",
        "//a[contains(@onclick, \"myLoad('/prereservation.asp')\")]",
        "//button[contains(@onclick, \"myLoad('/prereservation.asp')\")]",
        "//div[contains(@onclick, \"myLoad('/prereservation.asp')\")]",
        "//a[contains(@class, 'pull-left')]"
    ]

    for selector in selectors:
        try:
            back_element = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((By.XPATH, selector))
            )
            back_element.click()
            print("Lien retour prereservation.asp cliqué.")
            return
        except Exception:
            continue

    try:
        driver.execute_script("if (window.myLoad) { window.myLoad('/prereservation.asp'); }")
        print("Fallback myLoad('/prereservation.asp') exécuté.")
    except Exception:
        print("Lien retour prereservation.asp non trouvé.")

def click_reservation_double_if_present(driver: webdriver.Chrome, timeout: int = 10) -> None:
    try:
        reservation_link = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "//a[contains(@href, \"javascript:myLoad('/reservation_capsule.asp?id_sport=2')\")]"
                )
            )
        )
        reservation_link.click()
        print("Lien reservation_capsule.asp cliqué.")
        return
    except Exception:
        pass

    try:
        reservation_button = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "//button[contains(@onclick, \"reservation_capsule.asp?id_sport=2\")]"
                )
            )
        )
        reservation_button.click()
        print("Bouton reservation_capsule.asp cliqué.")
        return
    except Exception:
        pass

    try:
        driver.execute_script("if (window.myLoad) { window.myLoad('/reservation_capsule.asp?id_sport=2'); }")
        print("Fallback myLoad('/reservation_capsule.asp?id_sport=2') exécuté.")
    except Exception:
        print("Lien reservation_capsule.asp non trouvé.")

def click_reservation_single_if_present(driver: webdriver.Chrome, timeout: int = 10) -> None:
    selectors = [
        "//a[contains(@href, \"reservation_capsule.asp?id_sport=7\")]",
        "//button[contains(@onclick, \"reservation_capsule.asp?id_sport=7\")]",
        "//div[contains(@onclick, \"reservation_capsule.asp?id_sport=7\")]",
        "//a[contains(@href, \"javascript:myLoad('/reservation_capsule.asp?id_sport=7')\")]"
    ]

    for selector in selectors:
        try:
            element = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((By.XPATH, selector))
            )
            element.click()
            print(f"Élément SINGLE trouvé via {selector} et cliqué.")
            return
        except Exception:
            continue

    try:
        driver.execute_script("if (window.myLoad) { window.myLoad('/reservation_capsule.asp?id_sport=7'); }")
        print("Fallback myLoad('/reservation_capsule.asp?id_sport=7') exécuté.")
    except Exception:
        print("Lien reservation_capsule.asp single non trouvé.")

def debug_reservation_state(driver: webdriver.Chrome) -> None:
    print("DEBUG PAGE RESERVATION")
    print(f"URL actuelle : {driver.current_url}")
    print(f"TITLE : {driver.title}")

    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text
        stripped_body = " ".join(body_text.split())
        print(f"BODY : {stripped_body[:500]}")
    except Exception as exc:
        print(f"Impossible de lire le body : {exc}")

    try:
        links = driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            href = link.get_attribute("href") or ""
            text = " ".join((link.text or "").split())
            if any(token in href for token in ["prereservation.asp", "reservation_capsule.asp", "main.asp"]):
                print(f"LINK : href={href} text={text}")
    except Exception as exc:
        print(f"Impossible de lire les liens : {exc}")


def log_choosepop_buttons_status(driver: webdriver.Chrome, timeout: int = 2) -> None:
    results = []

    try:
        buttons = WebDriverWait(driver, timeout).until(
            lambda d: d.find_elements(By.XPATH, "//button[contains(@class, 'btn-horaires')]")
        )
    except Exception:
        print("Aucun bouton btn-horaires trouvé.")
        return

    for button in buttons:
        raw_label = (button.text or "").replace("\xa0", " ").strip()
        label = "\n".join(raw_label.splitlines()[:1]).strip()
        is_enabled = button.is_enabled()
        status = "available" if is_enabled else "unavailable"
        results.append({"LABEL": label, "STATUS": status})
        print(f"{label} {status}")

    print("Liste des objets :")
    for item in results:
        print(item)




def launch_and_fill(url: str, login_value: str, password_value: str) -> None:
    options = Options()
    options.add_argument("--start-maximized")

    service = ChromeService()
    driver = webdriver.Chrome(service=service, options=options)

    try:
        driver.get(url)
        time.sleep(2)

        login_fields = []
        password_fields = []

        login_fields.extend(driver.find_elements(By.NAME, "email"))
        password_fields.extend(driver.find_elements(By.NAME, "mot_de_passe"))


        print(f"Champs login trouvés : {len(login_fields)}")
        print(f"Champs mot de passe trouvés : {len(password_fields)}")

        if not login_fields:
            raise RuntimeError("Champ 'login' non trouvé (id/name 'login' ou 'username').")
        if not password_fields:
            raise RuntimeError("Champ 'mot_de_passe' non trouvé (id/name 'mot_de_passe' ou 'password').")

        login_field = login_fields[0]
        password_field = password_fields[0]

        login_field.clear()
        login_field.send_keys(login_value)
        password_field.clear()
        password_field.send_keys(password_value)

        submit_login_form(driver, login_field, password_field)
        wait_for_dynamic_page(driver, timeout=4)
        close_popup_if_present(driver)
        click_reservation_div_if_present(driver)
        time.sleep(0.5)
        click_reservation_double_if_present(driver)
        wait_for_dynamic_page(driver, timeout=3, markers=["nouvelle reservation", "reserver", "btn-horaires"])
        #debug_reservation_state(driver)
        log_choosepop_buttons_status(driver)
        click_back_div_if_present(driver)
        time.sleep(0.5)

        click_reservation_single_if_present(driver)
        wait_for_dynamic_page(driver, timeout=4, markers=["nouvelle reservation", "reserver", "btn-horaires"])
        #debug_reservation_state(driver)
        log_choosepop_buttons_status(driver)
        #click_back_div_if_present(driver)
        #wait_for_dynamic_page(driver, timeout=10, markers=["reserver", "reservation"])

    finally:
        driver.quit()


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python autofill_login.py <login> <mot_de_passe>")
        sys.exit(1)

    url = "https://banana-padel.mymobileapp.fr/"
    login_value = sys.argv[1]
    password_value = sys.argv[2]

    launch_and_fill(url, login_value, password_value)


if __name__ == "__main__":
    main()
