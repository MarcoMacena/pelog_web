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
    db_host = os.environ.get("DB_HOST")
    db_name = os.environ.get("DB_NAME")
    db_user = os.environ.get("DB_USER")
    db_password = os.environ.get("DB_PASSWORD")
    db_port = os.environ.get("DB_PORT")

    if not db_host or not db_name or not db_user or not db_password or not db_port:
        raise Exception("Variáveis de ambiente do banco não configuradas corretamente.")

    return psycopg2.connect(
        host=db_host,
        database=db_name,
        user=db_user,
        password=db_password,
        port=db_port
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

                        if nivel == "portaria":
                            return redirect("/portaria")
                        return redirect("/dashboard")

                except ValueError:
                    return "Hash de senha inválido no banco. Recrie esse usuário."

            return "Usuário ou senha inválidos!"

        except Exception as e:
            return f"Erro no login: {e}"

    return render_template("login.html")


# =============================
# DASHBOARD ADMIN
# =============================
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")

    if session.get("nivel") != "admin":
        return redirect("/portaria")

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

        return render_template("dashboard.html", dados=dados, nivel=session.get("nivel"))

    except Exception as e:
        return f"Erro ao carregar dashboard: {e}"


# =============================
# TELA DA PORTARIA
# =============================
@app.route("/portaria")
def portaria():
    if "user" not in session:
        return redirect("/")

    if session.get("nivel") != "portaria":
        return redirect("/dashboard")

    return render_template("portaria.html")


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
            return "Preencha os campos obrigatórios: placa, motorista, empresa e doca."

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

        if session.get("nivel") == "portaria":
            return redirect("/portaria")

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

    if session.get("nivel") != "admin":
        return "Acesso negado"

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

    if session.get("nivel") != "admin":
        return "Acesso negado"

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
# USUÁRIOS
# =============================
@app.route("/usuarios", methods=["GET", "POST"])
def usuarios():
    if "user" not in session or session.get("nivel") != "admin":
        return "Acesso negado"

    try:
        conn = conectar()
        cur = conn.cursor()

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            senha = request.form.get("senha", "").strip()
            nivel = request.form.get("nivel", "").strip().lower()

            if not username or not senha or not nivel:
                cur.close()
                conn.close()
                return "Preencha todos os campos."

            if nivel not in ["admin", "portaria"]:
                cur.close()
                conn.close()
                return "Nível inválido."

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