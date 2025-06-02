#!/usr/bin/env python3
"""
Script simple pour lire API key et Secret depuis api-key.txt
"""

def read_api_keys(filename="api-key.txt"):
    """Lit les clés API depuis un fichier texte"""
    try:
        with open(filename, 'r') as file:
            lines = file.read().strip().split('\n')

        api_key = None
        api_secret = None

        for i, line in enumerate(lines):
            line = line.strip()
            if line.startswith('API key') and i + 1 < len(lines):
                api_key = lines[i + 1].strip()
            elif line.startswith('API secret') and i + 1 < len(lines):
                api_secret = lines[i + 1].strip()

        return api_key, api_secret

    except FileNotFoundError:
        print(f"Fichier {filename} introuvable")
        return None, None
    except Exception as e:
        print(f"Erreur lecture: {e}")
        return None, None

if __name__ == "__main__":
    api_key, api_secret = read_api_keys("api-key-test.txt")
