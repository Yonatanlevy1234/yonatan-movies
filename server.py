import contextlib
import logging
import re
import urllib.parse
from typing import Optional

from fastapi import FastAPI, HTTPException, Header, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import BASE_DIR, HOST, PORT
import database as db
from telegram_client import telegram_streamer

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("server")


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""
    logger.info("Initializing SQLite database...")
    db.init_db()

    logger.info("Starting Telegram MTProto Streamer...")
    try:
        await telegram_streamer.start()
        # Trigger background sync automatically on startup
        import asyncio
        asyncio.create_task(telegram_streamer.sync_channel_movies())
    except Exception as e:
        logger.warning(f"Telegram client startup background note: {e}")

    yield

    logger.info("Stopping Telegram MTProto Streamer...")
    await telegram_streamer.stop()


app = FastAPI(
    title="Telegram Cinema Portal",
    description="Professional Movie Database and Streaming Platform",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = f"{BASE_DIR}/static"
templates_dir = f"{BASE_DIR}/templates"

app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)


@app.get("/", response_class=HTMLResponse)
async def serve_index(request: Request):
    """Serves the main professional text table frontend."""
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/api/movies")
async def get_movies(limit: Optional[int] = Query(None), offset: int = 0):
    """Endpoint: Fetch clean list of all movies in channel."""
    movies = db.get_all_movies(limit=limit, offset=offset)
    total = db.get_total_count()
    return {
        "status": "success",
        "total_count": total,
        "returned_count": len(movies),
        "movies": movies,
    }


@app.get("/api/search")
async def search_movies_api(q: str = Query("", description="Search query")):
    """Endpoint: Search API for movie title and year."""
    results = db.search_movies(q)
    return {
        "status": "success",
        "query": q,
        "count": len(results),
        "total_count": db.get_total_count(),
        "movies": results,
    }


@app.post("/api/sync")
async def sync_channel():
    """Endpoint: Triggers manual sync of Telegram channel posts into database."""
    count = await telegram_streamer.sync_channel_movies()
    total = db.get_total_count()
    return {"status": "success", "synced_new": count, "total_movies": total}


@app.get("/api/movies/{movie_id}")
async def get_movie_details(movie_id: int):
    """Endpoint: Get movie metadata by ID."""
    movie = db.get_movie_by_id(movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    return {"status": "success", "movie": movie}


@app.get("/api/stream/{movie_id}")
async def stream_movie(movie_id: int, range: Optional[str] = Header(None)):
    """Streaming Endpoint: HTTP Range Requests for video player seeking."""
    movie = db.get_movie_by_id(movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    file_size = movie["file_size"] or 1500000000
    mime_type = movie.get("mime_type") or "video/mp4"
    message_id = movie["message_id"]

    start = 0
    end = file_size - 1

    if range:
        range_match = re.search(r"bytes=(\d+)-(\d*)", range)
        if range_match:
            start_str = range_match.group(1)
            end_str = range_match.group(2)
            start = int(start_str)
            if end_str:
                end = min(int(end_str), file_size - 1)

    if start >= file_size:
        raise HTTPException(
            status_code=416, detail="Requested Range Not Satisfiable"
        )

    content_length = (end - start) + 1

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
        "Content-Type": mime_type,
        "Cache-Control": "no-cache",
    }

    stream_generator = telegram_streamer.stream_file_range(
        message_id=message_id, start=start, end=end
    )

    status_code = 206 if range else 200

    return StreamingResponse(
        stream_generator, status_code=status_code, headers=headers
    )


@app.get("/api/download/{movie_id}")
async def download_movie(movie_id: int):
    """Download Endpoint: Direct file download."""
    movie = db.get_movie_by_id(movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    file_size = movie["file_size"] or 1500000000
    mime_type = movie.get("mime_type") or "video/mp4"
    file_name = movie.get("file_name") or f"movie_{movie_id}.mp4"
    message_id = movie["message_id"]

    # Sanitize filename: ASCII fallback and UTF-8 encoded RFC 5987 version
    safe_name = re.sub(r'[\\/*?:"<>|]', "", file_name)
    ascii_filename = re.sub(r"[^\x00-\x7F]+", "_", safe_name) or f"movie_{movie_id}.mp4"
    encoded_filename = urllib.parse.quote(safe_name)

    headers = {
        "Content-Disposition": f'attachment; filename="{ascii_filename}"; filename*=UTF-8\'\'{encoded_filename}',
        "Content-Length": str(file_size),
        "Content-Type": mime_type,
    }

    stream_generator = telegram_streamer.stream_file_range(
        message_id=message_id, start=0, end=file_size - 1
    )

    return StreamingResponse(
        stream_generator, status_code=200, headers=headers
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host=HOST, port=PORT, reload=True)
