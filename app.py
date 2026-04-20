from flask import Flask, render_template, request, redirect, session, send_file
import psycopg2
from datetime import datetime
import pandas as pd
import bcrypt

app = Flask(__name__)
app.secret_key = "pelog_secret"

# =============================
# CONEXÃO
# =============================
def conectar():
    return psycopg2.connect(
        database="pelog",
        user="pelog_user",
        password="1234",
        host="localhost",
        port="5432"
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
        conn.close()

        if resultado:
            senha_hash, nivel = resultado

            if bcrypt.checkpw(senha.encode(), senha_hash.encode()):
                session["user"] = user
                session["nivel"] = nivel
                return redirect("/dashboard")

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
    conn.close()

    return render_template("dashboard.html", dados=dados)

# =============================
# ENTRADA
# =============================
@app.route("/entrada", methods=["POST"])
def entrada():
    if "user" not in session:
        return redirect("/")

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO caminhoes (
            placa, motorista, cpf, empresa,
            tipo_material, nota_fiscal, local_entrega, horario
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        request.form["placa"],
        request.form["motorista"],
        request.form["cpf"],
        request.form["empresa"],
        request.form["material"],
        request.form["nf"],
        request.form["local"],
        datetime.now()
    ))

    conn.commit()
    conn.close()

    return redirect("/dashboard")

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
# USUÁRIOS (NOVO)
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

        senha_hash = bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()

        cur.execute("""
            INSERT INTO usuarios (username, senha, nivel)
            VALUES (%s,%s,%s)
        """, (username, senha_hash, nivel))

        conn.commit()

    cur.execute("SELECT username, nivel FROM usuarios")
    lista = cur.fetchall()

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
app.run(debug=True)