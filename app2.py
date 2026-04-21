from flask import Flask, render_template, request, redirect, session, send_file
import psycopg2
from datetime import datetime
import pandas as pd
import bcrypt
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "pelog_secret")


# =============================
# CONEXÃO COM BANCO
# =============================
def conectar():
    return psycopg2.connect(
        database=os.environ.get("DB_NAME", "pelog"),
        user=os.environ.get("DB_USER", "pelog_user"),
        password=os.environ.get("DB_PASSWORD", "1234"),
        host=os.environ.get("DB_HOST", "localhost"),
        port=os.environ.get("DB_PORT", "5432")
    )


# =============================
# LOGIN
# =============================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        senha = request.form.get("senha", "").strip()

        try:
            conn = conectar()
            cur = conn.cursor()

            cur.execute(
                "SELECT senha, nivel FROM usuarios WHERE username = %s",
                (usuario,)
            )
            resultado = cur.fetchone()

            cur.close()
            conn.close()

            if resultado:
                senha_hash, nivel = resultado

                try:
                    if bcrypt.checkpw(senha.encode("utf-8"), senha_hash.encode("utf-8")):
                        session["user"] = usuario
                        session["nivel"] = nivel
                        return redirect("/dashboard")
                except ValueError:
                    return "Hash de senha inválido no banco. Recrie esse usuário."

            return "Usuário ou senha inválidos!"

        except Exception as e:
            return f"Erro no login: {e}"

    return render_template("login.html")


# =============================
# DASHBOARD
# =============================
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")

    busca = request.args.get("busca", "").strip()

    try:
        conn = conectar()
        cur = conn.cursor()

        if busca:
            cur.execute("""
                SELECT id, placa, motorista, cpf, empresa, tipo_material,
                       nota_fiscal, doca, horario, horario_saida
                FROM caminhoes
                WHERE placa ILIKE %s
                ORDER BY horario DESC
            """, ('%' + busca + '%',))
        else:
            cur.execute("""
                SELECT id, placa, motorista, cpf, empresa, tipo_material,
                       nota_fiscal, doca, horario, horario_saida
                FROM caminhoes
                ORDER BY horario DESC
            """)

        dados = cur.fetchall()

        cur.close()
        conn.close()

        return render_template("dashboard.html", dados=dados)

    except Exception as e:
        return f"Erro ao carregar dashboard: {e}"


# =============================
# ENTRADA
# =============================
@app.route("/entrada", methods=["POST"])
def entrada():
    if "user" not in session:
        return redirect("/")

    try:
        placa = request.form.get("placa", "").strip()
        motorista = request.form.get("motorista", "").strip()
        cpf = request.form.get("cpf", "").strip()
        empresa = request.form.get("empresa", "").strip()
        material = request.form.get("material", "").strip()
        nf = request.form.get("nf", "").strip()
        doca = request.form.get("doca", "").strip()

        if not placa or not motorista or not empresa or not doca:
            return "Preencha os campos obrigatórios."

        conn = conectar()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO caminhoes (
                placa, motorista, cpf, empresa,
                tipo_material, nota_fiscal, doca, horario
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            placa,
            motorista,
            cpf,
            empresa,
            material,
            nf,
            doca,
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

    try:
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

    except Exception as e:
        return f"Erro ao registrar saída: {e}"


# =============================
# RELATÓRIO
# =============================
@app.route("/relatorio")
def relatorio():
    if "user" not in session:
        return redirect("/")

    inicio = request.args.get("inicio")
    fim = request.args.get("fim")

    try:
        conn = conectar()

        if inicio and fim:
            query = """
                SELECT id, placa, motorista, cpf, empresa, tipo_material,
                       nota_fiscal, doca, horario, horario_saida
                FROM caminhoes
                WHERE horario BETWEEN %s AND %s
                ORDER BY horario DESC
            """
            df = pd.read_sql(query, conn, params=(inicio, fim))
        else:
            query = """
                SELECT id, placa, motorista, cpf, empresa, tipo_material,
                       nota_fiscal, doca, horario, horario_saida
                FROM caminhoes
                ORDER BY horario DESC
            """
            df = pd.read_sql(query, conn)

        caminho = "relatorio.xlsx"
        df.to_excel(caminho, index=False)

        conn.close()
        return send_file(caminho, as_attachment=True)

    except Exception as e:
        return f"Erro ao gerar relatório: {e}"


# =============================
# USUÁRIOS (LIBERADO TEMPORARIAMENTE)
# =============================
@app.route("/usuarios", methods=["GET", "POST"])
def usuarios():
    try:
        conn = conectar()
        cur = conn.cursor()

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            senha = request.form.get("senha", "").strip()
            nivel = request.form.get("nivel", "").strip()

            if not username or not senha or not nivel:
                return "Preencha todos os campos."

            senha_hash = bcrypt.hashpw(
                senha.encode("utf-8"),
                bcrypt.gensalt()
            ).decode("utf-8")

            cur.execute("""
                INSERT INTO usuarios (username, senha, nivel)
                VALUES (%s, %s, %s)
            """, (username, senha_hash, nivel))

            conn.commit()

        cur.execute("SELECT username, nivel FROM usuarios ORDER BY username")
        lista = cur.fetchall()

        cur.close()
        conn.close()

        return render_template("usuarios.html", lista=lista)

    except Exception as e:
        return f"Erro na tela de usuários: {e}"


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