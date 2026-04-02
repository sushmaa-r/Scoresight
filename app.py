# -------------------------------------------------------
# 🏆 EPL Predictor — Full Flask App
# -------------------------------------------------------
import os
import re
import string
import random
import requests
from datetime import datetime
from io import BytesIO
import base64

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from flask import Flask, render_template, request, jsonify, url_for, redirect, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt

import joblib
import pytz
from dotenv import load_dotenv

# AI clients
import google.generativeai as genai
import openai

# -------------------------------------------------------
# APP INITIALIZATION
# -------------------------------------------------------
load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecretkey")

# Database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///user.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message_category = "info"

# -------------------------------------------------------
# USER MODEL
# -------------------------------------------------------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# -------------------------------------------------------
# API KEYS
# -------------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")
FD_API_KEY = os.getenv("FD_API_KEY")

genai.api_key = GEMINI_API_KEY
openai.api_key = OPENAI_API_KEY

API_BASE_URL = "https://v3.football.api-sports.io"
HEADERS_API = {"x-apisports-key": API_FOOTBALL_KEY}

FD_BASE_URL = "https://api.football-data.org/v4/competitions/PL"
HEADERS_FD = {"X-Auth-Token": FD_API_KEY}

# -------------------------------------------------------
# HELPER FUNCTIONS
# -------------------------------------------------------
def utc_to_ist(utc_time_str):
    try:
        utc_time = datetime.strptime(utc_time_str, "%Y-%m-%dT%H:%M:%S%z")
        ist_time = utc_time.astimezone(pytz.timezone("Asia/Kolkata"))
        return ist_time.strftime("%Y-%m-%d %I:%M %p")
    except Exception:
        return utc_time_str

# -------------------------------------------------------
# LOAD ML MODELS
# -------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

rf_home = joblib.load(os.path.join(BASE_DIR, "models", "rf2_home.pkl"))
rf_away = joblib.load(os.path.join(BASE_DIR, "models", "rf2_away.pkl"))

print("✅ Models loaded successfully!")

# -------------------------------------------------------
# TEAM LIST
# -------------------------------------------------------
teams = [
    "Arsenal", "Aston Villa", "Bournemouth", "Brentford", "Brighton",
    "Burnley", "Chelsea", "Crystal Palace", "Everton", "Fulham",
    "Liverpool", "Luton Town", "Manchester City", "Manchester United",
    "Newcastle United", "Nottingham Forest", "Sheffield United",
    "Tottenham Hotspur", "West Ham United", "Wolverhampton"
]

# -------------------------------------------------------
# AUTH ROUTES
# -------------------------------------------------------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        if User.query.filter_by(username=username).first():
            flash("⚠️ Username already taken!", "warning")
            return redirect(url_for('signup'))
        if User.query.filter_by(email=email).first():
            flash("⚠️ Email already registered!", "warning")
            return redirect(url_for('signup'))

        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(username=username, email=email, password=hashed_pw)
        db.session.add(user)
        db.session.commit()
        flash("✅ Account created! Please log in.", "success")
        return redirect(url_for('login'))
    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            flash(f"Welcome back, {user.username}! 🎉", "success")
            return redirect(url_for('home'))
        else:
            flash("❌ Invalid username or password.", "danger")
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out successfully!", "info")
    return redirect(url_for('login'))

# -------------------------------------------------------
# MAIN ROUTES
# -------------------------------------------------------
@app.route('/')
@login_required
def home():
    return render_template('index.html', user=current_user)

# -------------------------------------------------------
# EPL MATCHES
# -------------------------------------------------------
@app.route("/matches")
@login_required
def get_matches():
    fd_response = requests.get(f"{FD_BASE_URL}/matches?status=SCHEDULED", headers=HEADERS_FD)
    fd_data = fd_response.json()
    fd_matches = fd_data.get("matches", [])
    matches_data = []
    for match in fd_matches[:5]:
        matches_data.append({
            "homeTeam": match["homeTeam"]["name"],
            "awayTeam": match["awayTeam"]["name"],
            "utcDate": match["utcDate"][:10],
            "status": "Upcoming",
            "score": "-"
        })
    return render_template("matches.html", matches=matches_data)

# -------------------------------------------------------
# MATCH INSIGHTS
# -------------------------------------------------------
@app.route("/match_insights", methods=["GET"])
@login_required
def match_insights():
    try:
        teams_sorted = sorted(teams)
        team_name_map = {
            "Arsenal": "Arsenal FC",
            "Aston Villa": "Aston Villa FC",
            "Bournemouth": "AFC Bournemouth",
            "Brentford": "Brentford FC",
            "Brighton": "Brighton & Hove Albion FC",
            "Burnley": "Burnley FC",
            "Chelsea": "Chelsea FC",
            "Crystal Palace": "Crystal Palace FC",
            "Everton": "Everton FC",
            "Fulham": "Fulham FC",
            "Liverpool": "Liverpool FC",
            "Luton Town": "Luton Town FC",
            "Manchester City": "Manchester City FC",
            "Manchester United": "Manchester United FC",
            "Newcastle United": "Newcastle United FC",
            "Nottingham Forest": "Nottingham Forest FC",
            "Sheffield United": "Sheffield United FC",
            "Tottenham Hotspur": "Tottenham Hotspur FC",
            "West Ham United": "West Ham United FC",
            "Wolverhampton": "Wolverhampton Wanderers FC"
        }

        selected_team = request.args.get("team_name")
        stats = None
        if selected_team:
            api_team_name = team_name_map.get(selected_team)
            r = requests.get(f"{FD_BASE_URL}/standings", headers=HEADERS_FD)
            data = r.json()
            standings = data["standings"][0]["table"]
            team_stats = next((t for t in standings if t["team"]["name"] == api_team_name), None)
            if team_stats:
                stats = {
                    "played": team_stats["playedGames"],
                    "wins": team_stats["won"],
                    "draws": team_stats["draw"],
                    "losses": team_stats["lost"],
                    "goals_for": team_stats["goalsFor"],
                    "goals_against": team_stats["goalsAgainst"]
                }
        return render_template("match_insights.html", teams=teams_sorted, team=selected_team, stats=stats, error=None)
    except Exception as e:
        print("❌ Match Insights Error:", e)
        return render_template("match_insights.html", teams=teams, team=None, stats=None, error="Could not fetch match insights. Try again later.")

# -------------------------------------------------------
# HALF-TIME PREDICTION
# -------------------------------------------------------
@app.route('/halftime', methods=['GET', 'POST'])
@login_required
def halftime():

    # ---------- DEFAULT VALUES ----------
    data = {
        "teams": teams,
        "match_date": "",
        "home_team": "",
        "away_team": "",
        "HS": "", "HST": "", "HF": "", "HC": "", "HY": "", "HR": "",
        "AS": "", "AST": "", "AF": "", "AC": "", "AY": "", "AR": "",
        "hthg": None,
        "htag": None,
        "result": None,
        "home_prob": None,
        "draw_prob": None,
        "away_prob": None
    }

    if request.method == "POST":
        try:
            # ---------- READ FORM ----------
            data["match_date"] = request.form.get("match_date", "")
            data["home_team"] = request.form.get("home_team", "")
            data["away_team"] = request.form.get("away_team", "")

            for key in ["HS","HST","HF","HC","HY","HR","AS","AST","AF","AC","AY","AR"]:
                data[key] = request.form.get(key, "")

            # ---------- MODEL FEATURES ----------
            features = [
                float(request.form.get(f, 0))
                for f in ["HS","AS","HST","AST","HF","AF","HC","AC","HY","AY","HR","AR"]
            ]

            while len(features) < 17:
                features.append(0.0)

            features = np.array(features).reshape(1, -1)

            home_goals = rf_home.predict(features)[0]
            away_goals = rf_away.predict(features)[0]

            # ---------- RESULT ----------
            if home_goals > away_goals:
                result = f"{data['home_team']} (Home)"
                home_prob, draw_prob, away_prob = 65, 5, 30
            elif away_goals > home_goals:
                result = f"{data['away_team']} (Away)"
                home_prob, draw_prob, away_prob = 30, 5, 65
            else:
                result = "Draw"
                home_prob, draw_prob, away_prob = 45, 10, 45

            # ---------- PIE ----------
            plt.figure(facecolor="white")
            plt.pie(
                [home_prob, draw_prob, away_prob],
                labels=["Home", "Draw", "Away"],
                autopct="%1.1f%%",
                startangle=90
            )
            os.makedirs("static", exist_ok=True)
            plt.savefig("static/half_pie.png")
            plt.close()

            data.update({
                "hthg": round(home_goals, 2),
                "htag": round(away_goals, 2),
                "result": result,
                "home_prob": home_prob,
                "draw_prob": draw_prob,
                "away_prob": away_prob
            })

        except Exception as e:
            return f"Half-Time Error: {e}"

    return render_template("half_time.html", **data)

# -------------------------------------------------------
# FULL-TIME PREDICTION
# -------------------------------------------------------
@app.route('/fulltime', methods=['GET', 'POST'])
@login_required
def fulltime():
    # Default values (important for GET and first load)
    context = {
        "teams": teams,
        "home_team": None,
        "away_team": None,
        "ht_home": None,
        "ht_away": None,
        "hthg": None,
        "htag": None,
        "ft_home": None,
        "ft_away": None,
        "result": None,
        "home_prob": None,
        "draw_prob": None,
        "away_prob": None,
    }

    if request.method == 'POST':
        try:
            # --------- FORM INPUTS ----------
            home_team = request.form.get('home_team')
            away_team = request.form.get('away_team')
            ht_home = float(request.form.get('ht_home', 0))
            ht_away = float(request.form.get('ht_away', 0))

            # --------- FEATURE VECTOR ----------
            features = [ht_home, ht_away]
            while len(features) < 17:
                features.append(0.0)
            features = np.array(features).reshape(1, -1)

            # --------- MODEL PREDICTION ----------
            ft_home_pred = rf_home.predict(features)[0]
            ft_away_pred = rf_away.predict(features)[0]

            ft_home = int(ht_home + ft_home_pred)
            ft_away = int(ht_away + ft_away_pred)

            # --------- RESULT LOGIC ----------
            if ft_home > ft_away:
                result = f"{home_team} (Home)"
                home_prob, draw_prob, away_prob = 70, 20, 10
            elif ft_away > ft_home:
                result = f"{away_team} (Away)"
                home_prob, draw_prob, away_prob = 10, 20, 70
            else:
                result = "Draw"
                home_prob, draw_prob, away_prob = 33, 34, 33

            # --------- UPDATE CONTEXT ----------
            context.update({
                "home_team": home_team,
                "away_team": away_team,
                "ht_home": int(ht_home),
                "ht_away": int(ht_away),
                "hthg": int(ht_home),
                "htag": int(ht_away),
                "ft_home": ft_home,
                "ft_away": ft_away,
                "result": result,
                "home_prob": home_prob,
                "draw_prob": draw_prob,
                "away_prob": away_prob,
            })

        except Exception as e:
            print("❌ Full-Time Prediction Error:", e)
            flash("Something went wrong during prediction.", "danger")

    # --------- RENDER SAME TEMPLATE FOR GET & POST ----------
    return render_template("full_time.html", **context)
# -------------------------------------------------------
# FIXTURES
# -------------------------------------------------------
DATA_PATH = r"C:\Users\sushm\OneDrive\Desktop\Scoresight\Dataset of epl\EPL_features.csv"
LOGO_PATH = r"C:\Users\sushm\OneDrive\Desktop\Scoresight\static\team_logo"

TEAM_NAME_MAP = {
    "man city": "Manchester City",
    "man united": "Manchester United",
    "wolves": "Wolverhampton",
    "spurs": "Tottenham Hotspur",
    "newcastle": "Newcastle United",
    "forest": "Nottingham Forest",
    "brighton": "Brighton",
    "villa": "Aston Villa",
    "sheff utd": "Sheffield United",
    "luton": "Luton Town",
}

@app.route('/fixtures')
@login_required
def fixtures_page():
    df = pd.read_csv(DATA_PATH, parse_dates=['Date'])
    df['HomeTeam'] = df['HomeTeam'].apply(lambda x: TEAM_NAME_MAP.get(str(x).lower(), x))
    df['AwayTeam'] = df['AwayTeam'].apply(lambda x: TEAM_NAME_MAP.get(str(x).lower(), x))

    teams_sorted = sorted(df['HomeTeam'].unique())
    selected_team = request.args.get('team', 'All Teams')
    if selected_team != "All Teams":
        df_filtered = df[(df['HomeTeam'] == selected_team) | (df['AwayTeam'] == selected_team)]
    else:
        df_filtered = df.copy()

    df_filtered = df_filtered[['Date', 'HomeTeam', 'AwayTeam', 'FTR']].sort_values('Date')
    df_filtered['Date'] = df_filtered['Date'].dt.strftime('%Y-%m-%d')

    team_logos = {}
    for team in teams_sorted:
        team_lower = team.replace(" ", "").lower()
        found = None
        for file in os.listdir(LOGO_PATH):
            file_lower = file.replace(" ", "").replace("_", "").lower()
            if team_lower in file_lower:
                found = file
                break
        team_logos[team] = found

    return render_template("fixtures.html", teams=teams_sorted, selected_team=selected_team,
                           fixtures=df_filtered.to_dict(orient='records'), team_logos=team_logos)

@app.route('/get_logo/<team>')
@login_required
def get_logo_api(team):
    logo_folder = os.path.join('static', 'team_logo')
    team_clean = re.sub(r'[^a-z0-9]', '', team.lower())
    for file in os.listdir(logo_folder):
        file_clean = re.sub(r'[^a-z0-9]', '', file.lower().replace('.svg',''))
        if team_clean in file_clean:
            return jsonify({'logo': url_for('static', filename=f'team_logo/{file}')})
    return jsonify({'logo': None})
# -------------------------------------------------------
# CHATBOT
# -------------------------------------------------------
@app.route("/chat")
@login_required
def chat():
    return render_template("chat.html", user=current_user)

@app.route("/get_response", methods=["POST"])
@login_required
def get_response():
    try:
        user_input = request.json.get("message", "").strip()
        user_input_clean = user_input.translate(str.maketrans('', '', string.punctuation)).lower()
        print("🗣 User said:", user_input_clean)

        reply = None

        # ---------------- BASIC GREETINGS ----------------
        greetings = ["hi", "hello", "hey", "yo", "hii", "hiii"]
        farewells = ["bye", "goodbye", "see you", "bye bye"]

        if user_input_clean in greetings:
            reply = (
                "Hey there! 👋 Ready for some football talk?\n"
                "You can ask me about:\n"
                "- Live matches ⚽\n"
                "- Previous matches 📅\n"
                "- Next match 📆\n"
                "- Last season winners 🏆\n"
                "- Current standings 🏟️"
            )
        elif user_input_clean in farewells:
            reply = "Goodbye! ⚽ Catch you after the next match!"

        # ---------------- LIVE MATCHES ----------------
        elif any(word in user_input_clean for word in ["live", "score", "ongoing", "current match", "match today"]):
            try:
                r = requests.get(f"{API_BASE_URL}/fixtures?live=all", headers=HEADERS_API)
                data = r.json()
                live_matches = [m for m in data.get("response", []) if m["league"]["name"].lower() == "premier league"]
                if live_matches:
                    m = live_matches[0]
                    home = m["teams"]["home"]["name"]
                    away = m["teams"]["away"]["name"]
                    score_home = m["goals"]["home"]
                    score_away = m["goals"]["away"]
                    minute = m["fixture"]["status"]["elapsed"]
                    reply = f"⚽ Live now: {home} {score_home} - {score_away} {away} ({minute}’)"
                else:
                    reply = "No Premier League matches live right now ⏳"
            except Exception as e:
                print("⚠️ Live match fetch failed:", e)
                reply = "Couldn't fetch live matches, try again later."

        # ---------------- PREVIOUS MATCH ----------------
        elif any(word in user_input_clean for word in ["previous", "last match", "recent match"]):
            try:
                r = requests.get(f"{FD_BASE_URL}/matches?status=FINISHED", headers=HEADERS_FD)
                data = r.json()
                matches = data.get("matches", [])
                if matches:
                    m = matches[-1]
                    reply = f"📅 Last Match: {m['homeTeam']['name']} {m['score']['fullTime']['home']} - {m['score']['fullTime']['away']} {m['awayTeam']['name']}"
                else:
                    reply = "No finished matches found recently 🤔"
            except Exception as e:
                print("⚠️ Previous match fetch failed:", e)
                reply = "Couldn't fetch last match, try again later."

        # ---------------- NEXT MATCH ----------------
        elif any(word in user_input_clean for word in ["next match", "upcoming", "fixture", "future match"]):
            try:
                r = requests.get(f"{FD_BASE_URL}/matches?status=SCHEDULED", headers=HEADERS_FD)
                data = r.json()
                matches = data.get("matches", [])
                if matches:
                    m = matches[0]
                    date_utc = m["utcDate"].replace("Z", "+00:00")
                    date_ist = utc_to_ist(date_utc)
                    reply = f"📆 Next Match: {m['homeTeam']['name']} vs {m['awayTeam']['name']} on {date_ist} (IST)"
                else:
                    reply = "No upcoming matches found 📭"
            except Exception as e:
                print("⚠️ Next match fetch failed:", e)
                reply = "Couldn't fetch next match, try again later."

        # ---------------- LAST SEASON WINNER ----------------
        elif "who won" in user_input_clean and "last" in user_input_clean and "winner" in user_input_clean:
            try:
                r = requests.get(f"{FD_BASE_URL}/standings?season=2023", headers=HEADERS_FD)
                data = r.json()
                winner = data["standings"][0]["table"][0]["team"]["name"]
                reply = f"🏆 {winner} won the Premier League 2023–24 season!"
            except Exception as e:
                print("⚠️ Last season winner fetch failed:", e)
                reply = "Couldn't fetch last season's winner."

        # ---------------- STANDINGS ----------------
        elif any(word in user_input_clean for word in ["table", "standings", "top 5", "top teams"]):
            try:
                r = requests.get(f"{FD_BASE_URL}/standings", headers=HEADERS_FD)
                data = r.json()
                table = data["standings"][0]["table"][:5]
                reply = "🏆 Top 5 Teams:\n" + "\n".join([f"{t['position']}. {t['team']['name']} ({t['points']} pts)" for t in table])
            except Exception as e:
                print("⚠️ Standings fetch failed:", e)
                reply = "Couldn't fetch standings right now."

        # ---------------- AI FALLBACK (Dynamic) ----------------
        else:
            try:
                prompt = f"""
You are Scoresight, a football expert assistant. 
Answer football questions in detail. 
If the question is not about football, respond politely and briefly in a casual way. 

User said: "{user_input}"
"""
                response_gemini = genai.chat.create(
                    model="gemini-1.5",
                    messages=[{"role": "user", "content": prompt}]
                )
                reply = response_gemini.last['content'][0]['text']

                if not reply or len(reply.strip()) == 0:
                    reply = "I'm ready to talk football! Ask me anything about the Premier League."

            except Exception as e:
                print("⚠️ Gemini/OpenAI failed:", e)
                # Fallback static responses
                fallback_responses = [
                    "I'm all about football ⚽! Ask me anything about EPL matches.",
                    "Let's talk football! Who's your favorite team?",
                    "Sorry, I can't answer that directly, but let's talk football instead!"
                ]
                reply = random.choice(fallback_responses)

        print("🤖 Reply:", reply)
        return jsonify({"response": reply})

    except Exception as e:
        print("❌ Unexpected Server Error:", e)
        # Safe fallback for unexpected errors
        fallback_responses = [
            "Hmm, something went wrong 😕. But let's talk football!",
            "I had a hiccup 🤭. Try asking about EPL matches!",
            "Can't process that right now, but football chat is open!"
        ]
        return jsonify({"response": random.choice(fallback_responses)})

#  EPL NEWS ROUTE
# -------------------------------------------------------
from flask import render_template
from epl_news_service import news_service

@app.route("/news")
@login_required
def show_news():
    try:
        articles = news_service.get_all_news()
        return render_template("news.html", articles=articles)
    except Exception as e:
        print(f"⚠️ Error loading news: {e}")
        return render_template("news.html", articles=[])
    
# -------------------------------------------------------
# ABOUT
# -------------------------------------------------------
@app.route("/about")
@login_required
def about():
    return render_template("about.html")

# -------------------------------------------------------
# RUN APP
# -------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
