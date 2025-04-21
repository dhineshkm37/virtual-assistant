from flask import Flask, render_template, request, redirect, url_for, jsonify, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
import google.generativeai as genai
import time
import re
import threading
import smtplib
import random
import string
import json
from email.message import EmailMessage
from datetime import datetime, timedelta
from flask_cors import CORS
from flask_mail import Mail, Message

app = Flask(__name__)
CORS(app)
app.secret_key = 'your_secret_key_here'

# Configure Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'jaisurya6909j@gmail.com'
app.config['MAIL_PASSWORD'] = 'dxhl tixx utks blga'
app.config['MAIL_DEFAULT_SENDER'] = 'jaisurya6909j@gmail.com'
mail = Mail(app)

# Database Configuration
DB_CONFIG = {
    "host": "localhost",
    "dbname": "project",
    "user": "postgres",
    "password": "@jk3"
}

# Email Configuration
SENDER_EMAIL = "jaisurya6909j@gmail.com"
SENDER_PASSWORD = "dxhl tixx utks blga"

# AI Configuration
genai.configure(api_key="AIzaSyD_CyfsWrQL1pWoAoCPssX0V46Vusr5wKM")
model = genai.GenerativeModel("gemini-1.5-pro-latest")
study_model = genai.GenerativeModel('gemini-1.5-pro-latest')


# Database Functions
def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)


def create_tables():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(100) NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            password VARCHAR(100) NOT NULL
        )
    ''')
    cur.execute('DROP TABLE IF EXISTS task_details')
    cur.execute('''
        CREATE TABLE task_details (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) NOT NULL,
            task TEXT NOT NULL,
            description TEXT,
            due_date TEXT NOT NULL,
            remind_time TEXT NOT NULL,
            email TEXT NOT NULL
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()


# Utility Functions
def extract_line_count(user_input):
    match = re.search(r"(\d+)\s*lines?", user_input, re.IGNORECASE)
    return int(match.group(1)) if match else 5


def analyze_description(description):
    description = description.lower()
    category = "general"
    priority = 2
    keywords = []
    work_keywords = {'work', 'meeting', 'project', 'deadline'}
    personal_keywords = {'personal', 'family', 'vacation'}
    health_keywords = {'health', 'doctor', 'exercise'}
    urgent_keywords = {'urgent', 'asap', 'important'}
    found_keywords = set()

    for word in description.split():
        if word in work_keywords:
            found_keywords.add(word)
            category = "work"
        elif word in personal_keywords:
            found_keywords.add(word)
            category = "personal"
        elif word in health_keywords:
            found_keywords.add(word)
            category = "health"
        if word in urgent_keywords:
            found_keywords.add(word)
            priority = 1

    date_rules = {'work': 2, 'health': 1, 'personal': 3, 'general': 4}
    suggested_date = datetime.now() + timedelta(days=date_rules[category])
    recommendations = {
        'work': ["Schedule focused work sessions", "Break into subtasks with deadlines"],
        'health': ["Set multiple reminders", "Track progress daily"],
        'personal': ["Allocate specific time slots", "Balance with other commitments"],
        'general': ["Review task details regularly", "Set intermediate checkpoints"]
    }.get(category, [])

    if priority == 1:
        recommendations.insert(0, "High priority! Handle this task first")

    return {
        'category': category,
        'suggested_date': suggested_date.strftime("%Y-%m-%d"),
        'priority': priority,
        'recommendations': recommendations,
        'keywords': list(found_keywords)
    }


def send_email(receiver, task):
    msg = EmailMessage()
    msg['Subject'] = f'Reminder: {task}'
    msg['From'] = SENDER_EMAIL
    msg['To'] = receiver
    msg.set_content(f'Task reminder: {task} is due soon!')
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(SENDER_EMAIL, SENDER_PASSWORD)
            smtp.send_message(msg)
    except Exception as e:
        print(f"Email failed: {e}")


def reminder_thread():
    while True:
        now = datetime.now().strftime("%Y-%m-%d %I:%M %p")
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT * FROM task_details WHERE remind_time = %s", (now,))
            for task in cur.fetchall():
                send_email(task[6], task[2])
            conn.close()
        except Exception as e:
            print(f"Reminder error: {e}")
        time.sleep(60)


def generate_meeting_id(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def generate_study_content(topic):
    prompt = f"""For the topic "{topic}", generate:
    1. A concise 3-4 line introduction
    2. A detailed study plan with resources
    Format as JSON:
    {{
        "introduction": {{
            "overview": "Brief engaging overview",
            "key_points": ["Point 1", "Point 2"]
        }},
        "plan": {{
            "timeline": "Total duration estimate",
            "steps": [
                {{
                    "title": "Step title",
                    "description": "Detailed description",
                    "duration": "X hours/days",
                    "resources": ["URLs"],
                    "tip": "Pro tip for this step"
                }}
            ]
        }}
    }}
    Include practical examples and real resources where possible."""

    try:
        response = study_model.generate_content(prompt)
        raw_text = response.text
        cleaned = re.sub(r'^[^{]*', '', raw_text, flags=re.DOTALL)
        cleaned = re.sub(r'}[^}]*$', '}', cleaned, flags=re.DOTALL)
        return cleaned.replace('```json', '').replace('```', '').strip()
    except Exception as e:
        return json.dumps({"error": str(e)})


# Routes
@app.route("/")
def home():
    return render_template("ho.html")


@app.route('/study')
def study_home():
    return render_template('sm.html')



@app.route('/promo')
def promo_page():
    return render_template('promo.html')


@app.route('/music')
def music_page():
    return render_template('a.html')


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, password FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        if user and check_password_hash(user[1], password):
            session['user_id'] = user[0]
            return redirect(url_for("dashboard"))
        return render_template("lo.html", message="Invalid email or password!")
    return render_template("lo.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        hashed_password = generate_password_hash(password)
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
                (username, email, hashed_password))
            conn.commit()
            return redirect(url_for("login"))
        except psycopg2.IntegrityError:
            conn.rollback()
            return render_template("re.html", message="Email already exists!")
        finally:
            cur.close()
            conn.close()
    return render_template("re.html")


@app.route("/dashboard")
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template("dash.html")


@app.route("/chat")
def chat():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template("i.html")


@app.route("/ask", methods=["POST"])
def ask():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user_input = request.json.get("message")

    if user_input.lower() == "exit":
        return jsonify({"response": "Goodbye! Stay productive! 🚀"})

    try:
        # Get response from Gemini with built-in productivity focus
        gemini_response = ask_gemini(user_input)
        return jsonify({"response": gemini_response})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def ask_gemini(query, num_lines=5):
    # System prompt for productivity focus
    system_prompt = (
        "You are a productivity expert specializing in:\n"
        "- Time management (Pomodoro, Time Blocking)\n"
        "- Task prioritization (Eisenhower Matrix)\n"
        "- Study techniques & focus maintenance\n"
        "- SMART goal setting\n"
        "- Habit formation & routine optimization\n"
        "- Workflow organization\n\n"
        "Provide concise, actionable advice with examples. "
        "For unrelated queries, respond:\n"
        "\"I specialize in productivity enhancement. Let's focus on time management, task optimization, or study techniques!\""
    )

    # Generate response with both system prompt and user query
    response = model.generate_content([system_prompt, query]).text

    # Clean response and limit length
    cleaned_response = response.replace("**", "")  # Remove markdown
    sentences = cleaned_response.split('. ')
    limited_response = '. '.join(sentences[:num_lines]).strip()

    # Add final period if missing
    if not limited_response.endswith('.'):
        limited_response += '.'

    return limited_response


@app.route('/time')
def time_management():
    return send_from_directory('templates', 'time.html')


@app.route('/analyze', methods=['POST'])
def analyze_task():
    try:
        data = request.get_json()
        return jsonify(analyze_description(data.get('description', '')))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/add', methods=['POST'])
def add_task():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        data = request.form
        user_id = session['user_id']
        remind_datetime = datetime.strptime(
            f"{data['reminder_date']} {data['reminder_time']}",
            "%Y-%m-%d %H:%M"
        )
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO task_details 
                (user_id, task, description, due_date, remind_time, email)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (
            user_id,
            data['task'],
            data['description'],
            data['due_date'],
            remind_datetime.strftime("%Y-%m-%d %I:%M %p"),
            data['email']
        ))
        conn.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if 'conn' in locals():
            conn.close()


@app.route("/logout")
def logout():
    session.pop('user_id', None)
    return redirect(url_for('home'))


@app.route("/delete_task", methods=["POST"])
def delete_task():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    task_id = request.form.get('task_id')
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('''
            DELETE FROM task_details 
            WHERE id = %s 
            AND user_id = %s
        ''', (task_id, session['user_id']))
        conn.commit()
    except Exception as e:
        print(f"Delete error: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('view_tasks'))


@app.route("/view_tasks")
def view_tasks():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('''
            SELECT id, task, description, 
                   TO_CHAR(TO_DATE(due_date, 'YYYY-MM-DD'), 'DD Mon YYYY'), 
                   TO_CHAR(TO_TIMESTAMP(remind_time, 'YYYY-MM-DD HH:MI PM'), 'DD Mon YYYY HH12:MI PM')
            FROM task_details 
            WHERE user_id = %s
            ORDER BY TO_DATE(due_date, 'YYYY-MM-DD') DESC
        ''', (session['user_id'],))
        tasks = cur.fetchall()
        task_count = len(tasks)
    finally:
        cur.close()
        conn.close()
    return render_template("tasks.html", tasks=tasks, task_count=task_count)


@app.route('/calendar')
def calendar():
    return render_template('uu.html')


@app.route('/submit-plan', methods=['POST'])
def submit_plan():
    data = request.get_json()
    date = data.get('date')
    plan = data.get('plan')
    time = data.get('time')
    email = data.get('email')
    if email:
        try:
            msg = Message(subject=f"New Plan Scheduled on {date}",
                          recipients=[email],
                          body=f"Hi,\n\nYou have a new plan scheduled:\n\nDate: {date}\nTime: {time}\nPlan: {plan}\n\nRegards,\nCalendar Assistant")
            mail.send(msg)
            return jsonify({"message": "Plan submitted and email notification sent!"})
        except Exception as e:
            print("Email error:", e)
            return jsonify({"message": "Plan submitted, but email failed!"})
    return jsonify({"message": "Plan submitted successfully (No email provided)!"})


@app.route('/schedules')
def schedules_home():
    return render_template('schedules.html')


@app.route('/create_meeting')
def create_meeting():
    room_id = generate_meeting_id()
    return redirect(url_for('meeting_room', room_id=room_id))


@app.route('/meet/<room_id>')
def meeting_room(room_id):
    return render_template('meeting.html', room_id=room_id)

@app.route('/quiz')
def quizer():
    return render_template('quiz.html')

@app.route('/goal')
def goaler():
    return render_template('goal.html')


@app.route('/generate', methods=['POST'])
def generate_study_plan():
    topic = request.json.get('topic', '').strip().lower()
    if not topic:
        return jsonify({"error": "Please enter a topic"}), 400

    try:
        content = generate_study_content(topic)
        data = json.loads(content)

        if 'introduction' not in data or 'plan' not in data:
            raise ValueError("Invalid response structure")

        return jsonify(data)
    except json.JSONDecodeError:
        return jsonify({"error": "Failed to generate content"}), 500
    except ValueError as e:
        return jsonify({"error": str(e)}), 500
    except Exception:
        return jsonify({"error": "Server error"}), 500


if __name__ == '__main__':
    create_tables()
    threading.Thread(target=reminder_thread, daemon=True).start()
    app.run(host='0.0.0.0', port=5000, debug=True)