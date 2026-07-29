import requests

url = "https://api.livexperience.fr"
payload = {
    "email": "adm_bananapadel378",
    "password": "adm_bananapadel378"
}
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer YOUR_TOKEN"
}

response = requests.post(url, json=payload, headers=headers)
print(response.status_code, response.text)