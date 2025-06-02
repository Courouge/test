#!/usr/bin/env python3
"""
Script dédié pour créer les role bindings RBAC dans Confluent Cloud
Utilise des API keys avec permissions OrganizationAdmin/EnvironmentAdmin
"""

import argparse
import os
import sys
import json
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import requests
from requests.auth import HTTPBasicAuth

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def read_api_keys(filename: str) -> Tuple[str, str]:
    """
    Lit les API keys depuis un fichier
    Format attendu du fichier:
    api_key=YOUR_API_KEY
    api_secret=YOUR_API_SECRET
    """
    api_key = None
    api_secret = None
    
    try:
        if not os.path.exists(filename):
            raise FileNotFoundError(f"Fichier {filename} non trouvé")
        
        with open(filename, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        if key == 'api_key':
                            api_key = value
                        elif key == 'api_secret':
                            api_secret = value
        
        if not api_key or not api_secret:
            raise ValueError("API key ou secret manquant dans le fichier")
        
        logger.info(f"API keys chargées depuis {filename}")
        return api_key, api_secret
        
    except Exception as e:
        logger.error(f"Erreur lors de la lecture des API keys: {e}")
        logger.error("Format attendu du fichier:")
        logger.error("api_key=YOUR_API_KEY")
        logger.error("api_secret=YOUR_API_SECRET")
        sys.exit(1)

# Chargement des API keys au début du script
try:
    CONFLUENT_API_KEY, CONFLUENT_API_SECRET = read_api_keys("api-key")
except Exception:
    logger.error("Impossible de charger les API keys. Création du fichier exemple 'api-key'...")
    with open("api-key", 'w') as f:
        f.write("# Confluent Cloud API Keys pour role bindings\n")
        f.write("# Ces clés doivent avoir les permissions OrganizationAdmin ou EnvironmentAdmin\n")
        f.write("api_key=YOUR_CONFLUENT_API_KEY_HERE\n")
        f.write("api_secret=YOUR_CONFLUENT_API_SECRET_HERE\n")
    logger.info("Fichier 'api-key' créé. Veuillez le remplir avec vos credentials.")
    sys.exit(1)

@dataclass
class ConfluentConfig:
    """Configuration pour Confluent Cloud"""
    api_key: str
    api_secret: str
    base_url: str = "https://api.confluent.cloud"

class ConfluentRoleBindingAPI:
    """Client spécialisé pour les role bindings Confluent Cloud"""
    
    def __init__(self, config: ConfluentConfig):
        self.config = config
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(config.api_key, config.api_secret)
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
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
    
    def list_role_bindings(self, principal: str = None) -> List[Dict]:
        """Liste les role bindings existants"""
        url = f"{self.config.base_url}/iam/v2/role-bindings"
        params = {}
        if principal:
            params['principal'] = f"User:{principal}"
        
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json().get('data', [])
    
    def create_role_binding(self, principal: str, role_name: str, resource_type: str, 
                          resource_pattern: str, cluster_id: str, environment_id: str = None, 
                          pattern_type: str = "LITERAL") -> Dict:
        """Crée un role binding pour un principal sur une ressource"""
        url = f"{self.config.base_url}/iam/v2/role-bindings"
        
        # Si environment_id n'est pas fourni, le récupérer du cluster
        if not environment_id:
            try:
                cluster_info = self.get_cluster_info(cluster_id)
                environment_id = cluster_info.get('spec', {}).get('environment', {}).get('id')
                if environment_id:
                    logger.info(f"Environment ID détecté automatiquement: {environment_id}")
                else:
                    raise ValueError("Impossible de détecter l'environment ID")
            except Exception as e:
                logger.error(f"Erreur lors de la récupération de l'environment ID: {e}")
                raise
        
        # Construction du CRN selon la documentation Confluent Cloud officielle
        # Format: crn://confluent.cloud/organization=*/environment={env}/cloud-cluster={cluster}/kafka={cluster}/topic={pattern}
        if resource_type == "topic":
            if pattern_type == "PREFIXED":
                # Pour les patterns avec préfixe (ex: my-project-*)
                crn_pattern = f"crn://confluent.cloud/organization=*/environment={environment_id}/cloud-cluster={cluster_id}/kafka={cluster_id}/topic={resource_pattern}"
            else:
                # Pour les topics spécifiques
                crn_pattern = f"crn://confluent.cloud/organization=*/environment={environment_id}/cloud-cluster={cluster_id}/kafka={cluster_id}/topic={resource_pattern}"
                
        elif resource_type == "consumer-group":
            if pattern_type == "PREFIXED":
                # Pour les consumer groups avec préfixe
                crn_pattern = f"crn://confluent.cloud/organization=*/environment={environment_id}/cloud-cluster={cluster_id}/kafka={cluster_id}/group={resource_pattern}"
            else:
                # Pour les consumer groups spécifiques
                crn_pattern = f"crn://confluent.cloud/organization=*/environment={environment_id}/cloud-cluster={cluster_id}/kafka={cluster_id}/group={resource_pattern}"
                
        elif resource_type == "kafka-cluster":
            # Permission sur le cluster entier - format simplifié
            crn_pattern = f"crn://confluent.cloud/organization=*/environment={environment_id}/cloud-cluster={cluster_id}"
            
        else:
            raise ValueError(f"Type de ressource non supporté: {resource_type}")
        
        # Validation du principal (doit commencer par User:)
        if not principal.startswith('User:'):
            principal = f"User:{principal}"
        
        payload = {
            "principal": principal,
            "role_name": role_name,
            "crn_pattern": crn_pattern
        }
        
        logger.debug(f"Création role binding: {json.dumps(payload, indent=2)}")
        
        response = self.session.post(url, json=payload)
        
        if response.status_code >= 400:
            # Log détaillé pour diagnostiquer l'erreur 400
            logger.error(f"Erreur {response.status_code} lors de la création du role binding")
            logger.error(f"URL: {url}")
            logger.error(f"Payload: {json.dumps(payload, indent=2)}")
            try:
                error_detail = response.json()
                logger.error(f"Détails de l'erreur: {json.dumps(error_detail, indent=2)}")
            except:
                logger.error(f"Réponse brute: {response.text}")
        
        response.raise_for_status()
        
        role_binding = response.json()
        logger.info(f"✅ Role binding créé: {role_binding['id']} - {role_name} sur {resource_type}:{resource_pattern}")
        return role_binding
    
    def validate_role_and_resource(self, role_name: str, resource_type: str, resource_pattern: str) -> bool:
        """Valide si un rôle et une ressource sont compatibles"""
        
        # Rôles valides pour chaque type de ressource
        valid_roles = {
            "topic": ["DeveloperRead", "DeveloperWrite", "DeveloperManage", "ResourceOwner"],
            "consumer-group": ["DeveloperRead", "DeveloperWrite", "ResourceOwner"],
            "kafka-cluster": ["DeveloperRead", "DeveloperWrite", "DeveloperManage", "CloudClusterAdmin", "ResourceOwner"]
        }
        
        if resource_type not in valid_roles:
            logger.error(f"Type de ressource invalide: {resource_type}")
            return False
        
        if role_name not in valid_roles[resource_type]:
            logger.error(f"Rôle {role_name} invalide pour {resource_type}")
            logger.error(f"Rôles valides: {valid_roles[resource_type]}")
            return False
        
        # Vérifier la longueur du pattern (max 249 caractères selon la doc)
        if len(resource_pattern) > 249:
            logger.error(f"Pattern trop long: {len(resource_pattern)} caractères (max 249)")
            return False
        
        return True
    
    def test_api_permissions(self) -> bool:
        """Teste les permissions de l'API Key"""
        logger.info("🔍 Test des permissions de l'API Key...")
        
        try:
            # Test de lecture des role bindings
            response = self.session.get(f"{self.config.base_url}/iam/v2/role-bindings")
            if response.status_code == 200:
                logger.info("✅ Permissions de lecture OK")
            elif response.status_code == 403:
                logger.error("❌ Permissions insuffisantes pour lire les role bindings")
                return False
            else:
                logger.warning(f"⚠️  Réponse inattendue: {response.status_code}")
            
            # Test de lecture des service accounts
            response = self.session.get(f"{self.config.base_url}/iam/v2/service-accounts")
            if response.status_code == 200:
                logger.info("✅ Permissions service accounts OK")
            elif response.status_code == 403:
                logger.error("❌ Permissions insuffisantes pour lire les service accounts")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors du test des permissions: {e}")
            return False
        """Supprime un role binding"""
        url = f"{self.config.base_url}/iam/v2/role-bindings/{binding_id}"
        response = self.session.delete(url)
        
        if response.status_code == 204:
            logger.info(f"✅ Role binding {binding_id} supprimé")
            return True
        else:
            logger.error(f"Erreur lors de la suppression: {response.status_code} - {response.text}")
            return False

class TenantRoleBindingManager:
    """Gestionnaire pour les role bindings d'un tenant"""
    
    def __init__(self, api_client: ConfluentRoleBindingAPI):
        self.api = api_client
    
    def create_tenant_permissions(self, service_account_id: str, project_name: str, 
                                cluster_id: str, environment_id: str = None) -> Dict:
        """Crée toutes les permissions pour un tenant"""
        logger.info(f"🔧 Création des permissions RBAC pour le tenant {project_name}")
        logger.info(f"   Service Account: {service_account_id}")
        logger.info(f"   Cluster: {cluster_id}")
        
        # Test des permissions avant de commencer
        if not self.api.test_api_permissions():
            logger.error("❌ API Key n'a pas les permissions requises")
            return {"successful": [], "failed": [], "skipped": []}
        
        # Définir les permissions à créer avec validation
        permissions = [
            ("DeveloperRead", "topic", f"{project_name}-*", "PREFIXED"),
            ("DeveloperWrite", "topic", f"{project_name}-*", "PREFIXED"),
            ("DeveloperRead", "consumer-group", f"{project_name}-*", "PREFIXED"),
            ("DeveloperWrite", "consumer-group", f"{project_name}-*", "PREFIXED"),
            ("DeveloperRead", "kafka-cluster", cluster_id, "LITERAL")  # Permission générale sur le cluster
        ]
        
        results = {
            "successful": [],
            "failed": [],
            "skipped": []
        }
        
        for role_name, resource_type, pattern, pattern_type in permissions:
            try:
                # Validation avant création
                if not self.api.validate_role_and_resource(role_name, resource_type, pattern):
                    results["failed"].append({
                        "role": role_name,
                        "resource_type": resource_type,
                        "pattern": pattern,
                        "error": "Validation échouée"
                    })
                    continue
                
                # Vérifier si le role binding existe déjà
                existing_bindings = self.api.list_role_bindings(service_account_id)
                exists = any(
                    binding.get('role_name') == role_name and 
                    pattern in binding.get('crn_pattern', '')
                    for binding in existing_bindings
                )
                
                if exists:
                    logger.info(f"ℹ️  Role binding {role_name} déjà existant pour {resource_type}:{pattern}")
                    results["skipped"].append({
                        "role": role_name,
                        "resource_type": resource_type,
                        "pattern": pattern,
                        "reason": "already_exists"
                    })
                    continue
                
                # Créer le role binding
                binding = self.api.create_role_binding(
                    principal=service_account_id,
                    role_name=role_name,
                    resource_type=resource_type,
                    resource_pattern=pattern,
                    cluster_id=cluster_id,
                    environment_id=environment_id,
                    pattern_type=pattern_type
                )
                
                results["successful"].append({
                    "binding_id": binding.get('id'),
                    "role": role_name,
                    "resource_type": resource_type,
                    "pattern": pattern
                })
                
            except requests.exceptions.HTTPError as e:
                error_msg = f"HTTP {e.response.status_code}"
                try:
                    error_detail = e.response.json()
                    if 'errors' in error_detail:
                        error_msg += f": {error_detail['errors'][0].get('detail', error_detail)}"
                    elif 'detail' in error_detail:
                        error_msg += f": {error_detail['detail']}"
                    else:
                        error_msg += f": {error_detail}"
                except:
                    error_msg += f": {e.response.text}"
                
                results["failed"].append({
                    "role": role_name,
                    "resource_type": resource_type,
                    "pattern": pattern,
                    "error": error_msg
                })
                logger.error(f"❌ Échec {role_name} sur {resource_type}:{pattern} - {error_msg}")
                
            except Exception as e:
                results["failed"].append({
                    "role": role_name,
                    "resource_type": resource_type,
                    "pattern": pattern,
                    "error": str(e)
                })
                logger.error(f"❌ Erreur inattendue {role_name} sur {resource_type}:{pattern} - {e}")
        
        # Résumé
        total = len(permissions)
        successful = len(results["successful"])
        failed = len(results["failed"])
        skipped = len(results["skipped"])
        
        print(f"\n📊 Résumé des permissions RBAC:")
        print(f"   ✅ Créées: {successful}")
        print(f"   ⏭️  Ignorées (existantes): {skipped}")
        print(f"   ❌ Échecs: {failed}")
        print(f"   📈 Total: {successful + skipped}/{total} permissions actives")
        
        if failed > 0:
            print(f"\n❌ Échecs détaillés:")
            for failure in results["failed"]:
                print(f"   - {failure['role']} sur {failure['resource_type']}:{failure['pattern']}")
                print(f"     Erreur: {failure['error']}")
        
        return results
    
    def list_tenant_permissions(self, service_account_id: str) -> List[Dict]:
        """Liste les permissions d'un tenant"""
        logger.info(f"📋 Permissions du service account {service_account_id}")
        
        try:
            bindings = self.api.list_role_bindings(service_account_id)
            
            if not bindings:
                print("   Aucune permission trouvée")
                return []
            
            print(f"   Nombre de role bindings: {len(bindings)}")
            print("\n   Détails:")
            for binding in bindings:
                role = binding.get('role_name', 'N/A')
                crn = binding.get('crn_pattern', 'N/A')
                binding_id = binding.get('id', 'N/A')
                print(f"   - {role}: {crn} (ID: {binding_id})")
            
            return bindings
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des permissions: {e}")
            return []
    
    def delete_tenant_permissions(self, service_account_id: str, project_name: str) -> bool:
        """Supprime toutes les permissions d'un tenant"""
        logger.info(f"🗑️  Suppression des permissions pour {project_name}")
        
        try:
            bindings = self.api.list_role_bindings(service_account_id)
            tenant_bindings = [
                b for b in bindings 
                if project_name in b.get('crn_pattern', '')
            ]
            
            if not tenant_bindings:
                logger.info("Aucune permission à supprimer")
                return True
            
            logger.info(f"Suppression de {len(tenant_bindings)} permissions...")
            
            deleted = 0
            for binding in tenant_bindings:
                binding_id = binding.get('id')
                if binding_id and self.api.delete_role_binding(binding_id):
                    deleted += 1
            
            logger.info(f"✅ {deleted}/{len(tenant_bindings)} permissions supprimées")
            return deleted == len(tenant_bindings)
            
        except Exception as e:
            logger.error(f"Erreur lors de la suppression: {e}")
            return False

def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(
        description="Gestionnaire de role bindings RBAC pour Confluent Cloud",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples d'utilisation:
  python create_role_bindings.py create --service-account sa-abc123 --project my-project --cluster lkc-xyz789
  python create_role_bindings.py list --service-account sa-abc123
  python create_role_bindings.py delete --service-account sa-abc123 --project my-project
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commandes disponibles')
    
    # Commande create
    create_parser = subparsers.add_parser('create', help='Créer les permissions pour un tenant')
    create_parser.add_argument('--service-account', required=True,
                              help='ID du service account (ex: sa-abc123)')
    create_parser.add_argument('--project', required=True,
                              help='Nom du projet/tenant')
    create_parser.add_argument('--cluster', required=True,
                              help='ID du cluster Kafka (ex: lkc-abc123)')
    create_parser.add_argument('--environment',
                              help='ID de l\'environnement (détecté automatiquement si omis)')
    
    # Commande list
    list_parser = subparsers.add_parser('list', help='Lister les permissions d\'un service account')
    list_parser.add_argument('--service-account', required=True,
                            help='ID du service account')
    
    # Commande delete
    delete_parser = subparsers.add_parser('delete', help='Supprimer les permissions d\'un tenant')
    delete_parser.add_argument('--service-account', required=True,
                              help='ID du service account')
    delete_parser.add_argument('--project', required=True,
                              help='Nom du projet/tenant')
    
    # Commande test
    test_parser = subparsers.add_parser('test', help='Tester les permissions et la configuration')
    test_parser.add_argument('--cluster',
                            help='ID du cluster pour tester les CRN patterns')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    try:
        # Configuration avec les API keys chargées
        config = ConfluentConfig(
            api_key=CONFLUENT_API_KEY,
            api_secret=CONFLUENT_API_SECRET
        )
        
        # Initialisation des clients
        api_client = ConfluentRoleBindingAPI(config)
        manager = TenantRoleBindingManager(api_client)
        
        # Exécution des commandes
        if args.command == 'create':
            results = manager.create_tenant_permissions(
                service_account_id=args.service_account,
                project_name=args.project,
                cluster_id=args.cluster,
                environment_id=args.environment
            )
            
            if len(results["failed"]) == 0:
                print(f"\n🎉 Toutes les permissions ont été créées avec succès pour {args.project}!")
            else:
                print(f"\n⚠️  Permissions partiellement créées. Vérifiez les erreurs ci-dessus.")
            
        elif args.command == 'list':
            manager.list_tenant_permissions(args.service_account)
            
        elif args.command == 'delete':
            success = manager.delete_tenant_permissions(args.service_account, args.project)
            if success:
                print(f"✅ Permissions supprimées pour {args.project}")
            else:
                print(f"❌ Erreur lors de la suppression")
                
        elif args.command == 'test':
            print("🧪 Test de la configuration et des permissions\n")
            
            # Test des permissions de base
            if api_client.test_api_permissions():
                print("✅ API Key valide avec permissions suffisantes")
            else:
                print("❌ Problème avec les permissions de l'API Key")
            
            # Test spécifique au cluster si fourni
            if args.cluster:
                try:
                    cluster_info = api_client.get_cluster_info(args.cluster)
                    env_id = cluster_info.get('spec', {}).get('environment', {}).get('id')
                    print(f"✅ Cluster {args.cluster} trouvé dans l'environment {env_id}")
                    
                    # Test de pattern CRN
                    test_crn = f"crn://confluent.cloud/organization=*/environment={env_id}/cloud-cluster={args.cluster}/kafka={args.cluster}/topic=test-*"
                    print(f"📝 Pattern CRN qui sera utilisé:")
                    print(f"   {test_crn}")
                    
                except Exception as e:
                    print(f"❌ Erreur avec le cluster {args.cluster}: {e}")
            
            print(f"\n💡 Pour créer des permissions:")
            print(f"   python create_role_bindings.py create --service-account sa-xxx --project my-project --cluster lkc-xxx")
    
    except Exception as e:
        logger.error(f"Erreur: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
