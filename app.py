from flask import Flask, render_template, request, redirect, session, send_file
import psycopg2
from datetime import datetime
import pandas as pd
import bcrypt
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "pelog_secret")

# =============================
# CONEXÃO
# =============================
def conectar():
    return psycopg2.connect(
        database=os.environ.get("DB_NAME"),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        host=os.environ.get("DB_HOST"),
        port=os.environ.get("DB_PORT", "5432")
    )

# =============================
# LOGIN
# =============================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form["usuario"]
        senha = request.form["senha"]

        conn = conectar()
        cur = conn.cursor()

        cur.execute(
            "SELECT senha, nivel FROM usuarios WHERE username = %s",
            (user,)
        )
        resultado = cur.fetchone()

        cur.close()
        conn.close()

        if resultado:
            senha_hash, nivel = resultado

            try:
                if bcrypt.checkpw(senha.encode("utf-8"), senha_hash.encode("utf-8")):
                    session["user"] = user
                    session["nivel"] = nivel
                    return redirect("/dashboard")
            except ValueError:
                return "Hash de senha inválido no banco. Recrie esse usuário."

        return "Usuário ou senha inválidos!"

    return render_template("login.html")

# =============================
# DASHBOARD
# =============================
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")

    busca = request.args.get("busca")

    conn = conectar()
    cur = conn.cursor()

    if busca:
        cur.execute("""
            SELECT * FROM caminhoes
            WHERE placa ILIKE %s
            ORDER BY horario DESC
        """, ('%' + busca + '%',))
    else:
        cur.execute("""
            SELECT * FROM caminhoes
            ORDER BY horario DESC
        """)

    dados = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("dashboard.html", dados=dados)

# =============================
# ENTRADA
# =============================
@app.route("/entrada", methods=["POST"])
def entrada():
    if "user" not in session:
        return redirect("/")

    try:
        conn = conectar()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO caminhoes (
                placa, motorista, cpf, empresa,
                tipo_material, nota_fiscal, doca, horario
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            request.form.get("placa"),
            request.form.get("motorista"),
            request.form.get("cpf"),
            request.form.get("empresa"),
            request.form.get("material"),
            request.form.get("nf"),
            request.form.get("doca"),
            datetime.now()
        ))

        conn.commit()
        cur.close()
        conn.close()

        return redirect("/dashboard")

    except Exception as e:
        return f"Erro ao registrar entrada: {e}"

# =============================
# SAÍDA
# =============================
@app.route("/saida/<int:id>")
def saida(id):
    if "user" not in session:
        return redirect("/")

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        UPDATE caminhoes
        SET horario_saida = %s
        WHERE id = %s
    """, (datetime.now(), id))

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/dashboard")

# =============================
# RELATÓRIO
# =============================
@app.route("/relatorio")
def relatorio():
    if "user" not in session:
        return redirect("/")

    inicio = request.args.get("inicio")
    fim = request.args.get("fim")

    conn = conectar()

    if inicio and fim:
        query = """
            SELECT * FROM caminhoes
            WHERE horario BETWEEN %s AND %s
        """
        df = pd.read_sql(query, conn, params=(inicio, fim))
    else:
        df = pd.read_sql("SELECT * FROM caminhoes", conn)

    caminho = "relatorio.xlsx"
    df.to_excel(caminho, index=False)

    conn.close()

    return send_file(caminho, as_attachment=True)

# =============================
# USUÁRIOS
# =============================
@app.route("/usuarios", methods=["GET", "POST"])
def usuarios():
    if "user" not in session or session.get("nivel") != "admin":
        return "Acesso negado"

    conn = conectar()
    cur = conn.cursor()

    if request.method == "POST":
        username = request.form["username"]
        senha = request.form["senha"]
        nivel = request.form["nivel"]

        senha_hash = bcrypt.hashpw(
            senha.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

        cur.execute("""
            INSERT INTO usuarios (username, senha, nivel)
            VALUES (%s,%s,%s)
        """, (username, senha_hash, nivel))

        conn.commit()

    cur.execute("SELECT username, nivel FROM usuarios")
    lista = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("usuarios.html", lista=lista)

# =============================
# LOGOUT
# =============================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# =============================
# RUN
# =============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))