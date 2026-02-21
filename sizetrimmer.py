import os
import json
import subprocess
import time
import logging
import shlex
import threading
import queue
import uvicorn
import psutil
import re
from fastapi import FastAPI, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from db import init_db, log_conversion, get_history, get_stats

# --- Configuration ---
DATA_DIR = os.environ.get("DATA_DIR", ".")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
LOG_FILE = os.path.join(DATA_DIR, "sizetrimmer.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

VIDEO_EXTS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
AUDIO_EXTS = {'.mp3', '.flac', '.wav', '.m4a', '.ogg', '.aac'}

conversion_queue = queue.Queue()
queued_files = set()
queue_lock = threading.Lock()
current_converting = {} # Store what's currently being converted

# Flag to signal background thread to reload config
config_updated_event = threading.Event()

# --- Web UI Setup ---
app = FastAPI(title="SizeTrimmer Media Service")

# We will mount static files once we create them
os.makedirs("web/static", exist_ok=True)

def load_config():
    default_config = {
        "parent_directory": "",
        "tv_show_keywords": ["tv", "shows", "season"],
        "movie_keywords": ["movies", "films"],
        "music_keywords": ["music", "audio"],
        "video_codec": "libx265",
        "ffmpeg_preset": "medium",
        "ffmpeg_crf": 26,
        "audio_codec_video": "aac",
        "audio_codec_music": "libmp3lame",
        "music_bitrate": "192k",
        "tv_resolution": "1280x720",
        "movie_resolution": "1920x1080",
        "dry_run": True
    }
    
    if not os.path.exists(CONFIG_FILE):
        return default_config
        
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            
        # Merge missing defaults
        for key, value in default_config.items():
            if key not in config:
                config[key] = value
                
        return config
    except Exception:
        return default_config

def save_config(new_config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(new_config, f, indent=4)
    return True

# --- API Endpoints ---
@app.get("/")
def serve_dashboard():
    return FileResponse("web/index.html")

@app.get("/api/stats")
def api_stats():
    sys_cpu = psutil.cpu_percent(interval=None)
    mem_info = psutil.virtual_memory()
    
    # Disk Usage
    disk_usage = 0
    config = load_config()
    parent_dir = config.get("parent_directory")
    if parent_dir and os.path.exists(parent_dir):
        try:
            disk_info = psutil.disk_usage(parent_dir)
            disk_usage = disk_info.percent
        except Exception:
            pass

    # GPU Usage
    gpu_usage = 0
    try:
        # Check if nvidia-smi is available
        nvidia_smi_output = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"], 
            text=True, stderr=subprocess.DEVNULL
        )
        # Handle multiple GPUs by taking the average or max; here we take the first one or average
        gpu_lines = [int(line.strip()) for line in nvidia_smi_output.strip().split('\n') if line.strip().isdigit()]
        if gpu_lines:
            gpu_usage = max(gpu_lines) # or sum(gpu_lines)/len(gpu_lines)
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass # No NVIDIA GPU or driver installed
    
    db_stats = get_stats()
    
    return {
        "cpu_usage": sys_cpu,
        "memory_usage": mem_info.percent,
        "gpu_usage": gpu_usage,
        "disk_usage": disk_usage,
        "queue_size": conversion_queue.qsize(),
        "currently_converting": list(current_converting.values()),
        "dry_run": config.get("dry_run", True),
        "total_saved_bytes": db_stats.get("space_saved_bytes", 0),
        "total_conversions": db_stats.get("success_count", 0) + db_stats.get("error_count", 0),
        "successful_conversions": db_stats.get("success_count", 0),
        "failed_conversions": db_stats.get("error_count", 0),
    }
    


@app.get("/api/history")
def api_history():
    return get_history()

@app.get("/api/config")
def api_get_config():
    return load_config()

@app.post("/api/config")
def api_set_config(new_config: dict):
    save_config(new_config)
    config_updated_event.set()
    return {"status": "success"}

@app.get("/api/folders")
def api_get_folders(path: str = None):
    try:
        if not path or path.strip() == "":
            path = os.path.expanduser("~")
            
        real_path = os.path.abspath(path)
        if not os.path.isdir(real_path):
            return {"error": "Invalid directory", "path": path}
            
        folders = []
        for item in os.listdir(real_path):
            item_path = os.path.join(real_path, item)
            if os.path.isdir(item_path) and not item.startswith('.'):
                folders.append({"name": item, "path": item_path})
                
        # Sort folders alphabetically
        folders.sort(key=lambda x: x["name"].lower())
        
        parent = os.path.dirname(real_path)
        if parent == real_path:
            parent = None
            
        return {
            "current_path": real_path,
            "parent_path": parent,
            "folders": folders
        }
    except Exception as e:
        return {"error": str(e), "path": path}

app.mount("/static", StaticFiles(directory="web/static"), name="static")

# --- Core Logic ---
def get_media_type(file_path, config):
    ext = os.path.splitext(file_path)[1].lower()
    path_lower = file_path.lower()
    
    for kw in config.get("music_keywords", ["music", "audio"]):
        if f"/{kw}/" in path_lower or f"\\{kw}\\" in path_lower:
            if ext in AUDIO_EXTS: return 'audio'
    
    if ext in AUDIO_EXTS: return 'audio'

    if ext in VIDEO_EXTS:
        for kw in config.get("tv_show_keywords", ["tv", "shows", "season"]):
            if f"/{kw}/" in path_lower or f"\\{kw}\\" in path_lower: return 'tv'
        for kw in config.get("movie_keywords", ["movies", "films"]):
            if f"/{kw}/" in path_lower or f"\\{kw}\\" in path_lower: return 'movie'
        return 'movie'
    return None

def is_file_stable(file_path, wait_time=5):
    try:
        size1 = os.path.getsize(file_path)
        time.sleep(wait_time)
        size2 = os.path.getsize(file_path)
        return size1 == size2
    except OSError:
        return False

def get_ffprobe_info(file_path, media_type):
    try:
        if media_type == 'audio':
            cmd = ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=codec_name", "-of", "json", file_path]
        else:
            cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name,width,height", "-of", "json", file_path]
        
        output = subprocess.check_output(cmd, text=True)
        data = json.loads(output)
        
        if not data.get("streams"): return None, None, None
            
        stream = data["streams"][0]
        return stream.get("codec_name"), stream.get("width"), stream.get("height")
    except Exception:
        return None, None, None

def is_already_optimized(file_path, media_type, config):
    codec, width, height = get_ffprobe_info(file_path, media_type)
    if not codec: return False

    if media_type == 'audio':
        desired_codec = config.get("audio_codec_music", "libmp3lame")
        if desired_codec == "libmp3lame" and codec == "mp3": return True
        return codec == desired_codec
    else:
        desired_codec = config.get("video_codec", "libx265")
        is_hevc = (codec in ['hevc', 'h265']) and (desired_codec in ['libx265', 'hevc'])
        
        target_res = config.get("tv_resolution", "1280x720") if media_type == 'tv' else config.get("movie_resolution", "1920x1080")
        target_width = int(target_res.split('x')[0])
        
        is_small_enough = True
        if width and target_width and width > target_width:
            is_small_enough = False
                
        is_mkv = file_path.lower().endswith('.mkv')
        return is_hevc and is_small_enough and is_mkv

def get_media_duration(file_path):
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(result.stdout.strip())
    except Exception:
        return 0.0

def parse_ffmpeg_time(time_str):
    parts = time_str.split(':')
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    return 0.0

def convert_media(file_path, media_type, config):
    if not os.path.exists(file_path): return

    while not is_file_stable(file_path):
        time.sleep(10)

    if is_already_optimized(file_path, media_type, config):
        return True

    file_name = os.path.basename(file_path)
    current_converting[file_path] = {"file": file_name, "type": media_type, "progress": 0}
    
    # Store initial size
    try:
        orig_size = os.path.getsize(file_path)
    except Exception:
        orig_size = 0

    base_name, _ = os.path.splitext(file_path)
    cmd = ["ffmpeg", "-y", "-i", file_path]
    
    if media_type == 'audio':
        out_ext = ".mp3"
        tmp_file = f"{base_name}.tmp{out_ext}"
        cmd.extend(["-c:a", config.get("audio_codec_music", "libmp3lame"), "-b:a", config.get("music_bitrate", "192k")])
    else:
        out_ext = ".mkv"
        tmp_file = f"{base_name}.tmp{out_ext}"
        target_res = config.get("tv_resolution", "1280x720") if media_type == 'tv' else config.get("movie_resolution", "1920x1080")
        
        video_codec = config.get("video_codec", "libx265")
        preset = config.get("ffmpeg_preset", "medium")
        
        # Hardware encoders like nvenc and amf have restricted preset options
        # Map common software presets down to the closest hardware equivalent
        if video_codec in ['hevc_nvenc', 'h264_nvenc', 'hevc_amf', 'h264_amf', 'hevc_qsv']:
            if preset in ['veryslow', 'slower', 'slow']:
                preset = "slow"
            elif preset in ['fast', 'faster', 'veryfast', 'superfast', 'ultrafast']:
                preset = "fast"
            else:
                preset = "medium"
                
            cmd.extend([
                "-c:v", video_codec,
                "-preset", preset,
                "-cq", str(config.get("ffmpeg_crf", 26))
            ])
        else:
            # Software encode
            cmd.extend([
                "-c:v", video_codec,
                "-preset", preset,
                "-crf", str(config.get("ffmpeg_crf", 26))
            ])
            
        cmd.extend([
            f"-vf", f"scale='min({target_res.split('x')[0]},iw)':-2",
            "-c:a", config.get("audio_codec_video", "aac"),
            "-c:s", "copy",
            "-map", "0:v:0", "-map", "0:a?", "-map", "0:s?",
            "-b:a", "128k"
        ])

    cmd.append(tmp_file)
    final_file = f"{base_name}{out_ext}"
    
    if config.get("dry_run", True):
        time.sleep(2) 
        log_conversion(file_name, media_type, orig_size, orig_size, "success (dry-run)")
        if file_path in current_converting: del current_converting[file_path]
        return True

    try:
        total_duration = get_media_duration(file_path)
        
        process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        
        while True:
            line = process.stderr.readline()
            if not line and process.poll() is not None:
                break
                
            if "time=" in line and total_duration > 0:
                match = re.search(r"time=(\d{2}:\d{2}:\d{2}\.\d{2})", line)
                if match:
                    current_s = parse_ffmpeg_time(match.group(1))
                    progress = int((current_s / total_duration) * 100)
                    if file_path in current_converting:
                        current_converting[file_path]["progress"] = min(100, max(0, progress))
                        
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, cmd)
        
        if file_path != final_file:
            os.remove(file_path)
            
        os.rename(tmp_file, final_file)
        
        new_size = os.path.getsize(final_file)
        log_conversion(file_name, media_type, orig_size, new_size, "success")
        
        if file_path in current_converting: del current_converting[file_path]
        return True
    except subprocess.CalledProcessError as e:
        if os.path.exists(tmp_file): os.remove(tmp_file)
        log_conversion(file_name, media_type, orig_size, 0, "error", str(e))
        if file_path in current_converting: del current_converting[file_path]
        return False
    except Exception as e:
        if os.path.exists(tmp_file): os.remove(tmp_file)
        log_conversion(file_name, media_type, orig_size, 0, "error", str(e))
        if file_path in current_converting: del current_converting[file_path]
        return False

def worker_loop(config_ref):
    while True:
        item = conversion_queue.get()
        if item is None: break
        file_path, media_type = item
        
        config = load_config() # Reload live
        try:
            convert_media(file_path, media_type, config)
        except Exception as e:
            logging.error(f"Worker error: {e}")
            
        with queue_lock:
            if file_path in queued_files:
                queued_files.remove(file_path)
            
        conversion_queue.task_done()

def enqueue_file(file_path, media_type):
    with queue_lock:
        if file_path not in queued_files:
            queued_files.add(file_path)
            conversion_queue.put((file_path, media_type))

def process_directory(directory, config):
    for root, dirs, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            if ".tmp." in file: continue
            media_type = get_media_type(file_path, config)
            if media_type: enqueue_file(file_path, media_type)

class MediaHandler(FileSystemEventHandler):
    def __init__(self, config):
        self.config = config

    def on_created(self, event):
        if not event.is_directory:
            media_type = get_media_type(event.src_path, self.config)
            if media_type: enqueue_file(event.src_path, media_type)

    def on_moved(self, event):
        if not event.is_directory:
            media_type = get_media_type(event.dest_path, self.config)
            if media_type: enqueue_file(event.dest_path, media_type)

def bg_loop():
    # Start workers once globally since they can handle hot-reloads of config
    config = load_config()
    num_workers = config.get("max_concurrent_encodes", 1) if config else 1
    for _ in range(num_workers):
        threading.Thread(target=worker_loop, args=(config,), daemon=True).start()

    while True:
        config = load_config()
        config_updated_event.clear()
        
        if not config:
            time.sleep(5)
            continue
            
        parent_dir = config.get("parent_directory")
        if not parent_dir or not os.path.isdir(parent_dir):
            # Wait for config to be updated with a valid directory
            config_updated_event.wait(timeout=5)
            continue

        process_directory(parent_dir, config)

        observer = None
        if config.get("use_watchdog", True):
            event_handler = MediaHandler(config)
            observer = Observer()
            observer.schedule(event_handler, parent_dir, recursive=True)
            observer.start()

        # Wait until config is explicitly updated or interval passes
        if observer:
            config_updated_event.wait() # Block until settings are saved
            observer.stop()
            observer.join()
        else:
            interval = config.get("scan_interval_seconds", 3600)
            config_updated_event.wait(timeout=interval)

import platform
import sys

def check_dependencies():
    try:
        subprocess.run(["ffmpeg", "-version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        print("\n" + "="*60)
        print(" CRITICAL ERROR: FFmpeg is not installed on this system.")
        print("="*60)
        print(" SizeTrimmer requires FFmpeg to perform media conversions.")
        if platform.system() == "Windows":
            print("\n Please run the included setup script as Administrator:")
            print(" > powershell -ExecutionPolicy Bypass -File setup.ps1")
        elif platform.system() == "Linux":
            print("\n Please run the included setup script to install it:")
            print(" $ chmod +x setup.sh")
            print(" $ ./setup.sh")
        else:
            print("\n Please install FFmpeg manually from https://ffmpeg.org/download.html")
        print("="*60 + "\n")
        sys.exit(1)

if __name__ == "__main__":
    check_dependencies()
    
    init_db()
    # Initialize psutil
    psutil.cpu_percent()
    
    # Start the background checking and conversion in a daemon thread
    bg_thread = threading.Thread(target=bg_loop, daemon=True)
    bg_thread.start()
    
    # Start the fastAPI server on the main thread
    config = load_config()
    port = config.get("web_port", 8000)
    logging.info(f"Starting Web UI on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="error")
