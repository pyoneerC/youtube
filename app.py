import re
import ssl
import time
import urllib.error
import urllib.request
import json
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from flask import Flask, redirect, session, request, render_template, send_file
from xhtml2pdf import pisa
import io
from bs4 import BeautifulSoup # Added missing import

# --- Flask App Setup ---
app = Flask(__name__)
import os
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))  # More secure secret key

# --- API Configuration ---
YOUTUBE_API_KEY = 'AIzaSyA_pBApSdV9s5DjVyDh44mByJ5QYvkZzqg' # Consider moving to environment variables

# --- Social Media Checker Configuration & Dependencies ---
# Ignore SSL errors - use only for development/testing, not production
ssl._create_default_https_context = ssl._create_unverified_context

# HARDCODED API KEY AND MODEL AS REQUESTED
GROQ_API_KEY = 'gsk_WVuGV4vOW4evfjNE7jlDWGdyb3FYTCLqeWU4v2CB351ckeugq1qwx' # Consider moving to environment variables
GROQ_ENDPOINT = 'https://api.groq.com/openai/v1/chat/completions'
GROQ_MODEL = 'meta-llama/llama-4-scout-17b-16e-instruct'

# Configure logging
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
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    req = urllib.request.Request(url, headers=headers)
    html_content = None
    status_code = None

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            status_code = response.getcode()
            html_content = response.read().decode('utf-8', errors='ignore')
            return html_content, status_code
    except urllib.error.HTTPError as e:
        app.logger.warning(f"HTTP Error for {url} — Status: {e.code} — {e.reason}")
        status_code = e.code
        try:
            html_content = e.read().decode('utf-8', errors='ignore')
        except Exception as read_err:
            app.logger.error(f"Failed to read error page content for {url} — {read_err}")
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

    soup = BeautifulSoup(html_content, "html.parser") # Uses BeautifulSoup

    for tag in soup(["script", "style", "nav", "footer", "header", "link", "svg", "img", "form", "iframe", "button", "input"]):
        tag.decompose()

    text = soup.get_text(separator=' ', strip=True)
    text = re.sub(r'\s+', ' ', text)
    return text[:4000]


def call_groq_ai(prompt):
    """
    Calls the Groq AI API with a given prompt.
    """
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 50,
        "temperature": 0.0,
        "top_p": 1,
        "stop": ["\n", "User:", "Answer:"],
    }

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {GROQ_API_KEY}'
    }

    req = urllib.request.Request(GROQ_ENDPOINT, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            response_json = json.loads(response.read().decode('utf-8'))
            if response_json and response_json.get('choices'):
                return response_json['choices'][0]['message']['content'].strip()
            else:
                app.logger.error(f"Groq API: No choices found in response: {response_json}")
                return "AI Error: No response content"
    except urllib.error.HTTPError as e:
        error_message = e.read().decode('utf-8')
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
        "Facebook": f"https://www.facebook.com/{username}"
    }

    results_for_display = []

    for platform, url in platforms.items():
        app.logger.info(f"Checking {platform} for {username}...")
        html_content, status_code = fetch_page_html(url)

        is_real, reason = validate_profile_ai(html_content, status_code, url)

        row_data = {
            "platform": platform,
            "status": "Real Profile" if is_real else "Not Found / Fake",
            "status_color": "green" if is_real else "red", # For Tailwind CSS styling
            "url_display": url if is_real else "N/A", # Show URL if real, N/A if not
            "reason": reason # Display the reason given by AI/logic
        }
        results_for_display.append(row_data)

        time.sleep(2) # Be polite to social media sites and Groq API

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
            rate_limit_data[ip] = {'count': 0, 'reset_time': now + timedelta(seconds=RATE_LIMIT_PERIOD)}
        
        if rate_limit_data[ip]['count'] >= RATE_LIMIT:
            if now < rate_limit_data[ip]['reset_time']:
                wait_time = (rate_limit_data[ip]['reset_time'] - now).seconds
                return render_template('dashboard.html', 
                    user=session['user'],
                    error=f"Rate limit exceeded. Please wait {wait_time} seconds.",
                    results=[], 
                    social_media_results=[])
            else:
                rate_limit_data[ip] = {'count': 0, 'reset_time': now + timedelta(seconds=RATE_LIMIT_PERIOD)}
        
        rate_limit_data[ip]['count'] += 1
        return f(*args, **kwargs)
    return decorated_function

# --- Flask Routes ---

VALID_USER = 'eliberto'
VALID_PASS = 'demo123'

@app.route('/')
def index():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    user = request.form['user']
    password = request.form['password']

    if user == VALID_USER and password == VALID_PASS:
        session['user'] = user
        return redirect('/dashboard')
    else:
        return render_template('login.html', error="Invalid credentials")

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/')
    return render_template('dashboard.html', user=session['user'], results=[], social_media_results=[])

@app.route('/analyze', methods=['POST'])
def analyze():
    if 'user' not in session:
        return redirect('/')

    keyword = request.form['search']
    channel = request.form['channel']
    start_date_str = request.form['start_date']
    end_date_str = request.form['end_date']
    max_videos = min(int(request.form.get('max_videos', '3')), 5)

        start = datetime.strptime(start_date_str, "%Y-%m-%d")
        end = datetime.strptime(end_date_str, "%Y-%m-%d")

    search_term = f"{keyword} {channel}".strip()
    posts = fetch_youtube_comments(search_term, max_videos) # Uses the keyword/max_videos version
    
    filtered_posts = [p for p in posts if start <= datetime.strptime(p['date'], "%Y-%m-%d") <= end]

        filtered_posts = [p for p in posts if start <= datetime.strptime(p['date'], "%Y-%m-%d") <= end]
        logger.info(f"Analyzed {len(filtered_posts)} posts for keyword: {keyword}")

        return render_template('dashboard.html', user=session['user'], results=filtered_posts,
                           keyword=keyword, channel=channel, start=start_date_str, end=end_date_str,
                           social_media_results=[])

    except (KeyError, ValueError) as e:
        logger.error(f"Error in analyze route: {str(e)}")
        return render_template('dashboard.html', user=session['user'], 
                           error="Invalid input parameters",
                           results=[], social_media_results=[])
    except Exception as e:
        logger.error(f"Unexpected error in analyze route: {str(e)}")
        return render_template('dashboard.html', user=session['user'], 
                           error="An unexpected error occurred",
                           results=[], social_media_results=[])
@app.route('/check_social', methods=['POST'])
@rate_limit
def check_social_route():
    if 'user' not in session:
        return redirect('/')

    try:
        username_to_check = request.form.get('social_username', '').strip()
        
        if not username_to_check:
            return render_template('dashboard.html', 
                user=session['user'],
                error="Please provide a username to check",
                results=[], 
                social_media_results=[])

        if not re.match(r'^[a-zA-Z0-9_.-]+$', username_to_check):
            return render_template('dashboard.html', 
                user=session['user'],
                error="Invalid username format. Use only letters, numbers, dots, underscores, and hyphens.",
                results=[], 
                social_media_results=[])

        social_media_results = check_username_for_flask(username_to_check)
        
        logger.info(f"Completed social media check for username: {username_to_check}")
        
        return render_template('dashboard.html', 
            user=session['user'],
            results=[], 
            social_media_results=social_media_results,
            checked_username=username_to_check)

    except Exception as e:
        logger.error(f"Error in social media check: {str(e)}")
        return render_template('dashboard.html', 
            user=session['user'],
            error="An error occurred while checking social media profiles",
            results=[], 
            social_media_results=[])
@app.route('/logout')
def logout():
    try:
        user = session.get('user', 'unknown')
        session.clear()
        logger.info(f"User {user} logged out successfully")
        return redirect('/')
    except Exception as e:
        logger.error(f"Error during logout: {str(e)}")
        session.clear()  # Make sure session is cleared even if there's an error
        return redirect('/')

@app.route('/report', methods=['POST'])
def report():
    try:
        if 'user' not in session:
            return redirect('/')

        if not request.form.get('data'):
            logger.error("No data provided for report generation")
            return "No data provided", 400

    pdf = io.BytesIO()
    pisa.CreatePDF(html, dest=pdf)
    pdf.seek(0)

        html = render_template("report_template.html", results=data, chart_img=chart_img)

        pdf = io.BytesIO()
        pisa_status = pisa.CreatePDF(html, dest=pdf)
        
        if pisa_status.err:
            logger.error(f"Error creating PDF: {pisa_status.err}")
            return "Error creating PDF", 500

        pdf.seek(0)
        
        logger.info(f"Successfully generated PDF report for user {session['user']}")
        return send_file(
            pdf,
            mimetype="application/pdf",
            download_name=f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            as_attachment=True
        )
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON data for report: {str(e)}")
        return "Invalid data format", 400
    except Exception as e:
        logger.error(f"Unexpected error generating report: {str(e)}")
        return "Error generating report", 500


# Session configuration
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

@app.before_request
def check_session_timeout():
    if 'user' in session:
        if 'last_activity' not in session:
            session['last_activity'] = datetime.now().timestamp()
        else:
            last_activity = datetime.fromtimestamp(session['last_activity'])
            if datetime.now() - last_activity > timedelta(minutes=30):
                session.clear()
                return redirect('/')
        session['last_activity'] = datetime.now().timestamp()


# --- YouTube API Functions ---

# Removed the shadowed fetch_youtube_comments(video_id) function as it was unused
# and overwritten by the one below. If it was intended for a different purpose,
# it should be given a unique name.

def fetch_youtube_video_details(video_id):
    """
    Fetches details of a YouTube video (like count, view count, etc.) using the YouTube Data API.
    Returns a dictionary with video details or None on error.
    """
    try:
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        video_response = youtube.videos().list(
            part='statistics',
            id=video_id
        ).execute()

        if not video_response['items']:
            app.logger.warning(f"No video found for ID: {video_id}")
            return None

        return video_response['items'][0]['statistics']

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
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        channel_response = youtube.channels().list(
            part='contentDetails',
            id=channel_id
        ).execute()

        if not channel_response['items']:
            app.logger.warning(f"No channel found for ID: {channel_id}")
            return videos

        uploads_playlist_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        playlist_response = youtube.playlistItems().list(
            part='snippet',
            playlistId=uploads_playlist_id,
            maxResults=50 # Fetches up to 50 videos. Add pagination if more are needed.
        ).execute()

        for item in playlist_response.get('items', []):
            video_id = item['snippet']['resourceId']['videoId']
            video_title = item['snippet']['title']
            video_description = item['snippet']['description']
            video_thumbnail = item['snippet']['thumbnails']['high']['url']
            video_publish_date = item['snippet']['publishedAt']

            videos.append({
                'id': video_id,
                'title': video_title,
                'description': video_description,
                'thumbnail': video_thumbnail,
                'publish_date': video_publish_date
            })
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
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        search_response = youtube.search().list(
            part='snippet',
            q=query,
            type='channel',
            maxResults=10
        ).execute()

        for item in search_response.get('items', []):
            channel_id = item['snippet']['channelId']
            channel_title = item['snippet']['title']
            channel_description = item['snippet']['description']
            channel_thumbnail = item['snippet']['thumbnails']['high']['url']

            channels.append({
                'id': channel_id,
                'title': channel_title,
                'description': channel_description,
                'thumbnail': channel_thumbnail
            })
    except HttpError as e:
        app.logger.error(f"An error occurred: {e}")
    except Exception as e:
        app.logger.error(f"Unexpected error: {e}")
    return channels


def fetch_youtube_comments(keyword, max_videos=5): # This is the version used by /analyze
    """
    Fetches comments from YouTube videos matching the keyword.
    Returns list of posts with their comments and metadata.
    """
    try:
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        
        search_response = youtube.search().list(
            q=keyword,
            part='id,snippet',
            type='video',
            maxResults=max_videos,
            order='date'
        ).execute()

        posts = []
        
        for search_result in search_response.get('items', []):
            video_id = search_result['id']['videoId']
            video_title = search_result['snippet']['title']
            video_date = search_result['snippet']['publishedAt'][:10]
            
            video_stats_response = youtube.videos().list(
                part='statistics',
                id=video_id
            ).execute()
            
            engagement = 0
            if video_stats_response['items']:
                engagement = int(video_stats_response['items'][0]['statistics'].get('likeCount', 0))
            
            try:
                comments_response = youtube.commentThreads().list(
                    part='snippet',
                    videoId=video_id,
                    maxResults=10,
                    textFormat='plainText'
                ).execute()
                
                comments_data = []
                for item in comments_response.get('items', []):
                    comment_text = item['snippet']['topLevelComment']['snippet']['textDisplay']
                    comment_type = determine_comment_type(comment_text)
                    comments_data.append({
                        'text': comment_text,
                        'type': comment_type
                    })
                
                posts.append({
                    'title': video_title,
                    'comments': comments_data,
                    'date': video_date,
                    'engagement': engagement,
                    'url': f'https://www.youtube.com/watch?v={video_id}'
                })
                
            except HttpError as e:
                app.logger.error(f"Error fetching comments for video {video_id}: {e}")
                continue # Continue to next video if comments fail for one
                
        return posts
        
    except HttpError as e:
        app.logger.error(f"An HTTP error occurred during YouTube search/video fetch: {e}")
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
    
    valid_types = {'positive', 'negative', 'neutral', 'suggestion'}
    return response if response in valid_types else 'neutral'

# The duplicated Flask routes and YouTube API functions from line 447 onwards have been removed.

if __name__ == '__main__':
    app.run(debug=True) # Added for local development