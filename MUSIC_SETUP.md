# Music Player Setup

The Space Sim includes a background music player that loops continuously. Follow the steps below to add your own music.

## How to Add Music

1. **Create a `music` folder** in the same directory as `space_sim_v6.py`:
   ```
   Spacesim/
   ├── space_sim_v6.py
   ├── space_sim_v6.html
   └── music/              ← Create this folder
   ```

2. **Place audio files** in the `music/` folder. Supported formats:
   - `.mp3` (MPEG Audio)
   - `.ogg` (Ogg Vorbis) — recommended for best compatibility
   - `.wav` (WAV)
   - `.flac` (FLAC)

3. **Restart the game** — it will automatically load and sort music files alphabetically.

## Music Controls

| Key | Action |
|-----|--------|
| **M** | Toggle play/pause |
| **N** | Next track |
| **P** | Previous track |
| **+** / **=** | Increase volume (+5%) |
| **-** | Decrease volume (-5%) |

## Music Display

- The current track name and progress (`track_name (current/total)`) display in the top-left corner.
- A green indicator shows when music is playing; gray when paused.
- Volume percentage is displayed below the track name.

## Tips

- **Use `.ogg` format** for best compatibility and smaller file sizes (convert `.mp3` to `.ogg` with tools like Audacity or FFmpeg).
- **Naming convention**: Prefix with numbers (e.g., `01_ambient.ogg`, `02_exploration.ogg`) to control playback order.
- **Loop behavior**: Music loops indefinitely when a track is playing. Songs will auto-advance to the next track when complete (if using a playlist).
- **No music folder**: If the `music/` folder is missing or empty, the player will display "No music files found" and music controls are disabled.

## Example Setup

```
music/
├── 01_ambient.ogg
├── 02_exploration.ogg
├── 03_battle.ogg
└── 04_calm.ogg
```

Press **M** to start playing, **N** to skip to the next track, and adjust volume with **+/-**.

---

**Happy listening!** 🎵
