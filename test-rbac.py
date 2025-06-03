import argparse
import sys

def main():
    """Exemple d'utilisation avec paramètres configurables"""
    # Configuration des arguments en ligne de commande
    parser = argparse.ArgumentParser(description='Gestionnaire de tenant unifié')
    parser.add_argument('--project-name', 
                       default="org.entity.factory1",
                       help='Nom du projet (défaut: org.entity.factory1)')
    parser.add_argument('--cluster-id', 
                       default="lkc-xwp2kx",
                       help='ID du cluster (défaut: lkc-xwp2kx)')
    parser.add_argument('--environment-id', 
                       default="env-036012",
                       help='ID de l\'environnement (défaut: env-036012)')
    parser.add_argument('--organization-id', 
                       default="org",
                       help='ID de l\'organisation (défaut: org)')
    parser.add_argument('--api-keys-file',
                       default="api-key-test.txt",
                       help='Fichier contenant les clés API (défaut: api-key-test.txt)')
    
    args = parser.parse_args()
    
    try:
        # Lire les clés API
        API_KEY, API_SECRET = read_api_keys(args.api_keys_file)
        logger.info(f"Utilisation des clés API de test: {API_KEY}")
        
        # Créer le gestionnaire unifié
        manager = UnifiedTenantManager(API_KEY, API_SECRET, organization_id=args.organization_id)
        
        # Configuration du tenant avec les paramètres fournis
        tenant_config = TenantConfig(
            project_name=args.project_name, 
            cluster_id=args.cluster_id,
            environment_id=args.environment_id,
            organization_id=args.organization_id
        )
        
        print(f"🔧 Configuration du tenant:")
        print(f"   Projet: {args.project_name}")
        print(f"   Cluster: {args.cluster_id}")
        print(f"   Environnement: {args.environment_id}")
        print(f"   Organisation: {args.organization_id}")
        print()
        
        # Créer le tenant avec RBAC
        result = manager.create_tenant_with_rbac(tenant_config)
        print(f"🎉 Tenant configuré avec succès!")
        print(f"   Service Account ID: {result['service_account_id']}")
        print(f"   API Key: {result['api_key']}")
        print(f"   API Secret: {result['api_secret']}")
        print(f"   Préfixe pour les ressources: {result['prefix']}")
        
        # Afficher le statut des ressources
        existing = result['existing_resources']
        print(f"\n📊 Statut des ressources:")
        print(f"   Service Account: {'✅ Existant' if existing['service_account'] else '🆕 Nouveau'}")
        print(f"   API Key: {'✅ Existante' if existing['api_key'] else '🆕 Nouvelle'}")
        print(f"   Permissions RBAC: {'✅ Existantes' if existing['permissions'] else '🆕 Nouvelles'}")
        
    except Exception as e:
        logger.error(f"Erreur lors de l'exécution: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
