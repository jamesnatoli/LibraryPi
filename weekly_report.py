# weekly_report.py
import os
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

# --- CONFIGURATION ---
# Media Server Configuration
SERVER_URL = "http://127.0.0.1:8096"  # Replace with your Jellyfin/Emby URL
API_KEY = "055c826723a6469a95cd5fb05596d166"        # Replace with your actual admin token

# Email Server Configuration (SMTP)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "james.v.natoli@gmail.com"
SENDER_PASSWORD = "your-app-password" # Use an App Password, not your real password
RECEIVER_EMAIL = "james.v.natoli@gmail.com"

def get_weekly_content():
    """Fetches movies and episodes added in the last 7 days."""
    url = f"{SERVER_URL}/Items"
    
    # Calculate the timestamp for 7 days ago in ISO format
    time_threshold = (datetime.utcnow() - timedelta(days=7)).isoformat() + "Z"
    
    headers = {
        "Authorization": f'MediaBrowser Token="{API_KEY}"',
        "Accept": "application/json"
    }
    
    params = {
        "IncludeItemTypes": "Movie,Episode",
        "Recursive": "true",
        "Fields": "DateCreated,Overview",
        "SortBy": "DateCreated",
        "SortOrder": "Descending",
        "StartIndex": 0,
        "Limit": 20 # Limit to top 20 newest items
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        movies = []
        episodes = []
        
        for item in data.get("Items", []):
            # Verify the item was created within the last 7 days
            if item.get("DateCreated", "") >= time_threshold:
                if item.get("Type") == "Movie":
                    movies.append(item.get("Name"))
                elif item.get("Type") == "Episode":
                    # Formats as: Show Name - SeasonXEpisode - Episode Name
                    show_name = item.get("SeriesName", "Unknown Show")
                    ep_name = item.get("Name")
                    episodes.append(f"{show_name} - {ep_name}")
                    
        return movies, episodes
    except Exception as e:
        print(f"Error fetching data from media server: {e}")
        return [], []

def send_email(movies, episodes):
    """Formats and sends the HTML email newsletter."""
    if not movies and not episodes:
        print("No new content found this week. Email skipped.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"What's New This Week - {datetime.now().strftime('%B %d, %Y')}"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL

    # Build the HTML content
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
        <h2 style="color: #0078d4; border-bottom: 2px solid #0078d4; padding-bottom: 5px;">Your Weekly Media Digest</h2>
        <p>Here is a breakdown of all the fresh content added to the server over the last 7 days:</p>
    """

    if movies:
        html += '<h3 style="color: #e81123;">New Movies</h3><ul>'
        for movie in movies:
            html += f'<li><strong>{movie}</strong></li>'
        html += "</ul>"

    if episodes:
        html += '<h3 style="color: #107c41;">New TV Episodes</h3><ul>'
        for ep in episodes:
            html += f'<li>{ep}</li>'
        html += "</ul>"

    html += """
        <br>
        <p style="font-size: 0.8em; color: #777;">This is an automated system notification from your media server.</p>
    </body>
    </html>
    """

    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        print("Weekly email report sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")

if __name__ == "__main__":
    new_movies, new_episodes = get_weekly_content()
    send_email(new_movies, new_episodes)
