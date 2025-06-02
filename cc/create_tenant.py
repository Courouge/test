#!/usr/bin/env python3
"""
Confluent Cloud Tenant Manager
Automatise la création de service accounts et la gestion des permissions RBAC
pour des tenants applicatifs dans Confluent Cloud.
"""

import argparse
import os
import sys
import json
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from dotenv import load_dotenv
import requests
from requests.auth import HTTPBasicAuth
from read_api_key_file import read_api_keys

CONFLUENT_API_KEY, CONFLUENT_API_SECRET = read_api_keys("api-key-test.txt")

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ConfluentConfig:
    """Configuration pour Confluent Cloud"""
    api_key: str
    api_secret: str
    base_url: str = "https://api.confluent.cloud"


@dataclass
class TenantPermissions:
    """Définition des permissions pour un tenant"""
    project_name: str
    cluster_id: str
    topics: List[str]
    consumer_groups: List[str]
    schemas: List[str]


class ConfluentCloudAPI:
    """Client pour l'API Confluent Cloud"""

    def __init__(self, config: ConfluentConfig):
        self.config = config
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(config.api_key, config.api_secret)
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })

    def create_service_account(self, name: str, description: str = "") -> Dict:
        """Crée un service account"""
        url = f"{self.config.base_url}/iam/v2/service-accounts"
        payload = {
            "display_name": name,
            "description": description or f"Service account for {name} tenant"
        }

        response = self.session.post(url, json=payload)
        response.raise_for_status()

        service_account = response.json()
        logger.info(f"Service account créé: {service_account['id']}")
        return service_account

    def create_api_key(self, service_account_id: str, cluster_id: str) -> Dict:
        """Crée une API key pour un service account sur un cluster"""
        url = f"{self.config.base_url}/iam/v2/api-keys"
        payload = {
            "spec": {
                "display_name": f"API Key for {service_account_id}",
                "description": f"API Key for cluster {cluster_id}",
                "owner": {
                    "id": service_account_id,
                    "api_version": "iam/v2",
                    "kind": "ServiceAccount"
                },
                "resource": {
                    "id": cluster_id,
                    "api_version": "cmk/v2",
                    "kind": "Cluster"
                }
            }
        }

        response = self.session.post(url, json=payload)
        response.raise_for_status()

        api_key = response.json()
        logger.info(f"API Key créée: {api_key['id']}")
        return api_key

    def get_cluster_info(self, cluster_id: str) -> Dict:
        """Récupère les informations détaillées d'un cluster"""
        url = f"{self.config.base_url}/cmk/v2/clusters/{cluster_id}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_environment_info(self, environment_id: str) -> Dict:
        """Récupère les informations d'un environnement"""
        url = f"{self.config.base_url}/org/v2/environments/{environment_id}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def create_role_binding(self, principal: str, role_name: str, resource_type: str,
                          resource_pattern: str, cluster_id: str, environment_id: str = None, pattern_type: str = "LITERAL") -> Dict:
        """Crée un role binding pour un principal sur une ressource"""
        url = f"{self.config.base_url}/iam/v2/role-bindings"

        # Si environment_id n'est pas fourni, essayer de le récupérer du cluster
        if not environment_id:
            try:
                cluster_info = self.get_cluster_info(cluster_id)
                environment_id = cluster_info.get('spec', {}).get('environment', {}).get('id')
                if environment_id:
                    logger.info(f"Environment ID détecté automatiquement: {environment_id}")
                else:
                    logger.warning("Impossible de détecter l'environment ID automatiquement")
            except Exception as e:
                logger.warning(f"Erreur lors de la récupération des infos cluster: {e}")

        # Construction du CRN selon la documentation officielle Confluent
        if resource_type == "topic":
            if pattern_type == "PREFIXED":
                # Pattern pour topics avec préfixe
                crn_pattern = f"crn://confluent.cloud/organization=*/environment={environment_id or '*'}/cloud-cluster={cluster_id}/kafka={cluster_id}/topic={resource_pattern}"
            else:
                crn_pattern = f"crn://confluent.cloud/organization=*/environment={environment_id or '*'}/cloud-cluster={cluster_id}/kafka={cluster_id}/topic={resource_pattern}"
        elif resource_type == "consumer-group":
            if pattern_type == "PREFIXED":
                # Pattern pour consumer groups avec préfixe
                crn_pattern = f"crn://confluent.cloud/organization=*/environment={environment_id or '*'}/cloud-cluster={cluster_id}/kafka={cluster_id}/group={resource_pattern}"
            else:
                crn_pattern = f"crn://confluent.cloud/organization=*/environment={environment_id or '*'}/cloud-cluster={cluster_id}/kafka={cluster_id}/group={resource_pattern}"
        elif resource_type == "kafka-cluster":
            # Permission sur le cluster entier
            crn_pattern = f"crn://confluent.cloud/organization=*/environment={environment_id or '*'}/cloud-cluster={cluster_id}"
        else:
            raise ValueError(f"Type de ressource non supporté: {resource_type}")

        payload = {
            "principal": f"User:{principal}",
            "role_name": role_name,
            "crn_pattern": crn_pattern
        }

        logger.debug(f"Tentative de création role binding: {json.dumps(payload, indent=2)}")

        response = self.session.post(url, json=payload)

        # Log détaillé de l'erreur pour debug
        if response.status_code >= 400:
            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response body: {response.text}")
            logger.debug(f"Request payload: {json.dumps(payload, indent=2)}")

        response.raise_for_status()

        role_binding = response.json()
        logger.info(f"Role binding créé: {role_binding['id']} - {role_name} sur {resource_type}:{resource_pattern}")
        return role_binding

    def _build_crn_pattern(self, resource_type: str, resource_id: str, pattern_type: str = "LITERAL") -> str:
        """Construit un pattern CRN pour les permissions"""
        # Pour les patterns avec préfixe, on utilise une structure CRN simplifiée
        if pattern_type == "PREFIXED":
            if resource_type == "topic":
                return f"crn://confluent.cloud/organization=*/environment=*/cloud-cluster=*/kafka-cluster=*/topic={resource_id}"
            elif resource_type == "consumer-group":
                return f"crn://confluent.cloud/organization=*/environment=*/cloud-cluster=*/kafka-cluster=*/group={resource_id}"

        # Pour les patterns littéraux
        if resource_type == "kafka-cluster":
            return f"crn://confluent.cloud/organization=*/environment=*/cloud-cluster=*/kafka-cluster={resource_id}"
        elif resource_type == "schema-registry":
            return f"crn://confluent.cloud/organization=*/environment={resource_id}/schema-registry-cluster=*"

        return f"crn://confluent.cloud/organization=*/environment=*/cloud-cluster=*/kafka-cluster=*/{resource_type}={resource_id}"

    def get_service_account_by_name(self, name: str) -> Optional[Dict]:
        """Recherche un service account par nom"""
        url = f"{self.config.base_url}/iam/v2/service-accounts"
        response = self.session.get(url)
        response.raise_for_status()

        service_accounts = response.json().get('data', [])
        for sa in service_accounts:
            if sa.get('display_name') == name:
                return sa
        return None


class ConfluentTenantManager:
    """Gestionnaire principal pour les tenants Confluent Cloud"""

    def __init__(self, confluent_config: ConfluentConfig):
        self.confluent = ConfluentCloudAPI(confluent_config)

    def create_tenant(self, project_name: str, cluster_id: str,
                     environment_id: str = None) -> Dict:
        """Crée un tenant complet avec service account et permissions"""
        logger.info(f"Création du tenant {project_name} sur le cluster {cluster_id}")

        # 1. Créer le service account
        sa_name = f"{project_name}-service-account"
        existing_sa = self.confluent.get_service_account_by_name(sa_name)

        if existing_sa:
            logger.info(f"Service account existant trouvé: {existing_sa['id']}")
            service_account = existing_sa
        else:
            service_account = self.confluent.create_service_account(
                name=sa_name,
                description=f"Service account pour le tenant {project_name}"
            )

        # 2. Créer l'API key
        api_key_response = self.confluent.create_api_key(
            service_account['id'],
            cluster_id
        )

        # 3. Afficher/stocker les credentials
        self._display_credentials(
            project_name,
            api_key_response['id'],
            api_key_response['spec']['secret']
        )

        # 4. Appliquer les permissions RBAC
        rbac_success = self._apply_tenant_permissions(
            service_account['id'],
            project_name,
            cluster_id,
            environment_id
        )

        result = {
            "service_account": service_account,
            "api_key_id": api_key_response['id'],
            "api_secret": api_key_response['spec']['secret'],
            "project_name": project_name,
            "cluster_id": cluster_id,
            "rbac_applied": rbac_success
        }

        if not rbac_success:
            logger.warning("⚠️  Les permissions RBAC n'ont pas pu être appliquées automatiquement")
            logger.warning("   Vous devrez les configurer manuellement dans la console Confluent Cloud")

        return result

    def _apply_tenant_permissions(self, service_account_id: str, project_name: str,
                                cluster_id: str, environment_id: str = None):
        """Applique les permissions RBAC pour un tenant"""
        logger.info(f"Application des permissions RBAC pour {project_name}")

        # Récupérer l'environment ID si pas fourni
        if not environment_id:
            try:
                cluster_info = self.confluent.get_cluster_info(cluster_id)
                environment_id = cluster_info.get('spec', {}).get('environment', {}).get('id')
                if environment_id:
                    logger.info(f"Environment ID détecté: {environment_id}")
                else:
                    logger.warning("Impossible de détecter l'environment ID")
            except Exception as e:
                logger.warning(f"Erreur lors de la récupération de l'environment ID: {e}")

        # Vérifier d'abord les permissions de l'API Key
        logger.info("Vérification des permissions de l'API Key...")
        try:
            response = self.confluent.session.get(f"{self.confluent.config.base_url}/iam/v2/role-bindings")
            if response.status_code != 200:
                logger.warning(f"API Key semble avoir des permissions limitées: {response.status_code}")
        except Exception as e:
            logger.warning(f"Impossible de vérifier les permissions: {e}")

        # Permissions de base avec environnement
        basic_roles = [
            ("DeveloperRead", "topic", f"{project_name}-*"),
            ("DeveloperWrite", "topic", f"{project_name}-*"),
            ("DeveloperRead", "consumer-group", f"{project_name}-*"),
            ("DeveloperWrite", "consumer-group", f"{project_name}-*")
        ]

        successful_bindings = 0
        failed_bindings = 0

        for role_name, resource_type, pattern in basic_roles:
            try:
                self.confluent.create_role_binding(
                    principal=service_account_id,
                    role_name=role_name,
                    resource_type=resource_type,
                    resource_pattern=pattern,
                    cluster_id=cluster_id,
                    environment_id=environment_id,
                    pattern_type="PREFIXED"
                )
                successful_bindings += 1
                logger.info(f"✅ Role binding {role_name} créé avec succès pour {resource_type}:{pattern}")

            except requests.exceptions.HTTPError as e:
                failed_bindings += 1
                error_details = ""
                try:
                    error_body = e.response.json()
                    error_details = error_body.get('detail', '')
                except:
                    error_details = e.response.text

                if e.response.status_code == 403:
                    logger.error(f"❌ Permissions insuffisantes pour créer le role binding {role_name}")
                    logger.error(f"   Détails: {error_details}")

                    # Suggestions spécifiques selon l'erreur
                    if "OrganizationAdmin" in error_details:
                        logger.error(f"   Votre API Key doit avoir le rôle 'OrganizationAdmin'")
                    elif "EnvironmentAdmin" in error_details:
                        logger.error(f"   Votre API Key doit avoir le rôle 'EnvironmentAdmin' sur l'environment {environment_id}")
                    else:
                        logger.error(f"   Vérifiez que votre API Key a les permissions 'OrganizationAdmin' ou 'EnvironmentAdmin'")

                elif e.response.status_code == 409:
                    logger.info(f"ℹ️  Role binding {role_name} déjà existant pour {pattern}")
                    successful_bindings += 1
                elif e.response.status_code == 422:
                    logger.warning(f"⚠️  Erreur de validation: {error_details}")
                    logger.warning(f"   Role: {role_name}, Resource: {resource_type}:{pattern}")

                    # Essayer des rôles alternatifs
                    if role_name.startswith("Developer"):
                        alternative_role = role_name.replace("Developer", "Resource")
                        logger.info(f"Tentative avec le rôle alternatif: {alternative_role}")
                        try:
                            self.confluent.create_role_binding(
                                principal=service_account_id,
                                role_name=alternative_role,
                                resource_type=resource_type,
                                resource_pattern=pattern,
                                cluster_id=cluster_id,
                                environment_id=environment_id,
                                pattern_type="PREFIXED"
                            )
                            successful_bindings += 1
                            logger.info(f"✅ Role binding {alternative_role} créé avec succès")
                        except Exception as e2:
                            logger.warning(f"Échec aussi avec {alternative_role}: {e2}")
                else:
                    logger.warning(f"Erreur {e.response.status_code} lors de la création du role binding {role_name}: {error_details}")
            except Exception as e:
                failed_bindings += 1
                logger.error(f"Erreur inattendue lors de la création du role binding {role_name}: {e}")

        # Résumé avec instructions détaillées
        total_attempted = len(basic_roles)
        if successful_bindings > 0:
            logger.info(f"✅ {successful_bindings}/{total_attempted} permissions RBAC appliquées avec succès")
        else:
            logger.error(f"❌ Aucune permission RBAC n'a pu être appliquée ({failed_bindings} échecs)")
            logger.error("🔧 ACTIONS REQUISES:")
            logger.error("   1. Vérifiez que votre API Key a l'un de ces rôles:")
            logger.error("      - OrganizationAdmin (sur toute l'organisation)")
            logger.error(f"      - EnvironmentAdmin (sur l'environment {environment_id or 'requis'})")
            logger.error("   2. OU configurez manuellement dans la console Confluent Cloud:")
            logger.error(f"      - Service Account: {service_account_id}")
            logger.error(f"      - Environment: {environment_id or 'requis'}")
            logger.error(f"      - Cluster: {cluster_id}")
            logger.error(f"      - Topics: {project_name}-* (DeveloperRead, DeveloperWrite)")
            logger.error(f"      - Consumer Groups: {project_name}-* (DeveloperRead, DeveloperWrite)")

        return successful_bindings > 0

    def _display_credentials(self, project_name: str, api_key: str, api_secret: str):
        """Affiche les credentials de manière sécurisée"""
        print("\n" + "="*70)
        print("🔑 CREDENTIALS GÉNÉRÉES - À SAUVEGARDER IMMÉDIATEMENT")
        print("="*70)
        print(f"Projet: {project_name}")
        print(f"API Key: {api_key}")
        print(f"API Secret: {api_secret}")
        print(f"Créé le: {datetime.now().isoformat()}")
        print("="*70)
        print("⚠️  IMPORTANT: Sauvegardez ces credentials dans un gestionnaire")
        print("   de secrets sécurisé. Ils ne seront plus affichés.")
        print("="*70)

    def delete_tenant(self, project_name: str) -> bool:
        """Supprime un tenant (service account et credentials Vault)"""
        logger.info(f"Suppression du tenant {project_name}")

        # Récupérer le service account
        sa_name = f"{project_name}-service-account"
        service_account = self.confluent.get_service_account_by_name(sa_name)

        if not service_account:
            logger.warning(f"Service account {sa_name} non trouvé")
            return False

        # Note: L'API Confluent Cloud ne permet pas toujours la suppression
        # des service accounts via l'API REST publique
        logger.warning("Suppression manuelle requise dans la console Confluent Cloud")

        return True

    def list_tenant_resources(self, project_name: str) -> Dict:
        """Liste les ressources d'un tenant"""
        # Rechercher le service account associé
        sa_name = f"{project_name}-service-account"
        service_account = self.confluent.get_service_account_by_name(sa_name)

        if not service_account:
            logger.error(f"Aucun service account trouvé pour {project_name}")
            return {}

        return {
            "project_name": project_name,
            "service_account_id": service_account['id'],
            "service_account_name": service_account['display_name'],
            "topic_prefix": f"{project_name}-*",
            "consumer_group_prefix": f"{project_name}-*",
            "created_at": service_account.get('metadata', {}).get('created_at', 'N/A')
        }


def load_configuration() -> ConfluentConfig:
    """Charge la configuration depuis les variables d'environnement"""
    load_dotenv()

    # Configuration Confluent Cloud
    confluent_config = ConfluentConfig(
        api_key=CONFLUENT_API_KEY,
        api_secret=CONFLUENT_API_SECRET,
        base_url=os.getenv('CONFLUENT_BASE_URL', 'https://api.confluent.cloud')
    )

    # Validation
    required_vars = [
        ('CONFLUENT_API_KEY', confluent_config.api_key),
        ('CONFLUENT_API_SECRET', confluent_config.api_secret)
    ]

    missing_vars = [var for var, value in required_vars if not value]
    if missing_vars:
        raise ValueError(f"Variables d'environnement manquantes: {', '.join(missing_vars)}")

    return confluent_config


def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(
        description="Gestionnaire de tenants Confluent Cloud",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples d'utilisation:
  python create_tenant.py create --project my-project --cluster-id lkc-xxxxx
  python create_tenant.py list --project my-project
  python create_tenant.py delete --project my-project
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Commandes disponibles')

    # Commande create
    create_parser = subparsers.add_parser('create', help='Créer un tenant')
    create_parser.add_argument('--project', required=True,
                              help='Nom du projet/tenant')
    create_parser.add_argument('--cluster-id', required=True,
                              help='ID du cluster Kafka (ex: lkc-xxxxx)')
    create_parser.add_argument('--environment-id',
                              help='ID de l\'environnement pour Schema Registry')

    # Commande list
    list_parser = subparsers.add_parser('list', help='Lister les ressources d\'un tenant')
    list_parser.add_argument('--project', required=True,
                            help='Nom du projet/tenant')

    # Commande delete
    delete_parser = subparsers.add_parser('delete', help='Supprimer un tenant')
    delete_parser.add_argument('--project', required=True,
                              help='Nom du projet/tenant')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        # Charger la configuration
        confluent_config = load_configuration()

        # Initialiser le gestionnaire
        manager = ConfluentTenantManager(confluent_config)

        # Exécuter la commande
        if args.command == 'create':
            result = manager.create_tenant(
                project_name=args.project,
                cluster_id=args.cluster_id,
                environment_id=args.environment_id
            )
            print(f"✅ Tenant créé avec succès:")
            print(f"   Service Account ID: {result['service_account']['id']}")
            print(f"   API Key ID: {result['api_key_id']}")
            print(f"   Cluster ID: {result['cluster_id']}")

            if result.get('rbac_applied'):
                print(f"   ✅ Permissions RBAC appliquées automatiquement")
            else:
                print(f"   ⚠️  Permissions RBAC à configurer manuellement")
                print(f"   📋 Actions requises dans la console Confluent Cloud:")
                print(f"      - Service Account: {result['service_account']['id']}")
                print(f"      - Topics: {args.project}-* (Read/Write)")
                print(f"      - Consumer Groups: {args.project}-* (Read/Write)")

        elif args.command == 'list':
            result = manager.list_tenant_resources(args.project)
            if result:
                print(f"📋 Ressources du tenant {args.project}:")
                print(f"   Service Account ID: {result['service_account_id']}")
                print(f"   Service Account Name: {result['service_account_name']}")
                print(f"   Topic Prefix: {result['topic_prefix']}")
                print(f"   Consumer Group Prefix: {result['consumer_group_prefix']}")
                if result.get('created_at'):
                    print(f"   Créé le: {result['created_at']}")
            else:
                print(f"❌ Aucune ressource trouvée pour {args.project}")

        elif args.command == 'delete':
            success = manager.delete_tenant(args.project)
            if success:
                print(f"✅ Tenant {args.project} marqué pour suppression")
                print("⚠️  Suppression manuelle requise dans la console Confluent Cloud")
            else:
                print(f"❌ Erreur lors de la suppression du tenant {args.project}")

    except Exception as e:
        logger.error(f"Erreur: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
