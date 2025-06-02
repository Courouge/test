import requests
from requests.auth import HTTPBasicAuth
import json

api_key = "VOTRE_API_KEY"
api_secret = "VOTRE_API_SECRET"

def debug_role_bindings():
    base_url = "https://api.confluent.cloud"
    auth = HTTPBasicAuth(api_key, api_secret)
    
    print("=== DEBUG ROLE BINDINGS ===\n")
    
    # Test 1: Headers différents
    print("1. 🧪 Test avec différents headers")
    print("-" * 40)
    
    header_variants = [
        {'Content-Type': 'application/json'},
        {'Accept': 'application/json'},
        {'Content-Type': 'application/json', 'Accept': 'application/json'},
        {}  # Pas de headers
    ]
    
    for i, headers in enumerate(header_variants, 1):
        print(f"\nTest {i}: Headers = {headers}")
        
        try:
            response = requests.get(f"{base_url}/iam/v2/role-bindings", auth=auth, headers=headers)
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    bindings = data.get('data', [])
                    print(f"   ✅ Succès! {len(bindings)} role binding(s)")
                    
                    if bindings and len(bindings) <= 2:  # Afficher si peu de résultats
                        for binding in bindings:
                            print(f"      - {binding.get('principal')} → {binding.get('role_name')}")
                    break  # Sortir dès qu'on a du succès
                    
                except Exception as e:
                    print(f"   ⚠️  JSON Error: {e}")
                    print(f"   Raw: {response.text[:200]}...")
            else:
                print(f"   ❌ Error: {response.text[:200]}...")
                
        except Exception as e:
            print(f"   💥 Request Error: {e}")
    
    print("\n" + "="*60 + "\n")
    
    # Test 2: Méthodes HTTP différentes
    print("2. 🧪 Test avec méthodes HTTP différentes")
    print("-" * 50)
    
    headers = {'Accept': 'application/json'}  # Utiliser Accept au lieu de Content-Type
    
    methods = ['GET', 'POST']
    for method in methods:
        print(f"\nTest {method}:")
        
        try:
            if method == 'GET':
                response = requests.get(f"{base_url}/iam/v2/role-bindings", auth=auth, headers=headers)
            else:
                # POST avec body vide
                response = requests.post(f"{base_url}/iam/v2/role-bindings", auth=auth, headers=headers, json={})
            
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text[:300]}...")
            
        except Exception as e:
            print(f"   Error: {e}")
    
    print("\n" + "="*60 + "\n")
    
    # Test 3: Avec paramètres simples
    print("3. 🧪 Test avec paramètres simples")
    print("-" * 40)
    
    headers = {'Accept': 'application/json'}
    
    # Récupérer d'abord les utilisateurs pour avoir un principal valide
    user_response = requests.get(f"{base_url}/iam/v2/users", auth=auth, headers=headers)
    
    test_principal = None
    if user_response.status_code == 200:
        users = user_response.json().get('data', [])
        if users:
            test_principal = f"User:{users[0].get('id')}"
            print(f"Principal de test trouvé: {test_principal}")
    
    param_tests = [
        {},  # Aucun paramètre
        {'page_size': '10'},  # Pagination
        {'principal': test_principal} if test_principal else {'role_name': 'OrganizationAdmin'},  # Filtre simple
    ]
    
    for i, params in enumerate(param_tests, 1):
        print(f"\nTest {i}: Params = {params}")
        
        try:
            response = requests.get(f"{base_url}/iam/v2/role-bindings", 
                                    auth=auth, headers=headers, params=params)
            print(f"   Status: {response.status_code}")
            print(f"   URL finale: {response.url}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    bindings = data.get('data', [])
                    print(f"   ✅ Succès! {len(bindings)} résultat(s)")
                    
                    if bindings:
                        print("   📋 Exemple de role binding:")
                        binding = bindings[0]
                        for key, value in binding.items():
                            print(f"      {key}: {value}")
                        break
                    
                except Exception as e:
                    print(f"   JSON Error: {e}")
            else:
                print(f"   ❌ Erreur: {response.text[:200]}...")
                
        except Exception as e:
            print(f"   Request Error: {e}")
    
    print("\n" + "="*60 + "\n")
    
    # Test 4: Vérifier la version de l'API
    print("4. 🧪 Test versions d'API alternatives")
    print("-" * 45)
    
    api_versions = [
        "/iam/v2/role-bindings",
        "/iam/v1/role-bindings",  # Version antérieure
        "/rbac/v1/role-bindings",  # Autre endpoint possible
    ]
    
    headers = {'Accept': 'application/json'}
    
    for endpoint in api_versions:
        print(f"\nTest: {endpoint}")
        
        try:
            response = requests.get(f"{base_url}{endpoint}", auth=auth, headers=headers)
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                print(f"   ✅ Endpoint valide!")
                try:
                    data = response.json()
                    if 'data' in data:
                        print(f"   📊 {len(data['data'])} élément(s)")
                except:
                    pass
            elif response.status_code == 404:
                print(f"   ⚠️  Endpoint non trouvé")
            else:
                print(f"   ❌ {response.text[:100]}...")
                
        except Exception as e:
            print(f"   Error: {e}")

if __name__ == "__main__":
    debug_role_bindings()
