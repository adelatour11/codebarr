# 🎵 Lidarr Barcode Scanner Integration

This project provides a **web-based barcode scanner** connected to a **Flask backend** that integrates directly with **Lidarr**.
It allows users to scan the barcode of a CD or vinyl, retrieve album information from **MusicBrainz**, confirm the details, and automatically add the album to **Lidarr** while displaying real-time progress updates.

<p align="center"><img width="75%"  alt="image" src="https://github.com/user-attachments/assets/edf00538-6d13-43f2-b4c8-cacd57123b1f" />


## 🚀 Features

### 🔍 Barcode Scanning

* Uses **QuaggaJS** for live camera scanning (EAN-13 barcodes).
* Works with any webcam or mobile device camera.
* Automatically detects valid barcodes and fetches album info.
* Visual scanning guides help align the barcode correctly.

### 🎶 Album Lookup (MusicBrainz)

* Once a barcode is detected, the app retrieves:

  * Artist name
  * Album title
  * Release information from the **MusicBrainz API**
* Displays the album and artist name for user confirmation.

### ➕ Add to Lidarr

* After confirming the album, the user can click **“Add Album to Lidarr”**.
* The Flask backend communicates with your **Lidarr API**:

  * Verifies if the artist already exists.
  * Creates the artist in Lidarr if missing.
  * Adds and monitors the album automatically.
* A live **progress bar** shows the operation stages:

  1. Processing barcode
  2. Retrieving album data
  3. Checking/creating artist
  4. Adding/monitoring album

### 💡 Utility Controls

* **Reset button:** Clears the scanner, progress bar, and album info for a new scan.
* **Start/Stop scanner:** Full control of scanning state.

### 🧩 UI Highlights

* Clean Lidarr-inspired dark theme.
* Responsive layout compatible with desktop and mobile browsers.
* Inline progress updates via **Server-Sent Events (SSE)** for smooth feedback.

---

## ⚙️ Setup & Configuration

### 1. Download Codebarr

#### Using Docker

Download the latest `compose.yaml` and `.env.example`:

```bash
wget -O compose.yaml https://github.com/adelatour11/codebarr/raw/refs/heads/main/compose.yaml
wget -O .env https://github.com/adelatour11/codebarr/raw/refs/heads/main/.env.example
```

#### From Source

##### Requirements

* Python 3.9+
* Git

Clone the repository and install dependencies:

```bash
git clone https://github.com/adelatour11/codebarr
cd codebarr
pip install -r requirements.txt
```

Copy the `.env.example` file:

```bash
cp .env.example .env
```

### 2. Configure Lidarr API

Edit the following variables in your `.env`:

```ini
CODEBARR_SECRET_KEY=your_secret_key_here    # Flask secret key (randomly-generated, long string)
CODEBARR_USERNAME=user                      # Change as needed
CODEBARR_PASSWORD=password                  # Change as needed
LIDARR_URL=https://localhost:8686           # Lidarr URL
LIDARR_API_KEY=yourkey                      # Lidarr API key
LIDARR_ROOT_FOLDER_PATH=/music              # Music root folder
LIDARR_QUALITY_PROFILE=2                    # Quality profile ID
LIDARR_METADATA_PROFILE=9                   # Metadata profile ID
LIDARR_ARTIST_MONITORED=false               # Monitor artist/album by default
LIDARR_MONITOR_NEW_ITEMS=none               # How new releases are handled (options: all, none, new)
LIDARR_SEARCH_ON_ADD=false                  # Auto-search missing albums
```

Ensure that your Lidarr instance is reachable and the API key is valid.

### 3. Run the Application

Start Codebarr using Docker Compose:

```bash
docker compose pull
docker compose up -d
```

Or using Python (from source):

```bash
python app.py
```

Then open your browser and navigate to:

```
http://localhost:5083
```

### Usage

1. Click **Start Scanner**.
2. Point your camera at a CD barcode.
3. Confirm the album details from MusicBrainz.
4. Click **Add Album to Lidarr**.
5. Watch progress updates until completion.


📱 Mobile Camera Access

If you want to use your phone camera to scan barcodes:

⚠️ Browsers only allow camera access on secure (HTTPS) connections or localhost.

---

## 🧠 Architecture Overview

**Frontend:**

* HTML + CSS + JavaScript (QuaggaJS)
* Fetches MusicBrainz data and displays results
* Sends album addition requests to Flask via `POST /submit`
* Listens to server-sent progress events for updates

**Backend (Flask):**

* Handles barcode submission
* Integrates with:

  * MusicBrainz API (for metadata)
  * Lidarr API (for artist and album management)
* Streams progress updates to the browser in real time

---

## 📸 Example Workflow

1. Scan barcode → “💿 CD Barcode detected: 602438979812”
2. Fetch MusicBrainz info → “🎵 Album found: *Ghost Stories* by *Coldplay*”
3. Confirm addition → “✅ Artist created and album added to Lidarr”

---

## 🧰 Optional Enhancements

* Display album cover from MusicBrainz or Cover Art Archive.
* Support manual input for fallback barcodes.
* Add multiple Lidarr root folders or quality profiles as configuration options.

---

## 🛠️ License

This project is distributed under the **MIT License**.
