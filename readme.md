# 🎵 Lidarr Barcode Scanner Integration

This project provides a **web-based barcode scanner** connected to a **Flask backend** that integrates directly with **Lidarr**.
It allows users to scan the barcode of a CD or vinyl, retrieve album information from **MusicBrainz**, confirm the details, and automatically add the album to **Lidarr** while displaying real-time progress updates.

<img width="668" height="858" alt="image" src="https://github.com/user-attachments/assets/84a35133-73d2-42c8-a406-23db689385b3" />


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

### 1. Requirements

* Python 3.9+
* Flask
* Requests

Install dependencies:

```bash
pip install flask requests
```

### 2. Configure Lidarr API

Edit the following variables in your `app.py`:

```python
LIDARR_URL = "https://your-lidarr-url"
API_KEY = "your_lidarr_api_key"
```

Ensure that your Lidarr instance is reachable and the API key is valid.

### 3. Run the Application

Start Flask:

```bash
python app.py
```

Then open your browser and navigate to:

```
http://localhost:5083
```

### 4. Usage

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

---

Would you like me to extend this README with **troubleshooting tips** (e.g., camera permissions, Flask setup, or CORS issues)? It can make onboarding smoother for others using your tool.
