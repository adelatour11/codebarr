from flask import Flask, render_template, request, redirect, url_for, flash, Response, stream_with_context
import os
import signal
import requests
import time
import json
import threading
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("CODEBARR_SECRET_KEY", "your_secret_key_here")

# Your Lidarr config
LIDARR_URL = os.getenv("LIDARR_URL", "https://localhost:8686")
API_KEY = os.getenv("LIDARR_API_KEY", "yourkey")
HEADERS = {"X-Api-Key": API_KEY}

# Simple credentials (change as needed)
USERNAME = os.getenv("CODEBARR_USERNAME", "user")
PASSWORD = os.getenv("CODEBARR_PASSWORD", "password")



LIDARR_DEFAULTS = {
    "rootFolderPath": os.getenv("LIDARR_ROOT_FOLDER_PATH", "/music"),
    "qualityProfileId": int(os.getenv("LIDARR_QUALITY_PROFILE", 2)),
    "metadataProfileId": int(os.getenv("LIDARR_METADATA_PROFILE", 9)),
    "monitored": os.getenv("LIDARR_ARTIST_MONITORED", "False").lower() in {"true", "t", "1", "yes"},
    "monitorNewItems": os.getenv("LIDARR_MONITOR_NEW_ITEMS", "none"),
    "addOptions": {
        "searchForMissingAlbums": os.getenv("LIDARR_SEARCH_ON_ADD", "False").lower() in {"true", "t", "1", "yes"}
    }
}


# Check username/password
def check_auth(username, password):
    return username == USERNAME and password == PASSWORD

# Return 401 response to trigger browser login popup
def authenticate():
    return Response(
        "Authentication required", 401,
        {"WWW-Authenticate": 'Basic realm="Codebarr"'}
    )

# Decorator to protect routes
def requires_auth(f):
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    decorated.__name__ = f.__name__
    return decorated




def check_lidarr_config():
    endpoints = {
        "Root folders": "/api/v1/rootfolder",
        "Quality profiles": "/api/v1/qualityprofile",
        "Metadata profiles": "/api/v1/metadataprofile"
    }
    for name, endpoint in endpoints.items():
        url = f"{LIDARR_URL}{endpoint}"
        try:
            r = requests.get(url, headers=HEADERS)
            if r.status_code != 200:
                flash(f"❌ {name} request failed with {r.status_code}: {r.text}", "error")
        except Exception as e:
            flash(f"⚠️ Error checking {name}: {e}", "error")

def get_release_from_barcode(barcode):
    url = f"https://musicbrainz.org/ws/2/release/?query=barcode:{barcode}&fmt=json"
    r = requests.get(url)
    r.raise_for_status()
    data = r.json()
    if not data.get('releases'):
        raise Exception(f"No release found for barcode {barcode}")
    return data['releases'][0]

def get_album_from_barcode(barcode):
    """
    Fetch the exact release from MusicBrainz using the barcode.
    Returns: artist_name, artist_mbid, album_title, release_group_mbid, release_mbid
    """
    url = f"https://musicbrainz.org/ws/2/release/?query=barcode:{barcode}&fmt=json"
    r = requests.get(url)
    r.raise_for_status()
    data = r.json()

    if not data.get('releases'):
        raise Exception(f"No release found for barcode {barcode}")

    # Take the first exact match (should match the barcode)
    release = data['releases'][0]
    release_group_mbid = release['release-group']['id']
    release_mbid = release['id']  # <-- exact release ID
    album_title = release['title']

    artist_info = release['artist-credit'][0]
    artist_name = artist_info['name']
    artist_mbid = artist_info['artist']['id']

    return artist_name, artist_mbid, album_title, release_group_mbid, release_mbid


def find_or_create_artist(artist_name, artist_mbid):
    existing = requests.get(f"{LIDARR_URL}/api/v1/artist", headers=HEADERS).json()
    for artist in existing:
        if artist['foreignArtistId'] == artist_mbid:
            flash(f"✅ Artist '{artist_name}' already exists.", "info")
            return artist['id']
    payload = {
        "artistName": artist_name,
        "foreignArtistId": artist_mbid,
        "rootFolderPath": "/music",
        **LIDARR_DEFAULTS
}
    r = requests.post(f"{LIDARR_URL}/api/v1/artist", headers=HEADERS, json=payload)
    r.raise_for_status()
    data = r.json()
    flash(f"✅ Artist '{artist_name}' created (no albums monitored).", "info")
    return data["id"]

def update_or_add_album(artist_id, release_group_mbid, release_mbid, album_title):
    """
    Add or update album in Lidarr, monitoring the exact release.
    """
    # First check if this release already exists
    albums = requests.get(f"{LIDARR_URL}/api/v1/album?artistId={artist_id}", headers=HEADERS).json()
    for album in albums:
        if album.get('foreignAlbumId') == release_group_mbid:
            # Update monitored to True
            album_data = requests.get(f"{LIDARR_URL}/api/v1/album/{album['id']}", headers=HEADERS).json()
            album_data['monitored'] = True
            # Set exact release
            album_data['foreignReleaseId'] = release_mbid
            r = requests.put(f"{LIDARR_URL}/api/v1/album/{album['id']}", headers=HEADERS, json=album_data)
            r.raise_for_status()
            flash(f"✅ Album '{album_title}' is now monitored (exact release).", "success")
            return r.json()

    # If album not found, create it
    artist_data = requests.get(f"{LIDARR_URL}/api/v1/artist/{artist_id}", headers=HEADERS).json()
    payload = {
        "artistId": artist_id,
        "artist": artist_data,
        "foreignAlbumId": release_group_mbid,
        "foreignReleaseId": release_mbid,  # <-- exact release
        "title": album_title,
        "monitored": True,
        "addOptions": {"searchForNewAlbum": True}
    }
    r = requests.post(f"{LIDARR_URL}/api/v1/album", headers=HEADERS, json=payload)
    r.raise_for_status()
    flash(f"✅ Album '{album_title}' added and monitored (exact release).", "success")
    return r.json()


def monitor_exact_release(artist_id, release_group_mbid, release_mbid, album_title):
    """
    Add album if missing, then monitor the exact release after Lidarr fetches releases.
    """
    # 1️⃣ Check if album exists
    albums = requests.get(f"{LIDARR_URL}/api/v1/album?artistId={artist_id}", headers=HEADERS).json()
    album_id = None
    for album in albums:
        if album.get('foreignAlbumId') == release_group_mbid:
            album_id = album['id']
            break

    # 2️⃣ Add album if missing
    if not album_id:
        artist_data = requests.get(f"{LIDARR_URL}/api/v1/artist/{artist_id}", headers=HEADERS).json()
        payload = {
            "artistId": artist_id,
            "artist": artist_data,
            "foreignAlbumId": release_group_mbid,
            "title": album_title,
            "monitored": True,
            "addOptions": {"searchForNewAlbum": True}
        }
        album_resp = requests.post(f"{LIDARR_URL}/api/v1/album", headers=HEADERS, json=payload)
        album_resp.raise_for_status()
        album_id = album_resp.json()["id"]

    # 3️⃣ Wait for Lidarr to fetch releases (poll until the release appears)
    timeout = 30  # seconds
    interval = 3
    elapsed = 0
    while elapsed < timeout:
        album_data = requests.get(f"{LIDARR_URL}/api/v1/album/{album_id}", headers=HEADERS).json()
        releases = album_data.get("releases", [])
        target_release = next((r for r in releases if r["id"] == release_mbid), None)
        if target_release:
            break
        time.sleep(interval)
        elapsed += interval
    else:
        raise Exception("❌ Exact release not found in Lidarr after waiting")

    # 4️⃣ Mark the exact release as monitored
    for r in releases:
        r["monitored"] = r["id"] == release_mbid  # only monitor target release

    album_data["monitored"] = True
    album_data["releases"] = releases

    update_resp = requests.put(f"{LIDARR_URL}/api/v1/album/{album_id}", headers=HEADERS, json=album_data)
    update_resp.raise_for_status()
    return update_resp.json()


def add_album_with_exact_release(barcode):
    # --- 1️⃣ Get release info from MusicBrainz ---
    r = requests.get(f"https://musicbrainz.org/ws/2/release/?query=barcode:{barcode}&fmt=json")
    r.raise_for_status()
    data = r.json()
    if not data.get("releases"):
        raise Exception(f"No release found for barcode {barcode}")
    
    release = data["releases"][0]
    release_mbid = release["id"]                     # exact release MBID
    release_group_mbid = release["release-group"]["id"]
    album_title = release["title"]
    artist_credit = release["artist-credit"][0]
    artist_name = artist_credit["name"]
    artist_mbid = artist_credit["artist"]["id"]

    # --- 2️⃣ Find or create artist in Lidarr ---
    artists = requests.get(f"{LIDARR_URL}/api/v1/artist", headers=HEADERS).json()
    artist_id = None
    for a in artists:
        if a.get("foreignArtistId") == artist_mbid:
            artist_id = a["id"]
            break
    if not artist_id:
        payload = {
            "artistName": artist_name,
            "foreignArtistId": artist_mbid,
            "rootFolderPath": "/music",
            "qualityProfileId": 2,
            "metadataProfileId": 9,
            "monitored": False,
            "monitorNewItems": "none",
            "addOptions": {"searchForMissingAlbums": False}
        }
        resp = requests.post(f"{LIDARR_URL}/api/v1/artist", headers=HEADERS, json=payload)
        resp.raise_for_status()
        artist_id = resp.json()["id"]

    # --- 3️⃣ Check if album exists ---
    albums = requests.get(f"{LIDARR_URL}/api/v1/album?artistId={artist_id}", headers=HEADERS).json()
    album_id = None
    for alb in albums:
        if alb.get("foreignAlbumId") == release_group_mbid:
            album_id = alb["id"]
            break

    # --- 4️⃣ Add or update album ---
    if not album_id:
        # Album does not exist → create it with exact release
        artist_data = requests.get(f"{LIDARR_URL}/api/v1/artist/{artist_id}", headers=HEADERS).json()
        payload = {
            "artistId": artist_id,
            "artist": artist_data,
            "foreignAlbumId": release_group_mbid,
            "title": album_title,
            "monitored": True,
            "addOptions": {"searchForNewAlbum": True},
            "releases": [{"id": release_mbid, "monitored": True}]
        }
        album_resp = requests.post(f"{LIDARR_URL}/api/v1/album", headers=HEADERS, json=payload)
        album_resp.raise_for_status()
        album_id = album_resp.json()["id"]
    else:
        # Album exists → monitor exact release
        album_data = requests.get(f"{LIDARR_URL}/api/v1/album/{album_id}", headers=HEADERS).json()
        album_data["monitored"] = True
        album_data["releases"] = [{"id": release_mbid, "monitored": True}]
        update_resp = requests.put(f"{LIDARR_URL}/api/v1/album/{album_id}", headers=HEADERS, json=album_data)
        update_resp.raise_for_status()

    # --- 5️⃣ Ensure release is monitored ---
    release_payload = {
        "albumId": album_id,
        "releaseId": release_mbid,
        "monitored": True
    }
    r = requests.post(f"{LIDARR_URL}/api/v1/release", headers=HEADERS, json=release_payload)
    r.raise_for_status()

    return {
        "artist": artist_name,
        "album": album_title,
        "release_mbid": release_mbid,
        "album_id": album_id
    }




def update_album_release(album_id, artist_id, album_title, release_mbid):
    # Fetch current album info
    r = requests.get(f"{LIDARR_URL}/api/v1/album/{album_id}", headers=HEADERS)
    r.raise_for_status()
    album = r.json()

    # Prepare payload
    payload = {
        "id": album['id'],
        "artistId": artist_id,
        "title": album['title'],
        "monitored": True,
        "releases": [{"id": release_mbid, "monitored": True}]
    }

    # Send update
    r = requests.put(f"{LIDARR_URL}/api/v1/album/{album_id}", headers=HEADERS, json=payload)
    r.raise_for_status()
    return r.json()

def process_barcode(barcode):
    try:
        # Step 1: Fetch exact release from MusicBrainz
        yield json.dumps({"status": " Processing barcode...", "progress": 5}) + "\n\n"
        release = get_release_from_barcode(barcode)
        release_mbid = release['id']  # exact release MBID
        release_group_mbid = release['release-group']['id']
        album_title = release['title']
        artist_info = release['artist-credit'][0]
        artist_name = artist_info['name']
        artist_mbid = artist_info['artist']['id']
        yield json.dumps({"status": f" Found release '{album_title}' by {artist_name}", "progress": 15}) + "\n\n"

        # Step 2: Ensure artist exists
        yield json.dumps({"status": f" Checking artist '{artist_name}'...", "progress": 30}) + "\n\n"
        artist_id = find_or_create_artist(artist_name, artist_mbid)

        # Step 3: Ensure album exists
        albums = requests.get(f"{LIDARR_URL}/api/v1/album?artistId={artist_id}", headers=HEADERS).json()
        album_id = None
        for alb in albums:
            if alb.get("foreignAlbumId") == release_group_mbid:
                album_id = alb['id']
                break

        if not album_id:
            # Create album
            artist_data = requests.get(f"{LIDARR_URL}/api/v1/artist/{artist_id}", headers=HEADERS).json()
            payload = {
                "artistId": artist_id,
                "artist": artist_data,
                "foreignAlbumId": release_group_mbid,
                "title": album_title,
                "monitored": True,
                "addOptions": {"searchForNewAlbum": True}
            }
            album_resp = requests.post(f"{LIDARR_URL}/api/v1/album", headers=HEADERS, json=payload)
            album_resp.raise_for_status()
            album_id = album_resp.json()["id"]
            yield json.dumps({"status": f" Album '{album_title}' created in Lidarr.", "progress": 60}) + "\n\n"
        else:
            # Update album monitored flag
            album_data = requests.get(f"{LIDARR_URL}/api/v1/album/{album_id}", headers=HEADERS).json()
            album_data['monitored'] = True
            update_resp = requests.put(f"{LIDARR_URL}/api/v1/album/{album_id}", headers=HEADERS, json=album_data)
            update_resp.raise_for_status()
            yield json.dumps({"status": f" Album '{album_title}' already exists. Marked as monitored.", "progress": 60}) + "\n\n"

            # Step 4: Wait for Lidarr to fetch releases and monitor the exact one
            timeout = 60  # total seconds to wait
            interval = 3  # seconds between polls
            elapsed = 0
            matched_release = None

            while elapsed < timeout:
                album_data = requests.get(f"{LIDARR_URL}/api/v1/album/{album_id}", headers=HEADERS).json()
                releases = album_data.get("releases", [])
                matched_release = next((r for r in releases if r.get("foreignReleaseId") == release_mbid), None)
                if matched_release:
                    break
                time.sleep(interval)
                elapsed += interval
            else:
                raise Exception("❌ Exact release not found in Lidarr after waiting")

            # Only monitor the release matching the barcode
            for r in releases:
                r["monitored"] = r.get("foreignReleaseId") == release_mbid

            album_data["monitored"] = True
            album_data["releases"] = releases

            update_resp = requests.put(f"{LIDARR_URL}/api/v1/album/{album_id}", headers=HEADERS, json=album_data)
            update_resp.raise_for_status()
            yield json.dumps({"status": f"✅ Album '{album_title}' now monitoring exact release!", "progress": 100}) + "\n\n"

    except Exception as e:
        yield json.dumps({"status": f"❌ Error: {str(e)}", "progress": 100}) + "\n\n"


@app.route("/")
@requires_auth
def index():
    return render_template("index.html")

@app.route("/submit", methods=["POST"])
def submit():
    barcode = request.form.get("barcode")
    print("Received barcode:", barcode)  # Debug line
    if not barcode:
        return Response("error: No barcode provided", status=400, mimetype="text/plain")
    return Response(stream_with_context(process_barcode(barcode)), mimetype="text/event-stream")
    
    

@app.route("/shutdown", methods=["POST"])
def shutdown():
    def delayed_shutdown():
        time.sleep(1)
        os.kill(os.getpid(), signal.SIGTERM)

    threading.Thread(target=delayed_shutdown).start()
    # return a small HTML page that refreshes before DSM intercepts
    return Response(
        "Codebarr is shutting down...",
        mimetype="text/html",
    )

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5083)