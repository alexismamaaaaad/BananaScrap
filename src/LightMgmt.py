import time
import logging
from typing import Dict, Any
from tuya_connector import TuyaOpenAPI, TUYA_LOGGER

# ==============================================================================
# CONFIGURATION ET IDENTIFIANTS TUYA
# ==============================================================================

# Vos clés d'API récupérées sur la plateforme Tuya Developer (iot.tuya.com)
ACCESS_ID: str = "ahyxh7dhmknah784wxmr"
ACCESS_SECRET: str = "9dc4b0fb10eb4b4b8b055ca5357b7155"

# L'identifiant unique (Device ID) de votre prise LSC / Smart Life
DEVICE_ID: str = "bf0fe3af8b8905f80clid3"

# Endpoint pour l'Europe (France). Pour l'Amérique, ce serait "https://openapi.tuyaus.com"
ENDPOINT: str = "https://openapi.tuyaeu.com"

# Code de la commande de relais (standard Tuya : "switch_1" ou parfois "switch")
DP_SWITCH_CODE: str = "switch_1"

# Masquer les logs réseau verbeux du SDK Tuya pour garder une console propre
TUYA_LOGGER.setLevel(logging.ERROR)


# ==============================================================================
# CLASSE DE GESTION DE LA PRISE CONNECTÉE
# ==============================================================================

class SmartPlugController:
    """
    Classe permettant de piloter une prise connectée Tuya / Smart Life / LSC
    via l'API Cloud officielle.
    """

    def __init__(self, endpoint: str, access_id: str, access_secret: str) -> None:
        """
        Initialise le client OpenAPI Tuya et établit la connexion.
        """
        # Instanciation de l'objet OpenAPI avec les identifiants de projet
        self.api = TuyaOpenAPI(endpoint, access_id, access_secret)
        
        # Connexion initiale auprès des serveurs Tuya (récupération du jeton d'accès)
        print(" Connexion aux serveurs Tuya Cloud...")
        self.api.connect()
        print(" Connexion réussie à l'API Tuya.")

    def _set_power_state(self, device_id: str, state: bool) -> bool:
        """
        [Méthode Privée Factorisée]
        Envoie l'ordre générique de changement d'état (ON/OFF) à l'appareil.

        :param device_id: L'identifiant unique du périphérique Tuya.
        :param state: True pour allumer, False pour éteindre.
        :return: True si la commande a été acceptée avec succès, False sinon.
        """
        # Construction du payload JSON selon la spécification de l'API Tuya
        payload: Dict[str, Any] = {
            "commands": [
                {
                    "code": DP_SWITCH_CODE,
                    "value": state
                }
            ]
        }

        action_name = "ALLUMAGE" if state else "EXTINCTION"
        print(f" Envoi de la commande de/d' {action_name} à l'appareil [{device_id}]...")

        try:
            # Envoi de la requête POST vers le point de terminaison des commandes d'appareils
            response = self.api.post(f"/v1.0/devices/{device_id}/commands", payload)

            # L'API renvoie un dictionnaire contenant un booléen 'success'
            if response.get("success", False):
                print(f" Ordre de/d' {action_name} exécuté avec succès.")
                return True
            else:
                print(f" Erreur renvoyée par le Cloud Tuya : {response}")
                return False

        except Exception as e:
            print(f" Une exception réseau/système s'est produite : {e}")
            return False

    def turn_on(self, device_id: str) -> bool:
        """
        Allume la prise connectée spécifiée.

        :param device_id: L'ID de la prise à allumer.
        :return: True si l'allumage a réussi.
        """
        return self._set_power_state(device_id, True)

    def turn_off(self, device_id: str) -> bool:
        """
        Éteint la prise connectée spécifiée.

        :param device_id: L'ID de la prise à éteindre.
        :return: True si l'extinction a réussi.
        """
        return self._set_power_state(device_id, False)


# ==============================================================================
# POINT D'ENTRÉE DU SCRIPT (DÉMONSTRATION)
# ==============================================================================

if __name__ == "__main__":
    # 1. Initialisation du contrôleur avec vos clés d'accès
    plug_controller = SmartPlugController(
        endpoint=ENDPOINT,
        access_id=ACCESS_ID,
        access_secret=ACCESS_SECRET
    )

    print("\n--- TEST DES FONCTIONNALITÉS ---")

    # 2. Exemple d'utilisation de la méthode pour ALLUMER la prise
    plug_controller.turn_on(DEVICE_ID)
    time.sleep(5)
    plug_controller.turn_off(DEVICE_ID)

    # 3. Exemple d'utilisation de la méthode pour ÉTEINDRE la prise
    # (Décommentez la ligne suivante si vous souhaitez tester l'extinction immédiate)
    # plug_controller.turn_off(DEVICE_ID)