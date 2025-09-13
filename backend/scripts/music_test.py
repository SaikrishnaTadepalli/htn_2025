import sys, subprocess, requests, signal
from yt_dlp import YoutubeDL

def play(query: str):
    ydl_opts = {
        "quiet": True,
        "noplaylist": True,
        "format": "bestaudio/best",
    }

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch1:{query}", download=False)
        if "entries" in info:
            info = info["entries"][0]
        title = info.get("title", "Unknown")
        url = info["url"]
        headers = info.get("http_headers", {}) or {}

    print(f"▶ Playing: {title}")

    # Stream HTTP bytes to ffplay via stdin
    # -nodisp: no video window, -autoexit: quit when stream ends
    ffplay = subprocess.Popen(
        ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", "-i", "-"],
        stdin=subprocess.PIPE
    )

    def stop(*_):
        try:
            if ffplay.stdin:
                ffplay.stdin.close()
        finally:
            ffplay.terminate()

    # Clean shutdown on Ctrl+C
    signal.signal(signal.SIGINT, stop)

    with requests.get(url, headers=headers, stream=True) as r:
        r.raise_for_status()
        for chunk in r.iter_content(chunk_size=64 * 1024):
            if chunk and ffplay.stdin:
                ffplay.stdin.write(chunk)

    if ffplay.stdin:
        ffplay.stdin.close()
    ffplay.wait()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python play_query.py <your search terms>")
        sys.exit(1)
    play(" ".join(sys.argv[1:]))
