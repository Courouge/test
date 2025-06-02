#!/usr/bin/env python3
"""
Confluent Cloud Tenant Manager Unifié
Combine la création de tenants et la gestion RBAC en une seule interface
"""

import os
import logging
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
    topics: List[str] = None
    consumer_groups: List[str] = None
    schemas: List[str] = None

class UnifiedTenantManager:
    """Gestionnaire unifié pour les tenants et RBAC"""

    def __init__(self, api_key: str, api_secret: str):
        self.config = ConfluentConfig(api_key=api_key, api_secret=api_secret)
        self.tenant_manager = ConfluentTenantManager(self.config)
        self.rbac_manager = ConfluentRoleBindingManager(api_key, api_secret)
        self.resource_helper = ConfluentResourceHelper()
        self.api = ConfluentCloudAPI(self.config)

    def _get_or_create_service_account(self, project_name: str) -> Dict:
        """
        Récupère un service account existant ou en crée un nouveau
        
        Args:
            project_name: Nom du projet/tenant
            
        Returns:
            Dict contenant les informations du service account
        """
        # Essayer de trouver un service account existant
        existing_sa = self.api.get_service_account_by_name(project_name)
        if existing_sa:
            logger.info(f"Service account existant trouvé pour {project_name}")
            return existing_sa

        # Si aucun service account n'existe, en créer un nouveau
        logger.info(f"Création d'un nouveau service account pour {project_name}")
        return self.api.create_service_account(
            name=project_name,
            description=f"Service account pour le tenant {project_name}"
        )

    def create_tenant_with_rbac(self, tenant_config: TenantConfig) -> Dict:
        """
        Crée un tenant et configure ses permissions RBAC
        
        Args:
            tenant_config: Configuration du tenant
            
        Returns:
            Dict contenant les informations du tenant créé
        """
        try:
            # 1. Créer ou récupérer le service account
            service_account = self._get_or_create_service_account(tenant_config.project_name)
            service_account_id = service_account['id']

            # 2. Créer l'API key pour le cluster
            api_key = self.api.create_api_key(service_account_id, tenant_config.cluster_id)
            
            # 3. Configurer les permissions RBAC
            # Permissions sur les topics
            if tenant_config.topics:
                for topic in tenant_config.topics:
                    crn = self.resource_helper.kafka_topic_crn(
                        org_id="*",  # Utiliser l'org courante
                        env_id=tenant_config.environment_id or "*",
                        cluster_id=tenant_config.cluster_id,
                        topic_name=topic
                    )
                    self.rbac_manager.create_role_binding(
                        principal=f"User:{service_account_id}",
                        role_name="DeveloperRead",
                        crn_pattern=crn
                    )

            # Permissions sur les consumer groups
            if tenant_config.consumer_groups:
                for group in tenant_config.consumer_groups:
                    crn = self.resource_helper.kafka_consumer_group_crn(
                        org_id="*",
                        env_id=tenant_config.environment_id or "*",
                        cluster_id=tenant_config.cluster_id,
                        consumer_group=group
                    )
                    self.rbac_manager.create_role_binding(
                        principal=f"User:{service_account_id}",
                        role_name="DeveloperRead",
                        crn_pattern=crn
                    )

            return {
                'service_account_id': service_account_id,
                'api_key': api_key['spec']['key'],
                'api_secret': api_key['spec']['secret']
            }

        except Exception as e:
            logger.error(f"Erreur lors de la création du tenant: {str(e)}")
            raise

    def delete_tenant(self, project_name: str) -> bool:
        """Supprime un tenant et ses permissions RBAC"""
        return self.tenant_manager.delete_tenant(project_name)

def main():
    """Exemple d'utilisation"""
    # Lire les clés API
    API_KEY, API_SECRET = read_api_keys("api-key-test.txt")
    
    # Créer le gestionnaire unifié
    manager = UnifiedTenantManager(API_KEY, API_SECRET)
    
    # Configuration du tenant
    tenant_config = TenantConfig(
        project_name="taas.cagip.factory1",
        cluster_id="lkc-xwp2kx",
        environment_id=None,  # Optionnel
        topics=["topic1", "topic2"],
        consumer_groups=["group1", "group2"]
    )
    
    try:
        # Créer le tenant avec RBAC
        result = manager.create_tenant_with_rbac(tenant_config)
        print(f"Tenant créé avec succès: {result}")
    except Exception as e:
        logger.error(f"Erreur lors de l'exécution: {str(e)}")

if __name__ == "__main__":
    main() 