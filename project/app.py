import os
from dotenv import load_dotenv, find_dotenv

# Load environment variables from .env file
load_dotenv(find_dotenv())

from flask import Flask, render_template, request, redirect, session
from flask import make_response
from reportlab.pdfgen import canvas
from io import BytesIO
import random
import smtplib
from email.mime.text import MIMEText
from groq import Groq
import sqlite3

app = Flask(__name__)

# Load configuration from environment variables
app.secret_key = os.getenv("FLASK_SECRET_KEY", "researchagent123")

# Database configuration
DATABASE_PATH = os.getenv("DATABASE_PATH", "users.db")
conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)

cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    email TEXT UNIQUE,
    password TEXT
)
""")

conn.commit()

cursor.execute("""
CREATE TABLE IF NOT EXISTS searches(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    query TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()
LAST_QUERY = ""
LAST_RESULT = ""

# Groq client - API key loaded from environment variable
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Email configuration - loaded from environment variables
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
APP_PASSWORD = os.getenv("APP_PASSWORD")

def groq_generate(prompt):
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2048,
    )
    return response.choices[0].message.content

def send_otp(receiver_email, otp):

    try:

        msg = MIMEText(
            f"Your OTP for NexusResearch is: {otp}"
        )

        msg["Subject"] = "OTP Verification"
        msg["From"] = SENDER_EMAIL
        msg["To"] = receiver_email

        server = smtplib.SMTP("smtp.gmail.com", 587)

        server.starttls()

        server.login(
            SENDER_EMAIL,
            APP_PASSWORD
        )

        server.send_message(msg)

        server.quit()

        print("OTP SENT SUCCESSFULLY")

    except Exception as e:

        print("EMAIL ERROR:", e)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():

    if request.method == "POST":

        session["username"] = request.form.get("username")
        session["email"] = request.form.get("email")
        session["password"] = request.form.get("password")
        try:

            cursor.execute(
                "INSERT INTO users(username,email,password) VALUES(?,?,?)",
                (
                    session["username"],
                    session["email"],
                    session["password"]
                )
            )

            conn.commit()

        except:

            return "Email Already Registered"

        session["otp"] = str(
            random.randint(100000, 999999)
        )
        

        
        send_otp(
            session["email"],
            session["otp"]
        )

        return redirect("/verifyotp")

    return render_template("signup.html")


@app.route("/verifyotp", methods=["GET", "POST"])
def verifyotp():

    if request.method == "POST":

        if (
            request.form.get("otp")
            ==
            session.get("otp")
        ):

            session["logged_in"] = True

            return redirect("/dashboard")

        return "Invalid OTP"

    return render_template("otp.html")


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")

        cursor.execute(
            "SELECT * FROM users WHERE email=? AND password=?",
            (email, password)
        )

        user = cursor.fetchone()

        if user:

            session["logged_in"] = True
            session["username"] = user[1]

            return redirect("/dashboard")

        return "Invalid Email or Password"

            

    return render_template("login.html")


@app.route("/dashboard")
def dashboard():

    if not session.get("logged_in"):
        return redirect("/login")

    return render_template(
        "dashboard.html",
        username=session.get("username")
    )

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")

@app.route("/deepresearch")
def deepresearch():

    language = request.args.get("language", "English")

    prompt = f"""
    Explain Artificial Intelligence in detail.

    IMPORTANT: Respond entirely in {language} language.

    Give:
    1. Professional Summary
    2. Detailed Analysis
    3. Key Points
    4. Future Scope
    5. Conclusion
    """

    result = groq_generate(prompt)

    return render_template(
        "result.html",
        query="Deep Research",
        result=result,
        language=language
    )

@app.route("/search", methods=["POST"])
def search():

    query = request.form.get("query")
    language = request.form.get("language", "English")

    try:

        prompt = f"""
        Topic: {query}

        IMPORTANT: Respond entirely in {language} language.

        Give:

        1. Professional Summary

        2. Detailed Analysis

        3. Key Points

        4. Future Scope

        5. Conclusion

        """

        result = groq_generate(prompt)

        global LAST_QUERY, LAST_RESULT

        LAST_QUERY = query
        LAST_RESULT = result

        cursor.execute(
            "INSERT INTO searches(username,query) VALUES(?,?)",
            (
                session.get("username"),
                query
            )
        )

        conn.commit()
        print("QUERY SAVED:", LAST_QUERY)

        return render_template(
            "result.html",
            query=query,
            result=result,
            language=language
        )

    except Exception as e:

        return f"Error: {e}"

@app.route("/download_pdf")
def download_pdf():

    global LAST_QUERY, LAST_RESULT

    query = LAST_QUERY
    result = LAST_RESULT

    buffer = BytesIO()

    p = canvas.Canvas(buffer)

    y = 800

    p.setFont("Helvetica-Bold", 18)
    p.drawString(50, y, "AI Research Report")

    y -= 40

    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, f"Topic: {query}")

    y -= 40

    p.setFont("Helvetica", 10)

    lines = result.split("\n")
    clean_lines = []

    for line in lines:

        line = line.replace("#", "")
        line = line.replace("*", "")

        clean_lines.append(line)

    lines = clean_lines

    for line in lines:

        if y < 50:
            p.showPage()
            y = 800
            p.setFont("Helvetica", 10)

        p.drawString(50, y, line[:85])

        y -= 15

    p.save()

    buffer.seek(0)

    response = make_response(buffer.getvalue())

    response.headers["Content-Type"] = "application/pdf"

    response.headers["Content-Disposition"] = \
        "attachment; filename=AI_Research_Report.pdf"

    return response

@app.route("/history")
def history():

    cursor.execute(
    """
    SELECT id, query, created_at
    FROM searches
    WHERE username=?
    ORDER BY id DESC
    """,
    (session.get("username"),)
)

    history_data = cursor.fetchall()

    return render_template(
        "history.html",
        history=history_data
    )

@app.route("/delete_history/<int:id>")
def delete_history(id):

    cursor.execute(
        "DELETE FROM searches WHERE id=?",
        (id,)
    )

    conn.commit()

    return redirect("/history")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(debug=True, port=port)

