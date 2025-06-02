#!/usr/bin/env python3
"""
Confluent Cloud Tenant Manager Unifié
Combine la création de tenants et la gestion RBAC en une seule interface
Implémente une stratégie de multitenancy basée sur les préfixes et l'isolation
"""

import os
import logging
import re
from typing import Dict, List, Optional
from dataclasses import dataclass
from create_tenant import ConfluentConfig, ConfluentCloudAPI, ConfluentTenantManager
from rbac import ConfluentRoleBindingManager, ConfluentResourceHelper
from read_api_key_file import read_api_keys

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class TenantConfig:
    """Configuration pour un tenant"""
    project_name: str
    cluster_id: str
    environment_id: Optional[str] = None

class UnifiedTenantManager:
    """Gestionnaire unifié pour les tenants et RBAC"""

    def __init__(self, api_key: str, api_secret: str):
        self.config = ConfluentConfig(api_key=api_key, api_secret=api_secret)
        self.tenant_manager = ConfluentTenantManager(self.config)
        self.rbac_manager = ConfluentRoleBindingManager(api_key, api_secret)
        self.resource_helper = ConfluentResourceHelper()
        self.api = ConfluentCloudAPI(self.config)

    def _format_service_account_name(self, project_name: str) -> str:
        """
        Formate le nom du service account selon les conventions Confluent
        
        Args:
            project_name: Nom du projet
            
        Returns:
            Nom formaté pour le service account
        """
        # Remplacer les caractères non autorisés par des tirets
        name = re.sub(r'[^a-zA-Z0-9-]', '-', project_name)
        # S'assurer que le nom commence par une lettre
        if not name[0].isalpha():
            name = 'sa-' + name
        # Limiter la longueur à 64 caractères
        return name[:64]

    def _get_or_create_service_account(self, project_name: str) -> Dict:
        """
        Récupère un service account existant ou en crée un nouveau
        
        Args:
            project_name: Nom du projet/tenant
            
        Returns:
            Dict contenant les informations du service account
        """
        # Formater le nom du service account
        sa_name = self._format_service_account_name(project_name)
        logger.info(f"Recherche du service account avec le nom formaté: {sa_name}")

        # Essayer de trouver un service account existant
        existing_sa = self.api.get_service_account_by_name(sa_name)
        if existing_sa:
            logger.info(f"Service account existant trouvé pour {sa_name}")
            return existing_sa

        # Si aucun service account n'existe, en créer un nouveau
        logger.info(f"Création d'un nouveau service account pour {sa_name}")
        return self.api.create_service_account(
            name=sa_name,
            description=f"Service account pour le tenant {project_name}"
        )

    def _setup_tenant_permissions(self, service_account_id: str, project_name: str, cluster_id: str, environment_id: str = None):
        """
        Configure les permissions pour le tenant avec isolation
        
        Args:
            service_account_id: ID du service account
            project_name: Nom du projet (utilisé comme préfixe)
            cluster_id: ID du cluster
            environment_id: ID de l'environnement (optionnel)
        """
        try:
            # 1. Permissions sur le cluster (lecture seule)
            cluster_crn = self.resource_helper.kafka_cluster_crn(
                org_id="*",
                env_id=environment_id or "*",
                cluster_id=cluster_id
            )
            logger.info(f"Configuration des permissions CloudClusterAdmin pour {service_account_id}")
            self.rbac_manager.create_role_binding(
                principal=f"User:{service_account_id}",
                role_name="CloudClusterAdmin",
                crn_pattern=cluster_crn
            )

            # 2. Permissions sur l'environnement si spécifié
            if environment_id:
                env_crn = self.resource_helper.environment_crn(
                    org_id="*",
                    env_id=environment_id
                )
                logger.info(f"Configuration des permissions EnvironmentAdmin pour {service_account_id}")
                self.rbac_manager.create_role_binding(
                    principal=f"User:{service_account_id}",
                    role_name="EnvironmentAdmin",
                    crn_pattern=env_crn
                )

            # 3. Permissions sur les topics avec préfixe (lecture/écriture)
            topic_crn = self.resource_helper.kafka_topic_crn(
                org_id="*",
                env_id=environment_id or "*",
                cluster_id=cluster_id,
                topic_name=f"{project_name}.*"
            )
            logger.info(f"Configuration des permissions DeveloperRead pour les topics avec préfixe {project_name}.*")
            self.rbac_manager.create_role_binding(
                principal=f"User:{service_account_id}",
                role_name="DeveloperRead",
                crn_pattern=topic_crn
            )

            # 4. Permissions sur les consumer groups avec préfixe
            group_crn = self.resource_helper.kafka_consumer_group_crn(
                org_id="*",
                env_id=environment_id or "*",
                cluster_id=cluster_id,
                consumer_group=f"{project_name}.*"
            )
            logger.info(f"Configuration des permissions DeveloperRead pour les consumer groups avec préfixe {project_name}.*")
            self.rbac_manager.create_role_binding(
                principal=f"User:{service_account_id}",
                role_name="DeveloperRead",
                crn_pattern=group_crn
            )

            # 5. Permissions sur les schemas avec préfixe
            schema_crn = f"crn://confluent.cloud/organization=*/environment={environment_id or '*'}/schema-registry=*/subject={project_name}.*"
            logger.info(f"Configuration des permissions DeveloperRead pour les schemas avec préfixe {project_name}.*")
            self.rbac_manager.create_role_binding(
                principal=f"User:{service_account_id}",
                role_name="DeveloperRead",
                crn_pattern=schema_crn
            )

        except Exception as e:
            logger.error(f"Erreur lors de la configuration des permissions tenant: {str(e)}")
            raise

    def create_tenant_with_rbac(self, tenant_config: TenantConfig) -> Dict:
        """
        Crée un tenant et configure ses permissions RBAC avec isolation
        
        Args:
            tenant_config: Configuration du tenant
            
        Returns:
            Dict contenant les informations du tenant créé
        """
        try:
            # 1. Créer ou récupérer le service account
            service_account = self._get_or_create_service_account(tenant_config.project_name)
            service_account_id = service_account['id']
            logger.info(f"Service account ID: {service_account_id}")

            # 2. Créer l'API key pour le cluster
            api_key = self.api.create_api_key(service_account_id, tenant_config.cluster_id)
            logger.info(f"API Key créée: {api_key['spec']['key']}")
            
            # 3. Configurer les permissions avec isolation
            self._setup_tenant_permissions(
                service_account_id=service_account_id,
                project_name=tenant_config.project_name,
                cluster_id=tenant_config.cluster_id,
                environment_id=tenant_config.environment_id
            )

            return {
                'service_account_id': service_account_id,
                'api_key': api_key['spec']['key'],
                'api_secret': api_key['spec']['secret'],
                'prefix': f"{tenant_config.project_name}.*"
            }

        except Exception as e:
            logger.error(f"Erreur lors de la création du tenant: {str(e)}")
            raise

    def delete_tenant(self, project_name: str) -> bool:
        """Supprime un tenant et ses permissions RBAC"""
        return self.tenant_manager.delete_tenant(project_name)

def main():
    """Exemple d'utilisation"""
    # Lire les clés API de test
    API_KEY, API_SECRET = read_api_keys("api-key-test.txt")
    logger.info(f"Utilisation des clés API de test: {API_KEY}")
    
    # Créer le gestionnaire unifié
    manager = UnifiedTenantManager(API_KEY, API_SECRET)
    
    # Configuration du tenant
    tenant_config = TenantConfig(
        project_name="taas.cagip.factory1",
        cluster_id="lkc-xwp2kx",
        environment_id="env-036012"
    )
    
    try:
        # Créer le tenant avec RBAC
        result = manager.create_tenant_with_rbac(tenant_config)
        print(f"Tenant créé avec succès: {result}")
        print(f"Le tenant peut créer des ressources avec le préfixe: {result['prefix']}")
    except Exception as e:
        logger.error(f"Erreur lors de l'exécution: {str(e)}")

if __name__ == "__main__":
    main() 