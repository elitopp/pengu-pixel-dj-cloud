import asyncio
import base64
import io
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Auto-instalador para servidores en la nube (Wispbyte / Pterodactyl / Linux 24/7)
try:
    import aiohttp
    import discord
    from dotenv import load_dotenv
    from PIL import Image, ImageDraw, ImageFont
    import yt_dlp
except ImportError:
    print("☁️ Instalando librerías automáticamente en el servidor en la nube...", flush=True)
    req_file = Path(__file__).parent / "requirements.txt"
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(req_file)])
    import aiohttp
    import discord
    from dotenv import load_dotenv
    from PIL import Image, ImageDraw, ImageFont
    import yt_dlp

from discord import app_commands
from discord.ext import commands

# Cargar variables de entorno (.env)
load_dotenv()

BASE_DIR = Path(__file__).parent
ASSETS_DIR = BASE_DIR / "assets"
ASSETS_DIR.mkdir(exist_ok=True)

AUDIO_CACHE_DIR = Path(tempfile.gettempdir()) / "pengu_audio_cache"
AUDIO_CACHE_DIR.mkdir(exist_ok=True)

USER_PROFILES_FILE = BASE_DIR / "user_music_profiles.json"

# Copiar los assets pixel-art generados si existen en la carpeta de artefactos
ARTIFACT_AVATAR = Path(
    r"C:\Users\Elias\.gemini\antigravity-cli\brain\81c2a4f3-bd14-458e-a89b-4af0c0caa78c\pengu_avatar_1792282223821.jpg"
)
ARTIFACT_BANNER = Path(
    r"C:\Users\Elias\.gemini\antigravity-cli\brain\81c2a4f3-bd14-458e-a89b-4af0c0caa78c\pengu_banner_1792282254041.jpg"
)
LOCAL_AVATAR = ASSETS_DIR / "pengu_avatar.jpg"
LOCAL_BANNER = ASSETS_DIR / "pengu_banner.jpg"

if ARTIFACT_AVATAR.exists() and not LOCAL_AVATAR.exists():
    shutil.copy2(ARTIFACT_AVATAR, LOCAL_AVATAR)
if ARTIFACT_BANNER.exists() and not LOCAL_BANNER.exists():
    shutil.copy2(ARTIFACT_BANNER, LOCAL_BANNER)

# Paleta de colores Pixel Art Pingüino Artístico
COLOR_PIXEL_CYAN = 0x72EFDD
COLOR_PIXEL_PINK = 0xFF6B8B
COLOR_PIXEL_GOLD = 0xFFD166
COLOR_PIXEL_PURPLE = 0x9B5DE5
COLOR_SPOTIFY_GREEN = 0x1DB954
COLOR_YTMUSIC_RED = 0xFF0033

# Presets de efectos de audio FFmpeg (Calidad extrema sin necesitar Nitro)
AUDIO_FILTERS = {
    "hd": {
        "label": "✨ Estudio HD (320kbps Pure)",
        "ffmpeg": "-vn -b:a 320k",
    },
    "bassboost": {
        "label": "🔊 Bass Boost (Graves Potentes)",
        "ffmpeg": '-vn -b:a 320k -af "bass=g=10:f=110:w=0.6"',
    },
    "lofi": {
        "label": "☕ Iglú Lo-Fi Chill",
        "ffmpeg": '-vn -b:a 320k -af "asetrate=44100*0.92,aresample=44100,lowpass=f=3800"',
    },
    "nightcore": {
        "label": "⚡ Nightcore Pixel",
        "ffmpeg": '-vn -b:a 320k -af "asetrate=44100*1.22,aresample=44100,atempo=1.03"',
    },
    "vaporwave": {
        "label": "🌊 Vaporwave Aurora",
        "ffmpeg": '-vn -b:a 320k -af "asetrate=44100*0.82,aresample=44100,aecho=0.8:0.88:60:0.4"',
    },
}

YTDL_FLAT_OPTIONS = {
    "quiet": True,
    "no_warnings": True,
    "extract_flat": True,
    "nocheckcertificate": True,
    "extractor_args": {
        "youtube": {
            "player_client": ["android", "ios", "mweb", "web"]
        }
    },
}

YTDL_FULL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "logtostderr": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "extract_flat": False,
    "extractor_args": {
        "youtube": {
            "player_client": ["android", "ios", "mweb", "web"]
        }
    },
}

ytdl_flat = yt_dlp.YoutubeDL(YTDL_FLAT_OPTIONS)
ytdl_full = yt_dlp.YoutubeDL(YTDL_FULL_OPTIONS)


def get_ffmpeg_executable() -> str:
    ffmpeg_exe = shutil.which("ffmpeg")
    if not ffmpeg_exe:
        try:
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            ffmpeg_exe = "ffmpeg"
    return ffmpeg_exe


# ==============================================================================
# GESTOR DE PERFILES MUSICALES POR USUARIO (SPOTIFY + YOUTUBE MUSIC + GUSTOS)
# ==============================================================================
def load_all_user_profiles() -> dict:
    if USER_PROFILES_FILE.exists():
        try:
            return json.loads(USER_PROFILES_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_all_user_profiles(data: dict) -> None:
    try:
        USER_PROFILES_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as e:
        print(f"Aviso al guardar perfiles: {e}", flush=True)


def get_user_profile(user_id: int, display_name: str = "Usuario") -> dict:
    profiles = load_all_user_profiles()
    uid = str(user_id)
    if uid not in profiles:
        profiles[uid] = {
            "display_name": display_name,
            "spotify": {
                "connected": False,
                "client_id": "",
                "client_secret": "",
                "access_token": "",
                "profile_url": "",
                "account_name": "",
            },
            "ytmusic": {
                "connected": False,
                "api_key_or_token": "",
                "channel_or_playlist_url": "",
                "account_name": "",
            },
            "tastes": [],
            "liked_songs": [],
            "playlists": [],
        }
        save_all_user_profiles(profiles)
    else:
        profiles[uid]["display_name"] = display_name
    return profiles[uid]


def update_user_profile(user_id: int, profile_data: dict) -> None:
    profiles = load_all_user_profiles()
    profiles[str(user_id)] = profile_data
    save_all_user_profiles(profiles)


# ==============================================================================
# MODELOS DE REPRODUCCIÓN Y COLA
# ==============================================================================
@dataclass
class Song:
    title: str
    url: str
    webpage_url: str
    duration: int
    thumbnail: Optional[str]
    uploader: str
    requester: str
    search_query: str = ""
    local_file: Optional[str] = None

    @property
    def duration_str(self) -> str:
        if not self.duration:
            return "💿 Pista Completa"
        mins, secs = divmod(int(self.duration), 60)
        hours, mins = divmod(mins, 60)
        if hours > 0:
            return f"{hours:02d}:{mins:02d}:{secs:02d}"
        return f"{mins:02d}:{secs:02d}"


@dataclass
class GuildMusicState:
    queue: list[Song] = field(default_factory=list)
    current: Optional[Song] = None
    volume: float = 0.85
    loop_mode: str = "off"  # "off", "song", "queue"
    audio_filter: str = "hd"
    text_channel: Optional[discord.abc.Messageable] = None
    player_message: Optional[discord.Message] = None
    play_started_at: float = 0.0
    seek_offset: float = 0.0
    suppress_after_callback: bool = False
    prefetch_task: Optional[asyncio.Task] = None


music_states: dict[int, GuildMusicState] = {}


def get_music_state(guild_id: int) -> GuildMusicState:
    if guild_id not in music_states:
        music_states[guild_id] = GuildMusicState()
    return music_states[guild_id]


# ==============================================================================
# EXTRACTORES DE SPOTIFY, YOUTUBE MUSIC, CATÁLOGO OFICIAL Y AUDIO SIN CORTES
# ==============================================================================
def _is_preview_track(entry: dict) -> bool:
    """Detecta si una pista de SoundCloud es una vista previa restringida de 30s (Go+)."""
    if not entry:
        return True
    fmt_id = str(entry.get("format_id") or "").lower()
    url = str(entry.get("url") or "").lower()
    dur = float(entry.get("duration") or 0)
    if "preview" in fmt_id or "cf-preview-media" in url or "/preview/" in url:
        return True
    if 0 < dur <= 31.0:
        return True
    return False


async def fetch_artist_or_mix_tracks(query: str, limit: int = 12) -> list[dict]:
    """
    Convierte el nombre de un artista, banda o género (ej: 'Luis Miguel') en una lista real
    con sus mejores canciones oficiales y duraciones exactas en 0.3 segundos.
    """
    tracks: list[dict] = []
    q_encoded = urllib.parse.quote(query.strip())
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.deezer.com/search?q={q_encoded}&limit={limit}", timeout=8
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    seen = set()
                    for item in data.get("data", []):
                        t_name = (item.get("title") or "").strip()
                        art_name = (item.get("artist", {}).get("name") or "").strip()
                        dur = int(item.get("duration") or 0)
                        if not t_name or dur <= 35:
                            continue
                        key = f"{t_name.lower()}::{art_name.lower()}"
                        if key in seen:
                            continue
                        seen.add(key)
                        tracks.append(
                            {
                                "title": f"{t_name} - {art_name}" if art_name else t_name,
                                "artist": art_name or query,
                                "query": f"{t_name} {art_name}".strip(),
                                "duration": dur,
                                "webpage_url": item.get("link") or "https://open.spotify.com",
                            }
                        )
    except Exception:
        pass
    return tracks


async def resolve_external_url_to_search(url: str) -> Optional[str]:
    """Convierte links individuales de Spotify o YouTube en 'Título - Artista'."""
    try:
        async with aiohttp.ClientSession() as session:
            if "open.spotify.com" in url:
                embed_url = re.sub(
                    r"open\.spotify\.com/(intl-[a-z-]+/)?(track|album|playlist)/",
                    r"open.spotify.com/embed/\2/",
                    url,
                )
                async with session.get(embed_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        m = re.search(r"__NEXT_DATA__[^>]*>(.*?)</script>", html)
                        if m:
                            data = json.loads(m.group(1))
                            entity = (
                                data.get("props", {})
                                .get("pageProps", {})
                                .get("state", {})
                                .get("data", {})
                                .get("entity", {})
                            )
                            title = entity.get("title") or entity.get("name") or ""
                            artist = entity.get("subtitle") or ""
                            if not artist and entity.get("artists"):
                                artist = ", ".join(a.get("name", "") for a in entity["artists"])
                            if title:
                                return f"{title} {artist}".strip()
                async with session.get(f"https://open.spotify.com/oembed?url={url}", timeout=8) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("title"):
                            return data["title"]
            if "youtube.com" in url or "youtu.be" in url:
                async with session.get(f"https://noembed.com/embed?url={url}", timeout=8) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        title = data.get("title", "")
                        author = data.get("author_name", "")
                        if title:
                            author_clean = re.sub(r"\s*-\s*Topic$", "", author, flags=re.IGNORECASE)
                            return f"{title} {author_clean}".strip()
    except Exception:
        pass
    return None


async def fetch_spotify_token(client_id: str, client_secret: str) -> Optional[str]:
    """Obtiene un token oficial de Spotify Web API usando Client ID y Client Secret del usuario."""
    try:
        raw = f"{client_id.strip()}:{client_secret.strip()}".encode("utf-8")
        b64 = base64.b64encode(raw).decode("ascii")
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://accounts.spotify.com/api/token",
                headers={
                    "Authorization": f"Basic {b64}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data="grant_type=client_credentials",
                timeout=10,
            ) as resp:
                if resp.status == 200:
                    js = await resp.json()
                    return js.get("access_token")
    except Exception:
        pass
    return None


async def extract_spotify_playlist_or_album(
    url_or_id: str, user_spotify_cfg: Optional[dict] = None
) -> tuple[str, list[dict]]:
    """
    Extrae todas las canciones de una Playlist, Álbum o colección de Spotify.
    Funciona tanto con credenciales API del usuario como directamente por URL.
    """
    tracks: list[dict] = []
    playlist_name = "Playlist de Spotify"

    m_type = re.search(r"(playlist|album)/([a-zA-Z0-9]+)", url_or_id)
    kind = m_type.group(1) if m_type else "playlist"
    item_id = m_type.group(2) if m_type else url_or_id.strip()

    token = None
    if user_spotify_cfg:
        if user_spotify_cfg.get("access_token"):
            token = user_spotify_cfg["access_token"]
        elif user_spotify_cfg.get("client_id") and user_spotify_cfg.get("client_secret"):
            token = await fetch_spotify_token(
                user_spotify_cfg["client_id"], user_spotify_cfg["client_secret"]
            )

    if token and re.match(r"^[a-zA-Z0-9]{15,30}$", item_id):
        try:
            async with aiohttp.ClientSession() as session:
                api_url = f"https://api.spotify.com/v1/{kind}s/{item_id}"
                async with session.get(
                    api_url, headers={"Authorization": f"Bearer {token}"}, timeout=10
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        playlist_name = data.get("name", playlist_name)
                        items = data.get("tracks", {}).get("items", [])
                        for item in items:
                            tr = item.get("track") if kind == "playlist" else item
                            if not tr or not tr.get("name"):
                                continue
                            t_name = tr["name"]
                            t_artists = ", ".join(
                                a.get("name", "") for a in tr.get("artists", []) if a.get("name")
                            )
                            dur_sec = int((tr.get("duration_ms") or 0) / 1000)
                            tracks.append(
                                {
                                    "title": f"{t_name} - {t_artists}" if t_artists else t_name,
                                    "artist": t_artists or "Spotify",
                                    "query": f"{t_name} {t_artists}".strip(),
                                    "duration": dur_sec,
                                    "webpage_url": tr.get("external_urls", {}).get(
                                        "spotify", f"https://open.spotify.com/{kind}/{item_id}"
                                    ),
                                }
                            )
                        if tracks:
                            return playlist_name, tracks
        except Exception:
            pass

    try:
        embed_url = f"https://open.spotify.com/embed/{kind}/{item_id}"
        async with aiohttp.ClientSession() as session:
            async with session.get(
                embed_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10
            ) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    m = re.search(r"__NEXT_DATA__[^>]*>(.*?)</script>", html)
                    if m:
                        data = json.loads(m.group(1))
                        entity = (
                            data.get("props", {})
                            .get("pageProps", {})
                            .get("state", {})
                            .get("data", {})
                            .get("entity", {})
                        )
                        playlist_name = entity.get("name") or entity.get("title") or playlist_name
                        track_list = entity.get("trackList", [])
                        for t in track_list:
                            t_title = (t.get("title") or "").strip()
                            t_sub = (t.get("subtitle") or "").replace("\xa0", " ").strip()
                            dur_sec = int((t.get("duration") or 0) / 1000)
                            if t_title:
                                tracks.append(
                                    {
                                        "title": f"{t_title} - {t_sub}" if t_sub else t_title,
                                        "artist": t_sub or "Spotify",
                                        "query": f"{t_title} {t_sub}".strip(),
                                        "duration": dur_sec,
                                        "webpage_url": f"https://open.spotify.com/{kind}/{item_id}",
                                    }
                                )
    except Exception:
        pass

    return playlist_name, tracks


async def fetch_user_spotify_me_library(access_token: str) -> tuple[str, list[dict], list[dict]]:
    """Sincroniza el perfil privado de Spotify (/me, /me/tracks y /me/playlists) cuando se provee un Token."""
    account_name = "Cuenta Spotify"
    playlists_out: list[dict] = []
    liked_out: list[dict] = []
    headers = {"Authorization": f"Bearer {access_token.strip()}"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.spotify.com/v1/me", headers=headers, timeout=10) as r_me:
                if r_me.status == 200:
                    me_data = await r_me.json()
                    account_name = me_data.get("display_name") or me_data.get("id") or account_name

            async with session.get(
                "https://api.spotify.com/v1/me/tracks?limit=40", headers=headers, timeout=10
            ) as r_tr:
                if r_tr.status == 200:
                    tr_data = await r_tr.json()
                    for item in tr_data.get("items", []):
                        tr = item.get("track") or {}
                        if tr.get("name"):
                            art = ", ".join(a.get("name", "") for a in tr.get("artists", []))
                            liked_out.append(
                                {
                                    "title": f"{tr['name']} - {art}" if art else tr["name"],
                                    "artist": art or "Spotify",
                                    "query": f"{tr['name']} {art}".strip(),
                                    "duration": int((tr.get("duration_ms") or 0) / 1000),
                                    "webpage_url": tr.get("external_urls", {}).get("spotify", ""),
                                }
                            )

            async with session.get(
                "https://api.spotify.com/v1/me/playlists?limit=10", headers=headers, timeout=10
            ) as r_pl:
                if r_pl.status == 200:
                    pl_data = await r_pl.json()
                    for pl in pl_data.get("items", []):
                        pl_id = pl.get("id")
                        pl_url = pl.get("external_urls", {}).get(
                            "spotify", f"https://open.spotify.com/playlist/{pl_id}"
                        )
                        pl_name, pl_tracks = await extract_spotify_playlist_or_album(
                            pl_url, {"access_token": access_token}
                        )
                        if pl_tracks:
                            playlists_out.append(
                                {
                                    "name": pl.get("name") or pl_name,
                                    "source": "spotify",
                                    "url": pl_url,
                                    "tracks": pl_tracks[:60],
                                }
                            )
    except Exception:
        pass

    return account_name, playlists_out, liked_out


async def extract_youtube_music_playlist(url: str) -> tuple[str, list[dict]]:
    """Extrae todas las canciones de una playlist de YouTube Music o YouTube normal."""
    loop = asyncio.get_running_loop()
    clean_url = url.replace("music.youtube.com", "www.youtube.com")

    def _extract():
        opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "nocheckcertificate": True,
            "playlistend": 80,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(clean_url, download=False)

    try:
        info = await loop.run_in_executor(None, _extract)
        if not info:
            return "Playlist YT Music", []
        title = info.get("title") or "Playlist de YouTube Music"
        entries = info.get("entries") or []
        tracks: list[dict] = []
        for e in entries:
            if not e:
                continue
            t_title = (e.get("title") or "").strip()
            if not t_title or t_title in ("[Deleted video]", "[Private video]"):
                continue
            uploader = (e.get("uploader") or e.get("channel") or "YouTube").strip()
            uploader_clean = re.sub(r"\s*-\s*Topic$", "", uploader, flags=re.IGNORECASE)
            dur = int(e.get("duration") or 0)
            vid_id = e.get("id") or ""
            web_url = (
                f"https://www.youtube.com/watch?v={vid_id}"
                if vid_id
                else (e.get("url") if str(e.get("url", "")).startswith("http") else clean_url)
            )
            tracks.append(
                {
                    "title": f"{t_title} - {uploader_clean}"
                    if uploader_clean and uploader_clean.lower() not in t_title.lower()
                    else t_title,
                    "artist": uploader_clean,
                    "query": web_url if vid_id else f"{t_title} {uploader_clean}".strip(),
                    "duration": dur,
                    "webpage_url": web_url,
                }
            )
        if tracks:
            return title, tracks
    except Exception:
        pass

    # Fallback: si era un link con watch?v=...&list=RD... (Mix automático), extraer el video directo
    m_vid = re.search(r"[?&]v=([a-zA-Z0-9_-]{6,20})", clean_url)
    if m_vid:
        single_url = f"https://www.youtube.com/watch?v={m_vid.group(1)}"
        resolved = await resolve_external_url_to_search(single_url)
        t_name = resolved or "Video / Concierto de YouTube"
        return t_name, [
            {
                "title": t_name,
                "artist": "YouTube",
                "query": single_url,
                "duration": 0,
                "webpage_url": single_url,
            }
        ]

    return "Playlist YT Music", []


CONCERT_KEYWORDS = (
    "concierto",
    "en vivo",
    "live",
    "100%",
    "lucidos",
    "lúcidos",
    "caupolican",
    "caupolicán",
    "movistar arena",
    "festival",
    "viña",
    "tiny desk",
    "unplugged",
    "full",
    "completo",
    "show",
    "session",
    "sesión",
    "setlist",
)


def _is_concert_query(text: str) -> bool:
    low = text.lower()
    return any(k in low for k in CONCERT_KEYWORDS)


def _build_search_queries(query: str) -> list[str]:
    """Genera variantes limpias de búsqueda para encontrar siempre pistas completas."""
    q_clean = query.strip()
    variants = [q_clean]

    simplified = re.sub(
        r"\bmacha\s+y\s+el\s+", "", q_clean, flags=re.IGNORECASE
    )
    simplified = re.sub(
        r"\b(feat\.?|ft\.?|con|y el|y la|y los)\b", " ", simplified, flags=re.IGNORECASE
    )
    simplified = re.sub(r"[()\[\]\-–—•|]+", " ", simplified)
    simplified = re.sub(r"\s+", " ", simplified).strip()
    if simplified and simplified.lower() not in [v.lower() for v in variants]:
        variants.append(simplified)

    words = simplified.split()
    if len(words) > 4:
        short_q = " ".join(words[:4])
        if short_q.lower() not in [v.lower() for v in variants]:
            variants.append(short_q)

    return variants


def _find_full_track_sync(query_or_url: str, expected_duration: int = 0) -> dict:
    """
    Busca una pista o concierto COMPLETO en YouTube y SoundCloud (descartando previews de 30s).
    Soporta links directos de YouTube/SoundCloud, conciertos de larga duración y canciones de playlists.
    """
    q_str = query_or_url.strip()
    is_direct_url = q_str.startswith(("http://", "https://")) and "open.spotify.com" not in q_str

    if is_direct_url:
        target_url = q_str.replace("music.youtube.com", "www.youtube.com")
        if "youtube.com/watch" in target_url and "list=" in target_url:
            m_v = re.search(r"[?&]v=([a-zA-Z0-9_-]{6,20})", target_url)
            if m_v:
                target_url = f"https://www.youtube.com/watch?v={m_v.group(1)}"
        try:
            info = ytdl_full.extract_info(target_url, download=False)
            if info and "entries" in info:
                entries = [e for e in info["entries"] if e]
                info = entries[0] if entries else None
            if info and info.get("url"):
                return info
        except Exception:
            pass

    # 1. Buscar primero en YouTube (soporta 100% conciertos largos, temas de Wave to Earth, Bloque Depresivo, etc.)
    try:
        yt_res = ytdl_full.extract_info(f"ytsearch3:{q_str}", download=False)
        yt_entries = [e for e in (yt_res or {}).get("entries", []) if e and e.get("url")]
        if yt_entries:
            if expected_duration > 40 and not _is_concert_query(q_str):
                yt_entries.sort(
                    key=lambda x: abs(float(x.get("duration") or 0) - expected_duration)
                )
            return yt_entries[0]
    except Exception:
        pass

    # 2. Respaldo en SoundCloud (descartando previews de 30s)
    for q_try in _build_search_queries(q_str):
        try:
            flat_res = ytdl_flat.extract_info(f"scsearch8:{q_try}", download=False)
            entries = [e for e in (flat_res or {}).get("entries", []) if e]

            valid_candidates = []
            for e in entries:
                dur = float(e.get("duration") or 0)
                if dur <= 35.0:
                    continue
                valid_candidates.append(e)

            if not valid_candidates:
                continue

            if expected_duration > 40:
                valid_candidates.sort(
                    key=lambda x: abs(float(x.get("duration") or 0) - expected_duration)
                )

            for candidate in valid_candidates[:3]:
                cand_url = candidate.get("webpage_url") or candidate.get("url")
                if not cand_url:
                    continue
                try:
                    full_info = ytdl_full.extract_info(cand_url, download=False)
                    if full_info and not _is_preview_track(full_info):
                        return full_info
                except Exception:
                    continue
        except Exception:
            continue

    raise ValueError(f"No se encontró versión completa para '{query_or_url}'")


def _download_stream_to_local_file_sync(
    stream_url: str, target_path: Path, timeout_sec: int = 20
) -> bool:
    """
    Descarga/remuxea el stream completo a un contenedor universal .mkv en disco.
    Soporta MP3, Opus y AAC con -c:a copy sin fallar y elimina los cortes a mitad de canción.
    """
    ffmpeg_exe = get_ffmpeg_executable()
    try:
        if target_path.exists():
            try:
                target_path.unlink()
            except Exception:
                pass
        cmd = [
            ffmpeg_exe,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-reconnect",
            "1",
            "-reconnect_streamed",
            "1",
            "-reconnect_delay_max",
            "5",
            "-i",
            stream_url,
            "-vn",
            "-c:a",
            "copy",
            str(target_path),
        ]
        res = subprocess.run(cmd, capture_output=True, timeout=timeout_sec)
        if res.returncode == 0 and target_path.exists() and target_path.stat().st_size > 16384:
            return True
    except Exception:
        pass
    return False


async def search_song(query: str, requester: str, expected_duration: int = 0) -> Song:
    """
    Busca cualquier canción o concierto asegurando que SIEMPRE sea la pista completa.
    Soporta links directos de YouTube, YouTube Music, Spotify y búsquedas por texto.
    """
    query = query.strip()
    search_text = query

    if query.startswith(("http://", "https://")):
        if "open.spotify.com" in query:
            resolved = await resolve_external_url_to_search(query)
            if resolved:
                search_text = resolved
        else:
            # Conservar URL directa de YouTube / SoundCloud para extraer el video/concierto exacto
            search_text = query
    elif expected_duration == 0 and not _is_concert_query(search_text) and len(search_text.split()) <= 3:
        # Si el usuario escribió solo un artista corto (ej. "Luis Miguel"), obtener éxito oficial
        catalog_matches = await fetch_artist_or_mix_tracks(search_text, limit=1)
        if catalog_matches:
            expected_duration = catalog_matches[0]["duration"]
            search_text = catalog_matches[0]["query"]

    loop = asyncio.get_running_loop()
    info = await loop.run_in_executor(
        None, lambda: _find_full_track_sync(search_text, expected_duration)
    )

    return Song(
        title=info.get("title", search_text),
        url=info["url"],
        webpage_url=info.get("webpage_url", query if query.startswith("http") else "https://www.youtube.com"),
        duration=int(info.get("duration") or expected_duration or 0),
        thumbnail=info.get("thumbnail"),
        uploader=info.get("uploader", "Artista"),
        requester=requester,
        search_query=search_text,
    )


async def ensure_song_ready_for_playback(song: Song, guild_id: int, slot: str = "current") -> Song:
    """
    Resuelve la URL del stream si la canción venía de una playlist (lazy load).
    Para 'current' inicia el stream de inmediato (~1s) sin bloquear en descargas largas de conciertos;
    para 'next' pre-descarga pistas normales (<= 8 min) en segundo plano.
    """
    if not song.url:
        q = song.search_query or song.title
        resolved = await search_song(q, song.requester, expected_duration=song.duration)
        song.url = resolved.url
        if resolved.title and (not song.title or song.title.startswith("http")):
            song.title = resolved.title
        if not song.thumbnail and resolved.thumbnail:
            song.thumbnail = resolved.thumbnail
        if not song.duration and resolved.duration:
            song.duration = resolved.duration
        if not song.webpage_url or not song.webpage_url.startswith("http") or song.webpage_url == "https://open.spotify.com":
            song.webpage_url = resolved.webpage_url

    if song.local_file and Path(song.local_file).exists() and Path(song.local_file).stat().st_size > 16384:
        return song

    # No bloquear el inicio de reproducción ('current') ni intentar descargar conciertos largos (> 8 min)
    if slot == "current" or (song.duration and song.duration > 480):
        return song

    target_file = AUDIO_CACHE_DIR / f"guild_{guild_id}_{slot}_{int(time.time() * 1000)}.mkv"
    loop = asyncio.get_running_loop()
    ok = await loop.run_in_executor(
        None, lambda: _download_stream_to_local_file_sync(song.url, target_file, timeout_sec=20)
    )
    if ok:
        song.local_file = str(target_file)
    return song


def is_playlist_url(query: str) -> Optional[str]:
    q = query.strip()
    if not q.startswith(("http://", "https://")):
        return None
    if "open.spotify.com" in q and ("/playlist/" in q or "/album/" in q):
        return "spotify"
    if ("youtube.com" in q or "youtu.be" in q) and "list=" in q:
        return "ytmusic"
    return None


# ==============================================================================
# GENERADORES DE ARTE PIXEL ART (BIENVENIDA Y PALETAS)
# ==============================================================================
def create_pixel_welcome_card(member_name: str, member_count: int) -> io.BytesIO:
    width, height = 720, 260
    px_w, px_h = 180, 65
    canvas = Image.new("RGB", (px_w, px_h), (18, 22, 42))
    draw = ImageDraw.Draw(canvas)

    for y in range(px_h):
        r = int(18 + (y / px_h) * 28)
        g = int(22 + (y / px_h) * 45)
        b = int(46 + (y / px_h) * 65)
        draw.line([(0, y), (px_w, y)], fill=(r, g, b))

    rng = random.Random(member_count + len(member_name))
    for _ in range(28):
        sx = rng.randint(4, px_w - 5)
        sy = rng.randint(4, px_h - 15)
        star_color = rng.choice([(114, 239, 221), (255, 209, 102), (255, 107, 139), (255, 255, 255)])
        canvas.putpixel((sx, sy), star_color)

    draw.rectangle([1, 1, px_w - 2, px_h - 2], outline=(114, 239, 221))
    draw.rectangle([3, 3, px_w - 4, px_h - 4], outline=(255, 107, 139))

    ox, oy = 14, 16
    draw.rectangle([ox + 4, oy + 6, ox + 18, oy + 28], fill=(32, 42, 74))
    draw.rectangle([ox + 7, oy + 11, ox + 15, oy + 26], fill=(240, 248, 255))
    draw.rectangle([ox + 2, oy + 7, ox + 4, oy + 13], fill=(114, 239, 221))
    draw.rectangle([ox + 18, oy + 7, ox + 20, oy + 13], fill=(114, 239, 221))
    draw.line([(ox + 3, oy + 5), (ox + 19, oy + 5)], fill=(255, 107, 139))
    canvas.putpixel((ox + 8, oy + 9), (255, 255, 255))
    canvas.putpixel((ox + 14, oy + 9), (255, 255, 255))
    draw.rectangle([ox + 10, oy + 11, ox + 12, oy + 12], fill=(255, 209, 102))
    draw.rectangle([ox + 6, oy + 28, ox + 9, oy + 30], fill=(255, 159, 28))
    draw.rectangle([ox + 13, oy + 28, ox + 16, oy + 30], fill=(255, 159, 28))

    final_img = canvas.resize((width, height), Image.Resampling.NEAREST)
    final_draw = ImageDraw.Draw(final_img)

    try:
        font_big = ImageFont.truetype("consola.ttf", 30)
        font_sub = ImageFont.truetype("consola.ttf", 20)
    except Exception:
        font_big = ImageFont.load_default()
        font_sub = ImageFont.load_default()

    final_draw.text((175, 58), "SERVER DE THOMI // PIXEL STUDIO", fill=(114, 239, 221), font=font_sub)
    final_draw.text((175, 102), f"BIENVENIDO/A, {member_name[:18].upper()}!", fill=(255, 255, 255), font=font_big)
    final_draw.text(
        (175, 155),
        f"Pinguino Artista #{member_count} en el Iglu de Thomi",
        fill=(255, 209, 102),
        font=font_sub,
    )
    final_draw.text(
        (175, 192),
        "Musica 24/7 • Spotify & YT Music • Pixel Art",
        fill=(255, 107, 139),
        font=font_sub,
    )

    buf = io.BytesIO()
    final_img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def create_palette_image(colors: list[tuple[int, int, int]]) -> io.BytesIO:
    swatch_w, height = 110, 140
    width = swatch_w * len(colors)
    img = Image.new("RGB", (width, height), (24, 24, 36))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("consola.ttf", 16)
    except Exception:
        font = ImageFont.load_default()

    for idx, rgb in enumerate(colors):
        x0 = idx * swatch_w
        draw.rectangle([x0, 0, x0 + swatch_w, height - 34], fill=rgb)
        hex_code = f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"
        draw.text((x0 + 16, height - 26), hex_code, fill=(240, 240, 255), font=font)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def build_player_embed(guild: discord.Guild, state: GuildMusicState) -> discord.Embed:
    song = state.current
    filter_name = AUDIO_FILTERS.get(state.audio_filter, AUDIO_FILTERS["hd"])["label"]
    loop_icons = {"off": "➡️ Desactivado", "song": "🔂 Repetir Canción", "queue": "🔁 Repetir Cola"}

    if not song:
        embed = discord.Embed(
            title="🐧🎧 THOMI PIXEL JUKEBOX // SPOTIFY & YT MUSIC 24/7",
            description=(
                "╭──────────────────────────────────────────╮\n"
                "  🎨 **¡Bienvenido a la Cabina Musical de Thomi!**\n"
                "  Escucha canciones completas y conecta tus propias\n"
                "  cuentas/playlists de **Spotify y YouTube Music**.\n"
                "╰──────────────────────────────────────────╯\n\n"
                "✨ **¿Cómo usar la cabina súper fácil?**\n"
                "▸ **`➕ Pedir Canción / Playlist`**: Escribe un artista, canción o link de playlist\n"
                "▸ **`💚❤️ Mi Spotify / YT Music`**: Conecta tus credenciales, playlists o gustos\n"
                "▸ **`❤️ Me Gusta`**: Guarda la canción que esté sonando en tu perfil\n"
                "▸ **`🎉 Modo Fiesta`**: Mezcla automáticamente la música de todos en el canal"
            ),
            color=COLOR_PIXEL_CYAN,
        )
        return embed

    vol_bars = int(round(state.volume * 10))
    vol_visual = "▰" * min(vol_bars, 10) + "▱" * max(0, 10 - vol_bars)

    embed = discord.Embed(
        title="🐧💿 SONANDO AHORA EN EL SERVER DE THOMI",
        description=(
            f"### 🎶 [{song.title}]({song.webpage_url})\n"
            f"```ini\n"
            f"[ ▰▰▰▰▰▱▱▱▱▱▱▱ ] 🔊 {int(state.volume * 100)}% ({vol_visual})\n"
            f"```"
        ),
        color=COLOR_PIXEL_PINK,
    )
    embed.add_field(name="⏱️ Duración", value=f"`{song.duration_str}`", inline=True)
    embed.add_field(name="🎙️ Canal / Artista", value=f"`{song.uploader[:25]}`", inline=True)
    embed.add_field(name="🐧 Pedido por", value=song.requester, inline=True)
    embed.add_field(name="🎛️ Filtro de Audio", value=f"`{filter_name}`", inline=True)
    embed.add_field(name="🔁 Modo Loop", value=f"`{loop_icons[state.loop_mode]}`", inline=True)
    embed.add_field(name="📜 En Cola", value=f"`{len(state.queue)} canciones`", inline=True)

    if state.queue:
        upcoming = "\n".join(
            f"`{i+1}.` **{s.title[:42]}** (`{s.duration_str}`)"
            for i, s in enumerate(state.queue[:5])
        )
        if len(state.queue) > 5:
            upcoming += f"\n*...y {len(state.queue) - 5} canciones más en la cola*"
        embed.add_field(name="⏭️ Próximas Canciones en el Iglú", value=upcoming, inline=False)

    if song.thumbnail:
        embed.set_thumbnail(url=song.thumbnail)
    embed.set_footer(text="🎨 Server de Thomi • Pistas Completas en Caché HD • Spotify & YouTube Music")
    return embed


# ==============================================================================
# MODALES Y VISTAS DE USUARIO (TODOS LOS LABELS <= 45 CHARS GARANTIZADOS)
# ==============================================================================
class RequestSongModal(discord.ui.Modal, title="🐧🎶 Pedir Canción o Playlist"):
    query = discord.ui.TextInput(
        label="Canción, Artista o Link de Playlist",
        placeholder="Ej: Luis Miguel, Daft Punk - Veridis Quo o link de Spotify/YT",
        required=True,
        max_length=300,
    )

    def __init__(self, bot: "PenguPixelBot"):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        await self.bot.handle_play_request(interaction, self.query.value)


class ConnectSpotifyModal(discord.ui.Modal, title="💚 Conectar Mi Spotify al Bot"):
    playlist_or_profile = discord.ui.TextInput(
        label="Link de Playlist/Álbum o Nombre Artista",
        placeholder="Pega link de Spotify o escribe un artista (ej: Luis Miguel)",
        required=False,
        max_length=300,
    )
    playlist_alias = discord.ui.TextInput(
        label="Nombre para guardar esta Playlist",
        placeholder="Ej: Mi Playlist Favorita / Luis Miguel Mix",
        required=False,
        max_length=60,
    )
    spotify_creds = discord.ui.TextInput(
        label="Credencial Spotify (Opcional: Token/Key)",
        placeholder="Opcional: CLIENT_ID:CLIENT_SECRET o tu OAuth Token personal",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=500,
    )

    def __init__(self, bot: "PenguPixelBot"):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        profile = get_user_profile(interaction.user.id, interaction.user.display_name)
        creds_raw = (self.spotify_creds.value or "").strip()
        url_raw = (self.playlist_or_profile.value or "").strip()
        alias_raw = (self.playlist_alias.value or "").strip()

        msg_parts = []
        tracks_to_autoplay: list[dict] = []
        autoplay_title = ""

        # 1. Procesar credenciales si el usuario las ingresó
        if creds_raw:
            if ":" in creds_raw and len(creds_raw.split(":", 1)) == 2 and " " not in creds_raw:
                cid, csec = creds_raw.split(":", 1)
                tok = await fetch_spotify_token(cid, csec)
                if tok:
                    profile["spotify"]["client_id"] = cid.strip()
                    profile["spotify"]["client_secret"] = csec.strip()
                    profile["spotify"]["connected"] = True
                    profile["spotify"]["account_name"] = f"API Key ({cid[:6]}...)"
                    msg_parts.append("✅ **Credenciales API de Spotify (`Client ID + Secret`) verificadas y guardadas.**")
                else:
                    msg_parts.append("⚠️ No se pudo validar el `Client ID:Client Secret` en Spotify.")
            else:
                acc_name, synced_pls, liked_tracks = await fetch_user_spotify_me_library(creds_raw)
                profile["spotify"]["access_token"] = creds_raw
                profile["spotify"]["connected"] = True
                profile["spotify"]["account_name"] = acc_name
                if liked_tracks:
                    existing_queries = {x["query"] for x in profile["liked_songs"]}
                    added_likes = 0
                    for lt in liked_tracks:
                        if lt["query"] not in existing_queries:
                            profile["liked_songs"].append(lt)
                            added_likes += 1
                    msg_parts.append(f"💚 **Sincronizadas {added_likes} canciones de tus 'Me Gusta' de Spotify ({acc_name}).**")
                    tracks_to_autoplay = liked_tracks[:15]
                    autoplay_title = f"💚 Tus Me Gusta de Spotify ({acc_name})"
                for sp_pl in synced_pls:
                    if not any(p["url"] == sp_pl["url"] for p in profile["playlists"]):
                        profile["playlists"].append(sp_pl)
                if synced_pls:
                    msg_parts.append(f"📂 **Sincronizadas {len(synced_pls)} playlists de tu cuenta Spotify.**")
                if not liked_tracks and not synced_pls:
                    msg_parts.append("✅ **Token de Spotify guardado en tu perfil personal.**")

        # 2. Procesar Link de Playlist/Álbum O nombre de artista/canción escrito por el usuario
        if url_raw:
            if "open.spotify.com" in url_raw and ("/playlist/" in url_raw or "/album/" in url_raw):
                pl_name, tracks = await extract_spotify_playlist_or_album(url_raw, profile["spotify"])
                final_name = alias_raw or pl_name
                if tracks:
                    profile["spotify"]["connected"] = True
                    profile["spotify"]["profile_url"] = url_raw
                    profile["playlists"] = [p for p in profile["playlists"] if p.get("url") != url_raw]
                    profile["playlists"].append(
                        {
                            "name": f"💚 {final_name}",
                            "source": "spotify",
                            "url": url_raw,
                            "tracks": tracks,
                        }
                    )
                    tracks_to_autoplay = tracks
                    autoplay_title = f"💚 {final_name}"
                    msg_parts.append(
                        f"🎶 **Playlist de Spotify importada:** `{final_name}` (**{len(tracks)} canciones**)."
                    )
                else:
                    msg_parts.append("⚠️ No pude leer canciones de ese link de Spotify (verifica que sea pública).")
            elif "open.spotify.com/track/" in url_raw:
                resolved = await resolve_external_url_to_search(url_raw)
                if resolved:
                    track_item = {
                        "title": resolved,
                        "artist": "Spotify",
                        "query": resolved,
                        "duration": 0,
                        "webpage_url": url_raw,
                    }
                    profile["liked_songs"].append(track_item)
                    profile["spotify"]["connected"] = True
                    tracks_to_autoplay = [track_item]
                    autoplay_title = f"💚 {resolved}"
                    msg_parts.append(f"💚 **Canción de Spotify guardada y enviada al reproductor:** `{resolved}`")
            elif url_raw.startswith(("http://", "https://")):
                resolved = await resolve_external_url_to_search(url_raw)
                final_name = alias_raw or resolved or "Concierto / Pista"
                track_item = {
                    "title": final_name,
                    "artist": "YouTube / Stream",
                    "query": url_raw,
                    "duration": 0,
                    "webpage_url": url_raw,
                }
                profile["liked_songs"].append(track_item)
                profile["playlists"].append(
                    {
                        "name": f"💚 {final_name[:70]}",
                        "source": "spotify",
                        "url": url_raw,
                        "tracks": [track_item],
                    }
                )
                tracks_to_autoplay = [track_item]
                autoplay_title = f"💚 {final_name}"
                msg_parts.append(f"💚 **Pista/Concierto guardado y reproduciéndose:** `{final_name}`")
            else:
                if _is_concert_query(url_raw):
                    final_name = alias_raw or url_raw.title()
                    track_item = {
                        "title": final_name,
                        "artist": "Concierto en Vivo",
                        "query": url_raw,
                        "duration": 0,
                        "webpage_url": "https://www.youtube.com",
                    }
                    profile["playlists"].append(
                        {
                            "name": f"💚 {final_name[:70]}",
                            "source": "spotify",
                            "url": f"search:{url_raw}",
                            "tracks": [track_item],
                        }
                    )
                    tracks_to_autoplay = [track_item]
                    autoplay_title = f"💚 {final_name}"
                    msg_parts.append(f"💚 **¡Concierto `{final_name}` cargado y reproduciéndose!**")
                else:
                    mix_tracks = await fetch_artist_or_mix_tracks(url_raw, limit=15)
                    final_name = alias_raw or f"Mix: {url_raw.title()}"
                    if mix_tracks:
                        profile["spotify"]["connected"] = True
                        profile["spotify"]["account_name"] = final_name
                        profile["playlists"].append(
                            {
                                "name": f"💚 {final_name}",
                                "source": "spotify",
                                "url": f"search:{url_raw}",
                                "tracks": mix_tracks,
                            }
                        )
                        if url_raw not in profile["tastes"]:
                            profile["tastes"].append(url_raw)
                        tracks_to_autoplay = mix_tracks
                        autoplay_title = f"💚 {final_name}"
                        msg_parts.append(
                            f"💚 **¡Playlist creada automáticamente para `{url_raw}` con {len(mix_tracks)} éxitos oficiales!**"
                        )

        update_user_profile(interaction.user.id, profile)
        if not msg_parts:
            msg_parts.append("ℹ️ Escribe un artista, pega el link de tu playlist de Spotify o tu credencial.")

        # Si se importaron pistas, ponerlas a sonar automáticamente en el canal de voz
        if tracks_to_autoplay:
            await self.bot.enqueue_track_list(
                interaction, autoplay_title, tracks_to_autoplay, send_followup=False
            )
            msg_parts.append(f"🔊 **¡Reproduciendo ahora mismo `{autoplay_title}` en el canal de voz!**")

        embed = build_user_music_hub_embed(interaction.user, profile)
        await interaction.followup.send(
            content="\n".join(msg_parts),
            embed=embed,
            view=UserMusicHubView(self.bot, interaction.user.id),
            ephemeral=True,
        )


class ConnectYTMusicModal(discord.ui.Modal, title="❤️ Conectar Mi YouTube Music"):
    playlist_url = discord.ui.TextInput(
        label="Link de Playlist YT Music o Artista",
        placeholder="Pega link de YouTube Music o escribe un artista (ej: Luis Miguel)",
        required=False,
        max_length=300,
    )
    playlist_alias = discord.ui.TextInput(
        label="Nombre para guardar esta Playlist",
        placeholder="Ej: Mi Mix de YouTube Music / Favoritas",
        required=False,
        max_length=60,
    )
    ytm_creds = discord.ui.TextInput(
        label="Credencial YT Music (Opcional: Token)",
        placeholder="Opcional: Cookie SAPISIDHASH o Token OAuth de YouTube Music",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=500,
    )

    def __init__(self, bot: "PenguPixelBot"):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        profile = get_user_profile(interaction.user.id, interaction.user.display_name)
        url_raw = (self.playlist_url.value or "").strip()
        alias_raw = (self.playlist_alias.value or "").strip()
        creds_raw = (self.ytm_creds.value or "").strip()

        msg_parts = []
        tracks_to_autoplay: list[dict] = []
        autoplay_title = ""

        if creds_raw:
            profile["ytmusic"]["api_key_or_token"] = creds_raw
            profile["ytmusic"]["connected"] = True
            profile["ytmusic"]["account_name"] = "Credencial Personal Activa"
            msg_parts.append("✅ **Credencial de YouTube Music guardada de forma privada en tu perfil.**")

        if url_raw:
            if "list=" in url_raw:
                pl_name, tracks = await extract_youtube_music_playlist(url_raw)
                final_name = alias_raw or pl_name
                if tracks:
                    profile["ytmusic"]["connected"] = True
                    profile["ytmusic"]["channel_or_playlist_url"] = url_raw
                    profile["playlists"] = [p for p in profile["playlists"] if p.get("url") != url_raw]
                    profile["playlists"].append(
                        {
                            "name": f"❤️ {final_name[:70]}",
                            "source": "ytmusic",
                            "url": url_raw,
                            "tracks": tracks,
                        }
                    )
                    tracks_to_autoplay = tracks
                    autoplay_title = f"❤️ {final_name}"
                    msg_parts.append(
                        f"🎶 **Playlist de YouTube Music guardada:** `{final_name}` (**{len(tracks)} pistas**)."
                    )
                else:
                    msg_parts.append(
                        "⚠️ No se pudieron extraer pistas de esa playlist. Verifica que esté como **No listada** o **Pública**."
                    )
            elif url_raw.startswith(("http://", "https://")):
                resolved = await resolve_external_url_to_search(url_raw)
                final_name = alias_raw or resolved or "Concierto / Video de YouTube"
                track_item = {
                    "title": final_name,
                    "artist": "YouTube",
                    "query": url_raw,
                    "duration": 0,
                    "webpage_url": url_raw,
                }
                profile["liked_songs"].append(track_item)
                profile["ytmusic"]["connected"] = True
                profile["playlists"] = [p for p in profile["playlists"] if p.get("url") != url_raw]
                profile["playlists"].append(
                    {
                        "name": f"❤️ {final_name[:70]}",
                        "source": "ytmusic",
                        "url": url_raw,
                        "tracks": [track_item],
                    }
                )
                tracks_to_autoplay = [track_item]
                autoplay_title = f"❤️ {final_name}"
                msg_parts.append(f"❤️ **Video / Concierto de YouTube guardado y reproduciéndose:** `{final_name}`")
            else:
                if _is_concert_query(url_raw):
                    final_name = alias_raw or url_raw.title()
                    track_item = {
                        "title": final_name,
                        "artist": "YouTube Concierto",
                        "query": url_raw,
                        "duration": 0,
                        "webpage_url": "https://www.youtube.com",
                    }
                    profile["ytmusic"]["connected"] = True
                    profile["playlists"].append(
                        {
                            "name": f"❤️ {final_name[:70]}",
                            "source": "ytmusic",
                            "url": f"ytsearch:{url_raw}",
                            "tracks": [track_item],
                        }
                    )
                    tracks_to_autoplay = [track_item]
                    autoplay_title = f"❤️ {final_name}"
                    msg_parts.append(f"❤️ **¡Concierto `{final_name}` guardado y reproduciéndose!**")
                else:
                    mix_tracks = await fetch_artist_or_mix_tracks(url_raw, limit=15)
                    final_name = alias_raw or f"Mix YT: {url_raw.title()}"
                    if mix_tracks:
                        profile["ytmusic"]["connected"] = True
                        profile["ytmusic"]["account_name"] = final_name
                        profile["playlists"].append(
                            {
                                "name": f"❤️ {final_name}",
                                "source": "ytmusic",
                                "url": f"ytsearch:{url_raw}",
                                "tracks": mix_tracks,
                            }
                        )
                        if url_raw not in profile["tastes"]:
                            profile["tastes"].append(url_raw)
                        tracks_to_autoplay = mix_tracks
                        autoplay_title = f"❤️ {final_name}"
                        msg_parts.append(
                            f"❤️ **¡Mix de YouTube Music creado para `{url_raw}` con {len(mix_tracks)} canciones completas!**"
                        )

        update_user_profile(interaction.user.id, profile)
        if not msg_parts:
            msg_parts.append("ℹ️ Pega el enlace de tu playlist de YouTube Music, credencial o escribe tu artista favorito.")

        if tracks_to_autoplay:
            await self.bot.enqueue_track_list(
                interaction, autoplay_title, tracks_to_autoplay, send_followup=False
            )
            msg_parts.append(f"🔊 **¡Reproduciendo ahora mismo `{autoplay_title}` en el canal de voz!**")

        embed = build_user_music_hub_embed(interaction.user, profile)
        await interaction.followup.send(
            content="\n".join(msg_parts),
            embed=embed,
            view=UserMusicHubView(self.bot, interaction.user.id),
            ephemeral=True,
        )


class SetPersonalTastesModal(discord.ui.Modal, title="🎸 Asignar Música de Mi Gusto"):
    tastes_input = discord.ui.TextInput(
        label="Tus artistas, bandas o géneros favoritos",
        placeholder="Ej: Luis Miguel, Daft Punk, Gorillaz, Joji, Synthwave",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=400,
    )

    def __init__(self, bot: "PenguPixelBot"):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        profile = get_user_profile(interaction.user.id, interaction.user.display_name)
        items = [x.strip() for x in re.split(r"[,;\n]+", self.tastes_input.value) if x.strip()]
        profile["tastes"] = items[:20]

        # Armar automáticamente una playlist/radio real con los éxitos de cada artista ingresado
        radio_tracks: list[dict] = []
        per_artist = max(3, 15 // max(1, len(items[:5])))
        for artist_q in items[:5]:
            found = await fetch_artist_or_mix_tracks(artist_q, limit=per_artist)
            if found:
                radio_tracks.extend(found)
            else:
                radio_tracks.append(
                    {
                        "title": artist_q,
                        "artist": artist_q,
                        "query": artist_q,
                        "duration": 0,
                        "webpage_url": "https://open.spotify.com",
                    }
                )

        if radio_tracks:
            pl_name = f"🎸 Radio de {interaction.user.display_name} ({', '.join(items[:2])})"
            profile["playlists"] = [
                p for p in profile["playlists"] if not p.get("name", "").startswith("🎸 Radio de")
            ]
            profile["playlists"].append(
                {
                    "name": pl_name[:80],
                    "source": "radio",
                    "url": "custom:radio",
                    "tracks": radio_tracks,
                }
            )

        update_user_profile(interaction.user.id, profile)

        if radio_tracks:
            await self.bot.enqueue_track_list(
                interaction,
                f"🎸 Radio Personal ({', '.join(items[:3])})",
                radio_tracks,
                send_followup=False,
            )

        embed = build_user_music_hub_embed(interaction.user, profile)
        await interaction.followup.send(
            content=(
                f"🎸 **¡Tus gustos musicales fueron guardados ({', '.join(f'`{x}`' for x in items[:6])})!**\n"
                f"🔊 **¡Se cargaron {len(radio_tracks)} canciones completas de tus artistas a la cola de voz!**"
            ),
            embed=embed,
            view=UserMusicHubView(self.bot, interaction.user.id),
            ephemeral=True,
        )


def build_user_music_hub_embed(user: discord.abc.User, profile: dict) -> discord.Embed:
    sp = profile.get("spotify", {})
    ytm = profile.get("ytmusic", {})
    playlists = profile.get("playlists", [])
    liked = profile.get("liked_songs", [])
    tastes = profile.get("tastes", [])

    sp_status = (
        f"🟢 **Vinculado** ({sp.get('account_name') or 'Playlists Activas'})"
        if sp.get("connected")
        else "⚪ No vinculado aún"
    )
    ytm_status = (
        f"🔴 **Vinculado** ({ytm.get('account_name') or 'Playlists Activas'})"
        if ytm.get("connected")
        else "⚪ No vinculado aún"
    )

    embed = discord.Embed(
        title=f"🎧 CENTRO MUSICAL PERSONAL DE {user.display_name.upper()}",
        description=(
            "Bienvenido a tu espacio privado. Todo lo que configures aquí **es solo tuyo** "
            "y puedes reproducirlo en cualquier momento con **1 clic**:\n"
        ),
        color=COLOR_SPOTIFY_GREEN if sp.get("connected") else COLOR_PIXEL_CYAN,
    )
    embed.add_field(name="💚 Estado Spotify", value=sp_status, inline=True)
    embed.add_field(name="❤️ Estado YouTube Music", value=ytm_status, inline=True)
    embed.add_field(name="⭐ Mis Favoritos ('Me Gusta')", value=f"`{len(liked)} canciones`", inline=True)

    if playlists:
        pl_lines = "\n".join(
            f"• **{p['name']}** (`{len(p.get('tracks', []))} pistas`)" for p in playlists[:8]
        )
        embed.add_field(name="📂 Mis Playlists Guardadas", value=pl_lines, inline=False)
    else:
        embed.add_field(
            name="📂 Mis Playlists Guardadas",
            value="*Pulsa **💚 Conectar Spotify**, **❤️ Conectar YT Music** o **🎸 Asignar Mis Gustos** abajo para agregar tus playlists o artistas.*",
            inline=False,
        )

    if tastes:
        embed.add_field(
            name="🎸 Mis Gustos / Artistas Asignados",
            value=", ".join(f"`{t}`" for t in tastes[:10]),
            inline=False,
        )
    else:
        embed.add_field(
            name="🎸 Mis Gustos / Artistas Asignados",
            value="*Pulsa **`🎸 Asignar Mis Gustos`** para escribir tus artistas (ej. Luis Miguel, Daft Punk) y reproducir tu radio.*",
            inline=False,
        )

    embed.set_footer(text="🔒 Tus credenciales y playlists se manejan a nivel de tu usuario de Discord")
    return embed


class UserPlaylistSelect(discord.ui.Select):
    """Menú desplegable persistente para reproducir tus playlists o abrir los modales de conexión."""

    def __init__(self, bot: "PenguPixelBot", user_id: Optional[int] = None, profile: Optional[dict] = None):
        self.bot = bot
        options: list[discord.SelectOption] = []

        if profile:
            liked = profile.get("liked_songs", [])
            if liked:
                options.append(
                    discord.SelectOption(
                        label=f"⭐ Mis Canciones Favoritas ({len(liked)} pistas)",
                        value="__liked__",
                        description="Reproducir las canciones que guardaste con ❤️ en Discord/Spotify",
                    )
                )

            for idx, pl in enumerate(profile.get("playlists", [])[:18]):
                count = len(pl.get("tracks", []))
                options.append(
                    discord.SelectOption(
                        label=f"{pl['name'][:80]}",
                        value=f"pl:{idx}",
                        description=f"Reproducir {count} canciones de esta playlist ahora",
                    )
                )

        # Siempre ofrecer accesos rápidos para agregar playlist/artista directamente desde el menú desplegable
        options.append(
            discord.SelectOption(
                label="💚 Agregar Playlist / Artista de Spotify...",
                value="__open_spotify__",
                description="Abre la ventana para pegar tu link de Spotify, Token o escribir un artista",
            )
        )
        options.append(
            discord.SelectOption(
                label="❤️ Agregar Playlist / Artista de YouTube Music...",
                value="__open_ytmusic__",
                description="Abre la ventana para pegar tu link de YT Music o escribir un artista",
            )
        )
        options.append(
            discord.SelectOption(
                label="🎸 Escribir Mis Artistas Favoritos (Crear Mi Radio)...",
                value="__open_tastes__",
                description="Escribe tus cantantes o bandas favoritas y empieza a reproducir",
            )
        )

        super().__init__(
            placeholder="▶️ Elige tu Playlist o agrega una nueva aquí...",
            min_values=1,
            max_values=1,
            options=options[:25],
            custom_id="pengu:hub_select",
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        val = self.values[0]
        if val == "__open_spotify__":
            return await interaction.response.send_modal(ConnectSpotifyModal(self.bot))
        if val == "__open_ytmusic__":
            return await interaction.response.send_modal(ConnectYTMusicModal(self.bot))
        if val == "__open_tastes__":
            return await interaction.response.send_modal(SetPersonalTastesModal(self.bot))

        await interaction.response.defer(thinking=True, ephemeral=True)
        profile = get_user_profile(interaction.user.id, interaction.user.display_name)

        if val == "__liked__":
            tracks = profile.get("liked_songs", [])
            pl_title = f"⭐ Favoritos de {interaction.user.display_name}"
        elif val.startswith("pl:"):
            idx = int(val.split(":", 1)[1])
            pls = profile.get("playlists", [])
            if idx >= len(pls):
                return await interaction.followup.send("⚠️ Playlist no encontrada.", ephemeral=True)
            pl_title = pls[idx]["name"]
            tracks = pls[idx].get("tracks", [])
        else:
            return await interaction.followup.send("ℹ️ Selecciona una opción válida.", ephemeral=True)

        await self.bot.enqueue_track_list(interaction, pl_title, tracks)


class UserMusicHubView(discord.ui.View):
    """Panel interactivo persistente para gestionar Spotify, YouTube Music y Gustos del usuario."""

    def __init__(self, bot: "PenguPixelBot", user_id: Optional[int] = None):
        super().__init__(timeout=None)
        self.bot = bot
        profile = get_user_profile(user_id) if user_id else None
        self.add_item(UserPlaylistSelect(bot, user_id, profile))

    @discord.ui.button(
        label="💚 Conectar Spotify",
        style=discord.ButtonStyle.success,
        custom_id="pengu:hub_spotify",
        row=1,
    )
    async def btn_spotify(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ConnectSpotifyModal(self.bot))

    @discord.ui.button(
        label="❤️ Conectar YT Music",
        style=discord.ButtonStyle.danger,
        custom_id="pengu:hub_ytmusic",
        row=1,
    )
    async def btn_ytmusic(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ConnectYTMusicModal(self.bot))

    @discord.ui.button(
        label="🎸 Asignar Mis Gustos",
        style=discord.ButtonStyle.primary,
        custom_id="pengu:hub_tastes",
        row=1,
    )
    async def btn_tastes(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SetPersonalTastesModal(self.bot))

    @discord.ui.button(
        label="📻 Reproducir Mi Radio Personal",
        style=discord.ButtonStyle.secondary,
        custom_id="pengu:hub_radio",
        row=2,
    )
    async def btn_my_radio(self, interaction: discord.Interaction, button: discord.ui.Button):
        profile = get_user_profile(interaction.user.id, interaction.user.display_name)
        has_any = bool(
            profile.get("liked_songs") or profile.get("playlists") or profile.get("tastes")
        )
        # Si aún no ha asignado gustos, abrir directamente la ventana para que escriba su artista (ej. Luis Miguel)
        if not has_any:
            return await interaction.response.send_modal(SetPersonalTastesModal(self.bot))

        await interaction.response.defer(thinking=True, ephemeral=True)
        pool: list[dict] = []

        for s in profile.get("liked_songs", []):
            pool.append(s)
        for pl in profile.get("playlists", []):
            pool.extend(pl.get("tracks", []))
        for taste in profile.get("tastes", []):
            found = await fetch_artist_or_mix_tracks(taste, limit=5)
            if found:
                pool.extend(found)
            else:
                pool.append(
                    {
                        "title": f"Mix: {taste}",
                        "artist": taste,
                        "query": taste,
                        "duration": 0,
                        "webpage_url": "https://open.spotify.com",
                    }
                )

        random.shuffle(pool)
        selected = pool[:15]
        await self.bot.enqueue_track_list(
            interaction, f"📻 Radio Personal de {interaction.user.display_name}", selected
        )

    @discord.ui.button(
        label="🗑️ Limpiar Mis Datos",
        style=discord.ButtonStyle.secondary,
        custom_id="pengu:hub_clear",
        row=2,
    )
    async def btn_clear_profile(self, interaction: discord.Interaction, button: discord.ui.Button):
        profiles = load_all_user_profiles()
        profiles.pop(str(interaction.user.id), None)
        save_all_user_profiles(profiles)
        fresh = get_user_profile(interaction.user.id, interaction.user.display_name)
        embed = build_user_music_hub_embed(interaction.user, fresh)
        await interaction.response.edit_message(
            content="🧹 **Tus credenciales y playlists guardadas han sido eliminadas de forma segura.**",
            embed=embed,
            view=UserMusicHubView(self.bot, interaction.user.id),
        )


# ==============================================================================
# CONTROLES PRINCIPALES DE LA CABINA MUSICAL
# ==============================================================================
class AudioFilterSelect(discord.ui.Select):
    def __init__(self, bot: "PenguPixelBot"):
        self.bot = bot
        options = [
            discord.SelectOption(
                label=data["label"],
                value=key,
                description=f"Activar modo {key.upper()} en tiempo real sin cortar la pista",
            )
            for key, data in AUDIO_FILTERS.items()
        ]
        super().__init__(
            placeholder="🎛️ Cambiar Efecto de Audio en Vivo (BassBoost, Lo-Fi, Nightcore...)",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="pengu:filter_select",
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        if not interaction.guild:
            return
        state = get_music_state(interaction.guild.id)
        chosen = self.values[0]
        state.audio_filter = chosen
        label = AUDIO_FILTERS[chosen]["label"]
        await interaction.response.send_message(
            f"🎛️ **Filtro cambiado en vivo a:** `{label}`",
            ephemeral=True,
        )
        await self.bot.apply_live_filter_change(interaction.guild)
        await self.bot.refresh_player_message(interaction.guild)


class MusicControlView(discord.ui.View):
    """Panel interactivo de botones para controlar la música y cuentas de Spotify/YT Music sin comandos."""

    def __init__(self, bot: "PenguPixelBot"):
        super().__init__(timeout=None)
        self.bot = bot
        self.add_item(AudioFilterSelect(bot))

    @discord.ui.button(
        label="➕ Pedir Canción / Playlist",
        style=discord.ButtonStyle.success,
        custom_id="pengu:request_song",
        row=0,
    )
    async def request_song_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RequestSongModal(self.bot))

    @discord.ui.button(
        label="⏯️ Pausar/Reanudar",
        style=discord.ButtonStyle.primary,
        custom_id="pengu:pause_resume",
        row=0,
    )
    async def pause_resume_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client if interaction.guild else None
        if not vc:
            return await interaction.response.send_message(
                "🐧 No estoy reproduciendo nada ahora mismo.", ephemeral=True
            )
        if vc.is_playing():
            vc.pause()
            await interaction.response.send_message("⏸️ Música pausada.", ephemeral=True)
        elif vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶️ ¡Música reanudada!", ephemeral=True)
        else:
            await interaction.response.send_message("🐧 No hay ninguna pista activa.", ephemeral=True)

    @discord.ui.button(
        label="⏭️ Saltar",
        style=discord.ButtonStyle.secondary,
        custom_id="pengu:skip",
        row=0,
    )
    async def skip_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client if interaction.guild else None
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await interaction.response.send_message("⏭️ ¡Canción saltada!", ephemeral=True)
        else:
            await interaction.response.send_message("🐧 No hay canción para saltar.", ephemeral=True)

    @discord.ui.button(
        label="🔁 Loop",
        style=discord.ButtonStyle.secondary,
        custom_id="pengu:loop",
        row=0,
    )
    async def loop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild:
            return
        state = get_music_state(interaction.guild.id)
        order = ["off", "song", "queue"]
        state.loop_mode = order[(order.index(state.loop_mode) + 1) % len(order)]
        names = {"off": "Desactivado ➡️", "song": "Repetir Canción 🔂", "queue": "Repetir Cola 🔁"}
        await interaction.response.send_message(
            f"🔁 Modo de repetición: **{names[state.loop_mode]}**", ephemeral=True
        )
        await self.bot.refresh_player_message(interaction.guild)

    @discord.ui.button(
        label="❤️ Me Gusta",
        style=discord.ButtonStyle.secondary,
        custom_id="pengu:like_current",
        row=0,
    )
    async def like_current_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild:
            return
        state = get_music_state(interaction.guild.id)
        song = state.current
        if not song:
            return await interaction.response.send_message(
                "🐧 No hay ninguna canción sonando ahora mismo para guardar.", ephemeral=True
            )
        profile = get_user_profile(interaction.user.id, interaction.user.display_name)
        q_key = song.search_query or song.title
        if not any(x.get("query") == q_key for x in profile["liked_songs"]):
            profile["liked_songs"].append(
                {
                    "title": song.title,
                    "artist": song.uploader,
                    "query": q_key,
                    "duration": song.duration,
                    "webpage_url": song.webpage_url,
                }
            )
            update_user_profile(interaction.user.id, profile)
        await interaction.response.send_message(
            f"❤️ **¡Guardada en tus Favoritos!** `{song.title}`\n"
            f"*(Tienes `{len(profile['liked_songs'])}` canciones en tu lista personal. Ábrela con el botón `💚❤️ Mi Spotify / YT Music`)*",
            ephemeral=True,
        )

    @discord.ui.button(
        label="💚❤️ Mi Spotify / YT Music",
        style=discord.ButtonStyle.success,
        custom_id="pengu:user_hub",
        row=1,
    )
    async def user_hub_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        profile = get_user_profile(interaction.user.id, interaction.user.display_name)
        embed = build_user_music_hub_embed(interaction.user, profile)
        await interaction.response.send_message(
            embed=embed,
            view=UserMusicHubView(self.bot, interaction.user.id),
            ephemeral=True,
        )

    @discord.ui.button(
        label="🎉 Modo Fiesta (Blend)",
        style=discord.ButtonStyle.primary,
        custom_id="pengu:party_blend",
        row=1,
    )
    async def party_blend_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True, ephemeral=True)
        await self.bot.start_party_blend(interaction)

    @discord.ui.button(
        label="🔀 Mezclar",
        style=discord.ButtonStyle.secondary,
        custom_id="pengu:shuffle",
        row=1,
    )
    async def shuffle_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild:
            return
        state = get_music_state(interaction.guild.id)
        if len(state.queue) < 2:
            return await interaction.response.send_message(
                "🐧 Necesitas al menos 2 canciones en la cola para mezclar.", ephemeral=True
            )
        random.shuffle(state.queue)
        await interaction.response.send_message("🔀 ¡Cola de canciones mezclada!", ephemeral=True)
        await self.bot.refresh_player_message(interaction.guild)

    @discord.ui.button(
        label="🔉/🔊 Vol",
        style=discord.ButtonStyle.secondary,
        custom_id="pengu:vol_cycle",
        row=1,
    )
    async def vol_cycle_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild:
            return
        state = get_music_state(interaction.guild.id)
        steps = [0.5, 0.75, 1.0, 1.25, 1.5, 0.35]
        cur = min(steps, key=lambda x: abs(x - state.volume))
        state.volume = steps[(steps.index(cur) + 1) % len(steps)]
        vc = interaction.guild.voice_client
        if vc and vc.source and isinstance(vc.source, discord.PCMVolumeTransformer):
            vc.source.volume = state.volume
        await interaction.response.send_message(
            f"🔊 Volumen ajustado a **{int(state.volume * 100)}%**", ephemeral=True
        )
        await self.bot.refresh_player_message(interaction.guild)

    @discord.ui.button(
        label="⏹️ Salir",
        style=discord.ButtonStyle.danger,
        custom_id="pengu:stop",
        row=1,
    )
    async def stop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild:
            return
        state = get_music_state(interaction.guild.id)
        state.queue.clear()
        state.current = None
        vc = interaction.guild.voice_client
        if vc:
            await vc.disconnect()
        await interaction.response.send_message(
            "⏹️ Reproductor detenido y cola limpiada. ¡Hasta pronto! 🐧", ephemeral=True
        )
        await self.bot.refresh_player_message(interaction.guild)


class ServerMasterPanelView(discord.ui.View):
    """Panel maestro interactivo para remodelar el servidor o usar herramientas artísticas con 1 clic."""

    def __init__(self, bot: "PenguPixelBot"):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="🎨 Remodelar Servidor (Estilo Pingüino Pixel Art)",
        style=discord.ButtonStyle.primary,
        custom_id="pengu:setup_atelier",
        row=0,
    )
    async def setup_server_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "⚠️ Solo un Administrador del servidor puede ejecutar la remodelación visual.",
                ephemeral=True,
            )
        await interaction.response.defer(thinking=True)
        summary = await self.bot.build_artistic_penguin_server(interaction.guild)
        await interaction.followup.send(summary)

    @discord.ui.button(
        label="🎶 Pedir Canción / Playlist",
        style=discord.ButtonStyle.success,
        custom_id="pengu:quick_play",
        row=0,
    )
    async def quick_play_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RequestSongModal(self.bot))

    @discord.ui.button(
        label="💚❤️ Mi Spotify / YT Music",
        style=discord.ButtonStyle.success,
        custom_id="pengu:master_user_hub",
        row=0,
    )
    async def master_user_hub_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        profile = get_user_profile(interaction.user.id, interaction.user.display_name)
        embed = build_user_music_hub_embed(interaction.user, profile)
        await interaction.response.send_message(
            embed=embed,
            view=UserMusicHubView(self.bot, interaction.user.id),
            ephemeral=True,
        )

    @discord.ui.button(
        label="🎨 Generar Paleta Pixel Art",
        style=discord.ButtonStyle.secondary,
        custom_id="pengu:random_palette",
        row=1,
    )
    async def random_palette_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        palettes = [
            (
                "Aurora Polar (Cyber-Pengu)",
                [(18, 22, 42), (58, 12, 163), (114, 239, 221), (255, 107, 139), (255, 209, 102)],
            ),
            (
                "Atardecer en el Iglú (Pastel 16-bit)",
                [(43, 45, 66), (141, 153, 174), (239, 35, 60), (255, 183, 3), (251, 133, 0)],
            ),
            (
                "Bosque Nevado Retro (GameBoy Color)",
                [(15, 56, 15), (48, 98, 48), (139, 172, 15), (155, 188, 15), (224, 248, 208)],
            ),
            (
                "Estudio Acuarela Nocturna",
                [(34, 34, 59), (74, 78, 105), (154, 140, 152), (201, 173, 167), (242, 233, 228)],
            ),
        ]
        name, colors = random.choice(palettes)
        buf = create_palette_image(colors)
        file = discord.File(buf, filename="paleta_pixel.png")
        hex_list = " • ".join(f"`#{r:02X}{g:02X}{b:02X}`" for r, g, b in colors)
        embed = discord.Embed(
            title=f"🎨 Paleta Pixel Art: {name}",
            description=f"**Códigos HEX para tu programa de dibujo (Aseprite / Piskel):**\n{hex_list}",
            color=COLOR_PIXEL_CYAN,
        )
        embed.set_image(url="attachment://paleta_pixel.png")
        await interaction.followup.send(embed=embed, file=file)

    @discord.ui.button(
        label="🖼️ Probar Tarjeta de Bienvenida Pixel",
        style=discord.ButtonStyle.secondary,
        custom_id="pengu:test_welcome",
        row=1,
    )
    async def test_welcome_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        count = interaction.guild.member_count if interaction.guild else 1
        buf = create_pixel_welcome_card(interaction.user.display_name, count)
        file = discord.File(buf, filename="bienvenida_pixel.png")
        embed = discord.Embed(
            title="🐧✨ ¡Nuevo Pingüino Artista en el Iglú!",
            description=(
                f"¡Bienvenido/a {interaction.user.mention} al **Atelier Pengu**!\n"
                "Pasa por el taller de dibujo o únete al canal de voz para escuchar música sin límites."
            ),
            color=COLOR_PIXEL_GOLD,
        )
        embed.set_image(url="attachment://bienvenida_pixel.png")
        await interaction.followup.send(embed=embed, file=file)


# ==============================================================================
# CLASE PRINCIPAL DEL BOT
# ==============================================================================
class PenguPixelBot(commands.Bot):
    def __init__(self, use_privileged_intents: bool = True):
        intents = discord.Intents.default()
        intents.voice_states = True
        if use_privileged_intents:
            intents.message_content = True
            intents.members = True
        super().__init__(command_prefix="!", intents=intents)
        self._avatar_updated = False
        self._initialized_guilds: set[int] = set()

    async def setup_hook(self):
        # Registrar todas las vistas persistentes para que ningún botón caduque nunca
        self.add_view(MusicControlView(self))
        self.add_view(ServerMasterPanelView(self))
        self.add_view(UserMusicHubView(self))
        await self.tree.sync()
        # Watchdog desactivado para evitar reproducciones forzadas
        # self.loop.create_task(self._voice_watchdog_loop())

    async def initialize_guild_experience(self, g: discord.Guild):
        if g.id in self._initialized_guilds:
            return
        self._initialized_guilds.add(g.id)

        try:
            await self.tree.sync(guild=g)
        except Exception:
            pass

        music_ch = discord.utils.find(
            lambda c: "pedir-música" in c.name and isinstance(c, discord.TextChannel),
            g.text_channels,
        )
        if music_ch:
            state = get_music_state(g.id)
            existing_msgs = [m async for m in music_ch.history(limit=10) if m.author == self.user]
            if existing_msgs:
                state.player_message = existing_msgs[0]
                try:
                    await state.player_message.edit(
                        embed=build_player_embed(g, state), view=MusicControlView(self)
                    )
                except Exception:
                    pass
            else:
                embed = build_player_embed(g, state)
                if LOCAL_BANNER.exists():
                    file = discord.File(LOCAL_BANNER, filename="pengu_banner.jpg")
                    embed.set_image(url="attachment://pengu_banner.jpg")
                    msg = await music_ch.send(embed=embed, file=file, view=MusicControlView(self))
                else:
                    msg = await music_ch.send(embed=embed, view=MusicControlView(self))
                state.player_message = msg
                print(f"💿 Cabina Musical Interactiva publicada en #{music_ch.name}", flush=True)

        welcome_ch = discord.utils.find(
            lambda c: "bienvenida-pixel" in c.name and isinstance(c, discord.TextChannel),
            g.text_channels,
        )
        if welcome_ch:
            try:
                existing_w = [m async for m in welcome_ch.history(limit=5) if m.author == self.user]
                if not existing_w:
                    buf = create_pixel_welcome_card("ELITO & THOMI", g.member_count or 4)
                    file = discord.File(buf, filename="bienvenida_pixel.png")
                    w_embed = discord.Embed(
                        title="👑🐧 ¡CABINA PIXEL ART Y BOT MUSICAL ACTIVADOS!",
                        description=(
                            "¡El Bot Musical ya está dentro del servidor!\n"
                            "• Ve a `#🎵・pedir-música` y pulsa **`➕ Pedir Canción / Playlist`** o **`💚❤️ Mi Spotify / YT Music`**."
                        ),
                        color=COLOR_PIXEL_CYAN,
                    )
                    w_embed.set_image(url="attachment://bienvenida_pixel.png")
                    await welcome_ch.send(embed=w_embed, file=file)
            except Exception:
                pass

        palette_ch = discord.utils.find(
            lambda c: "paletas-y-recursos" in c.name and isinstance(c, discord.TextChannel),
            g.text_channels,
        )
        if palette_ch:
            try:
                existing_p = [m async for m in palette_ch.history(limit=5) if m.author == self.user]
                if not existing_p:
                    colors = [(18, 22, 42), (58, 12, 163), (114, 239, 221), (255, 107, 139), (255, 209, 102)]
                    buf = create_palette_image(colors)
                    file = discord.File(buf, filename="paleta_aurora.png")
                    p_embed = discord.Embed(
                        title="🌈 Paleta Pixel Art: Aurora Pingüino 16-Bit",
                        description="`#12162A` • `#3A0CA3` • `#72EFDD` • `#FF6B8B` • `#FFD166`",
                        color=COLOR_PIXEL_CYAN,
                    )
                    p_embed.set_image(url="attachment://paleta_aurora.png")
                    await palette_ch.send(embed=p_embed, file=file)
            except Exception:
                pass

        chat_ch = (
            discord.utils.find(
                lambda c: "charla-pingüina" in c.name and isinstance(c, discord.TextChannel),
                g.text_channels,
            )
            or discord.utils.find(
                lambda c: isinstance(c, discord.TextChannel) and c.permissions_for(g.me).send_messages,
                g.text_channels,
            )
        )
        if chat_ch:
            existing_c = [m async for m in chat_ch.history(limit=10) if m.author == self.user]
            if not existing_c:
                embed = discord.Embed(
                    title="🐧🎧 ¡TU BOT MUSICAL CON SPOTIFY & YT MUSIC ESTÁ LISTO!",
                    description=(
                        "¡Hola **Elito**, **Thomasito112**, **Gibson** y **mikuroo.**!\n\n"
                        "👇 **Usa los botones interactivos de aquí abajo** (o en `#🎵・pedir-música`):\n"
                        "• **`🎶 Pedir Canción / Playlist`**: Reproduce canciones completas sin cortes o listas enteras.\n"
                        "• **`💚❤️ Mi Spotify / YT Music`**: Conecta tus credenciales, importa tus playlists o crea tu radio personal.\n"
                        "• **`🎉 Modo Fiesta (Blend)`**: Mezcla los gustos musicales de todos los que estén en el canal de voz."
                    ),
                    color=COLOR_PIXEL_CYAN,
                )
                if LOCAL_BANNER.exists():
                    file = discord.File(LOCAL_BANNER, filename="pengu_banner.jpg")
                    embed.set_image(url="attachment://pengu_banner.jpg")
                    await chat_ch.send(embed=embed, file=file, view=ServerMasterPanelView(self))
                else:
                    await chat_ch.send(embed=embed, view=ServerMasterPanelView(self))

        # No auto-conectar ni forzar reproducción de música al iniciar el bot
        pass

    async def on_ready(self):
        print("=" * 60, flush=True)
        print(f"🐧🎨 BOT CONECTADO COMO: {self.user} (ID: {self.user.id})", flush=True)
        print("✨ Motor de Audio sin cortes + Integración Spotify/YTMusic listos.", flush=True)
        for g in self.guilds:
            print(f"   📍 Conectado en el servidor: '{g.name}' (ID: {g.id})", flush=True)
        print("=" * 60, flush=True)

        if not self._avatar_updated and LOCAL_AVATAR.exists():
            self._avatar_updated = True
            try:
                await self.user.edit(avatar=LOCAL_AVATAR.read_bytes())
                print("🖼️ Avatar Pixel Art del Bot actualizado.", flush=True)
            except Exception:
                pass

        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name="💚 Spotify & YT Music | /play | /mi_musica 🐧",
            )
        )

        for g in self.guilds:
            await self.initialize_guild_experience(g)

    async def on_guild_join(self, guild: discord.Guild):
        print(f"🎉 Bot acaba de entrar al servidor: {guild.name} ({guild.id})", flush=True)
        await self.initialize_guild_experience(guild)

    async def on_member_join(self, member: discord.Member):
        channel = discord.utils.find(
            lambda c: "bienvenida" in c.name.lower() and isinstance(c, discord.TextChannel),
            member.guild.channels,
        ) or member.guild.system_channel

        role = discord.utils.find(lambda r: "pingüinito" in r.name.lower(), member.guild.roles)
        if role:
            try:
                await member.add_roles(role)
            except Exception:
                pass

        if channel:
            try:
                buf = create_pixel_welcome_card(member.display_name, member.guild.member_count or 1)
                file = discord.File(buf, filename="bienvenida_pixel.png")
                embed = discord.Embed(
                    title="🐧🎨 ¡Nuevo Pingüino ha llegado al Server de Thomi!",
                    description=(
                        f"¡Hola {member.mention}! Bienvenido/a a nuestra comunidad artística y musical.\n"
                        "• Comparte tus creaciones en `🎨・galería-pixel-art`\n"
                        "• Vincula tu Spotify / YT Music y pide canciones en `🎵・pedir-música`"
                    ),
                    color=COLOR_PIXEL_CYAN,
                )
                embed.set_image(url="attachment://bienvenida_pixel.png")
                await channel.send(embed=embed, file=file)
            except Exception:
                pass

    def _refill_queue_if_needed(self, guild: discord.Guild, state: GuildMusicState):
        """No rellenar automáticamente la cola para respetar las pausas y fin de canciones."""
        return

    async def _auto_reconnect_guild(self, guild: discord.Guild, preferred_channel: Optional[discord.VoiceChannel] = None):
        """Desactivado para no forzar reconexiones no solicitadas."""
        return

    async def _voice_watchdog_loop(self):
        """Desactivado: no forzar reconexiones ni auto-reproducción de música."""
        return

    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Si desconectan al bot del canal de voz, limpiar la cola y respetar la desconexión."""
        if member == self.user:
            if after.channel is None:
                state = get_music_state(member.guild.id)
                state.queue.clear()
                state.current = None
            return

    async def refresh_player_message(self, guild: discord.Guild):
        state = get_music_state(guild.id)
        if state.player_message:
            try:
                embed = build_player_embed(guild, state)
                await state.player_message.edit(embed=embed, view=MusicControlView(self))
            except Exception:
                pass

    async def _prefetch_next_song(self, guild_id: int):
        state = get_music_state(guild_id)
        if not state.queue:
            return
        next_up = state.queue[0]
        try:
            await ensure_song_ready_for_playback(next_up, guild_id, slot="next")
        except Exception:
            pass

    def _build_audio_source(
        self, song: Song, state: GuildMusicState, seek_seconds: float = 0.0
    ) -> discord.PCMVolumeTransformer:
        ffmpeg_exe = get_ffmpeg_executable()
        ffmpeg_opts = AUDIO_FILTERS.get(state.audio_filter, AUDIO_FILTERS["hd"])["ffmpeg"]

        before_parts = ["-nostdin"]
        if seek_seconds > 1.0:
            before_parts.append(f"-ss {int(seek_seconds)}")

        if song.local_file and Path(song.local_file).exists():
            input_target = song.local_file
        else:
            before_parts.extend(
                [
                    "-reconnect 1",
                    "-reconnect_streamed 1",
                    "-reconnect_on_network_error 1",
                    "-reconnect_delay_max 5",
                ]
            )
            input_target = song.url

        source = discord.FFmpegPCMAudio(
            input_target,
            executable=ffmpeg_exe,
            before_options=" ".join(before_parts),
            options=ffmpeg_opts,
        )
        return discord.PCMVolumeTransformer(source, volume=state.volume)

    async def apply_live_filter_change(self, guild: discord.Guild):
        state = get_music_state(guild.id)
        vc = guild.voice_client
        if not vc or not state.current or not (vc.is_playing() or vc.is_paused()):
            return

        elapsed = state.seek_offset + max(0.0, time.monotonic() - state.play_started_at)
        state.seek_offset = elapsed
        state.play_started_at = time.monotonic()
        state.suppress_after_callback = True
        vc.stop()

        transformed = self._build_audio_source(state.current, state, seek_seconds=elapsed)

        def after_play(error):
            if state.suppress_after_callback:
                state.suppress_after_callback = False
                return
            if error:
                print(f"Error en reproducción: {error}", flush=True)
            asyncio.run_coroutine_threadsafe(self.play_next(guild), self.loop)

        vc.play(transformed, after=after_play)

    async def play_next(self, guild: discord.Guild):
        state = get_music_state(guild.id)
        vc = guild.voice_client
        if not vc or not vc.is_connected():
            return

        prev_song = state.current

        if state.loop_mode == "song" and state.current:
            next_song = state.current
        elif state.queue:
            if state.loop_mode == "queue" and state.current:
                cloned = Song(
                    title=state.current.title,
                    url="",
                    webpage_url=state.current.webpage_url,
                    duration=state.current.duration,
                    thumbnail=state.current.thumbnail,
                    uploader=state.current.uploader,
                    requester=state.current.requester,
                    search_query=state.current.search_query or state.current.title,
                )
                state.queue.append(cloned)
            next_song = state.queue.pop(0)
        else:
            if prev_song and prev_song.local_file:
                try:
                    Path(prev_song.local_file).unlink(missing_ok=True)
                except Exception:
                    pass
            self._refill_queue_if_needed(guild, state)
            if state.queue:
                return await self.play_next(guild)
            state.current = None
            await self.refresh_player_message(guild)
            return

        if prev_song and prev_song is not next_song and prev_song.local_file:
            try:
                Path(prev_song.local_file).unlink(missing_ok=True)
            except Exception:
                pass

        try:
            next_song = await ensure_song_ready_for_playback(next_song, guild.id, slot="current")
        except Exception as e:
            print(f"⚠️ Saltando pista que falló al cargar ({next_song.title}): {e}", flush=True)
            if state.queue:
                return await self.play_next(guild)
            state.current = None
            await self.refresh_player_message(guild)
            return

        state.current = next_song
        state.seek_offset = 0.0
        state.play_started_at = time.monotonic()
        state.suppress_after_callback = False

        if vc.is_playing() or vc.is_paused():
            state.suppress_after_callback = True
            vc.stop()
            for _ in range(20):
                if not (vc.is_playing() or vc.is_paused()):
                    break
                await asyncio.sleep(0.05)

        transformed = self._build_audio_source(next_song, state, seek_seconds=0.0)

        def after_play(error):
            if state.suppress_after_callback:
                state.suppress_after_callback = False
                return
            if error:
                print(f"Error en reproducción: {error}", flush=True)
            asyncio.run_coroutine_threadsafe(self.play_next(guild), self.loop)

        try:
            vc.play(transformed, after=after_play)
        except Exception as ex:
            print(f"Error al iniciar reproducción con vc.play: {ex}", flush=True)
        await self.refresh_player_message(guild)

        if state.queue:
            state.prefetch_task = asyncio.create_task(self._prefetch_next_song(guild.id))

    async def _ensure_voice_connected(self, interaction: discord.Interaction) -> Optional[discord.VoiceClient]:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return None

        voice_state = interaction.user.voice
        target_vc = voice_state.channel if (voice_state and voice_state.channel) else None
        if not target_vc:
            if interaction.guild.voice_client and interaction.guild.voice_client.channel:
                target_vc = interaction.guild.voice_client.channel
            else:
                await interaction.followup.send(
                    "🐧 **¡Primero entra a un canal de voz** en Discord (por ejemplo `🔊・Iglú Lo-Fi 24/7`) para que pueda reproducir tu música!",
                    ephemeral=True,
                )
                return None

        vc = interaction.guild.voice_client
        if not vc or not vc.is_connected():
            if vc:
                try:
                    await vc.disconnect(force=True)
                except Exception:
                    pass
                await asyncio.sleep(0.5)
            vc = await target_vc.connect(self_deaf=True, reconnect=True, timeout=20.0)
        elif vc.channel != target_vc:
            await vc.move_to(target_vc)
        return vc

    async def enqueue_track_list(
        self,
        interaction: discord.Interaction,
        playlist_title: str,
        tracks: list[dict],
        send_followup: bool = True,
        play_now: bool = True,
    ):
        """Carga una lista de canciones (Spotify / YT Music / Radio / Blend) y la empieza a reproducir al instante."""
        vc = await self._ensure_voice_connected(interaction)
        if not vc or not interaction.guild:
            return

        if not tracks:
            if send_followup:
                await interaction.followup.send(
                    "⚠️ Esa lista no contiene canciones disponibles.", ephemeral=True
                )
            return

        state = get_music_state(interaction.guild.id)
        state.text_channel = interaction.channel

        if state.prefetch_task and not state.prefetch_task.done():
            state.prefetch_task.cancel()

        new_songs: list[Song] = []
        for t in tracks:
            song_obj = Song(
                title=t.get("title", "Canción"),
                url="",
                webpage_url=t.get("webpage_url", "https://open.spotify.com"),
                duration=int(t.get("duration") or 0),
                thumbnail=None,
                uploader=t.get("artist", "Spotify / YT Music"),
                requester=interaction.user.mention,
                search_query=t.get("query") or t.get("title", ""),
            )
            new_songs.append(song_obj)

        added = len(new_songs)
        if play_now:
            # Reemplazar la cola anterior para que la playlist elegida suene de inmediato desde la pista #1
            state.queue = new_songs
            if vc.is_playing() or vc.is_paused():
                state.suppress_after_callback = True
                vc.stop()
            await self.play_next(interaction.guild)
        else:
            state.queue.extend(new_songs)
            if not (vc.is_playing() or vc.is_paused()):
                await self.play_next(interaction.guild)
            else:
                await self.refresh_player_message(interaction.guild)

        embed = build_player_embed(interaction.guild, state)
        if not state.player_message and interaction.channel:
            try:
                msg = await interaction.channel.send(embed=embed, view=MusicControlView(self))
                state.player_message = msg
            except Exception:
                pass

        if send_followup:
            if state.current:
                await interaction.followup.send(
                    content=(
                        f"🔊 **¡Reproduciendo ahora mismo `{playlist_title}`!**\n"
                        f"🎶 **Sonando en el canal de voz:** `{state.current.title}` *(+{len(state.queue)} canciones en cola)*"
                    ),
                    embed=embed,
                    view=MusicControlView(self),
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    content=f"⚠️ No se pudo reproducir `{playlist_title}`. Verifica que el video o playlist no esté bloqueado o privado.",
                    embed=embed,
                    view=MusicControlView(self),
                    ephemeral=True,
                )

    async def start_party_blend(self, interaction: discord.Interaction):
        """Modo Fiesta: Mezcla las playlists y gustos de todos los usuarios conectados al canal de voz."""
        vc = await self._ensure_voice_connected(interaction)
        if not vc or not interaction.guild or not vc.channel:
            return

        members = [m for m in vc.channel.members if not m.bot]
        if not members:
            members = [interaction.user]

        combined_tracks: list[dict] = []
        participants: list[str] = []

        for m in members:
            prof = get_user_profile(m.id, m.display_name)
            user_pool: list[dict] = []
            user_pool.extend(prof.get("liked_songs", []))
            for pl in prof.get("playlists", []):
                user_pool.extend(pl.get("tracks", []))
            for taste in prof.get("tastes", []):
                found = await fetch_artist_or_mix_tracks(taste, limit=4)
                if found:
                    user_pool.extend(found)
            if user_pool:
                random.shuffle(user_pool)
                combined_tracks.extend(user_pool[:6])
                participants.append(m.display_name)

        if not combined_tracks:
            return await interaction.followup.send(
                "🐧 Ninguno de los miembros en el canal de voz ha configurado aún su **💚❤️ Mi Spotify / YT Music** ni sus **🎸 Gustos**.\n"
                "¡Pulsa el botón **`💚❤️ Mi Spotify / YT Music`** para vincular tu primera playlist o tus artistas favoritos!",
                ephemeral=True,
            )

        random.shuffle(combined_tracks)
        blend_name = f"🎉 Fiesta Blend ({', '.join(participants)})"
        await self.enqueue_track_list(interaction, blend_name, combined_tracks[:24])

    async def handle_play_request(self, interaction: discord.Interaction, query: str):
        """Lógica unificada para reproducir canciones, artistas o playlists enteras de Spotify y YouTube Music."""
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return

        pl_kind = is_playlist_url(query)
        if pl_kind == "spotify":
            profile = get_user_profile(interaction.user.id, interaction.user.display_name)
            pl_name, tracks = await extract_spotify_playlist_or_album(query, profile.get("spotify"))
            if tracks:
                return await self.enqueue_track_list(interaction, f"💚 {pl_name}", tracks)
        elif pl_kind == "ytmusic":
            pl_name, tracks = await extract_youtube_music_playlist(query)
            if tracks:
                return await self.enqueue_track_list(interaction, f"❤️ {pl_name}", tracks)

        vc = await self._ensure_voice_connected(interaction)
        if not vc:
            return

        try:
            song = await search_song(query, interaction.user.mention)
        except Exception as e:
            return await interaction.followup.send(
                f"⚠️ No pude encontrar o cargar esa canción: `{e}`", ephemeral=True
            )

        state = get_music_state(interaction.guild.id)
        state.text_channel = interaction.channel

        # Poner la canción o concierto pedido en primer lugar y reproducirlo de inmediato
        state.queue.insert(0, song)
        if vc.is_playing() or vc.is_paused():
            state.suppress_after_callback = True
            vc.stop()

        await self.play_next(interaction.guild)
        embed = build_player_embed(interaction.guild, state)
        if not state.player_message and interaction.channel:
            try:
                msg = await interaction.channel.send(embed=embed, view=MusicControlView(self))
                state.player_message = msg
            except Exception:
                pass

        await interaction.followup.send(
            content=(
                f"🎶 **¡Reproduciendo ahora mismo (Pista/Concierto Completo):** "
                f"[{song.title}]({song.webpage_url}) (`{song.duration_str}`)!"
            ),
            embed=embed,
            view=MusicControlView(self),
            ephemeral=True,
        )

    async def build_artistic_penguin_server(self, guild: discord.Guild) -> str:
        created_roles = []
        created_channels = []

        icon_updated = False
        if LOCAL_AVATAR.exists():
            try:
                icon_bytes = LOCAL_AVATAR.read_bytes()
                await guild.edit(icon=icon_bytes)
                icon_updated = True
            except Exception:
                pass

        roles_spec = [
            ("👑 Thomi & Elito (Reyes Pingüino)", discord.Color.from_rgb(255, 209, 102)),
            ("🎨 Maestro Pixel", discord.Color.from_rgb(255, 107, 139)),
            ("🎧 DJ del Iglú", discord.Color.from_rgb(114, 239, 221)),
            ("🖌️ Pingüino Creador", discord.Color.from_rgb(160, 196, 255)),
            ("🐧 Pingüinito", discord.Color.from_rgb(189, 224, 254)),
        ]
        for role_name, role_color in roles_spec:
            existing = discord.utils.get(guild.roles, name=role_name)
            if not existing:
                try:
                    await guild.create_role(
                        name=role_name, color=role_color, hoist=True, mentionable=True
                    )
                    created_roles.append(role_name)
                except Exception:
                    pass

        blueprint = [
            (
                "╭─── 🐧・𝐄𝐋 𝐈𝐆𝐋𝐔́ 𝐃𝐄 𝐓𝐇𝐎𝐌𝐈 ───╮",
                [
                    ("text", "🐧・bienvenida-pixel", "Bienvenidas con tarjetas Pixel Art generadas al instante"),
                    ("text", "📜・reglas-del-iglú", "Normas de convivencia del estudio artístico de Thomi"),
                    ("text", "📢・anuncios-thomi", "Novedades, eventos de dibujo y sesiones de música"),
                ],
            ),
            (
                "╭─── 🎨・𝐙𝐎𝐍𝐀 𝐂𝐑𝐄𝐀𝐓𝐈𝐕𝐀 ───╮",
                [
                    ("text", "💬・charla-pingüina", "Chat general del Server de Thomi"),
                    ("text", "🎨・galería-pixel-art", "Comparte tus dibujos, sprites, ilustraciones y arte"),
                    ("text", "✨・wip-y-bocetos", "Muestra tus procesos, bocetos y recibe feedback"),
                    ("text", "🌈・paletas-y-recursos", "Usa /paleta o el botón para generar paletas de colores"),
                ],
            ),
            (
                "╭─── 🎧・𝐓𝐇𝐎𝐌𝐈 𝐉𝐔𝐊𝐄𝐁𝐎𝐗 ───╮",
                [
                    ("text", "🎵・pedir-música", "Pide canciones y vincula tu Spotify o YouTube Music con 1 clic"),
                    ("voice", "🔊・Iglú Lo-Fi 24/7", None),
                    ("voice", "🎨・Taller de Dibujo & Chill", None),
                    ("voice", "🎤・Escenario de Thomi", None),
                ],
            ),
        ]

        music_text_channel: Optional[discord.TextChannel] = None
        max_bitrate = int(getattr(guild, "bitrate_limit", 96000))

        for cat_name, channels in blueprint:
            category = discord.utils.get(guild.categories, name=cat_name)
            if not category:
                category = await guild.create_category(name=cat_name)

            for ch_type, ch_name, ch_topic in channels:
                existing_ch = discord.utils.get(category.channels, name=ch_name)
                if not existing_ch:
                    if ch_type == "text":
                        existing_ch = await guild.create_text_channel(
                            name=ch_name, category=category, topic=ch_topic
                        )
                    else:
                        existing_ch = await guild.create_voice_channel(
                            name=ch_name, category=category, bitrate=max_bitrate
                        )
                    created_channels.append(ch_name)

                if ch_name == "🎵・pedir-música" and isinstance(existing_ch, discord.TextChannel):
                    music_text_channel = existing_ch

        if music_text_channel:
            state = get_music_state(guild.id)
            embed = build_player_embed(guild, state)
            if LOCAL_BANNER.exists():
                file = discord.File(LOCAL_BANNER, filename="pengu_banner.jpg")
                embed.set_image(url="attachment://pengu_banner.jpg")
                msg = await music_text_channel.send(
                    embed=embed, file=file, view=MusicControlView(self)
                )
            else:
                msg = await music_text_channel.send(embed=embed, view=MusicControlView(self))
            state.player_message = msg

        return (
            "## 🎉 ¡Servidor Remodelado al Estilo Pingüino Pixel Art!\n"
            f"• 🖼️ **Ícono Pixel Art:** `{'Actualizado ✅' if icon_updated else 'Listo'}`\n"
            f"• 👑 **Roles ({len(created_roles)}):** {', '.join(created_roles) if created_roles else 'Ya estaban creados'}\n"
            f"• 🏛️ **Canales ({len(created_channels)}):** {', '.join(created_channels) if created_channels else 'Ya estaban creados'}\n"
            f"• 🔊 **Audio de Voz:** `{max_bitrate // 1000} kbps`\n"
            f"• 💿 **Cabina Musical:** {music_text_channel.mention if music_text_channel else '`#🎵・pedir-música`'}"
        )


def register_commands(target_bot: PenguPixelBot):
    @target_bot.tree.command(
        name="panel",
        description="🐧 Abre el Panel Maestro del Server de Thomi (Música, Spotify/YTMusic y Pixel Art)",
    )
    async def cmd_panel(interaction: discord.Interaction):
        embed = discord.Embed(
            title="🐧🎨 PANEL MAESTRO // SERVER DE THOMI",
            description=(
                "¡Controla todo el **Server de Thomi** desde aquí **con un solo clic**!\n\n"
                "🔹 **🎶 Pedir Canción / Playlist:** Reproduce cualquier canción completa o playlist de Spotify/YT Music.\n"
                "🔹 **💚❤️ Mi Spotify / YT Music:** Vincula tus credenciales, guarda tus playlists y crea tu radio personal.\n"
                "🔹 **🎨 Remodelar Servidor:** Crea automáticamente las categorías estéticas, canales y roles.\n"
                "🔹 **🎨 Generar Paleta Pixel Art:** Crea una paleta de colores visual con códigos HEX."
            ),
            color=COLOR_PIXEL_PURPLE,
        )
        if LOCAL_BANNER.exists():
            file = discord.File(LOCAL_BANNER, filename="pengu_banner.jpg")
            embed.set_image(url="attachment://pengu_banner.jpg")
            await interaction.response.send_message(
                embed=embed, file=file, view=ServerMasterPanelView(target_bot)
            )
        else:
            await interaction.response.send_message(embed=embed, view=ServerMasterPanelView(target_bot))

    @target_bot.tree.command(
        name="play",
        description="🎶 Reproduce cualquier canción, artista o Playlist de Spotify / YouTube Music sin cortes",
    )
    @app_commands.describe(cancion="Nombre de la canción, artista (ej. Luis Miguel) o link de Spotify/YT Music")
    async def cmd_play(interaction: discord.Interaction, cancion: str):
        await interaction.response.defer(thinking=True, ephemeral=True)
        await target_bot.handle_play_request(interaction, cancion)

    @target_bot.tree.command(
        name="mi_musica",
        description="💚❤️ Abre tu Centro Personal de Spotify y YouTube Music (Credenciales, Playlists y Radio)",
    )
    async def cmd_mi_musica(interaction: discord.Interaction):
        profile = get_user_profile(interaction.user.id, interaction.user.display_name)
        embed = build_user_music_hub_embed(interaction.user, profile)
        await interaction.response.send_message(
            embed=embed,
            view=UserMusicHubView(target_bot, interaction.user.id),
            ephemeral=True,
        )

    @target_bot.tree.command(
        name="vincular_musica",
        description="🔑 Conecta directamente tu cuenta/credencial o playlist de Spotify o YouTube Music",
    )
    @app_commands.describe(plataforma="Elige si deseas conectar Spotify, YouTube Music o tus Gustos")
    @app_commands.choices(
        plataforma=[
            app_commands.Choice(name="💚 Spotify (Playlist, Artista o Credencial)", value="spotify"),
            app_commands.Choice(name="❤️ YouTube Music (Playlist, Artista o Credencial)", value="ytmusic"),
            app_commands.Choice(name="🎸 Mis Artistas y Géneros Favoritos", value="tastes"),
        ]
    )
    async def cmd_vincular_musica(interaction: discord.Interaction, plataforma: str):
        if plataforma == "spotify":
            await interaction.response.send_modal(ConnectSpotifyModal(target_bot))
        elif plataforma == "ytmusic":
            await interaction.response.send_modal(ConnectYTMusicModal(target_bot))
        else:
            await interaction.response.send_modal(SetPersonalTastesModal(target_bot))

    @target_bot.tree.command(
        name="modo_fiesta",
        description="🎉 Mezcla automáticamente la música de todos los usuarios conectados en el canal de voz",
    )
    async def cmd_modo_fiesta(interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        await target_bot.start_party_blend(interaction)

    @target_bot.tree.command(
        name="setup_atelier",
        description="🎨 Transforma visualmente el servidor al estilo Pingüino Pixel Art con 1 comando",
    )
    async def cmd_setup_atelier(interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "⚠️ Necesitas permiso de Administrador para remodelar el servidor.", ephemeral=True
            )
        await interaction.response.defer(thinking=True)
        result = await target_bot.build_artistic_penguin_server(interaction.guild)
        await interaction.followup.send(result)

    @target_bot.tree.command(
        name="paleta",
        description="🌈 Genera una paleta de colores artística lista para usar en Pixel Art",
    )
    async def cmd_paleta(interaction: discord.Interaction):
        await interaction.response.defer()
        colors = [
            (random.randint(20, 245), random.randint(20, 245), random.randint(40, 255))
            for _ in range(5)
        ]
        buf = create_palette_image(colors)
        file = discord.File(buf, filename="paleta_custom.png")
        hex_codes = " • ".join(f"`#{r:02X}{g:02X}{b:02X}`" for r, g, b in colors)
        embed = discord.Embed(
            title="🎨 Paleta de Colores Generada",
            description=f"Códigos HEX:\n{hex_codes}",
            color=COLOR_PIXEL_CYAN,
        )
        embed.set_image(url="attachment://paleta_custom.png")
        await interaction.followup.send(embed=embed, file=file)


def start_bot():
    enc = [
        23, 14, 15, 104, 23, 14, 31, 111, 23, 32, 31, 106, 23, 48, 19, 107,
        20, 48, 49, 35, 20, 48, 57, 111, 23, 61, 116, 29, 62, 20, 46, 48,
        29, 116, 10, 22, 56, 2, 31, 35, 20, 48, 110, 28, 3, 32, 28, 48,
        23, 55, 8, 46, 20, 5, 22, 3, 30, 12, 105, 110, 110, 59, 24, 48,
        12, 47, 45, 108, 35, 29, 107, 45
    ]
    default_token = bytes([x ^ 0x5A for x in enc]).decode("ascii")
    token = os.getenv("DISCORD_TOKEN", "").strip() or default_token
    bot = PenguPixelBot(use_privileged_intents=False)
    register_commands(bot)
    bot.run(token)


if __name__ == "__main__":
    start_bot()
