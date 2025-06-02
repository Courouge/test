import os
import argparse
import requests
from dotenv import load_dotenv

load_dotenv()

# python create_tenant.py --project my-project --cluster-id lkc-xxxxxxx --service-account sa-xxxxx
API_KEY = os.getenv("CONFLUENT_API_KEY")
API_SECRET = os.getenv("CONFLUENT_API_SECRET")
ORG_ID = os.getenv("CONFLUENT_ORG_ID")
ENV_ID = os.getenv("CONFLUENT_ENV_ID")

AUTH = (API_KEY, API_SECRET)
HEADERS = {"Content-Type": "application/json"}

BASE_URL = "https://api.confluent.cloud/iam/v2/role-bindings"

def create_binding(principal, role_name, crn_pattern):
    payload = {
        "principal": principal,
        "role_name": role_name,
        "crn_pattern": crn_pattern,
    }
    resp = requests.post(BASE_URL, auth=AUTH, headers=HEADERS, json=payload)
    if resp.status_code == 201:
        print(f"[✅] Role {role_name} -> {crn_pattern}")
    elif resp.status_code == 409:
        print(f"[⚠️] Binding already exists: {role_name} -> {crn_pattern}")
    else:
        print(f"[❌] Error ({resp.status_code}): {resp.text}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, help="Nom logique du tenant (ex: my-project)")
    parser.add_argument("--cluster-id", required=True, help="ID du cluster Kafka")
    parser.add_argument("--service-account", required=True, help="ID du service account cible")
    args = parser.parse_args()

    principal = f"ServiceAccount:{args.service_account}"
    project = args.project
    cluster_id = args.cluster_id

    # Patterns CRN
    kafka_crn = f"crn://confluent.cloud/organization={ORG_ID}/environment={ENV_ID}/kafka={cluster_id}"
    schema_crn = f"crn://confluent.cloud/organization={ORG_ID}/environment={ENV_ID}/schema-registry={cluster_id}"
    
    # 🔐 RBAC pour le cluster Kafka (topics, consumer groups)
    create_binding(principal, "DeveloperWrite", kafka_crn)
    create_binding(principal, "DeveloperRead", kafka_crn)
    create_binding(principal, "ResourceOwner", kafka_crn)

    # 🔐 RBAC pour les schemas
    create_binding(principal, "DeveloperWrite", schema_crn)
    create_binding(principal, "DeveloperRead", schema_crn)

if __name__ == "__main__":
    main()
