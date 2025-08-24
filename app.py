from flask import Flask, render_template, request, redirect, send_file, jsonify
import sqlite3
import string, random
import os
import qrcode
import io

app = Flask(__name__)

# --- Inicializar banco de dados ---
def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_url TEXT NOT NULL,
                    short_code TEXT UNIQUE NOT NULL,
                    clicks INTEGER DEFAULT 0
                )''')
    conn.commit()
    conn.close()

init_db()

# --- Função para gerar código curto ---
def generate_short_code(length=6):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

# --- Rota principal ---
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        original_url = request.form["url"]
        custom_code = request.form.get("custom")

        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        if custom_code and custom_code.strip() != "":
            short_code = custom_code.strip()
            c.execute("SELECT id FROM links WHERE short_code=?", (short_code,))
            if c.fetchone():
                suggestion = short_code + str(random.randint(100, 999))
                conn.close()
                return render_template("index.html", short_url=None,
                                       error=f"Código já existe! Sugestão: {suggestion}")
        else:
            short_code = generate_short_code()

        # Salvar no banco
        c.execute("INSERT INTO links (original_url, short_code) VALUES (?, ?)",
                  (original_url, short_code))
        conn.commit()
        conn.close()

        return render_template("index.html",
                               short_url=f"/s/{short_code}",
                               qr_url=f"/qr/{short_code}",
                               qr_download=f"/qr/{short_code}/download")

    return render_template("index.html", short_url=None)

# --- Redirecionamento ---
@app.route("/s/<short_code>")
def redirect_url(short_code):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT original_url, clicks FROM links WHERE short_code=?", (short_code,))
    result = c.fetchone()

    if result:
        original_url, clicks = result
        c.execute("UPDATE links SET clicks=? WHERE short_code=?", (clicks+1, short_code))
        conn.commit()
        conn.close()
        return redirect(original_url)
    else:
        conn.close()
        return "Link não encontrado!", 404

# --- Geração de QR Code (visualizar no navegador) ---
@app.route("/qr/<short_code>")
def qr_code(short_code):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT original_url FROM links WHERE short_code=?", (short_code,))
    result = c.fetchone()
    conn.close()

    if result:
        original_url = result[0]
        img = qrcode.make(original_url)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return send_file(buf, mimetype="image/png")
    else:
        return "QR Code não encontrado!", 404

# --- Rota para baixar o QR Code ---
@app.route("/qr/<short_code>/download")
def qr_code_download(short_code):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT original_url FROM links WHERE short_code=?", (short_code,))
    result = c.fetchone()
    conn.close()

    if result:
        original_url = result[0]
        img = qrcode.make(original_url)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        filename = f"qrcode_{short_code}.png"
        return send_file(buf, mimetype="image/png", as_attachment=True, download_name=filename)
    else:
        return "QR Code não encontrado!", 404

# --- Estatísticas ---
@app.route("/stats")
def stats():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT original_url, short_code, clicks FROM links")
    links = c.fetchall()
    conn.close()

    # Preparar dados
    labels = [link[1] for link in links]   # short_code
    data = [link[2] for link in links]     # clicks
    total_links = len(links)
    total_clicks = sum(data) if data else 0
    top_link = max(links, key=lambda x: x[2]) if links else None

    return render_template(
        "stats.html",
        links=links,
        labels=labels,
        data=data,
        total_links=total_links,
        total_clicks=total_clicks,
        top_link=top_link
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
