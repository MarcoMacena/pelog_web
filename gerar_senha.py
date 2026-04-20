import bcrypt

senha = "1234"
hash_senha = bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
print(hash_senha)
