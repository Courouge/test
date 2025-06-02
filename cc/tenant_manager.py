#!/usr/bin/env python3
"""
Confluent Cloud Tenant Manager Unifié
Combine la création de tenants et la gestion RBAC en une seule interface
"""

import os
from typing import Dict, List, Optional
from dataclasses import dataclass
from create_tenant import ConfluentConfig, ConfluentCloudAPI, ConfluentTenantManager
from rbac import ConfluentRoleBindingManager, ConfluentResourceHelper
from read_api_key_file import read_api_keys

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

    def create_tenant_with_rbac(self, tenant_config: TenantConfig) -> Dict:
        """
        Crée un tenant et configure ses permissions RBAC
        
        Args:
            tenant_config: Configuration du tenant
            
        Returns:
            Dict contenant les informations du tenant créé
        """
        # 1. Créer le tenant
        tenant_info = self.tenant_manager.create_tenant(
            project_name=tenant_config.project_name,
            cluster_id=tenant_config.cluster_id,
            environment_id=tenant_config.environment_id
        )

        # 2. Configurer les permissions RBAC
        service_account_id = tenant_info['service_account_id']
        
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

        return tenant_info

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
        project_name="mon-tenant",
        cluster_id="lkc-xxxxx",
        environment_id="env-xxxxx",
        topics=["topic1", "topic2"],
        consumer_groups=["group1", "group2"]
    )
    
    # Créer le tenant avec RBAC
    result = manager.create_tenant_with_rbac(tenant_config)
    print(f"Tenant créé avec succès: {result}")

if __name__ == "__main__":
    main() 