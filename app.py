import re
import ssl
import time
import os
import urllib.error
import urllib.request
import json
import yaml
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np
from typing import Dict, List
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from flask import Flask, jsonify, request, send_from_directory, render_template, redirect, session
from flask_swagger_ui import get_swaggerui_blueprint
from config.logger import setup_logging, log_time, log_exceptions
from prometheus_client import Counter, Histogram, start_http_server

# Initialize Flask app
app = Flask(__name__)

# Setup secure session
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))
app.permanent_session_lifetime = timedelta(hours=2)

# Setup logging
logger = setup_logging()

# Configuración de análisis de sentimiento
SENTIMENT_THRESHOLDS = {
    "muy_positivo": 0.8,
    "positivo": 0.6,
    "neutral": 0.4,
    "negativo": 0.2
}

def calculate_engagement_rate(interactions: int, followers: int) -> float:
    """Calcula el engagement rate."""
    return (interactions / followers * 100) if followers > 0 else 0

def get_sentiment_class(sentiment_score: float) -> tuple:
    """Determina la clase y texto del sentimiento basado en el score."""
    if sentiment_score >= SENTIMENT_THRESHOLDS["muy_positivo"]:
        return "success", "Muy Positivo"
    elif sentiment_score >= SENTIMENT_THRESHOLDS["positivo"]:
        return "success", "Positivo"
    elif sentiment_score >= SENTIMENT_THRESHOLDS["neutral"]:
        return "warning", "Neutral"
    elif sentiment_score >= SENTIMENT_THRESHOLDS["negativo"]:
        return "danger", "Negativo"
    return "danger", "Muy Negativo"

def analyze_profile_metrics(social_data: Dict) -> Dict:
    """Analiza las métricas del perfil y genera insights."""
    total_followers = sum(platform["followers"] for platform in social_data.values())
    total_engagement = sum(platform["engagement"] for platform in social_data.values())
    avg_sentiment = np.mean([platform["sentiment"] for platform in social_data.values()])
    
    return {
        "seguidores_totales": total_followers,
        "engagement_total": total_engagement,
        "sentimiento_promedio": avg_sentiment
    }

def generate_insights(metrics: Dict, historical_data: Dict) -> List[Dict]:
    """Genera insights basados en los datos actuales e históricos."""
    insights = []
    
    # Análisis de crecimiento de seguidores
    follower_growth = (metrics["seguidores_totales"] - historical_data["seguidores_previos"]) / historical_data["seguidores_previos"] * 100
    if follower_growth > 5:
        insights.append({
            "tipo": "positive",
            "titulo": "Crecimiento Significativo",
            "descripcion": f"Tu audiencia creció un {follower_growth:.1f}% este mes",
            "tendencia": follower_growth,
            "periodo": "vs mes anterior"
        })
    
    # Análisis de engagement
    if metrics["engagement_total"] > historical_data["engagement_promedio"]:
        improvement = ((metrics["engagement_total"] / historical_data["engagement_promedio"]) - 1) * 100
        insights.append({
            "tipo": "positive",
            "titulo": "Mejora en Engagement",
            "descripcion": "El engagement ha mejorado significativamente",
            "tendencia": improvement,
            "periodo": "vs promedio histórico"
        })
    
    # Análisis de sentimiento
    sentiment_change = metrics["sentimiento_promedio"] - historical_data["sentimiento_previo"]
    if abs(sentiment_change) > 0.1:
        insights.append({
            "tipo": "warning" if sentiment_change < 0 else "positive",
            "titulo": "Cambio en Sentimiento",
            "descripcion": "Se detectó un cambio significativo en el sentimiento de la audiencia",
            "tendencia": sentiment_change * 100,
            "periodo": "vs mes anterior"
        })
    
    return insights

def process_social_data(profile_data: Dict) -> Dict:
    """Procesa los datos de redes sociales y genera métricas agregadas."""
    
    # Datos simulados históricos (en una implementación real, vendrían de una base de datos)
    historical_data = {
        "seguidores_previos": 50000,
        "engagement_promedio": 3.5,
        "sentimiento_previo": 0.65
    }
    
    # Procesar métricas actuales
    current_metrics = analyze_profile_metrics(profile_data)
    
    # Generar insights
    insights = generate_insights(current_metrics, historical_data)
    
    # Procesar datos por red social
    redes_sociales = []
    for platform, data in profile_data.items():
        sentiment_class, sentiment_text = get_sentiment_class(data["sentiment"])
        redes_sociales.append({
            "nombre": platform.capitalize(),
            "seguidores": data["followers"],
            "engagement": calculate_engagement_rate(data["engagement"], data["followers"]),
            "cambio_engagement": ((data["engagement"] / historical_data["engagement_promedio"]) - 1) * 100,
            "posts": data["posts"],
            "mejor_horario": data["best_time"],
            "sentimiento_clase": sentiment_class,
            "sentimiento_texto": sentiment_text
        })
    
    # Datos temporales para gráficos (simulados)
    fechas = [(datetime.now() - timedelta(days=x)).strftime('%Y-%m-%d') for x in range(30, 0, -1)]
    engagement_data = [round(random.uniform(2.0, 5.0), 2) for _ in range(30)]
    alcance_data = [int(random.uniform(5000, 15000)) for _ in range(30)]
    
    return {
        "metricas": {
            "seguidores_totales": current_metrics["seguidores_totales"],
            "cambio_seguidores": ((current_metrics["seguidores_totales"] / historical_data["seguidores_previos"]) - 1) * 100,
            "engagement_rate": current_metrics["engagement_total"],
            "cambio_engagement": ((current_metrics["engagement_total"] / historical_data["engagement_promedio"]) - 1) * 100,
            "alcance_promedio": sum(alcance_data) / len(alcance_data),
            "cambio_alcance": 15.5,  # Simulado
            "sentimiento_promedio": current_metrics["sentimiento_promedio"] * 100,
            "sentimiento_clase": get_sentiment_class(current_metrics["sentimiento_promedio"])[0],
            "sentimiento_texto": get_sentiment_class(current_metrics["sentimiento_promedio"])[1]
        },
        "insights": insights,
        "redes_sociales": redes_sociales,
        "fechas": fechas,
        "engagement_data": engagement_data,
        "alcance_data": alcance_data
    }

# Swagger UI Configuration
SWAGGER_URL = '/api/docs'
API_URL = '/static/swagger/openapi.yaml'

swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={
        'app_name': "InsightHub API Documentation",
        'deepLinking': True
    }
)

app.register_blueprint(swaggerui_blueprint)

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

# Prometheus metrics
REQUEST_COUNT = Counter(
    "app_requests_total",
    "Total app HTTP requests count",
    ["method", "endpoint", "http_status"],
)
REQUEST_LATENCY = Histogram(
    "app_request_latency_seconds", "Request latency in seconds", ["endpoint"]
)

# Start Prometheus metrics server with fallback ports
def start_metrics_server():
    ports = [8001, 8002, 8003]  # Try these ports in order
    for port in ports:
        try:
            start_http_server(port)
            logger.info(f"Prometheus metrics server started on port {port}")
            break
        except OSError as e:
            if port == ports[-1]:  # If this is the last port to try
                logger.warning(f"Could not start Prometheus server on any port: {e}")
            else:
                logger.info(f"Port {port} in use, trying next port")
                continue

if not app.debug:  # Only start metrics in non-debug mode
    start_metrics_server()


@app.before_request
def before_request():
    request.start_time = time.time()


@app.after_request
def after_request(response):
    # Log request details
    logger.info(
        f"Request: {request.method} {request.path} - Status: {response.status_code} - "
        f"Duration: {(time.time() - request.start_time):.2f}s"
    )

    # Record metrics
    REQUEST_COUNT.labels(
        method=request.method, endpoint=request.path, http_status=response.status_code
    ).inc()

    REQUEST_LATENCY.labels(endpoint=request.path).observe(
        time.time() - request.start_time
    )

    return response


@app.errorhandler(Exception)
def handle_exception(e):
    logger.exception("Unhandled exception occurred")
    return jsonify({"error": str(e), "status": "error"}), 500


from flask import Flask, redirect, session, request, render_template, send_file
from xhtml2pdf import pisa
import io
from bs4 import BeautifulSoup  # Added missing import

# --- Flask App Setup ---
app = Flask(__name__)
import os

app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))  # More secure secret key

# --- API Configuration ---
YOUTUBE_API_KEY = "AIzaSyA_pBApSdV9s5DjVyDh44mByJ5QYvkZzqg"  # Consider moving to environment variables

# --- Social Media Checker Configuration & Dependencies ---
# Ignore SSL errors - use only for development/testing, not production
ssl._create_default_https_context = ssl._create_unverified_context

# HARDCODED API KEY AND MODEL AS REQUESTED
GROQ_API_KEY = "gsk_WVuGV4vOW4evfjNE7jlDWGdyb3FYTCLqeWU4v2CB351ckeugq1qwx"  # Consider moving to environment variables
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

# Configure logging
import logging
from functools import wraps
from datetime import timedelta
import matplotlib

matplotlib.use("Agg")  # Use non-interactive backend for server
import matplotlib.pyplot as plt
import base64

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Social Media Checker Core Functions (Modified for Flask) ---


def fetch_page_html(url):
    """
    Fetches HTML content and its HTTP status code from a given URL.
    Returns (html_content, status_code) or (None, None) on significant error.
    Attempts to read HTML even for HTTP error responses.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    req = urllib.request.Request(url, headers=headers)
    html_content = None
    status_code = None

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            status_code = response.getcode()
            html_content = response.read().decode("utf-8", errors="ignore")
            return html_content, status_code
    except urllib.error.HTTPError as e:
        app.logger.warning(f"HTTP Error for {url} — Status: {e.code} — {e.reason}")
        status_code = e.code
        try:
            html_content = e.read().decode("utf-8", errors="ignore")
        except Exception as read_err:
            app.logger.error(
                f"Failed to read error page content for {url} — {read_err}"
            )
            html_content = None
        return html_content, status_code
    except urllib.error.URLError as e:
        app.logger.error(f"URL Error for {url} — {e.reason}")
        return None, None
    except Exception as e:
        app.logger.error(f"Failed to fetch {url} — {type(e).__name__}: {e}")
        return None, None


def clean_html_content(html_content):
    """
    Cleans HTML content by removing scripts, styles, etc., and extracts text.
    Limits content size and standardizes whitespace.
    """
    if not html_content:
        return ""

    soup = BeautifulSoup(html_content, "html.parser")  # Uses BeautifulSoup

    for tag in soup(
        [
            "script",
            "style",
            "nav",
            "footer",
            "header",
            "link",
            "svg",
            "img",
            "form",
            "iframe",
            "button",
            "input",
        ]
    ):
        tag.decompose()

    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return text[:4000]


def call_groq_ai(prompt):
    """
    Calls the Groq AI API with a given prompt.
    """
    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 50,
        "temperature": 0.0,
        "top_p": 1,
        "stop": ["\n", "User:", "Answer:"],
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GROQ_API_KEY}",
    }

    req = urllib.request.Request(
        GROQ_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            response_json = json.loads(response.read().decode("utf-8"))
            if response_json and response_json.get("choices"):
                return response_json["choices"][0]["message"]["content"].strip()
            else:
                app.logger.error(
                    f"Groq API: No choices found in response: {response_json}"
                )
                return "AI Error: No response content"
    except urllib.error.HTTPError as e:
        error_message = e.read().decode("utf-8")
        app.logger.error(f"Groq API HTTP Error ({e.code}): {error_message}")
        return f"AI Error: HTTP {e.code} - {error_message}"
    except urllib.error.URLError as e:
        app.logger.error(f"Groq API URL Error: {e.reason}")
        return f"AI Error: URL Error - {e.reason}"
    except json.JSONDecodeError as e:
        app.logger.error(f"Groq API JSON Decode Error: {e}")
        return f"AI Error: JSON Decode - {e}"
    except Exception as e:
        app.logger.error(f"Groq API Unknown Error: {type(e).__name__}: {e}")
        return f"AI Error: {str(e)}"


def validate_profile_ai(html_content, status_code, url):
    """
    Validates a social media profile using AI.
    If the status code is a clear error (404, 410, 403), constructs a specific prompt for the AI.
    Otherwise, cleans HTML and sends it to the AI.
    Returns (True/False, reason_string).
    """
    ai_input_text = ""
    reason_prefix = "AI says: "

    if status_code in (404, 410):
        ai_input_text = f"The URL '{url}' returned an HTTP {status_code} Not Found/Gone error page. This indicates the profile likely does not exist or has been removed."
        reason_prefix = f"HTTP {status_code} - "
    elif status_code == 403:
        ai_input_text = f"The URL '{url}' returned an HTTP {status_code} Forbidden error. This indicates access is denied, likely due to bot detection."
        reason_prefix = f"HTTP {status_code} - "
    elif not html_content:
        ai_input_text = f"No content could be retrieved from the URL '{url}' due to a network or connection error."
        reason_prefix = "Fetch Error - "
    else:
        ai_input_text = clean_html_content(html_content)
        if not ai_input_text.strip():
            ai_input_text = f"The page content from '{url}' was empty or contained no extractable text after cleaning."

    prompt = f"""You are an AI that validates social media profiles.
You will be given text content (which might be an error message or a webpage's actual content) and the URL.

Your task is to determine if this page represents a REAL, PUBLIC USER PROFILE with actual user-generated content (e.g., posts, bio, profile picture, followers count).

Respond `1` if it is a real public user profile.
Respond `0` if it is any of the following:
- A "Page Not Found" (404) or similar error page.
- A "Forbidden" (403) or "Access Denied" page.
- A login/signup wall or prompt.
- A generic placeholder page without specific user content (e.g., "Account not found" page, or a minimal page for a username that doesn't exist).
- A page indicating the account is suspended, banned, or private.
- If the input text describes an HTTP error or a failure to fetch content, consider it `0`.

Do not explain, just return 1 or 0.

URL: {url}
---
CONTENT:
{ai_input_text}
---
Answer:"""

    response = call_groq_ai(prompt)
    response_clean = response.strip()

    if response_clean.startswith("1"):
        return True, reason_prefix + "Real Profile"
    elif response_clean.startswith("0"):
        return False, reason_prefix + "Not Found / Fake / Generic"
    else:
        app.logger.warning(f"AI returned unexpected response for {url}: '{response}'")
        return False, f"AI Inconclusive: '{response}'"


def check_username_for_flask(username):
    """
    Checks the given username across various social media platforms.
    Returns a list of dictionaries, suitable for Flask template rendering.
    """
    platforms = {
        "Instagram": f"https://www.instagram.com/{username}/",
        "TikTok": f"https://www.tiktok.com/@{username}",
        "Twitter": f"https://twitter.com/{username}",
        "YouTube": f"https://www.youtube.com/@{username}",
        "Facebook": f"https://www.facebook.com/{username}",
    }

    results_for_display = []

    for platform, url in platforms.items():
        app.logger.info(f"Checking {platform} for {username}...")
        html_content, status_code = fetch_page_html(url)

        is_real, reason = validate_profile_ai(html_content, status_code, url)

        row_data = {
            "platform": platform,
            "status": "Real Profile" if is_real else "Not Found / Fake",
            "status_color": "green" if is_real else "red",  # For Tailwind CSS styling
            "url_display": url if is_real else "N/A",  # Show URL if real, N/A if not
            "reason": reason,  # Display the reason given by AI/logic
        }
        results_for_display.append(row_data)

        time.sleep(2)  # Be polite to social media sites and Groq API

    return results_for_display


# --- Rate Limiting Decorator ---

# Rate limiting setup
RATE_LIMIT = 10  # requests
RATE_LIMIT_PERIOD = 300  # seconds (5 minutes)
rate_limit_data = {}


def rate_limit(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        now = datetime.now()
        ip = request.remote_addr

        if ip not in rate_limit_data:
            rate_limit_data[ip] = {
                "count": 0,
                "reset_time": now + timedelta(seconds=RATE_LIMIT_PERIOD),
            }

        if rate_limit_data[ip]["count"] >= RATE_LIMIT:
            if now < rate_limit_data[ip]["reset_time"]:
                wait_time = (rate_limit_data[ip]["reset_time"] - now).seconds
                return render_template(
                    "dashboard.html",
                    user=session["user"],
                    error=f"Rate limit exceeded. Please wait {wait_time} seconds.",
                    results=[],
                    social_media_results=[],
                )
            else:
                rate_limit_data[ip] = {
                    "count": 0,
                    "reset_time": now + timedelta(seconds=RATE_LIMIT_PERIOD),
                }

        rate_limit_data[ip]["count"] += 1
        return f(*args, **kwargs)

    return decorated_function


# --- Flask Routes ---

VALID_USER = "eliberto"
VALID_PASS = "demo123"


@app.route("/")
def index():
    return render_template("login.html")


@app.route("/login", methods=["POST"])
def login():
    user = request.form["user"]
    password = request.form["password"]

    if user == VALID_USER and password == VALID_PASS:
        # Set permanent session
        session.permanent = True
        session["user"] = user
        session["logged_in"] = True
        session["last_activity"] = datetime.now().timestamp()
        logger.info(f"User {user} logged in successfully")
        return redirect("/dashboard")
    else:
        logger.warning(f"Failed login attempt for user: {user}")
        return render_template("login.html", error="Invalid credentials")


@app.route("/dashboard")
def dashboard():
    if not session.get('logged_in'):
        logger.warning("Unauthorized access attempt to dashboard")
        return redirect("/")
    
    # Update session activity
    session["last_activity"] = datetime.now().timestamp()
    session.modified = True
    
    return render_template(
        "dashboard.html", 
        user=session["user"], 
        results=[], 
        social_media_results=[],
        logged_in=True
    )


@app.route("/analyze", methods=["POST"])
@rate_limit
def analyze():
    if "user" not in session:
        return redirect("/")

    try:
        keyword = request.form["search"]
        channel = request.form["channel"]
        start_date_str = request.form["start_date"]
        end_date_str = request.form["end_date"]
        max_videos = min(int(request.form.get("max_videos", "3")), 5)

        start = datetime.strptime(start_date_str, "%Y-%m-%d")
        end = datetime.strptime(end_date_str, "%Y-%m-%d")

        search_term = f"{keyword} {channel}".strip()
        posts = fetch_youtube_comments(search_term, max_videos)

        filtered_posts = [
            p for p in posts if start <= datetime.strptime(p["date"], "%Y-%m-%d") <= end
        ]

        # Generate analytics summary
        analytics = get_analytics_summary(filtered_posts)

        logger.info(f"Analyzed {len(filtered_posts)} posts for keyword: {keyword}")

        return render_template(
            "dashboard.html",
            user=session["user"],
            results=filtered_posts,
            analytics=analytics,
            keyword=keyword,
            channel=channel,
            start=start_date_str,
            end=end_date_str,
            social_media_results=[],
        )

    except (KeyError, ValueError) as e:
        logger.error(f"Error in analyze route: {str(e)}")
        return render_template(
            "dashboard.html",
            user=session["user"],
            error="Invalid input parameters",
            results=[],
            social_media_results=[],
        )
    except Exception as e:
        logger.error(f"Unexpected error in analyze route: {str(e)}")
        return render_template(
            "dashboard.html",
            user=session["user"],
            error="An unexpected error occurred",
            results=[],
            social_media_results=[],
        )


@app.route("/check_social", methods=["POST"])
@rate_limit
def check_social_route():
    if "user" not in session:
        return redirect("/")

    try:
        username_to_check = request.form.get("social_username", "").strip()

        if not username_to_check:
            return render_template(
                "dashboard.html",
                user=session["user"],
                error="Please provide a username to check",
                results=[],
                social_media_results=[],
            )

        if not re.match(r"^[a-zA-Z0-9_.-]+$", username_to_check):
            return render_template(
                "dashboard.html",
                user=session["user"],
                error="Invalid username format. Use only letters, numbers, dots, underscores, and hyphens.",
                results=[],
                social_media_results=[],
            )

        social_media_results = check_username_for_flask(username_to_check)

        logger.info(f"Completed social media check for username: {username_to_check}")

        return render_template(
            "dashboard.html",
            user=session["user"],
            results=[],
            social_media_results=social_media_results,
            checked_username=username_to_check,
        )

    except Exception as e:
        logger.error(f"Error in social media check: {str(e)}")
        return render_template(
            "dashboard.html",
            user=session["user"],
            error="An error occurred while checking social media profiles",
            results=[],
            social_media_results=[],
        )


@app.route("/logout")
def logout():
    try:
        user = session.get("user", "unknown")
        session.clear()
        logger.info(f"User {user} logged out successfully")
        return redirect("/")
    except Exception as e:
        logger.error(f"Error during logout: {str(e)}")
        session.clear()  # Make sure session is cleared even if there's an error
        return redirect("/")


@app.route("/report", methods=["POST"])
def report():
    try:
        if "user" not in session:
            return redirect("/")

        if not request.form.get("data"):
            logger.error("No data provided for report generation")
            return "No data provided", 400

        raw_data = json.loads(request.form.get("data"))
        
        # Validate data format
        if not isinstance(raw_data, list):
            logger.error("Invalid data format - expected list of posts")
            return "Invalid data format", 400

        # Process data and add rich analytics
        analytics_data = {
            "posts": raw_data,
            "summary": {
                "total_posts": len(raw_data),
                "total_engagement": sum(post.get("engagement", 0) for post in raw_data),
                "total_comments": sum(len(post.get("comments", [])) for post in raw_data),
                "platforms": defaultdict(int),
                "sentiment_breakdown": defaultdict(int)
            },
            "trends": {
                "dates": [],
                "engagement_data": [],
                "views_data": []
            }
        }

        # Calculate trends and engagement over time
        for post in raw_data:
            post_date = post.get("date")
            if post_date:
                analytics_data["trends"]["dates"].append(post_date)
                analytics_data["trends"]["engagement_data"].append(post.get("engagement", 0))
                analytics_data["trends"]["views_data"].append(post.get("views", 0))
                analytics_data["summary"]["platforms"][post.get("platform", "unknown")] += 1

        # Calculate averages and percentages
        if raw_data:
            analytics_data["summary"]["avg_engagement"] = (
                analytics_data["summary"]["total_engagement"] / len(raw_data)
            )
            analytics_data["summary"]["engagement_rate"] = calculate_engagement_rate(
                analytics_data["summary"]["total_engagement"],
                sum(post.get("followers", 0) for post in raw_data)
            )

        # Process sentiment data and generate sentiment scores
        sentiment_counts = defaultdict(int)
        for post in raw_data:
            for comment in post.get("comments", []):
                sentiment = comment.get("type", "neutral")
                sentiment_counts[sentiment] += 1
                analytics_data["summary"]["sentiment_breakdown"][sentiment] += 1

        # Find top performing content
        if raw_data:
            analytics_data["top_content"] = max(
                raw_data, 
                key=lambda x: x.get("engagement", 0)
            )

        # Generate actionable insights
        insights = []
        if raw_data:
            # Engagement trends
            recent_engagement = analytics_data["trends"]["engagement_data"][-3:]
            if sum(recent_engagement) > sum(analytics_data["trends"]["engagement_data"][:3]):
                insights.append({
                    "type": "positive",
                    "message": "Engagement is trending upward - continue current content strategy"
                })
            
            # Platform performance
            top_platform = max(
                analytics_data["summary"]["platforms"].items(),
                key=lambda x: x[1]
            )[0]
            insights.append({
                "type": "info",
                "message": f"{top_platform} shows highest activity - consider focusing efforts here"
            })
            
            # Sentiment analysis
            positive_ratio = (
                sentiment_counts.get("positive", 0) + sentiment_counts.get("muy_positivo", 0)
            ) / sum(sentiment_counts.values()) if sum(sentiment_counts.values()) > 0 else 0
            
            if positive_ratio > 0.7:
                insights.append({
                    "type": "success",
                    "message": "Strong positive sentiment - maintain current tone and messaging"
                })
            elif positive_ratio < 0.3:
                insights.append({
                    "type": "warning",
                    "message": "Lower positive sentiment - review content strategy and engagement"
                })

        analytics_data["insights"] = insights
        
        # Generate the report
        logger.info("Generating report with %d posts and %d insights", 
                   len(raw_data), len(insights))
        
        return render_template(
            "report_template.html",
            data=analytics_data,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            user=session.get("user", "Anonymous")
        )

    except json.JSONDecodeError as e:
        logger.error("Invalid JSON data provided: %s", str(e))
        return "Invalid JSON data", 400
    except Exception as e:
        logger.exception("Error generating report: %s", str(e))
        return "Error generating report", 500


# Session configuration
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=30)


@app.before_request
def check_session_timeout():
    # Skip session check for static files and login page
    if request.endpoint == 'static' or request.path == '/' or request.path == '/login':
        return

    if not session.get('logged_in'):
        logger.debug("No active session found")
        return redirect('/')

    if "last_activity" not in session:
        session["last_activity"] = datetime.now().timestamp()
    else:
        last_activity = datetime.fromtimestamp(session["last_activity"])
        if datetime.now() - last_activity > timedelta(minutes=120):  # 2 hours timeout
            logger.info(f"Session timed out for user: {session.get('user')}")
            session.clear()
            return redirect('/')
        
    # Update last activity timestamp
    session["last_activity"] = datetime.now().timestamp()
    session.modified = True


# --- YouTube API Functions ---

# Removed the shadowed fetch_youtube_comments(video_id) function as it was unused
# and overwritten by the one below.


def fetch_youtube_video_details(video_id):
    """
    Fetches details of a YouTube video (like count, view count, etc.) using the YouTube Data API.
    Returns a dictionary with video details or None on error.
    """
    try:
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        video_response = youtube.videos().list(part="statistics", id=video_id).execute()

        if not video_response["items"]:
            app.logger.warning(f"No video found for ID: {video_id}")
            return None

        return video_response["items"][0]["statistics"]

    except HttpError as e:
        app.logger.error(f"An error occurred: {e}")
    except Exception as e:
        app.logger.error(f"Unexpected error: {e}")
    return None


def fetch_youtube_channel_videos(channel_id):
    """
    Fetches all videos from a YouTube channel using the YouTube Data API.
    Returns a list of videos with basic details or an empty list on error.
    """
    videos = []
    try:
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        channel_response = (
            youtube.channels().list(part="contentDetails", id=channel_id).execute()
        )

        if not channel_response["items"]:
            app.logger.warning(f"No channel found for ID: {channel_id}")
            return videos

        uploads_playlist_id = channel_response["items"][0]["contentDetails"][
            "relatedPlaylists"
        ]["uploads"]
        playlist_response = (
            youtube.playlistItems()
            .list(
                part="snippet",
                playlistId=uploads_playlist_id,
                maxResults=50,  # Fetches up to 50 videos. Add pagination if more are needed.
            )
            .execute()
        )

        for item in playlist_response.get("items", []):
            video_id = item["snippet"]["resourceId"]["videoId"]
            video_title = item["snippet"]["title"]
            video_description = item["snippet"]["description"]
            video_thumbnail = item["snippet"]["thumbnails"]["high"]["url"]
            video_publish_date = item["snippet"]["publishedAt"]

            videos.append(
                {
                    "id": video_id,
                    "title": video_title,
                    "description": video_description,
                    "thumbnail": video_thumbnail,
                    "publish_date": video_publish_date,
                }
            )
    except HttpError as e:
        app.logger.error(f"An error occurred: {e}")
    except Exception as e:
        app.logger.error(f"Unexpected error: {e}")
    return videos


def search_youtube_channels(query):
    """
    Searches for YouTube channels by query string using the YouTube Data API.
    Returns a list of channels with basic details or an empty list on error.
    """
    channels = []
    try:
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        search_response = (
            youtube.search()
            .list(part="snippet", q=query, type="channel", maxResults=10)
            .execute()
        )

        for item in search_response.get("items", []):
            channel_id = item["snippet"]["channelId"]
            channel_title = item["snippet"]["title"]
            channel_description = item["snippet"]["description"]
            channel_thumbnail = item["snippet"]["thumbnails"]["high"]["url"]

            channels.append(
                {
                    "id": channel_id,
                    "title": channel_title,
                    "description": channel_description,
                    "thumbnail": channel_thumbnail,
                }
            )
    except HttpError as e:
        app.logger.error(f"An error occurred: {e}")
    except Exception as e:
        app.logger.error(f"Unexpected error: {e}")
    return channels


def fetch_youtube_comments(
    keyword, max_videos=5
):  # This is the version used by /analyze
    """
    Fetches comments from YouTube videos matching the keyword.
    Returns list of posts with their comments and metadata.
    """
    try:
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

        search_response = (
            youtube.search()
            .list(
                q=keyword,
                part="id,snippet",
                type="video",
                maxResults=max_videos,
                order="date",
            )
            .execute()
        )

        posts = []

        for search_result in search_response.get("items", []):
            video_id = search_result["id"]["videoId"]
            video_title = search_result["snippet"]["title"]
            video_date = search_result["snippet"]["publishedAt"][:10]

            video_stats_response = (
                youtube.videos().list(part="statistics", id=video_id).execute()
            )

            engagement = 0
            if video_stats_response["items"]:
                engagement = int(
                    video_stats_response["items"][0]["statistics"].get("likeCount", 0)
                )

            try:
                comments_response = (
                    youtube.commentThreads()
                    .list(
                        part="snippet",
                        videoId=video_id,
                        maxResults=10,
                        textFormat="plainText",
                    )
                    .execute()
                )

                comments_data = []
                for item in comments_response.get("items", []):
                    comment_text = item["snippet"]["topLevelComment"]["snippet"][
                        "textDisplay"
                    ]
                    comment_type = determine_comment_type(comment_text)
                    comments_data.append({"text": comment_text, "type": comment_type})

                posts.append(
                    {
                        "title": video_title,
                        "comments": comments_data,
                        "date": video_date,
                        "engagement": engagement,
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                    }
                )

            except HttpError as e:
                app.logger.error(f"Error fetching comments for video {video_id}: {e}")
                continue  # Continue to next video if comments fail for one

        return posts

    except HttpError as e:
        app.logger.error(
            f"An HTTP error occurred during YouTube search/video fetch: {e}"
        )
        return []
    except Exception as e:
        app.logger.error(f"An unexpected error occurred during YouTube fetch: {e}")
        return []


def determine_comment_type(comment_text):
    """Uses Groq AI to determine the type of comment"""
    prompt = f"""Analyze this YouTube comment and classify it as exactly one of these types: positive, negative, neutral, or suggestion.
    Just return the type, nothing else.
    Comment: {comment_text}
    Type:"""

    response = call_groq_ai(prompt).lower().strip()

    valid_types = {"positive", "negative", "neutral", "suggestion"}
    return response if response in valid_types else "neutral"


def generate_engagement_chart(data):
    """
    Generates a base64-encoded chart image for engagement analytics
    """
    try:
        if not data:
            return None

        # Extract data for charts
        dates = []
        engagements = []
        titles = []

        for post in data:
            dates.append(post.get("date", ""))
            engagements.append(post.get("engagement", 0))
            titles.append(
                post.get("title", "")[:30] + "..."
                if len(post.get("title", "")) > 30
                else post.get("title", "")
            )

        if not dates:
            return None

        # Create figure with subplots
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
        fig.patch.set_facecolor("white")

        # Engagement over time
        ax1.plot(
            range(len(dates)),
            engagements,
            marker="o",
            linewidth=2,
            markersize=6,
            color="#3B82F6",
        )
        ax1.set_title("Engagement Over Time", fontsize=16, fontweight="bold", pad=20)
        ax1.set_xlabel("Posts", fontsize=12)
        ax1.set_ylabel("Engagement (Likes)", fontsize=12)
        ax1.grid(True, alpha=0.3)
        ax1.set_xticks(range(len(dates)))
        ax1.set_xticklabels(dates, rotation=45, ha="right")

        # Comment sentiment analysis
        sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0, "suggestion": 0}
        for post in data:
            for comment in post.get("comments", []):
                comment_type = comment.get("type", "neutral")
                if comment_type in sentiment_counts:
                    sentiment_counts[comment_type] += 1

        colors = ["#10B981", "#EF4444", "#6B7280", "#F59E0B"]
        ax2.pie(
            sentiment_counts.values(),
            labels=sentiment_counts.keys(),
            autopct="%1.1f%%",
            colors=colors,
            startangle=90,
        )
        ax2.set_title(
            "Comment Sentiment Distribution", fontsize=16, fontweight="bold", pad=20
        )

        plt.tight_layout()

        # Convert to base64
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format="png", dpi=300, bbox_inches="tight")
        img_buffer.seek(0)
        img_base64 = base64.b64encode(img_buffer.getvalue()).decode()
        plt.close()

        return f"data:image/png;base64,{img_base64}"

    except Exception as e:
        logger.error(f"Error generating chart: {str(e)}")
        return None


def get_analytics_summary(posts):
    """
    Generate comprehensive analytics summary from posts data
    """
    if not posts:
        return {}

    total_engagement = sum(post.get("engagement", 0) for post in posts)
    total_comments = sum(len(post.get("comments", [])) for post in posts)

    # Sentiment analysis
    sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0, "suggestion": 0}
    all_comments = []

    for post in posts:
        for comment in post.get("comments", []):
            comment_type = comment.get("type", "neutral")
            if comment_type in sentiment_counts:
                sentiment_counts[comment_type] += 1
            all_comments.append(comment.get("text", ""))

    # Top performing content
    top_post = max(posts, key=lambda x: x.get("engagement", 0)) if posts else None

    return {
        "total_posts": len(posts),
        "total_engagement": total_engagement,
        "avg_engagement": total_engagement / len(posts) if posts else 0,
        "total_comments": total_comments,
        "sentiment_breakdown": sentiment_counts,
        "top_performing_post": top_post,
        "engagement_rate": (total_engagement / len(posts)) if posts else 0,
    }


# --- Enhanced Analytics and Competitor Analysis Routes ---


@app.route("/analytics/<channel_id>")
def analytics_page(channel_id):
    """Enhanced analytics page for specific channel analysis"""
    if "user" not in session:
        return redirect("/")

    try:
        # Fetch channel videos and analyze
        videos = fetch_youtube_channel_videos(channel_id)
        analytics_data = []

        for video in videos[:10]:  # Analyze last 10 videos
            video_stats = fetch_youtube_video_details(video["id"])
            if video_stats:
                analytics_data.append(
                    {
                        "title": video["title"],
                        "date": video["publish_date"][:10],
                        "engagement": int(video_stats.get("likeCount", 0)),
                        "views": int(video_stats.get("viewCount", 0)),
                        "comments_count": int(video_stats.get("commentCount", 0)),
                    }
                )

        summary = get_analytics_summary(analytics_data)

        return render_template(
            "analytics.html",
            user=session["user"],
            analytics_data=analytics_data,
            summary=summary,
            channel_id=channel_id,
        )

    except Exception as e:
        logger.error(f"Error in analytics page: {str(e)}")
        return render_template(
            "dashboard.html",
            user=session["user"],
            error="Error loading analytics",
            results=[],
            social_media_results=[],
        )


@app.route("/competitor_analysis", methods=["POST"])
@rate_limit
def competitor_analysis():
    """Analyze competitor channels"""
    if "user" not in session:
        return redirect("/")

    try:
        competitor_username = request.form.get("competitor_username", "").strip()

        if not competitor_username:
            return render_template(
                "dashboard.html",
                user=session["user"],
                error="Please provide a competitor username",
                results=[],
                social_media_results=[],
            )

        # Search for the competitor channel
        channels = search_youtube_channels(competitor_username)

        if not channels:
            return render_template(
                "dashboard.html",
                user=session["user"],
                error="No channels found for the given username",
                results=[],
                social_media_results=[],
            )

        # Redirect to analytics page for the first found channel
        return redirect(f'/analytics/{channels[0]["id"]}')

    except Exception as e:
        logger.error(f"Error in competitor analysis: {str(e)}")
        return render_template(
            "dashboard.html",
            user=session["user"],
            error="Error analyzing competitor",
            results=[],
            social_media_results=[],
        )


@app.route("/health")
def health_check():
    """Health check endpoint for monitoring system status."""
    with log_time("Health Check"):
        try:
            return jsonify(
                {
                    "status": "healthy",
                    "version": "1.0.0",
                    "timestamp": datetime.utcnow().isoformat(),
                    "checks": {
                        "database": check_database_connection(),
                        "redis": check_redis_connection(),
                        "external_apis": check_external_apis(),
                    },
                }
            )
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return (
                jsonify(
                    {
                        "status": "unhealthy",
                        "error": str(e),
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
                500,
            )


def check_database_connection():
    """Check if database connection is working."""
    try:
        # Add your database connection check here
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {str(e)}")
        return False


def check_redis_connection():
    """Check if Redis connection is working."""
    try:
        # Add your Redis connection check here
        return True
    except Exception as e:
        logger.error(f"Redis connection check failed: {str(e)}")
        return False


def check_external_apis():
    """Check if external APIs are accessible."""
    try:
        # Add your external API checks here
        return True
    except Exception as e:
        logger.error(f"External API check failed: {str(e)}")
        return False
