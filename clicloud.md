# Tutoriel Role Binding Confluent Cloud avec Python

## Prérequis

### Installation des dépendances
```bash
pip install confluent-cloud-sdk requests python-dotenv
```

### Configuration des variables d'environnement
Créez un fichier `.env` :
```
CONFLUENT_CLOUD_API_KEY=your_api_key
CONFLUENT_CLOUD_API_SECRET=your_api_secret
CONFLUENT_CLOUD_ENVIRONMENT_ID=your_environment_id
CONFLUENT_CLOUD_CLUSTER_ID=your_cluster_id  # optionnel selon le scope
```

## Configuration de base

```python
import os
import requests
import base64
from dotenv import load_dotenv
import json

load_dotenv()

class ConfluentCloudRoleBinding:
    def __init__(self):
        self.api_key = os.getenv('CONFLUENT_CLOUD_API_KEY')
        self.api_secret = os.getenv('CONFLUENT_CLOUD_API_SECRET')
        self.base_url = "https://api.confluent.cloud"
        self.headers = self._get_headers()
        
    def _get_headers(self):
        # Authentification Basic Auth
        credentials = f"{self.api_key}:{self.api_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        return {
            'Authorization': f'Basic {encoded_credentials}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
```

## Gestion des Role Bindings

### Lister tous les role bindings

```python
    def list_role_bindings(self, principal=None, role_name=None):
        """
        Liste tous les role bindings avec filtres optionnels
        """
        url = f"{self.base_url}/iam/v2/role-bindings"
        params = {}
        
        if principal:
            params['principal'] = principal
        if role_name:
            params['role_name'] = role_name
            
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Erreur lors de la récupération des role bindings: {e}")
            return None
```

### Créer un role binding

```python
    def create_role_binding(self, principal, role_name, crn_pattern):
        """
        Crée un nouveau role binding
        
        Args:
            principal: L'utilisateur ou service account (ex: "User:john@example.com")
            role_name: Le nom du rôle (ex: "EnvironmentAdmin", "CloudClusterAdmin", etc.)
            crn_pattern: Le pattern CRN définissant le scope
        """
        url = f"{self.base_url}/iam/v2/role-bindings"
        
        payload = {
            "principal": principal,
            "role_name": role_name,
            "crn_pattern": crn_pattern
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Erreur lors de la création du role binding: {e}")
            if response.status_code == 400:
                print(f"Détails de l'erreur: {response.text}")
            return None
```

### Obtenir un role binding spécifique

```python
    def get_role_binding(self, role_binding_id):
        """
        Récupère un role binding par son ID
        """
        url = f"{self.base_url}/iam/v2/role-bindings/{role_binding_id}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Erreur lors de la récupération du role binding: {e}")
            return None
```

### Supprimer un role binding

```python
    def delete_role_binding(self, role_binding_id):
        """
        Supprime un role binding
        """
        url = f"{self.base_url}/iam/v2/role-bindings/{role_binding_id}"
        
        try:
            response = requests.delete(url, headers=self.headers)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            print(f"Erreur lors de la suppression du role binding: {e}")
            return False
```

## Patterns CRN couramment utilisés

```python
    def get_crn_patterns(self):
        """
        Retourne les patterns CRN les plus courants
        """
        environment_id = os.getenv('CONFLUENT_CLOUD_ENVIRONMENT_ID')
        cluster_id = os.getenv('CONFLUENT_CLOUD_CLUSTER_ID')
        
        patterns = {
            # Accès à tout l'environnement
            'environment_admin': f"crn://confluent.cloud/environment={environment_id}",
            
            # Accès à un cluster spécifique
            'cluster_admin': f"crn://confluent.cloud/environment={environment_id}/cloud-cluster={cluster_id}",
            
            # Accès à des topics spécifiques
            'topic_read': f"crn://confluent.cloud/environment={environment_id}/cloud-cluster={cluster_id}/kafka=*/topic=my-topic",
            
            # Accès à tous les topics d'un cluster
            'all_topics': f"crn://confluent.cloud/environment={environment_id}/cloud-cluster={cluster_id}/kafka=*/topic=*",
            
            # Accès global (organisation)
            'organization_admin': "crn://confluent.cloud/"
        }
        
        return patterns
```

## Rôles disponibles

```python
    def get_available_roles(self):
        """
        Liste les rôles disponibles dans Confluent Cloud
        """
        roles = {
            # Rôles d'organisation
            'OrganizationAdmin': 'Administrateur de l\'organisation complète',
            'Operator': 'Opérateur avec accès étendu',
            'EnvironmentAdmin': 'Administrateur d\'environnement',
            
            # Rôles de cluster
            'CloudClusterAdmin': 'Administrateur de cluster cloud',
            'DeveloperRead': 'Développeur en lecture seule',
            'DeveloperWrite': 'Développeur avec droits d\'écriture',
            'DeveloperManage': 'Développeur avec droits de gestion',
            
            # Rôles spécialisés
            'MetricsViewer': 'Visualiseur de métriques',
            'AccountingViewer': 'Visualiseur de facturation',
            'FlinkAdmin': 'Administrateur Flink',
            'FlinkDeveloper': 'Développeur Flink'
        }
        
        return roles
```

## Exemples d'utilisation

```python
def main():
    # Initialisation
    rb_manager = ConfluentCloudRoleBinding()
    
    # 1. Lister tous les role bindings
    print("=== Liste des role bindings ===")
    role_bindings = rb_manager.list_role_bindings()
    if role_bindings:
        for rb in role_bindings.get('data', []):
            print(f"ID: {rb['id']}, Principal: {rb['principal']}, Role: {rb['role_name']}")
    
    # 2. Créer un role binding pour un développeur
    print("\n=== Création d'un role binding ===")
    patterns = rb_manager.get_crn_patterns()
    
    new_role_binding = rb_manager.create_role_binding(
        principal="User:developer@example.com",
        role_name="DeveloperWrite",
        crn_pattern=patterns['cluster_admin']
    )
    
    if new_role_binding:
        print(f"Role binding créé avec l'ID: {new_role_binding['id']}")
        role_binding_id = new_role_binding['id']
        
        # 3. Récupérer le role binding créé
        print(f"\n=== Détails du role binding {role_binding_id} ===")
        details = rb_manager.get_role_binding(role_binding_id)
        if details:
            print(json.dumps(details, indent=2))
        
        # 4. Supprimer le role binding (optionnel)
        # print(f"\n=== Suppression du role binding {role_binding_id} ===")
        # if rb_manager.delete_role_binding(role_binding_id):
        #     print("Role binding supprimé avec succès")

if __name__ == "__main__":
    main()
```

## Cas d'usage avancés

### Gestion par équipe

```python
def setup_team_permissions(rb_manager, team_name, members, environment_id, cluster_id):
    """
    Configure les permissions pour une équipe
    """
    patterns = rb_manager.get_crn_patterns()
    
    # Créer un topic dédié à l'équipe
    team_topic_pattern = f"crn://confluent.cloud/environment={environment_id}/cloud-cluster={cluster_id}/kafka=*/topic={team_name}-*"
