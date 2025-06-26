import os
import re
import ssl
import time
import json
import logging
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from collections import defaultdict
from functools import wraps
from typing import Dict, List

import numpy as np
from flask import Flask, request, render_template, redirect, session, jsonify
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from bs4 import BeautifulSoup

# Initialize Flask app
app = Flask(__name__)

# Configuration
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here-change-in-production')
app.permanent_session_lifetime = timedelta(hours=2)
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=120)

# API Keys - Move to environment variables in production
YOUTUBE_API_KEY = "AIzaSyA_pBApSdV9s5DjVyDh44mByJ5QYvkZzqg"

# Login credentials
VALID_USER = "eliberto"
VALID_PASS = "demo123"

# Ignore SSL errors for development
ssl._create_default_https_context = ssl._create_unverified_context

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Sentiment thresholds
SENTIMENT_THRESHOLDS = {
    "muy_positivo": 0.8,
    "positivo": 0.6,
    "neutral": 0.4,
    "negativo": 0.2
}

# Rate limiting
RATE_LIMIT = 10
RATE_LIMIT_PERIOD = 300
rate_limit_data = {}

# ===== HELPER FUNCTIONS =====

def calculate_engagement_rate(interactions: int, followers: int) -> float:
    """Calculate engagement rate."""
    return (interactions / followers * 100) if followers > 0 else 0

def get_sentiment_class(sentiment_score: float) -> tuple:
    """Determine sentiment class and text based on score."""
    if sentiment_score >= SENTIMENT_THRESHOLDS["muy_positivo"]:
        return "success", "Very Positive"
    elif sentiment_score >= SENTIMENT_THRESHOLDS["positivo"]:
        return "success", "Positive"
    elif sentiment_score >= SENTIMENT_THRESHOLDS["neutral"]:
        return "warning", "Neutral"
    elif sentiment_score >= SENTIMENT_THRESHOLDS["negativo"]:
        return "danger", "Negative"
    return "danger", "Very Negative"

def analyze_comment_sentiment(comment_text):
    """Enhanced sentiment analysis for YouTube comments."""
    # Extended word lists for better accuracy
    positive_words = [
        # Basic positive
        'good', 'great', 'awesome', 'amazing', 'excellent', 'love', 'like', 'best', 
        'fantastic', 'wonderful', 'perfect', 'brilliant', 'outstanding', 'superb',
        # YouTube specific positive
        'subscribe', 'subscribed', 'thanks', 'thank', 'helpful', 'useful', 'cool',
        'nice', 'beautiful', 'incredible', 'impressive', 'inspiring', 'motivating',
        'hilarious', 'funny', 'entertaining', 'enjoyable', 'recommend', 'favorite',
        'favourite', 'appreciate', 'grateful', 'blessed', 'lucky', 'happy', 'joy',
        'excited', 'thrilled', 'pleased', 'satisfied', 'delighted', 'magnificent',
        # Emojis and expressions
        '❤️', '😍', '🔥', '👏', '💯', '🙌', '✨', '💖', '😊', '😃', '😄', '😁',
        'haha', 'lol', 'lmao', 'omg', 'wow', 'yes', 'yay', 'congrats', 'bravo'
    ]
    
    negative_words = [
        # Basic negative
        'bad', 'terrible', 'awful', 'horrible', 'hate', 'dislike', 'worst', 
        'disappointing', 'poor', 'pathetic', 'disgusting', 'annoying', 'boring', 'stupid',
        # YouTube specific negative
        'clickbait', 'fake', 'scam', 'spam', 'trash', 'garbage', 'waste', 'time',
        'unsubscribe', 'unsubscribed', 'disliked', 'thumbs down', 'cringe', 'crappy',
        'lame', 'dumb', 'idiotic', 'moronic', 'ridiculous', 'pointless', 'useless',
        'confused', 'frustrated', 'angry', 'mad', 'upset', 'disappointed', 'sad',
        'depressed', 'worried', 'concerned', 'shocked', 'disgusted', 'furious',
        # Emojis and expressions
        '😠', '😡', '🤮', '💩', '👎', '😞', '😢', '😭', '😤', '🙄', '😒',
        'ugh', 'meh', 'nah', 'nope', 'wtf', 'seriously', 'stop', 'enough'
    ]
    
    # Neutral indicators
    neutral_words = [
        'okay', 'ok', 'fine', 'alright', 'maybe', 'perhaps', 'probably', 'possibly',
        'question', 'ask', 'wonder', 'think', 'believe', 'guess', 'suppose',
        'first', 'second', 'third', 'here', 'there', 'when', 'where', 'what', 'how'
    ]
    
    text_lower = comment_text.lower()
    
    # Count sentiment words
    positive_count = sum(1 for word in positive_words if word in text_lower)
    negative_count = sum(1 for word in negative_words if word in text_lower)
    neutral_count = sum(1 for word in neutral_words if word in text_lower)
    
    # Check for special patterns
    # Exclamation marks often indicate positive sentiment
    exclamation_count = text_lower.count('!')
    if exclamation_count > 0:
        positive_count += min(exclamation_count, 3) * 0.5  # Cap the bonus
    
    # ALL CAPS might indicate strong emotion (could be positive or negative)
    caps_words = sum(1 for word in comment_text.split() if word.isupper() and len(word) > 2)
    if caps_words > 0:
        if positive_count > negative_count:
            positive_count += caps_words * 0.3
        elif negative_count > positive_count:
            negative_count += caps_words * 0.3
    
    # Questions are often neutral
    question_marks = text_lower.count('?')
    if question_marks > 0:
        neutral_count += question_marks * 0.5
    
    # Calculate sentiment score
    total_sentiment_words = positive_count + negative_count + neutral_count
    
    if total_sentiment_words == 0:
        # No sentiment indicators found, check length for neutral
        if len(comment_text.strip()) < 10:
            return 0.4  # Short comments tend to be less expressive
        return 0.5  # Default neutral
    
    # Weighted sentiment calculation
    positive_weight = positive_count / total_sentiment_words
    negative_weight = negative_count / total_sentiment_words
    neutral_weight = neutral_count / total_sentiment_words
    
    # Calculate final sentiment score (0 = very negative, 1 = very positive)
    sentiment_score = positive_weight + (neutral_weight * 0.5) + (negative_weight * 0.1)
    
    # Ensure score is between 0 and 1
    return max(0.0, min(1.0, sentiment_score))

def get_sentiment_label(sentiment_score):
    """Convert sentiment score to label"""
    if sentiment_score >= 0.7:
        return "very_positive"
    elif sentiment_score >= 0.6:
        return "positive"
    elif sentiment_score >= 0.4:
        return "neutral"
    elif sentiment_score >= 0.3:
        return "negative"
    else:
        return "very_negative"

def get_comment_type(comment_text):
    """Classify comment type using keyword-based analysis"""
    text_lower = comment_text.lower()
    
    # Question keywords
    question_keywords = ['how', 'what', 'when', 'where', 'why', 'which', 'who', '?']
    # Praise keywords  
    praise_keywords = ['amazing', 'awesome', 'great', 'love', 'perfect', 'excellent', 'fantastic', 'wonderful', 'brilliant', 'incredible']
    # Critique keywords
    critique_keywords = ['wrong', 'bad', 'terrible', 'hate', 'awful', 'horrible', 'stupid', 'worst', 'sucks', 'disappointing']
    # Request keywords
    request_keywords = ['please', 'can you', 'could you', 'would you', 'tutorial', 'guide', 'help', 'explain']
    
    # Count keyword matches
    question_score = sum(1 for keyword in question_keywords if keyword in text_lower)
    praise_score = sum(1 for keyword in praise_keywords if keyword in text_lower)
    critique_score = sum(1 for keyword in critique_keywords if keyword in text_lower)
    request_score = sum(1 for keyword in request_keywords if keyword in text_lower)
    
    # Determine type based on highest score
    scores = {
        'question': question_score,
        'praise': praise_score,
        'critique': critique_score,
        'request': request_score
    }
    
    max_type = max(scores, key=scores.get)
    
    # If no clear category or tie, default to 'general'
    if scores[max_type] == 0 or list(scores.values()).count(scores[max_type]) > 1:
        return 'general'
    
    return max_type

def determine_comment_type(comment_text):
    """Determine comment type using local analysis."""
    sentiment_score = analyze_comment_sentiment(comment_text)
    
    # Use sentiment to determine type
    if sentiment_score >= 0.6:
        return "positive"
    elif sentiment_score <= 0.4:
        return "negative"
    else:
        # Check for suggestion keywords
        suggestion_keywords = ['should', 'could', 'would', 'suggest', 'recommend', 'idea', 'maybe', 'perhaps']
        if any(keyword in comment_text.lower() for keyword in suggestion_keywords):
            return "suggestion"
        return "neutral"

def extract_channel_id_from_url(url):
    """Extract channel ID from various YouTube URL formats."""
    try:
        # Clean and normalize the URL
        url = url.strip()
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        logger.info(f"Processing URL: {url}")
        
        # Handle @username format (new YouTube handles)
        if '/@' in url:
            handle_match = re.search(r'youtube\.com/@([a-zA-Z0-9_.-]+)', url)
            if handle_match:
                handle = handle_match.group(1)
                logger.info(f"Found handle: @{handle}")
                return resolve_handle_to_channel_id(handle)
        
        # Handle direct channel ID URLs
        channel_match = re.search(r'youtube\.com/channel/([a-zA-Z0-9_-]{24})', url)
        if channel_match:
            channel_id = channel_match.group(1)
            logger.info(f"Found direct channel ID: {channel_id}")
            return channel_id
        
        # Handle legacy /c/ and /user/ URLs
        legacy_patterns = [
            r'youtube\.com/c/([a-zA-Z0-9_-]+)',                # /c/username
            r'youtube\.com/user/([a-zA-Z0-9_-]+)',             # /user/username
        ]
        
        for pattern in legacy_patterns:
            match = re.search(pattern, url)
            if match:
                username = match.group(1)
                logger.info(f"Found legacy username: {username}")
                return resolve_username_to_channel_id(username)
        
        return None
        
    except Exception as e:
        logger.error(f"Error extracting channel ID from URL {url}: {e}")
        return None

def resolve_username_to_channel_id(username):
    """Resolve a YouTube username/handle to channel ID using the API."""
    try:
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        
        # First try searching by channel name
        search_response = youtube.search().list(
            q=username,
            part="snippet",
            type="channel",
            maxResults=5
        ).execute()
        
        # Look for exact or close matches
        for item in search_response.get("items", []):
            channel_title = item["snippet"]["title"].lower()
            if username.lower() in channel_title or channel_title in username.lower():
                return item["snippet"]["channelId"]
        
        # If no exact match, return the first result if available
        if search_response.get("items"):
            return search_response["items"][0]["snippet"]["channelId"]
            
        return None
        
    except Exception as e:
        logger.error(f"Error resolving username {username} to channel ID: {e}")
        return None

def resolve_handle_to_channel_id(handle):
    """Resolve a YouTube handle (@username) to channel ID using the API."""
    try:
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        
        logger.info(f"Resolving handle: @{handle}")
        
        # Try searching for the handle with @ prefix
        search_queries = [
            f"@{handle}",  # Exact handle
            handle,       # Without @
            f"{handle} channel"  # With channel keyword
        ]
        
        for query in search_queries:
            logger.info(f"Searching for: {query}")
            
            search_response = youtube.search().list(
                q=query,
                part="snippet",
                type="channel",
                maxResults=10
            ).execute()
            
            # Look for exact matches first
            for item in search_response.get("items", []):
                channel_title = item["snippet"]["title"]
                channel_id = item["snippet"]["channelId"]
                
                logger.info(f"Found channel: {channel_title} (ID: {channel_id})")
                
                # Check if this looks like the right channel
                # Look for exact handle match or very similar title
                if (handle.lower() in channel_title.lower() or 
                    channel_title.lower() in handle.lower() or
                    handle.lower().replace('_', '').replace('-', '') in channel_title.lower().replace(' ', '').replace('_', '').replace('-', '')):
                    logger.info(f"Match found: {channel_title} -> {channel_id}")
                    return channel_id
            
            # If we found channels but no exact match, return the first one for the exact handle search
            if query == f"@{handle}" and search_response.get("items"):
                first_channel = search_response["items"][0]
                logger.info(f"Using first result: {first_channel['snippet']['title']} -> {first_channel['snippet']['channelId']}")
                return first_channel["snippet"]["channelId"]
        
        logger.warning(f"No channel found for handle: @{handle}")
        return None
        
    except Exception as e:
        logger.error(f"Error resolving handle @{handle} to channel ID: {e}")
        return None

# ===== RATE LIMITING DECORATOR =====

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
                    "youtube_dashboard.html",
                    user=session.get("user"),
                    error=f"Rate limit exceeded. Please wait {wait_time} seconds.",
                    results=[],
                )
            else:
                rate_limit_data[ip] = {
                    "count": 0,
                    "reset_time": now + timedelta(seconds=RATE_LIMIT_PERIOD),
                }

        rate_limit_data[ip]["count"] += 1
        return f(*args, **kwargs)
    return decorated_function

# ===== YOUTUBE API FUNCTIONS =====

def fetch_youtube_channel_videos(channel_url, max_videos=5):
    """Fetch recent videos from a YouTube channel URL."""
    try:
        logger.info(f"Starting analysis for URL: {channel_url}")
        
        # Extract channel ID from URL
        channel_id = extract_channel_id_from_url(channel_url)
        if not channel_id:
            logger.error(f"Could not extract channel ID from URL: {channel_url}")
            return []

        logger.info(f"Resolved channel ID: {channel_id}")
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

        # Get channel details
        channel_response = youtube.channels().list(
            part="snippet,contentDetails,statistics",
            id=channel_id
        ).execute()

        if not channel_response.get("items"):
            logger.error(f"Channel not found for ID: {channel_id}")
            return []

        channel_info = channel_response["items"][0]
        channel_title = channel_info["snippet"]["title"]
        uploads_playlist_id = channel_info["contentDetails"]["relatedPlaylists"]["uploads"]
        
        logger.info(f"Found channel: {channel_title}")
        logger.info(f"Fetching videos from uploads playlist: {uploads_playlist_id}")

        # Get recent videos from uploads playlist
        playlist_response = youtube.playlistItems().list(
            part="snippet",
            playlistId=uploads_playlist_id,
            maxResults=max_videos
        ).execute()

        if not playlist_response.get("items"):
            logger.warning(f"No videos found in channel: {channel_title}")
            return []

        logger.info(f"Found {len(playlist_response['items'])} videos")
        posts = []

        for playlist_item in playlist_response.get("items", []):
            video_id = playlist_item["snippet"]["resourceId"]["videoId"]
            video_title = playlist_item["snippet"]["title"]
            video_description = playlist_item["snippet"]["description"]
            video_date = playlist_item["snippet"]["publishedAt"][:10]
            channel_title = playlist_item["snippet"]["channelTitle"]
            
            logger.info(f"Processing video: {video_title}")
            
            # Get thumbnail
            thumbnails = playlist_item["snippet"]["thumbnails"]
            thumbnail_url = (
                thumbnails.get("high", {}).get("url") or
                thumbnails.get("medium", {}).get("url") or
                thumbnails.get("default", {}).get("url")
            )

            # Get video statistics
            video_stats_response = youtube.videos().list(
                part="statistics,contentDetails", 
                id=video_id
            ).execute()

            view_count = 0
            like_count = 0
            comment_count = 0
            duration = ""
            
            if video_stats_response["items"]:
                stats = video_stats_response["items"][0]["statistics"]
                content_details = video_stats_response["items"][0]["contentDetails"]
                
                view_count = int(stats.get("viewCount", 0))
                like_count = int(stats.get("likeCount", 0))
                comment_count = int(stats.get("commentCount", 0))
                
                # Parse duration
                duration_match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', content_details.get("duration", ""))
                if duration_match:
                    hours, minutes, seconds = duration_match.groups()
                    duration_parts = []
                    if hours: duration_parts.append(f"{hours}h")
                    if minutes: duration_parts.append(f"{minutes}m")
                    if seconds: duration_parts.append(f"{seconds}s")
                    duration = " ".join(duration_parts)

            # Calculate engagement rate
            engagement_rate = 0
            if view_count > 0:
                engagement_rate = ((like_count + comment_count) / view_count) * 100

            # Fetch comments
            comments_data = []
            sentiment_scores = []
            
            try:
                comments_response = youtube.commentThreads().list(
                    part="snippet",
                    videoId=video_id,
                    maxResults=20,
                    textFormat="plainText",
                    order="relevance"
                ).execute()
                
                for item in comments_response.get("items", []):
                    comment_text = item["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
                    comment_likes = item["snippet"]["topLevelComment"]["snippet"].get("likeCount", 0)
                    
                    sentiment_score = analyze_comment_sentiment(comment_text)
                    sentiment_scores.append(sentiment_score)
                    
                    comment_type = determine_comment_type(comment_text)
                    comments_data.append({
                        "text": comment_text,
                        "type": comment_type,
                        "likes": comment_likes,
                        "sentiment_score": sentiment_score
                    })
            except HttpError as e:
                if e.resp.status == 403:
                    logger.warning(f"Comments disabled for video {video_id}: {video_title}")
                else:
                    logger.error(f"Error fetching comments for video {video_id}: {e}")

            # Calculate average sentiment
            avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0.5

            posts.append({
                "title": video_title,
                "description": video_description[:200] + "..." if len(video_description) > 200 else video_description,
                "channel": channel_title,
                "comments": comments_data,
                "date": video_date,
                "published_at": datetime.strptime(video_date, "%Y-%m-%d"),
                "duration": duration,
                "view_count": view_count,
                "like_count": like_count,
                "comment_count": comment_count,
                "engagement": like_count,
                "engagement_rate": engagement_rate,
                "sentiment_score": avg_sentiment,
                "sentiment": get_sentiment_label(avg_sentiment),
                "thumbnail": thumbnail_url,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "video_id": video_id
            })

        logger.info(f"Successfully processed {len(posts)} videos")
        return posts

    except HttpError as e:
        logger.error(f"YouTube API error: {e}")
        if e.resp.status == 404:
            logger.error("Channel not found - check the URL")
        elif e.resp.status == 403:
            logger.error("API quota exceeded or access forbidden")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in YouTube fetch: {e}")
        return []

def get_analytics_summary(posts):
    """Generate analytics summary from posts data."""
    if not posts:
        return {
            "total_posts": 0,
            "views": 0,
            "total_comments": 0,
            "total_likes": 0,
            "engagement_rate": 0,
            "average_performance": 0,
            "sentiment_breakdown": {"positive": 0, "negative": 0, "neutral": 0, "suggestion": 0}
        }

    # Calculate totals
    total_views = sum(post.get("view_count", 0) for post in posts)
    total_likes = sum(post.get("like_count", 0) for post in posts)
    total_comments = sum(post.get("comment_count", 0) for post in posts)
    
    # Calculate average engagement rate
    engagement_rates = [post.get("engagement_rate", 0) for post in posts if post.get("engagement_rate", 0) > 0]
    avg_engagement_rate = sum(engagement_rates) / len(engagement_rates) if engagement_rates else 0

    # Sentiment analysis
    sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0, "suggestion": 0}
    for post in posts:
        for comment in post.get("comments", []):
            comment_type = comment.get("type", "neutral")
            if comment_type in sentiment_counts:
                sentiment_counts[comment_type] += 1

    # Calculate performance score
    max_views = max(post.get("view_count", 0) for post in posts) if posts else 1
    performance_scores = []
    for post in posts:
        views = post.get("view_count", 0)
        likes = post.get("like_count", 0)
        comments = post.get("comment_count", 0)
        
        view_score = (views / max_views) * 40 if max_views > 0 else 0
        engagement_score = ((likes + comments) / views) * 100 * 60 if views > 0 else 0
        performance_scores.append(min(view_score + engagement_score, 100))
    
    avg_performance = sum(performance_scores) / len(performance_scores) if performance_scores else 0

    return {
        "total_posts": len(posts),
        "views": total_views,
        "total_likes": total_likes,
        "total_comments": total_comments,
        "engagement_rate": avg_engagement_rate,
        "average_performance": avg_performance,
        "sentiment_breakdown": sentiment_counts,
    }

# ===== JINJA FILTERS =====

@app.template_filter('format_number')
def format_number(value):
    """Format numbers with commas."""
    if value is None:
        return '0'
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return str(value)

@app.template_filter('format_percentage')
def format_percentage(value):
    """Format percentage values."""
    if value is None:
        return '0.0'
    try:
        return f"{float(value):.1f}"
    except (ValueError, TypeError):
        return str(value)

# ===== SESSION MANAGEMENT =====

@app.before_request
def check_session_timeout():
    """Check session timeout and update activity."""
    if request.endpoint == 'static' or request.path == '/' or request.path == '/login':
        return

    if not session.get('logged_in'):
        return redirect('/')

    if "last_activity" not in session:
        session["last_activity"] = datetime.now().timestamp()
    else:
        last_activity = datetime.fromtimestamp(session["last_activity"])
        if datetime.now() - last_activity > timedelta(minutes=120):
            logger.info(f"Session timed out for user: {session.get('user')}")
            session.clear()
            return redirect('/')
        
    session["last_activity"] = datetime.now().timestamp()
    session.modified = True

# ===== ROUTES =====

@app.route("/")
def index():
    return render_template("modern_login.html")

@app.route("/login", methods=["POST"])
def login():
    username = request.form["username"]
    password = request.form["password"]

    if username == VALID_USER and password == VALID_PASS:
        session.permanent = True
        session["user"] = username
        session["logged_in"] = True
        session["last_activity"] = datetime.now().timestamp()
        logger.info(f"User {username} logged in successfully")
        return redirect("/dashboard")
    else:
        logger.warning(f"Failed login attempt for user: {username}")
        return render_template("modern_login.html", error="Invalid credentials")

@app.route("/dashboard")
def dashboard():
    if not session.get('logged_in'):
        logger.warning("Unauthorized access attempt to dashboard")
        return redirect("/")
    
    session["last_activity"] = datetime.now().timestamp()
    session.modified = True
    
    return render_template(
        "youtube_dashboard.html", 
        user=session["user"], 
        results=[], 
        logged_in=True
    )

@app.route("/analyze", methods=["POST"])
@rate_limit
def analyze():
    if "user" not in session:
        return redirect("/")

    try:
        channel_url = request.form["channel_url"]
        start_date_str = request.form["start_date"]
        end_date_str = request.form["end_date"]
        max_videos = min(int(request.form.get("max_videos", "5")), 20)

        # Validate YouTube URL
        if not any(domain in channel_url for domain in ['youtube.com', 'youtu.be']):
            return render_template(
                "youtube_dashboard.html",
                user=session["user"],
                error="Please enter a valid YouTube channel URL",
                results=[],
            )

        start = datetime.strptime(start_date_str, "%Y-%m-%d")
        end = datetime.strptime(end_date_str, "%Y-%m-%d")

        posts = fetch_youtube_channel_videos(channel_url, max_videos)

        if not posts:
            return render_template(
                "youtube_dashboard.html",
                user=session["user"],
                error="Could not fetch videos from this channel. Please check the URL and try again.",
                results=[],
            )

        # Filter posts by date
        filtered_posts = [
            p for p in posts 
            if start <= datetime.strptime(p["date"], "%Y-%m-%d") <= end
        ]

        analytics = get_analytics_summary(filtered_posts)
        logger.info(f"Analyzed {len(filtered_posts)} posts for channel: {channel_url}")

        return render_template(
            "youtube_dashboard.html",
            user=session["user"],
            results=filtered_posts,
            analytics=analytics,
            channel_url=channel_url,
            channel="youtube",
            start=start_date_str,
            end=end_date_str,
        )

    except (KeyError, ValueError) as e:
        logger.error(f"Error in analyze route: {str(e)}")
        return render_template(
            "youtube_dashboard.html",
            user=session["user"],
            error="Invalid input parameters",
            results=[],
        )
    except Exception as e:
        logger.error(f"Unexpected error in analyze route: {str(e)}")
        return render_template(
            "youtube_dashboard.html",
            user=session["user"],
            error="An unexpected error occurred",
            results=[],
        )

@app.route("/report", methods=["POST"])
def report():
    """Generate report from analysis data."""
    try:
        if "user" not in session:
            return redirect("/")

        if not request.form.get("data"):
            return "No data provided", 400

        raw_data = json.loads(request.form.get("data"))
        analytics_raw = json.loads(request.form.get("analytics", "{}"))
        keyword = request.form.get("keyword", "Unknown")
        
        if not isinstance(raw_data, list):
            return "Invalid data format", 400

        # Process data for report
        analytics_data = {
            "posts": raw_data,
            "summary": {
                "total_posts": len(raw_data),
                "total_engagement": sum(post.get("like_count", 0) for post in raw_data),
                "total_comments": sum(post.get("comment_count", 0) for post in raw_data),
                "total_views": sum(post.get("view_count", 0) for post in raw_data),
                "keyword": keyword,
                "sentiment_breakdown": defaultdict(int)
            },
            "insights": []
        }

        # Process sentiment data
        for post in raw_data:
            for comment in post.get("comments", []):
                sentiment = comment.get("type", "neutral")
                analytics_data["summary"]["sentiment_breakdown"][sentiment] += 1

        # Generate insights
        if raw_data:
            avg_engagement = analytics_data["summary"]["total_engagement"] / len(raw_data)
            if avg_engagement > 1000:
                analytics_data["insights"].append({
                    "type": "positive",
                    "message": "High engagement rate detected - content resonates well with audience"
                })

        logger.info(f"Generated report with {len(raw_data)} posts")
        
        return render_template(
            "report_template.html",
            data=analytics_data,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            user=session.get("user", "Anonymous")
        )

    except json.JSONDecodeError:
        return "Invalid JSON data", 400
    except Exception as e:
        logger.exception(f"Error generating report: {e}")
        return "Error generating report", 500

@app.route("/logout")
def logout():
    try:
        user = session.get("user", "unknown")
        session.clear()
        logger.info(f"User {user} logged out successfully")
        return redirect("/")
    except Exception as e:
        logger.error(f"Error during logout: {e}")
        session.clear()
        return redirect("/")

@app.route("/health")
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    })

# ===== ERROR HANDLERS =====

@app.errorhandler(Exception)
def handle_exception(e):
    logger.exception("Unhandled exception occurred")
    return jsonify({"error": str(e), "status": "error"}), 500

# ===== MAIN EXECUTION =====

if __name__ == "__main__":
    logger.info("Starting YouTube Analytics Flask application...")
    logger.info("Login credentials: username='eliberto', password='demo123'")
    logger.info("Application will be available at: http://localhost:5000")
    
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
        threaded=True
    )
