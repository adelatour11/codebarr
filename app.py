from flask import Flask, render_template, request, redirect, url_for, flash, Response, stream_with_context
import requests
import time
import json


app = Flask(__name__)
app.secret_key = "your_secret_key_here"

# Your Lidarr config
LIDARR_URL = "XXXX"
API_KEY = "XXXX"
HEADERS = {"X-Api-Key": API_KEY}

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
    release = get_release_from_barcode(barcode)
    release_group_mbid = release['release-group']['id']
    album_title = release['title']
    artist_name = release['artist-credit'][0]['name']
    artist_mbid = release['artist-credit'][0]['artist']['id']
    return artist_name, artist_mbid, album_title, release_group_mbid

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
        "qualityProfileId": 2,
        "metadataProfileId": 9,
        "monitored": True,  # Artist is not monitored
        "monitorNewItems": "none",  # No new albums are monitored
        "addOptions": {"searchForMissingAlbums": False}
    }
    r = requests.post(f"{LIDARR_URL}/api/v1/artist", headers=HEADERS, json=payload)
    r.raise_for_status()
    data = r.json()
    flash(f"✅ Artist '{artist_name}' created (no albums monitored).", "info")
    return data["id"]

def update_or_add_album(artist_id, release_group_mbid, album_title):
    albums_url = f"{LIDARR_URL}/api/v1/album?artistId={artist_id}"
    albums_resp = requests.get(albums_url, headers=HEADERS)
    albums_resp.raise_for_status()
    albums = albums_resp.json()
    for album in albums:
        if album['foreignAlbumId'] == release_group_mbid:
            album_url = f"{LIDARR_URL}/api/v1/album/{album['id']}"
            album_resp = requests.get(album_url, headers=HEADERS)
            album_resp.raise_for_status()
            album_data = album_resp.json()
            album_data['monitored'] = True
            update_url = f"{LIDARR_URL}/api/v1/album/{album['id']}"
            update_resp = requests.put(update_url, headers=HEADERS, json=album_data)
            update_resp.raise_for_status()
            flash(f"✅ Album '{album_title}' is now monitored.", "success")
            return album_data
    artist_url = f"{LIDARR_URL}/api/v1/artist/{artist_id}"
    artist_resp = requests.get(artist_url, headers=HEADERS)
    artist_resp.raise_for_status()
    artist_data = artist_resp.json()
    payload = {
        "artistId": artist_id,
        "artist": artist_data,
        "foreignAlbumId": release_group_mbid,
        "title": album_title,
        "monitored": True,  # Only this album is monitored
        "addOptions": {"searchForNewAlbum": True}
    }
    r = requests.post(f"{LIDARR_URL}/api/v1/album", headers=HEADERS, json=payload)
    r.raise_for_status()
    flash(f"✅ Album '{album_title}' added and monitored.", "success")
    return r.json()

def process_barcode(barcode):
    try:
        # Step 1: Processing barcode
        yield json.dumps({"status": "🔍 Processing barcode...", "progress": 5}) + "\n\n"
        artist_name, artist_mbid, album_title, release_group_mbid = get_album_from_barcode(barcode)
        yield json.dumps({"status": f"🎵 Album found: {album_title} by {artist_name}", "progress": 15}) + "\n\n"

        # Step 2: Checking artist
        yield json.dumps({"status": f"🔎 Checking artist '{artist_name}'...", "progress": 30}) + "\n\n"
        artist_id = find_or_create_artist(artist_name, artist_mbid)

        # Step 3: Waiting for Lidarr
        yield json.dumps({"status": "🕒 Waiting 30 seconds for Lidarr to process the artist...", "progress": 50}) + "\n\n"
        time.sleep(30)

        # Step 4: Adding/monitoring album
        yield json.dumps({"status": f"💿 Adding/monitoring album '{album_title}'...", "progress": 80}) + "\n\n"
        album_info = update_or_add_album(artist_id, release_group_mbid, album_title)

        # Step 5: Done
        yield json.dumps({"status": "✅ Album added and monitored!", "progress": 100}) + "\n\n"
    except Exception as e:
        yield json.dumps({"status": f"❌ Error: {str(e)}", "progress": 100}) + "\n\n"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/submit", methods=["POST"])
def submit():
    barcode = request.form.get("barcode")
    print("Received barcode:", barcode)  # Debug line
    if not barcode:
        return Response("error: No barcode provided", status=400, mimetype="text/plain")
    return Response(stream_with_context(process_barcode(barcode)), mimetype="text/event-stream")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
