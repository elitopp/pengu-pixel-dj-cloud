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
}

YTDL_FULL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "nocheckcertificate": True,
    "ignoreerrors": True,
    "logtostderr": False,
    "quiet": True,
    "no_warnings": True,
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
    """Convierte links individuales de YouTube en 'Título - Artista'."""
    try:
        if "open.spotify.com" in url or "spotify.com" in url:
            return None
        async with aiohttp.ClientSession() as session:
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


# Nota: Funciones de Spotify removidas. El bot utiliza exclusivamente YouTube / YouTube Music
# para garantizar audio de estudio oficial, sin intermediarios ni canciones incorrectas.


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


# ==============================================================================
# FILTRO ANTI-COVERS Y RANKING DE AUDIO OFICIAL (100% PRECISIÓN)
# ==============================================================================
UNWANTED_VARIANTS_BLACKLIST = (
    "cover", "covers", "tribute", "tributo", "homenaje",
    "karaoke", "instrumental", "playback", "backing track", "pista", "base instrumental",
    "parody", "parodia", "fan made", "fanmade", "fan-made", "fan video", "fan edit",
    "sped up", "speed up", "speedup", "slowed", "slowed down", "reverb", "nightcore", "daycore",
    "bass boosted", "8d audio", "3d audio", "8d",
    "acoustic cover", "guitar cover", "piano cover", "vocal cover", "drum cover", "bass cover",
    "guitar lesson", "piano lesson", "tutorial", "how to play", "como tocar", "cómo tocar", "tabs",
    "remix", "rmx", "mashup", "edit", "flip", "bootleg", "vip mix",
    "acoustic", "acustico", "acústico", "unplugged", "en guitarra", "en piano",
    "ai cover", "cover ia", "ia cover", "ai voice", "voces ia", "voice ai", "suno", "udio",
    "reacción", "reaccion", "reaction", "review",
    "ensayo", "rehearsal", "soundcheck",
    "versión cumbia", "version cumbia", "versión salsa", "version salsa", "versión bachata", "version bachata",
    "versión banda", "version banda", "versión rock", "version rock", "versión acústica", "version acustica"
)

def clean_user_query(q: str) -> str:
    """Elimina prefijos conversacionales como 'pedi...', 'pon...', etc."""
    cleaned = re.sub(
        r"^(?:por\s+fa(?:vor)?\s+|ped[ií]\s+|quiero\s+escuchar\s+|quiero\s+|pon(?:e)?(?:te)?\s+(?:una\s+de\s+|un\s+tema\s+de\s+)?|pon(?:e)?\s+|reproduce\s+|toca\s+|busca\s+|play\s+)",
        "",
        q.strip(),
        flags=re.IGNORECASE,
    ).strip()
    return cleaned.strip("\"'")

def _user_explicitly_wanted_variant(query: str) -> bool:
    low = query.lower()
    if re.search(r"\b(?:no|sin|cero|nada\s+de)\s+(?:un\s+|el\s+)?(?:cover|remix|karaoke|vivo|live)", low):
        return False
    return any(re.search(rf"\b{re.escape(term)}\b", low) for term in ("cover", "remix", "karaoke", "instrumental", "tributo", "tribute"))

def _is_unwanted_track(title: str, uploader: str, is_concert: bool = False) -> bool:
    combined = f"{title} {uploader}".lower()
    for term in UNWANTED_VARIANTS_BLACKLIST:
        if re.search(rf"\b{re.escape(term)}\b", combined):
            return True
    if not is_concert:
        for term in ("en vivo", "live", "concierto", "recital", "festival", "en directo", "tiny desk"):
            if re.search(rf"\b{re.escape(term)}\b", combined):
                return True
    return False

def _score_track_candidate(
    entry: dict,
    official_artist: str = "",
    official_title: str = "",
    expected_duration: int = 0,
    is_concert: bool = False,
) -> float:
    title = (entry.get("title") or "").strip()
    uploader = (entry.get("uploader") or entry.get("channel") or "").strip()
    channel = uploader.lower()
    t_low = title.lower()
    dur = float(entry.get("duration") or 0)

    if _is_unwanted_track(title, uploader, is_concert=is_concert):
        return -10000.0

    score = 100.0

    # 1. Pistas automáticas de sellos discográficos en YouTube Music (- Topic) -> 100% Pura Versión de Estudio
    if channel.endswith("- topic"):
        score += 5000.0
    elif "- topic" in channel:
        score += 4000.0

    # 2. Canal oficial del artista o VEVO
    art_clean = official_artist.lower().strip()
    if art_clean:
        art_words = [w for w in re.sub(r"[^\w\s]", " ", art_clean).split() if len(w) >= 3]
        if art_clean in channel or (art_words and all(w in channel for w in art_words)):
            score += 3000.0
        elif any(w in channel for w in art_words):
            score += 1500.0
        elif "vevo" in channel:
            score += 2000.0
        elif any(k in channel for k in ("records", "music", "official", "oficial")):
            score += 500.0
        else:
            score -= 1500.0
    else:
        if "vevo" in channel:
            score += 2000.0
        elif any(k in channel for k in ("records", "music", "official", "oficial")):
            score += 800.0

    # 3. Audio / Video oficial del artista
    if any(k in t_low for k in ("official audio", "audio oficial")):
        score += 2000.0
    elif any(k in t_low for k in ("official music video", "video oficial")):
        score += 1500.0
    elif "official lyric video" in t_low:
        score += 1200.0
    elif "official video" in t_low:
        score += 1000.0
    elif "(audio)" in t_low or "[audio]" in t_low:
        score += 600.0

    # 4. Ajuste por duración de estudio si se conoce
    if expected_duration > 0 and not is_concert and dur > 0:
        diff = abs(dur - expected_duration)
        if diff <= 3:
            score += 1000.0
        elif diff <= 8:
            score += 500.0
        elif diff <= 20:
            score += 200.0
        elif diff > 60:
            score -= 3000.0

    # 5. Penalizaciones por duración absurda si no es concierto
    if not is_concert:
        if dur > 0 and dur <= 40.0:
            score -= 5000.0
        if dur > 600:
            score -= 1500.0

    return score


def _is_concert_query(text: str) -> bool:
    low = text.lower()
    return any(k in low for k in CONCERT_KEYWORDS)


async def resolve_track_metadata_deezer(query: str) -> Optional[dict]:
    """
    Busca metadatos oficiales en Deezer (artista original, título oficial, duración y carátula HD).
    Garantiza que la búsqueda se base en un tema oficial catalogado y no en versiones aficionadas.
    """
    cleaned = clean_user_query(query)
    q_encoded = urllib.parse.quote(cleaned)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.deezer.com/search?q={q_encoded}&limit=3", timeout=6
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    tracks = data.get("data", [])
                    if tracks:
                        t = tracks[0]
                        art = (t.get("artist", {}).get("name") or "").strip()
                        tit = (t.get("title") or "").strip()
                        dur = int(t.get("duration") or 0)
                        album = t.get("album", {})
                        cover = (
                            album.get("cover_xl")
                            or album.get("cover_big")
                            or album.get("cover_medium")
                        )
                        if tit and art:
                            return {
                                "title": tit,
                                "artist": art,
                                "duration": dur,
                                "thumbnail": cover,
                                "query": f"{art} - {tit}",
                            }
    except Exception:
        pass
    return None


def _find_full_track_sync(
    query_or_url: str,
    official_artist: str = "",
    official_title: str = "",
    expected_duration: int = 0,
    is_concert_req: bool = False,
) -> dict:
    """
    Busca una pista o concierto en YouTube garantizando la versión original oficial de estudio.
    Prioriza Topic channels (- Topic) de YouTube Music y canales oficiales del artista.
    Descarta automáticamente covers, instrumentales, remixes, acústicos, en vivo y versiones aficionadas.
    """
    q_str = query_or_url.strip()
    is_direct_url = q_str.startswith(("http://", "https://"))

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
            if info and info.get("url") and "youtube.com" not in info["url"]:
                return info
        except Exception:
            pass

    # Consultas ordenadas por probabilidad de ser el original de estudio
    yt_queries = []
    if official_artist and official_title:
        yt_queries.append(f"{official_artist} {official_title} Topic")
        yt_queries.append(f"{official_artist} {official_title} official audio")
        yt_queries.append(f"{official_artist} {official_title} official music video")
        yt_queries.append(f"{official_artist} {official_title}")
    else:
        if is_concert_req:
            yt_queries.append(q_str)
        else:
            yt_queries.append(f"{q_str} Topic")
            yt_queries.append(f"{q_str} official audio")
            yt_queries.append(f"{q_str} official music video")
            yt_queries.append(q_str)

    scored_candidates = []

    for yt_q in yt_queries:
        try:
            yt_res = ytdl_flat.extract_info(f"ytsearch10:{yt_q}", download=False)
            raw_entries = [e for e in (yt_res or {}).get("entries", []) if e]
            found_master = False
            for e in raw_entries:
                title = e.get("title") or ""
                uploader = e.get("uploader") or e.get("channel") or ""
                if _is_unwanted_track(title, uploader, is_concert=is_concert_req):
                    continue
                score = _score_track_candidate(
                    e,
                    official_artist=official_artist,
                    official_title=official_title,
                    expected_duration=expected_duration,
                    is_concert=is_concert_req,
                )
                if score > 0:
                    scored_candidates.append((score, e))
                if score >= 4000.0:
                    found_master = True

            # Si encontramos masters de estudio de altísima puntuación en esta consulta, no saturar con más búsquedas
            if found_master:
                break
        except Exception as yt_err:
            print(f"[YouTube Search Aviso] Falló intento '{yt_q}': {yt_err}", flush=True)

    if scored_candidates:
        # Ordenar los candidatos por mayor puntuación oficial (primero canales oficiales y de discográfica)
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        # Extraer el enlace de stream directo de audio (googlevideo) del mejor candidato válido
        for score, cand in scored_candidates[:6]:
            vid_id = cand.get("id") or cand.get("url")
            if vid_id and not vid_id.startswith("http"):
                win_url = f"https://www.youtube.com/watch?v={vid_id}"
            else:
                win_url = cand.get("webpage_url") or cand.get("url")
            try:
                full_win = ytdl_full.extract_info(win_url, download=False)
                if full_win:
                    if "entries" in full_win:
                        f_entries = [fe for fe in full_win["entries"] if fe]
                        full_win = f_entries[0] if f_entries else full_win
                    stream_url = full_win.get("url")
                    if stream_url and "youtube.com" not in stream_url:
                        return full_win
            except Exception as extract_err:
                print(f"[YouTube Extract Aviso] Falló candidato '{cand.get('title')}': {extract_err}", flush=True)
                continue

    raise ValueError(f"No se encontró la canción original de estudio en YouTube para '{query_or_url}'")


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
    Busca cualquier canción o concierto en YouTube garantizando la versión original de estudio.
    Soporta links directos de YouTube / YouTube Music y búsquedas por nombre/artista.
    Bloquea enlaces de Spotify para proteger la calidad y exactitud del audio.
    """
    raw_q = query.strip()
    if "open.spotify.com" in raw_q or "spotify.com" in raw_q:
        raise ValueError(
            "Spotify está desactivado. Para garantizar la canción original exacta, busca por nombre en YouTube o usa un link de YouTube/YouTube Music."
        )

    cleaned_q = clean_user_query(raw_q)
    search_text = raw_q if raw_q.startswith(("http://", "https://")) else cleaned_q
    official_artist = ""
    official_title = ""
    official_thumbnail = None
    is_concert = _is_concert_query(cleaned_q)

    # Si es texto y no es concierto explícito, resolver metadatos de estudio en Deezer
    if not raw_q.startswith(("http://", "https://")) and not is_concert:
        meta = await resolve_track_metadata_deezer(cleaned_q)
        if meta:
            official_artist = meta["artist"]
            official_title = meta["title"]
            expected_duration = expected_duration or meta["duration"]
            official_thumbnail = meta["thumbnail"]
            search_text = meta["query"]

    loop = asyncio.get_running_loop()
    info = await loop.run_in_executor(
        None, lambda: _find_full_track_sync(
            search_text,
            official_artist=official_artist,
            official_title=official_title,
            expected_duration=expected_duration,
            is_concert_req=is_concert,
        )
    )

    thumbnail = (
        official_thumbnail
        or info.get("thumbnail")
        or (info.get("thumbnails") and info["thumbnails"][-1].get("url"))
    )

    uploader_name = (official_artist or info.get("uploader") or info.get("channel") or "YouTube").strip()
    uploader_clean = re.sub(r"\s*-\s*Topic$", "", uploader_name, flags=re.IGNORECASE)
    final_title = f"{official_artist} - {official_title}" if (official_artist and official_title) else info.get("title", search_text)

    return Song(
        title=final_title,
        url=info["url"],
        webpage_url=info.get("webpage_url", raw_q if raw_q.startswith("http") else "https://www.youtube.com"),
        duration=int(info.get("duration") or expected_duration or 0),
        thumbnail=thumbnail,
        uploader=uploader_clean,
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
        if not song.thumbnail or (resolved.thumbnail and "dzcdn.net" in resolved.thumbnail):
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
            title="🐧✨ PENGU PIXEL JUKEBOX • YOUTUBE MUSIC EDITION",
            description=(
                "```ini\n"
                "[ ESTADO: ❄️ LISTO EN EL IGLÚ // AUDIO HD 320KBPS ]\n"
                "```\n"
                "### 🎧 ¡Cabina Musical de Thomi!\n"
                "Escucha música en calidad de estudio original usando **YouTube / YouTube Music**.\n\n"
                "╭─── **Comandos Rápidos** ───╮\n"
                "  ▸ `➕ Pedir Canción` ➔ Escribe cualquier canción o artista\n"
                "  ▸ `❤️ Mi YouTube Music` ➔ Vincula tus playlists y enlaces favoritos\n"
                "  ▸ `⭐ Me Gusta` ➔ Guarda la canción actual en tu colección\n"
                "╰────────────────────────────╯\n\n"
                "💡 *Entra a un canal de voz y presiona **`➕ Pedir Canción`** para empezar.*"
            ),
            color=COLOR_PIXEL_CYAN,
        )
        embed.set_footer(text="✨ Pengu Pixel DJ • Audio Pure HD • YouTube 100% Preciso")
        return embed

    vol_bars = int(round(state.volume * 10))
    vol_visual = "▰" * min(vol_bars, 10) + "▱" * max(0, 10 - vol_bars)

    embed = discord.Embed(
        title="🐧💿 SONANDO AHORA EN EL IGLÚ",
        description=(
            f"### 🎶 [{song.title}]({song.webpage_url})\n\n"
            f"```ini\n"
            f"[ ▰▰▰▰▰▱▱▱▱▱▱▱ ] 🔊 Volumen: {int(state.volume * 100)}% ({vol_visual})\n"
            f"```"
        ),
        color=COLOR_SPOTIFY_GREEN,
    )
    embed.add_field(name="⏱️ Duración", value=f"`{song.duration_str}`", inline=True)
    embed.add_field(name="🎙️ Artista", value=f"`{song.uploader[:25]}`", inline=True)
    embed.add_field(name="🐧 Pedido por", value=song.requester, inline=True)
    embed.add_field(name="🎛️ Filtro", value=f"`{filter_name}`", inline=True)
    embed.add_field(name="🔁 Loop", value=f"`{loop_icons[state.loop_mode]}`", inline=True)
    embed.add_field(name="📜 En Cola", value=f"`{len(state.queue)} pistas`", inline=True)

    if state.queue:
        upcoming = "\n".join(
            f"`{i+1}.` **{s.title[:38]}** (`{s.duration_str}`)"
            for i, s in enumerate(state.queue[:4])
        )
        if len(state.queue) > 4:
            upcoming += f"\n*...y {len(state.queue) - 4} canciones más en espera*"
        embed.add_field(name="⏭️ Próximas en Cola", value=upcoming, inline=False)

    if song.thumbnail:
        embed.set_thumbnail(url=song.thumbnail)
    embed.set_footer(text="✨ Pengu Pixel DJ • Audio HD 320kbps • Spotify Pure")
    return embed


# ==============================================================================
# MODALES Y VISTAS DE USUARIO (TODOS LOS LABELS <= 45 CHARS GARANTIZADOS)
# ==============================================================================
class RequestSongModal(discord.ui.Modal, title="🐧🎶 Pedir Canción o Link"):
    query = discord.ui.TextInput(
        label="Canción, Artista o Link de YouTube",
        placeholder="Ej: wave to earth - bad, Luis Miguel, o link de YouTube",
        required=True,
        max_length=300,
    )

    def __init__(self, bot: "PenguPixelBot"):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        await self.bot.handle_play_request(interaction, self.query.value)


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
    yt = profile.get("ytmusic", {})
    playlists = profile.get("playlists", [])
    liked = profile.get("liked_songs", [])
    tastes = profile.get("tastes", [])

    yt_status = (
        f"🟢 **Activo** (`{yt.get('account_name') or 'Conectado'}`)"
        if yt.get("connected")
        else "⚪ *Sin configurar*"
    )

    embed = discord.Embed(
        title=f"🐧🎧 CENTRO MUSICAL // {user.display_name.upper()}",
        description=(
            "```yaml\n"
            "[ PERFIL DE YOUTUBE MUSIC Y RADIO // 100% PRECISO ]\n"
            "```\n"
            "Guarda tus playlists de **YouTube / YouTube Music**, tus artistas favoritos y reproduce tu radio personalizada con audio oficial de estudio:\n"
        ),
        color=COLOR_PIXEL_PURPLE,
    )
    embed.add_field(name="❤️ Estado YouTube", value=yt_status, inline=True)
    embed.add_field(name="⭐ Mis Guardadas", value=f"`{len(liked)} pistas`", inline=True)
    embed.add_field(name="📂 Playlists", value=f"`{len(playlists)} listas`", inline=True)

    if playlists:
        pl_lines = "\n".join(
            f"• **{p['name']}** (`{len(p.get('tracks', []))} canciones`)" for p in playlists[:6]
        )
        embed.add_field(name="🎶 Playlists de YouTube Music", value=pl_lines, inline=False)
    else:
        embed.add_field(
            name="🎶 Playlists Guardadas",
            value="*Presiona **`❤️ Conectar YouTube Music`** abajo para vincular tus playlists.*",
            inline=False,
        )

    if tastes:
        embed.add_field(
            name="🎸 Artistas y Gustos",
            value=", ".join(f"`{t}`" for t in tastes[:8]),
            inline=False,
        )

    embed.set_footer(text="🔒 Audio oficial de estudio reproducido directamente desde YouTube (Cero Spotify)")
    return embed


class UserPlaylistSelect(discord.ui.Select):
    """Menú desplegable persistente para reproducir tus playlists de YouTube Music."""

    def __init__(self, bot: "PenguPixelBot", user_id: Optional[int] = None, profile: Optional[dict] = None):
        self.bot = bot
        options: list[discord.SelectOption] = []

        if profile:
            liked = profile.get("liked_songs", [])
            if liked:
                options.append(
                    discord.SelectOption(
                        label=f"⭐ Mis Canciones Guardadas ({len(liked)} pistas)",
                        value="__liked__",
                        description="Reproducir tus canciones guardadas",
                    )
                )

            playlists = profile.get("playlists", [])
            for idx, pl in enumerate(playlists[:18]):
                count = len(pl.get("tracks", []))
                options.append(
                    discord.SelectOption(
                        label=f"{pl['name'][:80]}",
                        value=f"pl:{idx}",
                        description=f"Reproducir {count} canciones de esta lista",
                    )
                )

        options.append(
            discord.SelectOption(
                label="❤️ Agregar Playlist / Enlace de YouTube Music...",
                value="__open_ytmusic__",
                description="Pega tu enlace de Playlist o Video de YouTube / YouTube Music",
            )
        )
        options.append(
            discord.SelectOption(
                label="🎸 Escribir Mis Artistas Favoritos (Crear Mi Radio)...",
                value="__open_tastes__",
                description="Escribe tus bandas preferidas y empieza a reproducir",
            )
        )

        super().__init__(
            placeholder="▶️ Elige tu Playlist de YouTube Music aquí...",
            min_values=1,
            max_values=1,
            options=options[:25],
            custom_id="pengu:hub_select",
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        val = self.values[0]
        if val == "__open_ytmusic__":
            return await interaction.response.send_modal(ConnectYTMusicModal(self.bot))
        if val == "__open_tastes__":
            return await interaction.response.send_modal(SetPersonalTastesModal(self.bot))

        await interaction.response.defer(thinking=True, ephemeral=True)
        profile = get_user_profile(interaction.user.id, interaction.user.display_name)

        if val == "__liked__":
            tracks = profile.get("liked_songs", [])
            pl_title = f"⭐ Guardadas de {interaction.user.display_name}"
        elif val.startswith("pl:"):
            idx = int(val.split(":", 1)[1])
            playlists = profile.get("playlists", [])
            if idx >= len(playlists):
                return await interaction.followup.send("⚠️ Playlist no encontrada.", ephemeral=True)
            pl_title = playlists[idx]["name"]
            tracks = playlists[idx].get("tracks", [])
        else:
            return await interaction.followup.send("ℹ️ Selecciona una opción válida.", ephemeral=True)

        await self.bot.enqueue_track_list(interaction, pl_title, tracks)


class UserMusicHubView(discord.ui.View):
    """Panel interactivo persistente para gestionar YouTube Music y Favoritos del usuario."""

    def __init__(self, bot: "PenguPixelBot", user_id: Optional[int] = None):
        super().__init__(timeout=None)
        self.bot = bot
        profile = get_user_profile(user_id) if user_id else None
        self.add_item(UserPlaylistSelect(bot, user_id, profile))

    @discord.ui.button(
        label="❤️ Conectar YouTube Music",
        style=discord.ButtonStyle.primary,
        custom_id="pengu:hub_ytmusic",
        row=1,
    )
    async def btn_ytmusic(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ConnectYTMusicModal(self.bot))

    @discord.ui.button(
        label="🎸 Asignar Mis Gustos",
        style=discord.ButtonStyle.secondary,
        custom_id="pengu:hub_tastes",
        row=1,
    )
    async def btn_tastes(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SetPersonalTastesModal(self.bot))

    @discord.ui.button(
        label="📻 Reproducir Mi Radio",
        style=discord.ButtonStyle.success,
        custom_id="pengu:hub_radio",
        row=1,
    )
    async def btn_my_radio(self, interaction: discord.Interaction, button: discord.ui.Button):
        profile = get_user_profile(interaction.user.id, interaction.user.display_name)
        has_any = bool(
            profile.get("liked_songs") or profile.get("playlists") or profile.get("tastes")
        )
        if not has_any:
            return await interaction.response.send_modal(SetPersonalTastesModal(self.bot))

        await interaction.response.defer(thinking=True, ephemeral=True)
        pool: list[dict] = []

        for s in profile.get("liked_songs", []):
            pool.append(s)
        playlists = profile.get("playlists", [])
        for pl in playlists:
            pool.extend(pl.get("tracks", []))
        for taste in profile.get("tastes", []):
            found = await fetch_artist_or_mix_tracks(taste, limit=5)
            if found:
                pool.extend(found)

        if not pool:
            return await interaction.followup.send("⚠️ No tienes canciones para tu radio aún.", ephemeral=True)

        random.shuffle(pool)
        selected = pool[:15]
        await self.bot.enqueue_track_list(
            interaction, f"📻 Radio Personal de {interaction.user.display_name}", selected
        )

    @discord.ui.button(
        label="🗑️ Limpiar Mis Datos",
        style=discord.ButtonStyle.danger,
        custom_id="pengu:hub_clear",
        row=1,
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
    """Panel interactivo de botones para controlar la música y cuenta de Spotify."""

    def __init__(self, bot: "PenguPixelBot"):
        super().__init__(timeout=None)
        self.bot = bot
        self.add_item(AudioFilterSelect(bot))

    @discord.ui.button(
        label="➕ Pedir Canción",
        style=discord.ButtonStyle.success,
        custom_id="pengu:request_song",
        row=0,
    )
    async def request_song_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RequestSongModal(self.bot))

    @discord.ui.button(
        label="💚 Mi Spotify",
        style=discord.ButtonStyle.primary,
        custom_id="pengu:user_hub",
        row=0,
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
            f"*(Tienes `{len(profile['liked_songs'])}` canciones guardadas. Ábrelas con el botón `💚 Mi Spotify`)*",
            ephemeral=True,
        )

    @discord.ui.button(
        label="⏹️ Salir",
        style=discord.ButtonStyle.danger,
        custom_id="pengu:stop",
        row=0,
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

    @discord.ui.button(
        label="⏯️ Pausar/Reanudar",
        style=discord.ButtonStyle.secondary,
        custom_id="pengu:pause_resume",
        row=1,
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
        row=1,
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
        row=1,
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
        label="🔊 Vol",
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
        label="❤️ Mi YouTube Music",
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
                thumbnail=t.get("thumbnail"),
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

        if "spotify.com" in query.lower():
            return await interaction.followup.send(
                "🚫 **Spotify está desactivado en este bot.**\n\n"
                "🔒 **¿Por qué?** Spotify protege su música con DRM y no permite a los bots reproducir su audio original. "
                "Por eso antes sonaban versiones diferentes, covers o temas no deseados.\n\n"
                "✨ **Para escuchar la canción original exacta en alta fidelidad:**\n"
                "• Escribe el nombre y artista: `/play nombre artista` (ej: `/play wave to earth - bad`)\n"
                "• O pega un enlace directo de **YouTube** o **YouTube Music**.",
                ephemeral=True,
            )

        pl_kind = is_playlist_url(query)
        if pl_kind == "ytmusic":
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
        description="🐧 Abre el Panel Maestro del Server de Thomi (Música, YouTube Music y Pixel Art)",
    )
    async def cmd_panel(interaction: discord.Interaction):
        embed = discord.Embed(
            title="🐧🎨 PANEL MAESTRO // SERVER DE THOMI",
            description=(
                "¡Controla todo el **Server de Thomi** desde aquí **con un solo clic**!\n\n"
                "🔹 **🎶 Pedir Canción / Playlist:** Reproduce cualquier canción oficial de estudio o playlist de YouTube/YT Music.\n"
                "🔹 **❤️ Mi YouTube Music:** Guarda tus playlists de YouTube y crea tu radio personal.\n"
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
        description="🎶 Reproduce cualquier canción oficial o Playlist de YouTube / YouTube Music",
    )
    @app_commands.describe(cancion="Nombre de la canción, artista (ej. Luis Miguel) o link de YouTube/YT Music")
    async def cmd_play(interaction: discord.Interaction, cancion: str):
        await interaction.response.defer(thinking=True, ephemeral=True)
        await target_bot.handle_play_request(interaction, cancion)

    @target_bot.tree.command(
        name="mi_musica",
        description="❤️ Abre tu Centro Personal de YouTube Music (Playlists y Radio)",
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
        description="🔑 Conecta directamente tu Playlist de YouTube Music o tus Gustos Musicales",
    )
    @app_commands.describe(plataforma="Elige si deseas conectar YouTube Music o tus Gustos")
    @app_commands.choices(
        plataforma=[
            app_commands.Choice(name="❤️ YouTube Music (Playlist o Video)", value="ytmusic"),
            app_commands.Choice(name="🎸 Mis Artistas y Géneros Favoritos", value="tastes"),
        ]
    )
    async def cmd_vincular_musica(interaction: discord.Interaction, plataforma: str):
        if plataforma == "ytmusic":
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
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token:
        raise ValueError("DISCORD_TOKEN no configurado en variables de entorno o archivo .env")
    bot = PenguPixelBot(use_privileged_intents=False)
    register_commands(bot)
    bot.run(token)


if __name__ == "__main__":
    start_bot()
