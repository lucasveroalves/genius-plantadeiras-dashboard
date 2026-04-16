"""
Utilitário para gerar hashes bcrypt das senhas dos usuários.
Execute: python gerar_senhas.py
Cole os hashes gerados no arquivo .streamlit/secrets.toml
"""
import bcrypt
import getpass

USUARIOS = [
    "admin",
    "gerente1",
    "vendedor1",
    "vendedor2",
    "analista1",
    "analista2",
    "consultor",
]

print("=" * 60)
print("  Genius Plantadeiras — Gerador de Senhas")
print("=" * 60)
print("Digite a senha para cada usuário (min. 8 caracteres).")
print("Os hashes serão exibidos para copiar no secrets.toml\n")

hashes = {}
for usuario in USUARIOS:
    while True:
        senha = getpass.getpass(f"Senha para '{usuario}': ")
        if len(senha) < 8:
            print("  ⚠️  Senha muito curta. Use pelo menos 8 caracteres.")
            continue
        confirmacao = getpass.getpass(f"Confirme a senha para '{usuario}': ")
        if senha != confirmacao:
            print("  ❌ As senhas não coincidem. Tente novamente.")
            continue
        hash_gerado = bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()
        hashes[usuario] = hash_gerado
        print(f"  ✅ Hash gerado para '{usuario}'\n")
        break

print("\n" + "=" * 60)
print("  Cole o bloco abaixo em .streamlit/secrets.toml")
print("=" * 60)
print("\n[users]")
for usuario, hash_val in hashes.items():
    print(f'{usuario:<12} = "{hash_val}"')
