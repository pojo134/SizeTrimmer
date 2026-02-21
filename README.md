# SizeTrimmer

SizeTrimmer is a lightweight, hardware-accelerated media conversion service designed to automate compressing video and audio files using FFmpeg, equipped with a sleek realtime web dashboard.

## Deployment via Docker (Recommended for Media Servers)

The easiest way to run SizeTrimmer on a dedicated media server (like TrueNAS, Unraid, or an Ubuntu Server) is through Docker.

### 1. Transfer the Files
Copy this entire project folder to your target media server. The required files are:
- `Dockerfile`
- `docker-compose.yml`
- `requirements.txt`
- `sizetrimmer.py`
- `db.py`
- `web/` (directory)

### 2. Configure Docker Compose
Open `docker-compose.yml` on your server and customize the path on the left side of the volume mount to point to your media library:

```yaml
    volumes:
      # Change /path/to/your/media to your server's actual media directory
      - /path/to/your/media:/library
```

*Note: If your media server has an Nvidia GPU, ensure the `deploy` block at the bottom of the config is uncommented so the container can access the hardware encoder.*

### 3. Build and Run
Open a terminal on your media server, navigate to the folder containing these files, and run:
   ```bash
   docker compose up -d --build
   ```

Docker will automatically download the Python runtime, install FFmpeg cleanly inside the container, install the dependencies, and start the web dashboard!

Access the dashboard at `http://<YOUR_SERVER_IP>:8000`.

## Local Desktop Installation

If you prefer to run it directly on a desktop PC without Docker:

### Windows
1. Open PowerShell as Administrator in this folder.
2. Run: `powershell -ExecutionPolicy Bypass -File setup.ps1`
3. Once complete, run: `.\.venv\Scripts\Activate.ps1` followed by `python sizetrimmer.py`

### Linux
1. Open a terminal in this folder.
2. Run: `chmod +x setup.sh && ./setup.sh`
3. Once complete, run: `source .venv/bin/activate` followed by `python3 sizetrimmer.py`
