# Space Simulator

A 2D gravitational physics sandbox built with Python and Pygame. Simulate planetary systems, black holes, binary stars, wormholes, and more — in real time.
The purpose of this project was mainly to understand the capabilities of AI agents in coding. 
I won't overstate the value of this exercise but as a beginner getting into python, it was useful for my mental map of how programs are written.

![Python](https://img.shields.io/badge/Python-3.10+-blue) ![Pygame](https://img.shields.io/badge/Pygame-2.x-green)

---

## Features

### Physics
- N-body gravitational simulation with configurable time warp (0.25× – 10×)
- Orbital trajectory prediction with smoothing
- Collision detection and mass absorption with shockwave effects
- Roche limit — bodies shed mass when too close to a massive neighbour
- Tidal heating simulation
- Gravity wave visualisation on large collision events

### Spawnable Bodies
| Type | Description |
|---|---|
| Planet | Standard rocky/gas body |
| Star | Glowing luminous body |
| Neutron Star | High-density, high-gravity object |
| Black Hole | Absorbs nearby mass, renders accretion glow |
| Binary | Paired bodies orbiting a shared centre of mass |
| Comet | Small fast-moving body with a trail |
| Nebula | Diffuse cloud region |
| Wormhole | Paired portals — objects entering one exit the other |
| Ship | Player-controlled vessel |

### Player Ship
- Thrust (W/S), rotate (A/D)
- Land on planets and launch from the surface
- Autopilot modes: orbital insertion (O) and escape trajectory (E)
- Delta-v tracking display
- Tractor beam

### Camera & UI
- Pan (drag), zoom (scroll), and follow-lock on any body
- Arrow key camera movement
- Object finder panel — scrollable, filterable by body type
- Minimap
- Properties panel — edit mass, radius, velocity via sliders
- Rename any body (double-click)
- Spawn panel with size and colour controls

### Other
- Trajectory preview for all bodies (T toggle)
- Background star field
- Music player — drop MP3/OGG/WAV/FLAC files into a `music/` folder
- Full reset (R)
- Tutorial screen on first launch

---

## Controls

| Input | Action |
|---|---|
| Right-click drag | Spawn body (drag sets velocity) |
| Left-click drag | Pan camera |
| Scroll | Zoom |
| Click body | Follow/select |
| Double-click body | Rename |
| W / S | Ship thrust forward / back |
| A / D | Ship rotate |
| O | Autopilot: orbit nearest body |
| E | Autopilot: escape trajectory |
| T | Toggle trajectory preview |
| SHIFT | Orbit lock |
| R | Reset simulation |
| F10 | Toggle tutorial |

---

## Running from Source

**Requirements:** Python 3.10+, Pygame 2.x

```bash
pip install pygame
python space_sim_v6.py
```

Optional: add audio files to a `music/` folder in the same directory — the sim will autoplay them.

---

## Project Background

Built as a learning project to explore Python fundamentals and Pygame's game loop model. The codebase covers event handling, coordinate systems, vector math, camera transforms, and real-time simulation — all in a single-file architecture (~1,250 lines).

---

## Stack

- **Python** — core simulation logic
- **Pygame** — rendering, input, audio
- **math / random** — physics calculations and procedural generation
- **json** — (internal state serialisation)
