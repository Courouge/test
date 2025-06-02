import requests
import base64
from read_api_key_file import read_api_keys

# 🔐 Lecture de l’API Key depuis fichier
API_KEY, API_SECRET = read_api_keys("api-key-test.txt")

if not API_KEY or not API_SECRET:
    print("❌ API_KEY ou API_SECRET non définis.")
    exit(1)

# Authentification Basic
auth = base64.b64encode(f"{API_KEY}:{API_SECRET}".encode()).decode()
headers = {
    "Authorization": f"Basic {auth}",
    "Content-type": "application/json"
}

# 📌 Paramètres à personnaliser
SERVICE_ACCOUNT_ID = "sa-xxxxx"
ENVIRONMENT_ID = "env-xxxxx"
CLUSTER_ID = "lkc-xxxxx"
ROLE_NAME = "DeveloperRead"  # ou DeveloperWrite, ResourceOwner, etc.
RESOURCE_TYPE = "topic"       # ou consumer-group
RESOURCE_PATTERN = "my-project-*"  # préfixe ou nom exact

# 🧱 Construction du CRN
crn = f"crn://confluent.cloud/organization=*/environment={ENVIRONMENT_ID}/cloud-cluster={CLUSTER_ID}/kafka={CLUSTER_ID}/{RESOURCE_TYPE}={RESOURCE_PATTERN}"

# 📤 Requête POST pour créer le Role Binding
payload = {
    "principal": f"ServiceAccount:{SERVICE_ACCOUNT_ID}",
    "role_name": ROLE_NAME,
    "crn_pattern": crn
}

url = "https://api.confluent.cloud/iam/v2/role-bindings"

response = requests.post(url, headers=headers, json=payload)

# 🔍 Résultat
if response.status_code == 201:
    print(f"✅ Role binding créé : {ROLE_NAME} sur {RESOURCE_TYPE} = {RESOURCE_PATTERN}")
elif response.status_code == 409:
    print("⚠️  Role binding déjà existant.")
elif response.status_code == 403:
    print("❌ Accès interdit : votre API Key n’a pas les droits nécessaires.")
    print("   ➤ Il faut une API Key avec le rôle OrganizationAdmin ou EnvironmentAdmin.")
    print(response.text)
else:
    print(f"❌ Erreur {response.status_code}: {response.text}")
