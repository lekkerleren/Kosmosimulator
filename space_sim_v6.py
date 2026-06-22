import pygame
import math
import random
import sys
import json
from collections import deque

pygame.init()

W, H = 2560, 1440
screen = pygame.display.set_mode((W, H), pygame.SCALED)
pygame.display.set_caption("Space Sim")
clock = pygame.time.Clock()

_overlay = pygame.Surface((W, H), pygame.SRCALPHA)

G     = 100
SM    = 1_000_000
FDT   = 0.01
WARPS = [0.25, 0.5, 0.75, 1, 2, 5, 10]

WORLD_W, WORLD_H = 1048576, 1048576
WORLD_X0 = -WORLD_W // 2
WORLD_Y0 = -WORLD_H // 2

COLS = [
    ( 74, 144, 217), (193,  68,  14), (232, 160,  96), ( 80, 200, 120),
    (176, 122, 224), (232, 212,  77), (232, 122, 122), (204, 204, 204),
]

SPAWN_TYPES = ['planet', 'star', 'neutron', 'bh', 'binary', 'comet', 'nebula', 'wormhole', 'ship', 'delete']

cam             = {'x': 0.0, 'y': 0.0, 'zoom': 1.2}
follow_target   = None
warp_idx        = 0
warp            = WARPS[0]
panning         = False
pan_mx = pan_my = 0
spawning        = False
spawn_sx = spawn_sy = 0
mouse_sx = mouse_sy = 0
spawn_size      = 14
spawn_col_idx   = 0
slider_dragging = False
spawn_type      = 'planet'
player_ship     = None
wormhole_pending = None      # first wormhole body, waiting for its pair
binary_pending   = None      # first body of a binary pair, waiting for its partner
autopilot_mode   = None      # None | 'orbit' | 'escape'
ap_locked_target = None      # body locked by O key; None = nearest
landed_on        = None      # body ship is currently landed on
land_offset_x    = 0.0       # ship position relative to planet center when landed
land_offset_y    = 0.0
_land_candidate  = None      # planet eligible for landing this frame (for prompt)
_approach_target = None      # planet whose approach assist is active this frame
tractor_active   = False
ship_delta_v     = 0.0       # accumulated Δv display
_ship_prev_vx    = 0.0
_ship_prev_vy    = 0.0
gravity_waves    = []        # [{x,y,r,max_r,alpha,col}]
_roche_cooldown  = 0.0       # timer to throttle roche shedding
_spawn_count    = 0

# title screen shown at startup; any key/click → tutorial → game
title_visible    = True
tutorial_visible = False
_title_blink_t   = 0.0

# music player
import os

def resource_path(relative):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative)

music_playing = False
music_volume = 0.7
current_track_idx = 0
music_files = []
music_folder = resource_path('music')
music_autoplay_done = False

# toggle to show predicted trajectories for all bodies
show_all_trajs = False

def load_music_files():
    global music_files
    if os.path.isdir(music_folder):
        # load mp3, ogg, wav, flac from music folder
        exts = ('.mp3', '.ogg', '.wav', '.flac')
        music_files = sorted([f for f in os.listdir(music_folder) if f.lower().endswith(exts)])
        if music_files:
            pygame.mixer.music.set_volume(music_volume)

load_music_files()

bodies      = []
stars       = []
star_mm     = []
shockwaves  = []

renaming_body   = None
rename_text     = ''
_last_click_body = None
_last_click_time = 0.0

_props_slider_dragging = None   # (bar_x, bar_w, key, lo, hi, log_scale)
_props_slider_rects    = []     # [(hit_rect, bar_x, bar_w, key, lo, hi, log_scale), ...]
_props_lock_mass_rad   = False
_props_lock_btn_rect   = None

note_text     = ''
note_alpha    = 0.0
note_end_time = 0.0

_font_path = (pygame.font.match_font('couriernew') or
              pygame.font.match_font('dejavusansmono') or
              pygame.font.match_font('liberationmono') or
              pygame.font.match_font('freemono'))
if _font_path:
    font    = pygame.font.Font(_font_path, 22)
    font_sm = pygame.font.Font(_font_path, 17)
    font_xs = pygame.font.Font(_font_path, 13)
else:
    font    = pygame.font.SysFont('monospace', 22)
    font_sm = pygame.font.SysFont('monospace', 17)
    font_xs = pygame.font.SysFont('monospace', 13)

# Cyrillic-capable fonts for the title screen
_cyr_path = (pygame.font.match_font('arialblack') or
             pygame.font.match_font('arial') or
             pygame.font.match_font('freesansbold') or
             pygame.font.match_font('dejavusans'))
font_title  = (pygame.font.Font(_cyr_path, 108) if _cyr_path
               else pygame.font.SysFont('arial', 108, bold=True))
font_title2 = (pygame.font.Font(_cyr_path, 28)  if _cyr_path
               else pygame.font.SysFont('arial', 28))

# ── layout constants ──────────────────────────────────────────────────────────
# Object finder panel (top-centre, scrollable)
OBJ_W        = 880
OBJ_H        = 98
OBJ_X        = W//2 - OBJ_W//2
OBJ_Y        = 8
OBJ_ICON_W   = 72
OBJ_ICON_R   = 20
OBJ_FILTER_H = 24
OBJ_ICON_CY  = OBJ_Y + OBJ_FILTER_H + 10 + OBJ_ICON_R   # = 62
OBJ_BARH     = OBJ_Y + OBJ_H                              # = 106
_OBJ_ARROW_W = 26

_obj_scroll       = 0
_obj_filter       = 'all'
_obj_filter_rects = []
_obj_icon_rects   = []

PANEL_W, PANEL_H = 312, 310
PANEL_X = W - PANEL_W - 18;  PANEL_Y = H - PANEL_H - 18
SL_X = PANEL_X + 28;  SL_Y = PANEL_Y + 112;  SL_W = PANEL_W - 56
SL_MIN, SL_MAX = 4, 40
SWATCH_Y  = PANEL_Y + 190;  SWATCH_X0 = PANEL_X + 28
SWATCH_R  = 13;              SWATCH_GAP = 33

_btn_clone_rect      = None
_btn_belt_rect       = None
_btn_rnd_rect        = None
_warp_left_rect      = None
_warp_right_rect     = None
_spawn_type_btn_rect = None
_spawn_dropdown_open = False
_spawn_dropdown_rects = []

MM_W  = 240;  MM_H  = int(MM_W * WORLD_H / WORLD_W)
MM_X  = 18;   MM_Y  = H - MM_H - 18
MM_SX = MM_W / WORLD_W;  MM_SY = MM_H / WORLD_H

RESET_RECT = pygame.Rect(18, 94, 100, 26)

PROPS_W      = PANEL_W
PROPS_X      = PANEL_X
PROPS_Y      = 170
PROPS_ROW_H  = 44
_PROP_SLIDERS = [
    ('mass', 'Mass',   1e2,    1e12,   True),
    ('rad',  'Radius', 1.0,    150.0,  False),
    ('vx',   'Vel X',  -5000.0, 5000.0, False),
    ('vy',   'Vel Y',  -5000.0, 5000.0, False),
]
PROPS_H = 70 + len(_PROP_SLIDERS) * PROPS_ROW_H + 10

_panel_surf   = pygame.Surface((PANEL_W, PANEL_H), pygame.SRCALPHA)
_props_surf   = pygame.Surface((PROPS_W, PROPS_H), pygame.SRCALPHA)
_minimap_surf = pygame.Surface((MM_W, MM_H), pygame.SRCALPHA)
_rename_surf  = pygame.Surface((W, 40), pygame.SRCALPHA)

if hasattr(sys, '_MEIPASS'):
    SAVE_PATH = os.path.join(os.path.dirname(sys.executable), 'spacesim_save.json')
else:
    SAVE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'spacesim_save.json')

_SAVE_SKIP = frozenset({'trail', 'cloud_particles'})
_SAVE_REFS = frozenset({'partner', 'binary_partner'})


# ── core helpers ──────────────────────────────────────────────────────────────

def to_screen(wx, wy):
    return (wx - cam['x']) * cam['zoom'] + W/2, (wy - cam['y']) * cam['zoom'] + H/2

def to_world(sx, sy):
    return (sx - W/2) / cam['zoom'] + cam['x'], (sy - H/2) / cam['zoom'] + cam['y']

def circ(r, M):
    return math.sqrt(G * M / r)

def size_to_mass(sz):       return int((sz / 4) ** 3 * 500)
def size_to_star_mass(sz):  return int((sz / 4) ** 3 * 50_000)

def bh_spawn_mass(sz):
    ref = max((b['mass'] for b in bodies if b.get('glow') and not b.get('bh')), default=SM)
    t   = (sz - SL_MIN) / (SL_MAX - SL_MIN)
    mult = 100 + t * 900
    return int(ref * mult), int(mult)

def drag_to_speed(px):   return px ** 1.5 / 50.0

def clamp_cam():
    hw = (W / 2) / cam['zoom'];  hh = (H / 2) / cam['zoom']
    cam['x'] = 0.0 if hw*2 >= WORLD_W else max(WORLD_X0+hw, min(WORLD_X0+WORLD_W-hw, cam['x']))
    cam['y'] = 0.0 if hh*2 >= WORLD_H else max(WORLD_Y0+hh, min(WORLD_Y0+WORLD_H-hh, cam['y']))

def mk_body(name, col, x, y, vx, vy, mass, rad, tmax=500, glow=False, fixed=False, bh=False):
    return {
        'name': name, 'col': col,
        'x': float(x), 'y': float(y),
        'vx': float(vx), 'vy': float(vy),
        'mass': float(mass), 'rad': int(rad),
        'trail': deque(maxlen=tmax or None),
        'tmax': tmax, 'glow': glow, 'fixed': fixed, 'bh': bh,
        'spin': random.uniform(0, 6.28),
        'spin_rate': 0.0,
        'age': 0.0,
        'tidal_heat': 0.0,
        'has_rings': False,
        'comet': False, 'neutron': False, 'wormhole': False, 'nebula': False,
        'cloud_rad': 0,
        'partner': None,
        'fuel': 100.0,
    }

def init_sim():
    global bodies, stars, star_mm, _spawn_count, shockwaves
    global renaming_body, rename_text, _last_click_body, _last_click_time
    _spawn_count = 0;  shockwaves = []
    renaming_body = None;  rename_text = '';  _last_click_body = None;  _last_click_time = 0.0
    
    bh_mass = 50_000_000
    bodies = [
        mk_body('Sagittarius', (5, 5, 12), 0, 0, 0, 0, bh_mass, 90, 0, False, False, True),
    ]

    # Hill sphere radius: r_hill(a) ≈ a * (SM / (3*bh_mass))^(1/3) ≈ a * 0.188
    # Planet orbits kept below 0.25 * r_hill for stability.
    def add_star(name, col, a, t_deg, s_rad=55):
        t = math.radians(t_deg)
        sx = a * math.cos(t);  sy = a * math.sin(t)
        sp = circ(a, bh_mass)
        svx = -sp * math.sin(t);  svy = sp * math.cos(t)
        bodies.append(mk_body(name, col, sx, sy, svx, svy, SM, s_rad, 30000, True))
        return sx, sy, svx, svy, t

    def add_planet(name, col, sx, sy, svx, svy, t, pd, pmass, prad):
        # offset planet along star's tangential direction so it starts ahead in orbit
        px = sx + pd * (-math.sin(t))
        py = sy + pd * math.cos(t)
        pv = circ(pd, SM)
        # CCW orbit around star: velocity perp to offset direction = (-cos t, -sin t)
        b = mk_body(name, col, px, py,
                    svx + pv * (-math.cos(t)),
                    svy + pv * (-math.sin(t)),
                    pmass, prad, 30000)
        b['spin_rate'] = random.uniform(0.1, 0.8)
        if prad >= 28:
            b['has_rings'] = True
        bodies.append(b)

    # ── System 1: Helios — 8 000 — dangerously close, tidal forces prevent planets ──
    add_star('Helios',  (180, 220, 255),   8_000,   0, 50)

    # ── System 2: Pyraxis — 18 000 — 1 planet (r_hill≈3 400, orbit<850) ────────────
    sx, sy, svx, svy, t = add_star('Pyraxis', (255, 165,  80),  18_000,  60, 50)
    add_planet('Ignis',     (220,  70,  30), sx, sy, svx, svy, t,   700,  6_000, 18)

    # ── System 3: Cetara — 35 000 — 2 planets (r_hill≈6 600, orbits<1 650) ─────────
    sx, sy, svx, svy, t = add_star('Cetara',  (255, 220, 100),  35_000, 130, 55)
    add_planet('Cetara-1',  ( 50, 120, 210), sx, sy, svx, svy, t,   900,  5_000, 20)
    add_planet('Cetara-2',  (200, 150,  80), sx, sy, svx, svy, t,  1500, 20_000, 28)

    # ── System 4: Voryn — 60 000 — 3 planets (r_hill≈11 300, orbits<2 820) ─────────
    sx, sy, svx, svy, t = add_star('Voryn',   (255, 100,  70),  60_000, 200, 60)
    add_planet('Voryn-1',   (150, 100,  80), sx, sy, svx, svy, t,  1000,  4_000, 16)
    add_planet('Voryn-2',   (200, 230, 255), sx, sy, svx, svy, t,  2000, 12_000, 22)
    add_planet('Voryn-3',   (180, 140, 100), sx, sy, svx, svy, t,  2600, 25_000, 30)

    # ── System 5: Aethos — 90 000 — 3 planets (r_hill≈16 900, orbits<4 230) ────────
    sx, sy, svx, svy, t = add_star('Aethos',  (150, 200, 255),  90_000, 290, 55)
    add_planet('Aethos-1',  (190, 160, 140), sx, sy, svx, svy, t,  1200,  4_000, 15)
    add_planet('Aethos-2',  ( 70, 150,  80), sx, sy, svx, svy, t,  2500, 10_000, 22)
    add_planet('Aethos-3',  (100, 180, 220), sx, sy, svx, svy, t,  3800, 18_000, 26)

    # ── System 6: Lucerna — 130 000 — 4 planets (r_hill≈24 400, orbits<6 100) ──────
    sx, sy, svx, svy, t = add_star('Lucerna', (255, 245, 180), 130_000, 355, 55)
    add_planet('Lucerna-1', (180, 130, 100), sx, sy, svx, svy, t,  1500,  4_000, 15)
    add_planet('Lucerna-2', ( 40, 100, 180), sx, sy, svx, svy, t,  2800, 12_000, 24)
    add_planet('Lucerna-3', (210, 170,  90), sx, sy, svx, svy, t,  4200, 30_000, 32)
    add_planet('Lucerna-4', (150, 200, 230), sx, sy, svx, svy, t,  5800, 15_000, 24)

    # ── Binary pair: Kastor & Pollux — 190 000 — (r_hill_com≈45 000, sep=2 500) ───
    # Two stars in mutual orbit whose COM circles the BH.
    # v_mutual = sqrt(G*SM / (2*sep)) ≈ 141  →  binary period ≈ 56 sim-time units.
    def add_binary_pair(n1, col1, n2, col2, a, t_deg, sep=2_500, r1=50, r2=48):
        t  = math.radians(t_deg)
        v_com = circ(a, bh_mass)
        com_x  =  a * math.cos(t);   com_y  =  a * math.sin(t)
        com_vx = -v_com * math.sin(t); com_vy = v_com * math.cos(t)
        # radial (BH→COM) and tangential (CCW) unit vectors
        rx, ry = math.cos(t), math.sin(t)
        tx, ty = -math.sin(t), math.cos(t)
        v_mut = math.sqrt(G * SM / (2 * sep))
        # place stars along radial, orbit each other along tangential
        b1 = mk_body(n1, col1,
                     com_x + rx*sep/2, com_y + ry*sep/2,
                     com_vx + tx*v_mut, com_vy + ty*v_mut,
                     SM, r1, 30000, glow=True)
        b2 = mk_body(n2, col2,
                     com_x - rx*sep/2, com_y - ry*sep/2,
                     com_vx - tx*v_mut, com_vy - ty*v_mut,
                     SM, r2, 30000, glow=True)
        b1['spin_rate'] = random.uniform(0.05, 0.18)
        b2['spin_rate'] = random.uniform(0.05, 0.18)
        b1['binary_partner'] = b2;  b2['binary_partner'] = b1
        bodies.append(b1);  bodies.append(b2)

    add_binary_pair('Kastor', (190, 215, 255),   # blue-white A-type
                    'Pollux', (255, 160,  75),    # orange K-type
                    190_000, 45)

    # ── Neutron star: Nexar — 260 000 — lone remnant, fast spin ─────────────────
    def add_neutron_star(name, a, t_deg, s_rad=8):
        t   = math.radians(t_deg)
        v   = circ(a, bh_mass)
        b   = mk_body(name, (200, 240, 255),
                      a*math.cos(t), a*math.sin(t),
                      -v*math.sin(t), v*math.cos(t),
                      SM * 3, s_rad, 30000)
        b['neutron']   = True
        b['spin_rate'] = random.uniform(50.0, 90.0)
        bodies.append(b)

    add_neutron_star('Nexar', 260_000, 225)

    # ── Nebulae ────────────────────────────────────────────────────────────────
    def add_nebula(name, col, x, y, cloud_rad=3000):
        b = mk_body(name, col, x, y, 0, 0, 1, cloud_rad // 6, 0, fixed=True)
        b['nebula'] = True;  b['cloud_rad'] = cloud_rad;  b['tmax'] = 0
        bodies.append(b)

    add_nebula('Crimson Veil',   (210,  55,  40),  -48_000,  24_000, cloud_rad=3200)
    add_nebula('Cerulean Drift', ( 40,  90, 210),   22_000, -72_000, cloud_rad=2800)
    add_nebula('Ember Cloud',    (200, 120,  30),  100_000, -40_000, cloud_rad=2400)

    # ── Wormhole pair ─────────────────────────────────────────────────────────
    wh_a = mk_body('Gate-α', (160, 80, 255),  -95_000,  70_000, 0, 0, 1, 28, 0, fixed=True)
    wh_b = mk_body('Gate-β', (160, 80, 255),  210_000, -80_000, 0, 0, 1, 28, 0, fixed=True)
    wh_a['wormhole'] = True;  wh_a['tmax'] = 0
    wh_b['wormhole'] = True;  wh_b['tmax'] = 0
    wh_a['partner'] = wh_b;   wh_b['partner'] = wh_a
    bodies.append(wh_a);  bodies.append(wh_b)

    stars = [{'x': random.uniform(WORLD_X0, WORLD_X0+WORLD_W),
               'y': random.uniform(WORLD_Y0, WORLD_Y0+WORLD_H),
               'r': random.uniform(0.4, 2.4), 'p': random.uniform(0.70, 0.95)}
             for _ in range(8000)]
    star_mm = []
    for s in stars:
        mx = MM_X + int((s['x'] - WORLD_X0) * MM_SX)
        my = MM_Y + int((s['y'] - WORLD_Y0) * MM_SY)
        if MM_X <= mx < MM_X+MM_W and MM_Y <= my < MM_Y+MM_H:
            star_mm.append((mx, my))

init_sim()


def set_note(s):
    global note_text, note_alpha, note_end_time
    note_text = s;  note_alpha = 1.0
    note_end_time = pygame.time.get_ticks() / 1000.0 + 2.5

def play_music(idx):
    global current_track_idx, music_playing
    if not music_files or idx < 0 or idx >= len(music_files):
        return
    current_track_idx = idx
    try:
        path = os.path.join(music_folder, music_files[idx])
        pygame.mixer.music.load(path)
        pygame.mixer.music.play(-1)  # loop indefinitely
        music_playing = True
        set_note(f'Now playing: {music_files[idx]}')
    except Exception as e:
        set_note(f'Failed to load music: {e}')
        music_playing = False

def toggle_music():
    global music_playing
    if not music_files:
        set_note('No music files found in music folder')
        return
    if music_playing:
        pygame.mixer.music.pause()
        music_playing = False
        set_note('Music paused')
    else:
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.unpause()
        else:
            play_music(current_track_idx)
        music_playing = True
        set_note('Music playing')

def next_track():
    if not music_files:
        return
    idx = (current_track_idx + 1) % len(music_files)
    play_music(idx)

def prev_track():
    if not music_files:
        return
    idx = (current_track_idx - 1) % len(music_files)
    play_music(idx)

def change_volume(delta):
    global music_volume
    music_volume = max(0.0, min(1.0, music_volume + delta))
    pygame.mixer.music.set_volume(music_volume)
    set_note(f'Volume: {int(music_volume*100)}%')

def do_reset():
    global follow_target, warp_idx, warp, spawning, panning, slider_dragging
    global spawn_type, renaming_body, rename_text, music_autoplay_done
    global player_ship, wormhole_pending, binary_pending, gravity_waves, _roche_cooldown
    global autopilot_mode, ap_locked_target, tractor_active, ship_delta_v, _ship_prev_vx, _ship_prev_vy
    global landed_on, land_offset_x, land_offset_y
    global _obj_scroll, _obj_filter, _spawn_dropdown_open
    _spawn_dropdown_open = False
    init_sim()
    cam.update({'x': 0.0, 'y': 0.0, 'zoom': 1.2})
    follow_target = None;  warp_idx = 0;  warp = WARPS[0]
    spawning = False;  panning = False;  slider_dragging = False
    spawn_type = 'planet';  renaming_body = None;  rename_text = ''
    _glow_cache.clear();  _bh_glow_cache.clear()
    player_ship = None
    wormhole_pending = None;  binary_pending = None
    gravity_waves = [];  _roche_cooldown = 0.0
    autopilot_mode = None;  ap_locked_target = None;  tractor_active = False
    landed_on = None;  land_offset_x = 0.0;  land_offset_y = 0.0
    ship_delta_v = 0.0;  _ship_prev_vx = 0.0;  _ship_prev_vy = 0.0
    _obj_scroll = 0;  _obj_filter = 'all'
    music_autoplay_done = False
    set_note('Reset')


# ── orbit assist ──────────────────────────────────────────────────────────────

def orbit_info(wx, wy):
    best = None;  min_d = float('inf')
    for b in bodies:
        dx = b['x'] - wx;  dy = b['y'] - wy
        d  = math.sqrt(dx*dx + dy*dy)
        if 0 < d < min_d:
            min_d = d;  best = b
    if best is None:
        return None, float('inf'), 0.0
    return best, min_d, circ(min_d, best['mass'])

def orbit_velocity(wx, wy, drag_dx, drag_dy, override_body=None):
    if override_body is not None:
        dx = wx - override_body['x'];  dy = wy - override_body['y']
        dist = math.sqrt(dx*dx + dy*dy)
        if dist < 1:
            return 0.0, 0.0
        nb = override_body;  v_orb = circ(dist, nb['mass'])
    else:
        nb, dist, v_orb = orbit_info(wx, wy)
        if nb is None or dist < 1:
            return 0.0, 0.0
    rx = (wx - nb['x']) / dist;  ry = (wy - nb['y']) / dist
    ccw_x = -ry;  ccw_y = rx
    dl = math.hypot(drag_dx, drag_dy) or 1
    if (drag_dx/dl)*ccw_x + (drag_dy/dl)*ccw_y >= 0:
        return v_orb * ccw_x, v_orb * ccw_y
    return -v_orb * ccw_x, -v_orb * ccw_y


def predict_trajectory(wx, wy, vx, vy, steps=300, dt=20.0, sample=4, max_bodies=8):
    """Simulate a short trajectory (approximate) under current gravity field.
    Returns a list of world-space (x,y) points.
    """
    pts = []
    px, py = float(wx), float(wy)
    vx, vy = float(vx), float(vy)
    # choose the most influential bodies to speed up the prediction
    bodies_use = sorted(bodies, key=lambda b: b['mass'], reverse=True)[:max_bodies]
    cumd = 0.0
    lastx, lasty = px, py
    for s in range(steps):
        ax = ay = 0.0
        for b in bodies_use:
            dx = b['x'] - px;  dy = b['y'] - py
            r2 = dx*dx + dy*dy + 0.01
            f  = G * b['mass'] / (r2 * math.sqrt(r2))
            ax += f*dx;  ay += f*dy
        vx += ax * dt;  vy += ay * dt
        px += vx * dt;  py += vy * dt
        segd = math.hypot(px-lastx, py-lasty)
        cumd += segd
        lastx, lasty = px, py
        if s % sample == 0:
            pts.append((px, py))
        # stop if far enough or out of world bounds
        if cumd > 20000.0:
            break
        if px < WORLD_X0-2000 or px > WORLD_X0+WORLD_W+2000 or py < WORLD_Y0-2000 or py > WORLD_Y0+WORLD_H+2000:
            break
    return pts


def smooth_points(pts, window=5):
    if not pts:
        return pts
    n = len(pts)
    if n <= 2:
        return pts
    out = []
    hw = window//2
    for i in range(n):
        sx = sy = 0.0; cnt = 0
        for j in range(max(0, i-hw), min(n, i+hw+1)):
            sx += pts[j][0]; sy += pts[j][1]; cnt += 1
        out.append((sx/cnt, sy/cnt))
    return out


# ── shockwaves ────────────────────────────────────────────────────────────────

def create_shockwave(x, y, mass_gained, color=(255, 150, 60), is_super=False):
    if mass_gained < 10:
        return
    intensity = float(mass_gained)
    scale = math.pow(max(1.0, intensity / 120.0), 0.35)
    if is_super:
        max_r    = min(3200, max(900,  scale * 1400))
        strength = min(420.0, max(140.0, scale * 180.0))
        speed    = 220.0
    else:
        max_r    = min(1200, max(90,   scale * 420))
        strength = min(100.0, max(18.0, scale * 24.0))
        speed    = 180.0
    shockwaves.append({
        'x': float(x), 'y': float(y),
        'r': 0.0, 'prev_r': 0.0,
        'max_r': float(max_r),
        'strength': float(strength), 'strength0': float(strength),
        'speed': float(speed),
        'duration': max_r / speed,
        'age': 0.0,
        'col': color,
        'bodies_hit': set(),
    })

def update_shockwaves(dt):
    global shockwaves
    for sw in shockwaves:
        sw['prev_r'] = sw['r']
        sw['age']   += dt
        sw['r']      = min(sw['speed'] * sw['age'], sw['max_r'])
        t_norm       = min(1.0, sw['age'] / max(0.0001, sw['duration']))
        sw['strength'] = sw['strength0'] * (1.0 - t_norm ** 1.25)

        for bi, b in enumerate(bodies):
            if b['fixed'] or bi in sw['bodies_hit']:
                continue
            dx = b['x'] - sw['x'];  dy = b['y'] - sw['y']
            dist = math.hypot(dx, dy)
            if dist < 1 or not (sw['prev_r'] <= dist <= sw['r']):
                continue
            impulse = sw['strength'] * 90.0 / max(70.0, dist)
            bh_dampening = 0.05 if b.get('bh') else 1.0
            b['vx'] += (dx / dist) * impulse * bh_dampening
            b['vy'] += (dy / dist) * impulse * bh_dampening
            sw['bodies_hit'].add(bi)

    shockwaves = [sw for sw in shockwaves if sw['strength'] > 0.5 and sw['age'] < sw['duration'] * 1.4]


# ── slider / panel ────────────────────────────────────────────────────────────

def slider_hx():
    t = (spawn_size - SL_MIN) / (SL_MAX - SL_MIN)
    return int(SL_X + t * SL_W)

def slider_hit(pos):
    hx = slider_hx()
    return (math.hypot(pos[0]-hx, pos[1]-SL_Y) <= 14 or
            (SL_X <= pos[0] <= SL_X+SL_W and abs(pos[1]-SL_Y) <= 10))

def update_slider(pos):
    global spawn_size
    t = max(0.0, min(1.0, (pos[0]-SL_X)/SL_W))
    spawn_size = max(SL_MIN, min(SL_MAX, round(SL_MIN + t*(SL_MAX-SL_MIN))))

def swatch_at(pos):
    for i in range(len(COLS)):
        if math.hypot(pos[0]-(SWATCH_X0+i*SWATCH_GAP), pos[1]-SWATCH_Y) <= SWATCH_R+4:
            return i
    return -1

def panel_hit(pos):
    return (PANEL_X-4 <= pos[0] <= PANEL_X+PANEL_W+4 and
            PANEL_Y-4 <= pos[1] <= PANEL_Y+PANEL_H+4)

def props_panel_hit(pos):
    if follow_target is None or follow_target not in bodies:
        return False
    return (PROPS_X - 4 <= pos[0] <= PROPS_X + PROPS_W + 4 and
            PROPS_Y - 4 <= pos[1] <= PROPS_Y + PROPS_H + 4)

def _val_to_t(val, lo, hi, log_scale):
    if log_scale:
        lo_l = math.log10(max(1e-30, lo));  hi_l = math.log10(max(1e-30, hi))
        return max(0.0, min(1.0, (math.log10(max(1e-30, val)) - lo_l) / (hi_l - lo_l)))
    return max(0.0, min(1.0, (val - lo) / (hi - lo)))

def _t_to_val(t, lo, hi, log_scale):
    if log_scale:
        lo_l = math.log10(max(1e-30, lo));  hi_l = math.log10(max(1e-30, hi))
        return 10 ** (lo_l + t * (hi_l - lo_l))
    return lo + t * (hi - lo)

def _fmt_prop(key, val):
    if key == 'mass': return f'{val:.3e}'
    if key == 'rad':  return f'{int(val)}'
    return f'{val:.1f}'

def _apply_props_slider(b, key, t, lo, hi, log_scale):
    val = _t_to_val(t, lo, hi, log_scale)
    if key == 'rad':
        b['rad'] = max(1, int(val))
        if _props_lock_mass_rad:
            b['mass'] = (b['rad'] / 4.0) ** 3 * 500.0
    elif key == 'mass':
        b['mass'] = max(1.0, val)
        if _props_lock_mass_rad:
            b['rad'] = max(1, int(4.0 * (b['mass'] / 500.0) ** (1.0 / 3.0)))
    else:
        b[key] = val

def get_filtered_bodies():
    if _obj_filter == 'star':
        return [b for b in bodies if b.get('glow') and not b.get('bh')]
    if _obj_filter == 'planet':
        return [b for b in bodies if not any(b.get(k) for k in
                ('glow','bh','ship','neutron','comet','wormhole','nebula'))]
    if _obj_filter == 'bh':
        return [b for b in bodies if b.get('bh')]
    if _obj_filter == 'ship':
        return [b for b in bodies if b.get('ship')]
    if _obj_filter == 'other':
        return [b for b in bodies if any(b.get(k) for k in
                ('neutron','comet','wormhole','nebula'))]
    return list(bodies)

def obj_panel_hit(pos):
    return OBJ_X <= pos[0] <= OBJ_X+OBJ_W and OBJ_Y <= pos[1] <= OBJ_BARH

def obj_icon_at(pos):
    for rect, body in _obj_icon_rects:
        if rect.collidepoint(pos):
            return body
    return None

def obj_filter_at(pos):
    for rect, key in _obj_filter_rects:
        if rect.collidepoint(pos):
            return key
    return None


# ── physics ───────────────────────────────────────────────────────────────────

def grav_step(dt):
    # ships should not exert gravity: give them zero mass in the snapshot
    snap = [(i, b['x'], b['y'], 0.0 if b.get('ship') else b['mass']) for i, b in enumerate(bodies)]
    for bi, b in enumerate(bodies):
        if b['fixed']:
            continue
        ax = ay = 0.0
        for si, sx, sy, smass in snap:
            if si == bi:
                continue
            dx = sx-b['x'];  dy = sy-b['y']
            r2 = dx*dx + dy*dy + 0.01
            f  = G * smass / (r2 * math.sqrt(r2))
            ax += f*dx;  ay += f*dy
        b['vx'] += ax*dt;  b['vy'] += ay*dt
        b['x']  += b['vx']*dt;  b['y'] += b['vy']*dt
        if b['tmax']:
            b['trail'].append((b['x'], b['y']))


def check_collisions():
    global bodies, follow_target, player_ship
    merged = set()
    for i in range(len(bodies)):
        if i in merged:
            continue
        for j in range(i+1, len(bodies)):
            if j in merged:
                continue
            a, b = bodies[i], bodies[j]
            # skip collision between ship and its host planet while landed
            if landed_on is not None and ((a is player_ship and b is landed_on) or
                                          (b is player_ship and a is landed_on)):
                continue
            dx = a['x']-b['x'];  dy = a['y']-b['y']
            collision_radius = (a['rad'] + b['rad'])
            if dx*dx + dy*dy >= collision_radius**2:
                continue

            # ships never merge — always bounce off
            if a.get('ship') or b.get('ship'):
                norm = math.hypot(dx, dy) or 1
                ship_ = a if a.get('ship') else b
                other_ = b if a.get('ship') else a
                sign = 1 if a.get('ship') else -1
                sep = (a['rad'] + b['rad']) * 1.1
                ship_['x'] = other_['x'] + (dx / norm) * sign * sep
                ship_['y'] = other_['y'] + (dy / norm) * sign * sep
                nx_ = (dx / norm) * sign
                ny_ = (dy / norm) * sign
                dot = ship_['vx'] * nx_ + ship_['vy'] * ny_
                if dot < 0:
                    ship_['vx'] -= 2 * dot * nx_ * 0.65
                    ship_['vy'] -= 2 * dot * ny_ * 0.65
                continue

            wi, li = (i, j) if a['mass'] >= b['mass'] else (j, i)
            W_ = bodies[wi];  L_ = bodies[li]

            # glancing blow check: project relative velocity onto collision normal
            rel_vx = L_['vx'] - W_['vx'];  rel_vy = L_['vy'] - W_['vy']
            norm   = math.hypot(dx, dy) or 1
            v_radial = abs((rel_vx * dx + rel_vy * dy) / norm)
            v_total  = math.hypot(rel_vx, rel_vy) or 1
            impact_factor = v_radial / v_total   # 1 = head-on, 0 = pure graze

            # BHs, stars, neutron stars, ship hits, and near-head-on always fully merge
            is_full_merge = (impact_factor > 0.55
                             or W_.get('bh')      or L_.get('bh')
                             or W_.get('glow')    or L_.get('glow')
                             or W_.get('neutron') or L_.get('neutron')
                             or W_.get('ship')    or L_.get('ship')
                             or L_['mass'] > W_['mass'] * 0.6)

            if not is_full_merge:
                # partial / grazing collision: transfer momentum, shed small debris
                frac = 0.12 * (1.0 - impact_factor)
                transfer = L_['mass'] * frac
                L_['mass'] -= transfer
                L_['rad']   = max(3, int((L_['mass'] / 500.0) ** (1/3) * 4))
                W_['mass'] += transfer
                W_['rad']   = max(3, int((W_['mass'] / 500.0) ** (1/3) * 4))
                # elastic-ish rebound along normal
                bounce_vx = (dx / norm) * v_total * 0.25
                bounce_vy = (dy / norm) * v_total * 0.25
                L_['vx'] += bounce_vx;  L_['vy'] += bounce_vy
                W_['vx'] -= bounce_vx * (L_['mass'] / max(W_['mass'], 1))
                W_['vy'] -= bounce_vy * (L_['mass'] / max(W_['mass'], 1))
                # push apart so they don't immediately re-collide
                sep = (a['rad'] + b['rad']) * 1.05
                L_['x'] = W_['x'] + dx / norm * sep
                L_['y'] = W_['y'] + dy / norm * sep
                create_shockwave(W_['x'], W_['y'], transfer * 0.4, (255, 160, 80))
                set_note(f'{L_["name"]} grazed {W_["name"]}')
                continue

            new_mass = W_['mass'] + L_['mass']
            new_rad  = int((W_['rad']**3 + L_['rad']**3)**(1/3))

            both_stars = (W_.get('glow') and L_.get('glow') and
                          not W_.get('bh') and not L_.get('bh'))

            if both_stars:
                # Supernova → Black Hole
                ref_star_mass = max((b['mass'] for b in bodies if b.get('glow') and not b.get('bh')), default=SM)
                bh_factor = min(1000.0, max(100.0, 100.0 + (new_mass / max(ref_star_mass, 1.0) - 1.0) * 20.0))
                bh_m = int(ref_star_mass * bh_factor)
                orig_W_mass = W_['mass']
                if not W_['fixed']:
                    W_['vx'] = (orig_W_mass*W_['vx'] + L_['mass']*L_['vx']) / bh_m
                    W_['vy'] = (orig_W_mass*W_['vy'] + L_['mass']*L_['vy']) / bh_m
                W_['mass'] = bh_m
                W_['rad']  = max(55, int(new_rad * 1.7))
                W_['col']  = (5, 5, 12)
                W_['glow'] = False
                W_['bh']   = True
                _glow_cache.clear();  _bh_glow_cache.clear()
                create_shockwave(W_['x'], W_['y'], new_mass, (255, 255, 210), is_super=True)
                spawn_gravity_wave(W_['x'], W_['y'], new_mass, (255, 255, 210))
                set_note(f'SUPERNOVA — {W_["name"]} collapsed into a Black Hole!')
            else:
                if not W_['fixed']:
                    W_['vx'] = (W_['mass']*W_['vx'] + L_['mass']*L_['vx']) / new_mass
                    W_['vy'] = (W_['mass']*W_['vy'] + L_['mass']*L_['vy']) / new_mass
                W_['mass'] = new_mass
                W_['rad']  = new_rad

                if W_.get('bh') or L_.get('bh'):
                    sw_col = (150, 180, 255)
                    _bh_glow_cache.clear()
                    create_shockwave(W_['x'], W_['y'], L_['mass'] * 1.2, sw_col)
                    spawn_gravity_wave(W_['x'], W_['y'], L_['mass'], (150, 180, 255))
                elif W_.get('glow') or L_.get('glow'):
                    sw_col = (255, 210, 80)
                    _glow_cache.clear()
                    create_shockwave(W_['x'], W_['y'], L_['mass'], sw_col)
                else:
                    sw_col = (255, 120, 40)
                    create_shockwave(W_['x'], W_['y'], L_['mass'] * 0.8, sw_col)
                set_note(f'{L_["name"]} absorbed by {W_["name"]}')

            if follow_target is L_:
                follow_target = W_
            if player_ship is L_:
                player_ship = None
                set_note(f'{L_["name"]} was absorbed — ship lost')
            merged.add(li)

    if merged:
        bodies = [b for i, b in enumerate(bodies) if i not in merged]


def despawn_oob():
    global bodies, follow_target, player_ship
    keep = [];  first_lost = None
    for b in bodies:
        ok = b['fixed'] or (WORLD_X0 <= b['x'] <= WORLD_X0+WORLD_W and
                             WORLD_Y0 <= b['y'] <= WORLD_Y0+WORLD_H)
        if ok:
            keep.append(b)
        else:
            if follow_target is b:
                follow_target = None
            if player_ship is b:
                player_ship = None
            if first_lost is None:
                first_lost = b
    if first_lost:
        bodies = keep
        set_note(f'{first_lost["name"]} left the boundary')


# ── new object physics ────────────────────────────────────────────────────────

def spawn_gravity_wave(x, y, mass, col=(255, 255, 200)):
    if mass < SM * 0.5:
        return
    max_r = min(10000, max(1500, mass / SM * 2500))
    gravity_waves.append({'x': float(x), 'y': float(y), 'r': 0.0,
                          'max_r': float(max_r), 'alpha': 1.0,
                          'speed': 500.0, 'col': col})

def update_gravity_waves(dt):
    global gravity_waves
    for gw in gravity_waves:
        gw['r'] += gw['speed'] * dt
        gw['alpha'] = max(0.0, 1.0 - gw['r'] / gw['max_r'])
    gravity_waves = [gw for gw in gravity_waves if gw['alpha'] > 0.01]

def update_spin(dt):
    for b in bodies:
        if b.get('spin_rate'):
            b['spin'] = (b['spin'] + b['spin_rate'] * dt) % (2 * math.pi)

def update_tidal_heating(dt):
    for b in bodies:
        if b.get('bh') or b.get('glow') or b.get('neutron') or b.get('ship') or b.get('fixed'):
            b['tidal_heat'] = max(0.0, b.get('tidal_heat', 0.0) - dt * 0.8)
            continue
        heat = 0.0
        for m in bodies:
            if m is b or not (m.get('bh') or m.get('glow') or m.get('neutron')):
                continue
            dist = math.hypot(b['x'] - m['x'], b['y'] - m['y'])
            influence = m['rad'] * (6.0 if m.get('bh') else 4.0) * 80
            if dist < influence:
                heat = max(heat, 1.0 - dist / influence)
        b['tidal_heat'] = min(1.0, heat)

def check_roche_limit():
    global bodies, _spawn_count, _roche_cooldown
    _roche_cooldown -= FDT
    if _roche_cooldown > 0:
        return
    _roche_cooldown = 0.1
    new_bodies = []
    for b in list(bodies):
        if (b.get('bh') or b.get('glow') or b.get('neutron') or b.get('ship')
                or b.get('fixed') or b.get('wormhole') or b.get('nebula')
                or b['mass'] < 300):
            continue
        for massive in bodies:
            if massive is b or not (massive.get('bh') or
                    (massive.get('glow') and massive['mass'] > SM * 0.5)):
                continue
            dist = math.hypot(b['x'] - massive['x'], b['y'] - massive['y'])
            if dist < massive['rad'] * 2.2 * 5.0 and b['mass'] > 300:
                frac = 0.07
                shard_mass = b['mass'] * frac
                b['mass'] = max(100.0, b['mass'] - shard_mass)
                b['rad'] = max(3, int((b['mass'] / 500.0) ** (1 / 3) * 4))
                ang = math.atan2(b['y'] - massive['y'], b['x'] - massive['x']) + math.pi / 2
                spd = math.hypot(b['vx'], b['vy']) * 0.3 + 15
                _spawn_count += 1
                shard = mk_body(f'D{_spawn_count}', (195, 175, 155),
                                b['x'] + math.cos(ang) * b['rad'] * 2,
                                b['y'] + math.sin(ang) * b['rad'] * 2,
                                b['vx'] + math.cos(ang) * spd,
                                b['vy'] + math.sin(ang) * spd,
                                shard_mass, max(3, b['rad'] // 3), 10000)
                new_bodies.append(shard)
                set_note(f'{b["name"]} torn apart by tidal forces')
                break
    bodies.extend(new_bodies)

def update_wormholes():
    wh = [b for b in bodies if b.get('wormhole') and b.get('partner') in bodies]
    if not wh:
        return
    for b in list(bodies):
        if b.get('wormhole') or b.get('fixed'):
            continue
        for gate in wh:
            if math.hypot(b['x'] - gate['x'], b['y'] - gate['y']) < gate['rad'] * 6:
                partner = gate['partner']
                b['x'] = partner['x'] + random.uniform(-partner['rad'], partner['rad'])
                b['y'] = partner['y'] + random.uniform(-partner['rad'], partner['rad'])
                set_note(f'{b["name"]} passed through {gate["name"]}')
                break

def update_nebulae(dt):
    drag = max(0.97, 1.0 - 0.03 * dt * 60)
    for nb in bodies:
        if not nb.get('nebula'):
            continue
        cr = nb.get('cloud_rad', nb['rad'] * 6)
        for b in bodies:
            if b is nb or b.get('fixed'):
                continue
            if math.hypot(b['x'] - nb['x'], b['y'] - nb['y']) < cr:
                b['vx'] *= drag
                b['vy'] *= drag


# ── glow caches ───────────────────────────────────────────────────────────────

_glow_cache    = {}
_bh_glow_cache = {}
_spawn_traj_key  = None   # single-entry cache for spawn-preview trajectory
_spawn_traj_val  = []
_ship_traj_key   = None   # single-entry cache for ship-thrust trajectory
_ship_traj_val   = []

def get_glow_surf(rad, zoom):
    rz  = round(zoom, 1);  key = (rad, rz)
    if key not in _glow_cache:
        glow_r = min(500, max(4, int(rad * rz * 2.8)))
        size   = glow_r*2+4;  surf = pygame.Surface((size, size), pygame.SRCALPHA)
        cx = cy = size//2
        for i in range(10, 0, -1):
            pygame.draw.circle(surf, (255, 220, 80, int(71*(10-i)/10)), (cx,cy), int(glow_r*i/10))
        _glow_cache[key] = surf
    return _glow_cache[key]

def get_bh_glow_surf(rad, zoom):
    rz  = round(zoom, 1);  key = (rad, rz)
    if key not in _bh_glow_cache:
        glow_r = min(600, max(6, int(rad * rz * 5.0)))
        size   = glow_r*2+4;  surf = pygame.Surface((size, size), pygame.SRCALPHA)
        cx = cy = size//2
        for i in range(12, 0, -1):
            t   = i / 12
            alp = int(110 * (1-t))
            r_  = min(255, 160+int(95*t))
            g_  = min(255, 160+int(70*t))
            pygame.draw.circle(surf, (r_, g_, 255, alp), (cx,cy), int(glow_r*t))
        _bh_glow_cache[key] = surf
    return _bh_glow_cache[key]


# ── drawing ───────────────────────────────────────────────────────────────────

def get_star_lens_offset(sx, sy, bh_positions):
    ox = oy = 0.0
    for bhx, bhy, influence in bh_positions:
        dx = sx - bhx
        dy = sy - bhy
        d2 = dx*dx + dy*dy
        if d2 >= influence * influence:
            continue
        d = math.sqrt(d2) or 1.0
        t = 1.0 - d / influence
        strength = (t * t) * (18.0 / max(1.0, d * 0.05))
        ox += -dy / d * strength
        oy += dx / d * strength
    return ox, oy


def draw_stars():
    z = cam['zoom']
    bh_positions = []
    for b in bodies:
        if b.get('bh'):
            bx, by = to_screen(b['x'], b['y'])
            radius = max(120, int(b['rad'] * z * 2.0))
            bh_positions.append((bx, by, radius))

    for s in stars:
        P  = s['p']
        sx = (s['x'] - cam['x'] * P) * z + W/2
        sy = (s['y'] - cam['y'] * P) * z + H/2
        ox = oy = 0.0
        if bh_positions:
            ox, oy = get_star_lens_offset(sx, sy, bh_positions)
        dx = sx + ox
        dy = sy + oy
        if -4 <= dx <= W+4 and -4 <= dy <= H+4:
            r = max(1, int(s['r'] * z**0.4 + min(1.5, abs(ox) * 0.05 + abs(oy) * 0.05)))
            pygame.draw.circle(screen, (175,175,175), (int(dx), int(dy)), r)


def draw_trail(trail, col):
    if len(trail) < 2:
        return
    pts = list(trail);  n = len(pts);  sk = max(1, n//120)
    r, g, b = col
    for i in range(sk, n, sk):
        ax, ay = to_screen(*pts[i-sk]);  bx, by = to_screen(*pts[i])
        br = (i/n)*0.38
        pygame.draw.line(screen, (int(r*br), int(g*br), int(b*br)), (int(ax),int(ay)), (int(bx),int(by)))


def draw_world_border():
    corners = [(WORLD_X0, WORLD_Y0), (WORLD_X0+WORLD_W, WORLD_Y0),
               (WORLD_X0+WORLD_W, WORLD_Y0+WORLD_H), (WORLD_X0, WORLD_Y0+WORLD_H)]
    pts = [(int(x), int(y)) for x, y in (to_screen(wx, wy) for wx, wy in corners)]
    pygame.draw.polygon(screen, (38, 25, 62), pts, 2)


def draw_shockwaves():
    if not shockwaves:
        return
    _overlay.fill((0, 0, 0, 0))
    for sw in shockwaves:
        px, py   = to_screen(sw['x'], sw['y'])
        r_screen = int(sw['r'] * cam['zoom'])
        if r_screen < 2:
            continue
        # clip if entirely off-screen
        if px+r_screen < -200 or px-r_screen > W+200 or py+r_screen < -200 or py-r_screen > H+200:
            continue
        alpha_f = sw['strength'] / max(1, sw['strength0'])
        base_a  = int(alpha_f * 200)
        cr, cg, cb = sw['col']

        # outer glow rings
        for gi in range(5, 0, -1):
            gr = r_screen + int(r_screen * gi * 0.11)
            ga = int(base_a * 0.28 * gi / 5)
            tk = max(1, gi * 3)
            pygame.draw.circle(_overlay, (cr, cg, cb, ga), (int(px), int(py)), gr, tk)

        # main ring
        tk = max(2, r_screen // 14)
        pygame.draw.circle(_overlay, (cr, cg, cb, base_a), (int(px), int(py)), r_screen, tk)

        # core flash early in explosion
        t_norm = sw['age'] / max(0.001, sw['duration'])
        if t_norm < 0.25:
            core_a = int(alpha_f * 220 * (1 - t_norm / 0.25))
            core_r = max(1, int(r_screen * 0.25))
            pygame.draw.circle(_overlay, (255, 255, 255, core_a), (int(px), int(py)), core_r)

    screen.blit(_overlay, (0, 0))


def draw_gravity_waves():
    if not gravity_waves:
        return
    z = cam['zoom']
    _overlay.fill((0, 0, 0, 0))
    for gw in gravity_waves:
        cx, cy = to_screen(gw['x'], gw['y'])
        r_s = int(gw['r'] * z)
        if r_s < 2:
            continue
        a = int(gw['alpha'] * 200)
        col = gw['col']
        for ring in range(3):
            ro = r_s - ring * 5
            if ro > 0:
                pygame.draw.circle(_overlay, (*col, a // (ring + 1)), (int(cx), int(cy)), ro, 2)
    screen.blit(_overlay, (0, 0))

def draw_habitable_zone(px, py, vis_rad, z):
    ri = int(vis_rad * 20 * z)
    ro = int(vis_rad * 36 * z)
    if ri < 3:
        return
    _overlay.fill((0, 0, 0, 0))
    pygame.draw.circle(_overlay, (60, 180, 60, 14), (int(px), int(py)), ro)
    pygame.draw.circle(_overlay, (0, 0, 0, 0), (int(px), int(py)), ri)
    pygame.draw.circle(_overlay, (60, 180, 60, 32), (int(px), int(py)), ri, 2)
    pygame.draw.circle(_overlay, (60, 180, 60, 32), (int(px), int(py)), ro, 2)
    screen.blit(_overlay, (0, 0))

def draw_body_rings(px, py, r, col):
    for scale, alpha, thick in [(2.4, 55, 3), (3.2, 35, 2)]:
        rw = int(r * scale);  rh = max(1, int(r * scale * 0.25))
        surf = pygame.Surface((rw * 2 + 4, rh * 2 + 4), pygame.SRCALPHA)
        pygame.draw.ellipse(surf, (*col, alpha), (2, 2, rw * 2, rh * 2), thick)
        screen.blit(surf, (int(px) - rw - 2, int(py) - rh - 2))

def draw_comet_tail(b, px, py, r, z):
    nearest = None;  nd = float('inf')
    for m in bodies:
        if m is b or not (m.get('glow') or m.get('neutron') or m.get('bh')):
            continue
        d = math.hypot(b['x'] - m['x'], b['y'] - m['y'])
        if d < nd:
            nd = d;  nearest = m
    if nearest:
        dx = b['x'] - nearest['x'];  dy = b['y'] - nearest['y']
    else:
        dx, dy = b['vx'] or 0.0, b['vy'] or 0.0
    dist = math.hypot(dx, dy) or 1
    tx = dx / dist;  ty = dy / dist
    tail_len = max(int(r * 8), int(55 * z))
    _overlay.fill((0, 0, 0, 0))
    for i in range(18):
        t = i / 17
        ex = int(px + tx * tail_len * t);  ey = int(py + ty * tail_len * t)
        a = int(140 * (1 - t))
        w = max(1, int(r * (1 - t * 0.85)))
        pygame.draw.circle(_overlay, (200, 220, 255, a), (ex, ey), w)
    screen.blit(_overlay, (0, 0))

def draw_neutron_pulsar(px, py, r, spin):
    _overlay.fill((0, 0, 0, 0))
    beam_len = max(r * 18, 110)
    steps = 18
    for base_angle in [spin, spin + math.pi]:
        for step in range(steps):
            t = step / steps
            dist = beam_len * t
            # cone widens and fades with distance
            width = max(1, int((1 - t * 0.7) * r * 0.9 + t * r * 3.5))
            alpha = int((1.0 - t) ** 1.6 * 210)
            if alpha <= 0:
                continue
            cx_ = int(px + math.cos(base_angle) * dist)
            cy_ = int(py + math.sin(base_angle) * dist)
            # core bright beam
            beam_col = (180, 235, 255, alpha)
            pygame.draw.circle(_overlay, beam_col, (cx_, cy_), width)
            # outer glow halo at this slice
            halo_r = int(width * 2.0)
            halo_a = max(0, alpha // 4)
            if halo_r > 1:
                pygame.draw.circle(_overlay, (120, 200, 255, halo_a), (cx_, cy_), halo_r)
    screen.blit(_overlay, (0, 0))

def draw_wormhole_body(px, py, r):
    _overlay.fill((0, 0, 0, 0))
    for i in range(8, 0, -1):
        t = i / 8
        pygame.draw.circle(_overlay, (100, 50, 200, int(75 * t)), (int(px), int(py)), int(r * t * 2.4))
    pygame.draw.circle(_overlay, (200, 140, 255, 200), (int(px), int(py)), r, 3)
    pygame.draw.circle(_overlay, (240, 220, 255, 130), (int(px), int(py)), max(2, r // 3))
    screen.blit(_overlay, (0, 0))

def gen_nebula_particles(b):
    rng = random.Random(id(b))
    cr  = b.get('cloud_rad', b['rad'] * 6)
    pts = []

    # large background wisps
    for _ in range(12):
        ang = rng.uniform(0, math.tau)
        d   = abs(rng.gauss(0, cr * 0.42))
        r_p = rng.uniform(cr * 0.22, cr * 0.52)
        a_p = rng.randint(10, 28)
        cs  = rng.uniform(-20, 20)
        pts.append((math.cos(ang)*d, math.sin(ang)*d, r_p, a_p, cs))

    # mid-density body particles
    for _ in range(40):
        ang = rng.uniform(0, math.tau)
        d   = abs(rng.gauss(0, cr * 0.32))
        r_p = rng.uniform(cr * 0.04, cr * 0.11)
        a_p = rng.randint(45, 115)
        cs  = rng.uniform(-35, 35)
        pts.append((math.cos(ang)*d, math.sin(ang)*d, r_p, a_p, cs))

    # bright core sparks
    for _ in range(12):
        ang = rng.uniform(0, math.tau)
        d   = abs(rng.gauss(0, cr * 0.12))
        r_p = rng.uniform(cr * 0.01, cr * 0.035)
        a_p = rng.randint(140, 210)
        cs  = 30
        pts.append((math.cos(ang)*d, math.sin(ang)*d, r_p, a_p, cs))

    b['cloud_particles'] = pts
    b['spin_rate'] = rng.uniform(0.004, 0.016)


def draw_nebula_body(b, px, py, z):
    if 'cloud_particles' not in b:
        gen_nebula_particles(b)

    col  = b.get('col', (120, 80, 200))
    cr   = b.get('cloud_rad', b['rad'] * 6)
    spin = b.get('spin', 0.0)
    ca   = math.cos(spin);  sa = math.sin(spin)

    _overlay.fill((0, 0, 0, 0))
    glow_r = int(cr * z)
    if glow_r > 2:
        for i in range(6, 0, -1):
            t  = i / 6
            ga = int(20 * (1 - t) + 3)
            pygame.draw.circle(_overlay, (col[0] // 2, col[1] // 2, col[2] // 2, ga),
                               (int(px), int(py)), int(glow_r * t * 0.85))
    for ox, oy, rp, ap, cs in b['cloud_particles']:
        # rotate offset by current spin
        spx = px + (ox*ca - oy*sa) * z
        spy = py + (ox*sa + oy*ca) * z
        rs  = max(1, int(rp * z))
        # cull off-screen
        if spx < -rs or spx > W+rs or spy < -rs or spy > H+rs:
            continue
        rc = max(0, min(255, col[0] + int(cs)))
        gc = max(0, min(255, col[1]))
        bc = max(0, min(255, col[2] + int(cs * 0.5)))
        pygame.draw.circle(_overlay, (rc, gc, bc, ap), (int(spx), int(spy)), rs)

    screen.blit(_overlay, (0, 0))


def draw_bodies():
    z = cam['zoom']
    for b in bodies:
        px, py = to_screen(b['x'], b['y'])
        if b.get('bh'):
            vis_rad = b['rad'] * 2.2;  r = max(int(vis_rad * z), 5)
        elif b.get('neutron'):
            vis_rad = b['rad'] * 1.4;  r = max(int(vis_rad * z), 4)
        elif b.get('glow'):
            vis_rad = b['rad'] * 1.6;  r = max(int(vis_rad * z), 4)
        elif b.get('wormhole'):
            vis_rad = b['rad'] * 2.0;  r = max(int(vis_rad * z), 5)
        else:
            vis_rad = b['rad'];        r = max(int(vis_rad * z), 3)

        if b.get('ship'):
            ang = b.get('angle', 0.0)
            sz = max(2, int(b['rad'] * z))
            pts_local = [(sz*1.2, 0), (-sz*0.7, -sz*0.6), (-sz*0.7, sz*0.6)]
            pts = []
            ca = math.cos(ang); sa = math.sin(ang)
            for lx, ly in pts_local:
                pts.append((int(px + (lx*ca - ly*sa)), int(py + (lx*sa + ly*ca))))
            pygame.draw.polygon(screen, b.get('col', (200,200,255)), pts)
            pygame.draw.polygon(screen, (20,20,40), pts, 2)
            # direction needle — starts past nose, scales independently
            _nd_s = sz * 1.6
            _nd_e = max(18, sz * 7)
            _nx1 = int(px + ca * _nd_s);  _ny1 = int(py + sa * _nd_s)
            _nx2 = int(px + ca * _nd_e);  _ny2 = int(py + sa * _nd_e)
            pygame.draw.line(screen, (160, 190, 255), (_nx1, _ny1), (_nx2, _ny2), 1)
            _tk = 4
            for _ta in (0.45, -0.45):
                pygame.draw.line(screen, (160, 190, 255), (_nx2, _ny2),
                                 (int(_nx2 - ca*_tk + math.sin(_ta)*_tk),
                                  int(_ny2 - sa*_tk - math.cos(_ta)*_tk)), 1)
            fwd = b.get('thrust_fwd', False);  rev = b.get('thrust_back', False)
            if fwd:
                fpts = [
                    (int(px - math.cos(ang)*(sz*0.6) + math.sin(ang)*(sz*0.3)), int(py - math.sin(ang)*(sz*0.6) - math.cos(ang)*(sz*0.3))),
                    (int(px - math.cos(ang)*(sz*2.0)), int(py - math.sin(ang)*(sz*2.0))),
                    (int(px - math.cos(ang)*(sz*0.6) - math.sin(ang)*(sz*0.3)), int(py - math.sin(ang)*(sz*0.6) + math.cos(ang)*(sz*0.3))),
                ]
                pygame.draw.polygon(screen, (255,160,40), fpts)
            if rev:
                fpts_f = [
                    (int(px + math.cos(ang)*(sz*0.6) + math.sin(ang)*(sz*0.2)), int(py + math.sin(ang)*(sz*0.6) - math.cos(ang)*(sz*0.2))),
                    (int(px + math.cos(ang)*(sz*1.6)), int(py + math.sin(ang)*(sz*1.6))),
                    (int(px + math.cos(ang)*(sz*0.6) - math.sin(ang)*(sz*0.2)), int(py + math.sin(ang)*(sz*0.6) + math.cos(ang)*(sz*0.2))),
                ]
                pygame.draw.polygon(screen, (200,120,255), fpts_f)
            try:
                vx = b.get('vx', 0.0); vy = b.get('vy', 0.0)
                vscale = 0.12 * cam['zoom']
                ex = int(px + vx * vscale);  ey = int(py + vy * vscale)
                pygame.draw.line(screen, (120, 255, 140), (int(px), int(py)), (ex, ey), 3)
                if abs(vx) > 1e-6 or abs(vy) > 1e-6:
                    angv = math.atan2(vy, vx)
                    ah1 = (int(ex - 8*math.cos(angv-0.4)), int(ey - 8*math.sin(angv-0.4)))
                    ah2 = (int(ex - 8*math.cos(angv+0.4)), int(ey - 8*math.sin(angv+0.4)))
                    pygame.draw.polygon(screen, (120,255,140), [(ex, ey), ah1, ah2])
            except Exception:
                pass

        elif b.get('wormhole'):
            draw_wormhole_body(px, py, r)

        elif b.get('nebula'):
            draw_nebula_body(b, px, py, z)

        elif b.get('neutron'):
            gs = get_glow_surf(vis_rad * 0.6, z)
            half = gs.get_width() // 2
            screen.blit(gs, (int(px)-half, int(py)-half))
            pygame.draw.circle(screen, (200, 240, 255), (int(px), int(py)), r)
            draw_neutron_pulsar(px, py, r, b['spin'])

        elif b.get('bh'):
            gs = get_bh_glow_surf(vis_rad, z)
            half = gs.get_width() // 2
            screen.blit(gs, (int(px)-half, int(py)-half))
            pygame.draw.circle(screen, (0, 0, 5), (int(px), int(py)), r)
            pygame.draw.circle(screen, (40, 20, 70), (int(px), int(py)), int(r*1.45), 2)
            _overlay.fill((0, 0, 0, 0))
            pygame.draw.circle(_overlay, (90, 120, 255, 40), (int(px), int(py)), int(r * 2.6), 3)
            pygame.draw.circle(_overlay, (110, 160, 255, 24), (int(px), int(py)), int(r * 3.8), 4)
            screen.blit(_overlay, (0, 0))

        elif b['glow']:
            gs = get_glow_surf(vis_rad, z)
            half = gs.get_width() // 2
            screen.blit(gs, (int(px)-half, int(py)-half))
            pygame.draw.circle(screen, b['col'], (int(px), int(py)), r)
            draw_habitable_zone(px, py, vis_rad, z)

        else:
            pygame.draw.circle(screen, b['col'], (int(px), int(py)), r)
            if b.get('comet'):
                draw_comet_tail(b, px, py, r, z)

        # rings (drawn behind label but after body circle)
        if b.get('has_rings') and not b.get('ship'):
            draw_body_rings(px, py, r, b.get('col', (200, 200, 200)))

        # spin tick mark
        spin = b.get('spin', 0.0)
        if b.get('spin_rate') and r >= 5 and not b.get('ship') and not b.get('nebula') and not b.get('wormhole'):
            ex = int(px + math.cos(spin) * r * 0.85)
            ey = int(py + math.sin(spin) * r * 0.85)
            pygame.draw.line(screen, (255, 255, 255), (int(px), int(py)), (ex, ey), 1)

        # tidal heating glow
        heat = b.get('tidal_heat', 0.0)
        if heat > 0.04:
            a = int(heat * 110)
            _overlay.fill((0, 0, 0, 0))
            pygame.draw.circle(_overlay, (255, 130, 30, a), (int(px), int(py)), int(r * 1.7), 4)
            screen.blit(_overlay, (0, 0))

        # follow-target highlight
        if follow_target is b:
            _overlay.fill((0, 0, 0, 0))
            pygame.draw.circle(_overlay, (80, 200, 255, 140), (int(px), int(py)), r+8, 2)
            screen.blit(_overlay, (0, 0))

        lbl_col = (180, 200, 255) if b.get('bh') else (160, 100, 255) if b.get('wormhole') else (110, 110, 110)
        lbl = font_sm.render(b['name'], True, lbl_col)
        screen.blit(lbl, (int(px)+r+6, int(py)-9))
        if not b.get('wormhole') and not b.get('nebula') and not b.get('ship'):
            ms = font_xs.render(f'{b["mass"]:.2e} kg', True, (50, 50, 68))
            screen.blit(ms, (int(px)+r+6, int(py)+8))


def draw_object_finder():
    global _obj_scroll, _obj_filter_rects, _obj_icon_rects
    # panel background
    pygame.draw.rect(screen, (5, 5, 14),    (OBJ_X, OBJ_Y, OBJ_W, OBJ_H), border_radius=6)
    pygame.draw.rect(screen, (28, 28, 44),  (OBJ_X, OBJ_Y, OBJ_W, OBJ_H), 1, border_radius=6)

    # filter buttons
    _FILTERS = [('all','All'),('star','Stars'),('planet','Planets'),('bh','BH'),('ship','Ship'),('other','Other')]
    _obj_filter_rects.clear()
    fx = OBJ_X + 8;  fy = OBJ_Y + 4;  fh = OBJ_FILTER_H - 2
    for key, label in _FILTERS:
        tw = font_xs.size(label)[0] + 14
        rect = pygame.Rect(fx, fy, tw, fh)
        active = (_obj_filter == key)
        pygame.draw.rect(screen, (40,80,140) if active else (16,16,26), rect, border_radius=3)
        pygame.draw.rect(screen, (80,150,255) if active else (40,40,60), rect, 1, border_radius=3)
        tc = (200,230,255) if active else (90,90,120)
        ls = font_xs.render(label, True, tc)
        screen.blit(ls, (fx+(tw-ls.get_width())//2, fy+(fh-ls.get_height())//2))
        _obj_filter_rects.append((rect, key))
        fx += tw + 4

    # icon area
    vis = get_filtered_bodies()
    n   = len(vis)
    _obj_scroll = max(0, min(_obj_scroll, max(0, n-1)))
    icon_x0 = OBJ_X + _OBJ_ARROW_W
    slots   = (OBJ_W - _OBJ_ARROW_W*2) // OBJ_ICON_W
    _obj_icon_rects.clear()

    # scroll arrows
    if _obj_scroll > 0:
        sa = font_sm.render('<', True, (140,160,200))
        screen.blit(sa, (OBJ_X+(_OBJ_ARROW_W-sa.get_width())//2, OBJ_ICON_CY-sa.get_height()//2))
    if _obj_scroll + slots < n:
        sa = font_sm.render('>', True, (140,160,200))
        screen.blit(sa, (OBJ_X+OBJ_W-_OBJ_ARROW_W+(_OBJ_ARROW_W-sa.get_width())//2, OBJ_ICON_CY-sa.get_height()//2))

    for slot in range(slots):
        idx = _obj_scroll + slot
        if idx >= n:
            break
        b      = vis[idx]
        cx     = icon_x0 + slot*OBJ_ICON_W + OBJ_ICON_W//2
        cy     = OBJ_ICON_CY
        r      = OBJ_ICON_R
        sel    = follow_target is b
        if sel:
            pygame.draw.circle(screen, (18,38,76), (cx,cy), r+6)
        if b.get('bh'):
            pygame.draw.circle(screen, (0,0,8), (cx,cy), r)
            pygame.draw.circle(screen, (160,160,255), (cx,cy), r, 2)
        elif b.get('ship'):
            ang = b.get('angle', 0.0);  ca = math.cos(ang);  sa2 = math.sin(ang)
            pts_l = [(r*1.1,0),(-r,-r*0.9),(-r,r*0.9)]
            pts   = [(int(cx+(lx*ca-ly*sa2)), int(cy+(lx*sa2+ly*ca))) for lx,ly in pts_l]
            pygame.draw.polygon(screen, b.get('col',(200,200,255)), pts)
        elif b.get('neutron'):
            pygame.draw.circle(screen, (200,240,255), (cx,cy), r)
            pygame.draw.circle(screen, (120,200,255), (cx,cy), r, 2)
        elif b.get('wormhole'):
            pygame.draw.circle(screen, (60,20,130), (cx,cy), r)
            pygame.draw.circle(screen, (180,100,255), (cx,cy), r, 2)
        elif b.get('glow'):
            pygame.draw.circle(screen, b['col'], (cx,cy), r)
            pygame.draw.circle(screen, (255,240,160), (cx,cy), r+2, 2)
        else:
            pygame.draw.circle(screen, b['col'], (cx,cy), r)
        if sel:
            pygame.draw.circle(screen, (80,200,255), (cx,cy), r, 2)
        tc  = (80,200,255) if sel else (90,90,120)
        lbl = font_xs.render(b['name'][:9], True, tc)
        screen.blit(lbl, (cx-lbl.get_width()//2, cy+r+3))
        slot_rect = pygame.Rect(icon_x0+slot*OBJ_ICON_W, OBJ_Y+OBJ_FILTER_H+4, OBJ_ICON_W, OBJ_H-OBJ_FILTER_H-4)
        _obj_icon_rects.append((slot_rect, b))

    ct = font_xs.render(f'{n}', True, (40,40,60))
    screen.blit(ct, (OBJ_X+OBJ_W-ct.get_width()-5, OBJ_Y+5))


def draw_binary_links():
    for b in bodies:
        partner = b.get('binary_partner')
        if partner is None or partner not in bodies:
            continue
        if id(b) > id(partner):
            continue
        sx1, sy1 = to_screen(b['x'], b['y'])
        sx2, sy2 = to_screen(partner['x'], partner['y'])
        tot = b['mass'] + partner['mass']
        com_x = (b['mass']*b['x'] + partner['mass']*partner['x']) / tot
        com_y = (b['mass']*b['y'] + partner['mass']*partner['y']) / tot
        csx, csy = to_screen(com_x, com_y)
        _overlay.fill((0,0,0,0))
        pygame.draw.line(_overlay, (180,200,255,35), (int(sx1),int(sy1)), (int(sx2),int(sy2)), 1)
        pygame.draw.circle(_overlay, (180,200,255,70), (int(csx),int(csy)), 3)
        screen.blit(_overlay, (0,0))


def draw_spawn_preview():
    if not spawning:
        return
    mods  = pygame.key.get_mods()
    shift = bool(mods & pygame.KMOD_SHIFT)

    wx, wy   = to_world(spawn_sx, spawn_sy)
    px, py   = to_screen(wx, wy)
    col      = COLS[spawn_col_idx]
    r_screen = max(3, int(spawn_size * cam['zoom']))

    sdx = mouse_sx - spawn_sx;  sdy = mouse_sy - spawn_sy
    drag_len = math.hypot(sdx, sdy) or 1

    # if a body is selected (follow_target), use it as the shift-orbit anchor
    orbit_anchor = follow_target if (shift and follow_target is not None) else None
    if orbit_anchor is not None:
        dx_ = wx - orbit_anchor['x'];  dy_ = wy - orbit_anchor['y']
        d_  = math.sqrt(dx_*dx_ + dy_*dy_) or 1
        nb  = orbit_anchor;  v_orb = circ(d_, orbit_anchor['mass'])
    else:
        nb, _, v_orb = orbit_info(wx, wy)

    if shift and nb is not None:
        vx_o, vy_o = orbit_velocity(wx, wy, sdx, sdy, override_body=orbit_anchor)
        disp_speed = v_orb
        ov         = math.hypot(vx_o, vy_o) or 1
        nx, ny     = vx_o/ov, vy_o/ov
        arrow_col  = (80, 220, 255, 210)
        init_vx, init_vy = vx_o, vy_o
    else:
        disp_speed = drag_to_speed(drag_len)
        nx, ny     = sdx/drag_len, sdy/drag_len
        arrow_col  = (255, 200, 80, 200)
        init_vx, init_vy = nx * disp_speed, ny * disp_speed

    al     = min(drag_len, 1400)
    ex, ey = int(px + nx*al), int(py + ny*al)

    _overlay.fill((0, 0, 0, 0))

    # trajectory preview — single-entry cache; recompute only when inputs change
    global _spawn_traj_key, _spawn_traj_val
    traj_dt  = 0.05 / max(0.05, cam['zoom'])
    traj_key = (round(wx, 1), round(wy, 1), round(init_vx, 2), round(init_vy, 2), round(traj_dt, 4))
    if traj_key != _spawn_traj_key:
        try:
            raw_pts = predict_trajectory(wx, wy, init_vx, init_vy, steps=800, dt=traj_dt, sample=1, max_bodies=8)
            _spawn_traj_val = smooth_points(raw_pts, window=7) if raw_pts else []
        except (OverflowError, ZeroDivisionError, ValueError):
            _spawn_traj_val = []
        _spawn_traj_key = traj_key
    traj_sm = _spawn_traj_val

    if traj_sm:
        spts = [to_screen(x, y) for x, y in traj_sm]
        if len(spts) >= 2:
            try:
                pygame.draw.aalines(_overlay, (255, 220, 120, 160), False, spts)
            except (TypeError, ValueError):
                for i in range(len(spts)-1):
                    pygame.draw.line(_overlay, (255, 220, 120, 120),
                                     (int(spts[i][0]), int(spts[i][1])),
                                     (int(spts[i+1][0]), int(spts[i+1][1])), 2)
        # fading dots — single pass: accumulate distance and draw together
        tot = sum(math.hypot(traj_sm[i][0]-traj_sm[i-1][0], traj_sm[i][1]-traj_sm[i-1][1])
                  for i in range(1, len(traj_sm))) or 1.0
        run = 0.0
        for i, (sx, sy) in enumerate(spts):
            if i > 0:
                run += math.hypot(traj_sm[i][0]-traj_sm[i-1][0], traj_sm[i][1]-traj_sm[i-1][1])
            a = int(200 * (1.0 - min(1.0, run / tot)))
            pygame.draw.circle(_overlay, (255, 220, 120, a), (int(sx), int(sy)), 2)
    if spawn_type == 'bh':
        for gi in range(5, 0, -1):
            gr = r_screen + gi*r_screen//3
            pygame.draw.circle(_overlay, (160, 180, 255, 30*gi//5), (int(px), int(py)), gr)
        pygame.draw.circle(_overlay, (0, 0, 10, 200), (int(px), int(py)), r_screen)
    else:
        pygame.draw.circle(_overlay, (*col, 130), (int(px), int(py)), r_screen)
        if spawn_type == 'star':
            pygame.draw.circle(_overlay, (255, 220, 80, 60), (int(px), int(py)), r_screen*3)

    pygame.draw.line(_overlay, arrow_col, (int(px), int(py)), (ex, ey), 3)
    ang = math.atan2(ny, nx)
    ap1 = (int(ex-14*math.cos(ang-0.4)), int(ey-14*math.sin(ang-0.4)))
    ap2 = (int(ex-14*math.cos(ang+0.4)), int(ey-14*math.sin(ang+0.4)))
    pygame.draw.polygon(_overlay, (*arrow_col[:3], 230), [(ex,ey), ap1, ap2])
    screen.blit(_overlay, (0, 0))

    txt_col = (80, 220, 255) if shift else (255, 200, 80)
    if shift and nb is not None:
        screen.blit(font_xs.render(f'v = {disp_speed:.0f}  [ORBIT @ {nb["name"]}]', True, txt_col), (ex+12, ey-10))
    else:
        screen.blit(font_xs.render(f'v = {disp_speed:.0f}', True, txt_col), (ex+12, ey-10))
        if nb is not None:
            screen.blit(font_xs.render(f'orbit @ {nb["name"]}: {v_orb:.0f}  [SHIFT]', True, (55,130,200)), (ex+12, ey+12))


def draw_spawn_panel():
    global _btn_clone_rect, _btn_belt_rect, _btn_rnd_rect
    global _spawn_type_btn_rect, _spawn_dropdown_rects

    _TYPE_INFO = {
        'planet':  ('Planet',       (68,  170, 255)),
        'star':    ('Star',         (255, 208,  80)),
        'bh':      ('Black Hole',   (190, 170, 255)),
        'binary':  ('Binary Pair',  (120, 220, 180)),
        'ship':    ('Ship',         (180, 200, 255)),
        'comet':   ('Comet',        (180, 220, 255)),
        'neutron': ('Neutron Star', (160, 240, 255)),
        'wormhole':('Wormhole',     (200, 130, 255)),
        'nebula':  ('Nebula',       (140, 100, 210)),
        'delete':  ('Delete',       (255,  80,  80)),
    }
    lbl, hdr_col = _TYPE_INFO.get(spawn_type, ('Planet', (68,170,255)))

    # ── panel background ──────────────────────────────────────────────────
    _panel_surf.fill((0, 0, 0, 0))
    pygame.draw.rect(_panel_surf, (6,6,16,245),   (0,0,PANEL_W,PANEL_H), border_radius=8)
    pygame.draw.rect(_panel_surf, (28,28,44,255), (0,0,PANEL_W,PANEL_H), 1, border_radius=8)
    screen.blit(_panel_surf, (PANEL_X, PANEL_Y))
    ox = PANEL_X + 20

    # ── dropdown trigger button ───────────────────────────────────────────
    btn_h = 28
    _spawn_type_btn_rect = pygame.Rect(PANEL_X+8, PANEL_Y+8, PANEL_W-16, btn_h)
    bg_col = (36, 36, 58) if _spawn_dropdown_open else (22, 22, 38)
    pygame.draw.rect(screen, bg_col, _spawn_type_btn_rect, border_radius=5)
    pygame.draw.rect(screen, hdr_col, _spawn_type_btn_rect, 1, border_radius=5)
    pygame.draw.circle(screen, hdr_col, (_spawn_type_btn_rect.x+16, _spawn_type_btn_rect.centery), 5)
    ts = font_sm.render(f'SPAWN: {lbl.upper()}', True, hdr_col)
    screen.blit(ts, (PANEL_X+28, PANEL_Y+8+(btn_h-ts.get_height())//2))
    arr = font_xs.render('v' if not _spawn_dropdown_open else '^', True, hdr_col)
    screen.blit(arr, (PANEL_X+PANEL_W-18, PANEL_Y+8+(btn_h-arr.get_height())//2))

    # ── dropdown list (replaces rest of panel when open) ──────────────────
    _spawn_dropdown_rects.clear()
    if _spawn_dropdown_open:
        row_h  = 24
        drop_y = PANEL_Y + 8 + btn_h + 2
        drop_w = PANEL_W - 16
        bg_r   = pygame.Rect(PANEL_X+8, drop_y, drop_w, len(SPAWN_TYPES)*row_h+6)
        pygame.draw.rect(screen, (10,10,20), bg_r, border_radius=5)
        pygame.draw.rect(screen, (40,40,62), bg_r, 1, border_radius=5)
        for idx, key in enumerate(SPAWN_TYPES):
            itxt, icol = _TYPE_INFO.get(key, (key, (150,150,150)))
            iy   = drop_y + 3 + idx*row_h
            item_rect = pygame.Rect(PANEL_X+10, iy, drop_w-4, row_h-2)
            if key == spawn_type:
                pygame.draw.rect(screen, (30,45,72), item_rect, border_radius=3)
            pygame.draw.circle(screen, icol, (PANEL_X+22, iy+(row_h-2)//2), 4)
            is_ = font_xs.render(itxt, True, icol)
            screen.blit(is_, (PANEL_X+32, iy+(row_h-2-is_.get_height())//2))
            _spawn_dropdown_rects.append((item_rect, key))
        return   # don't draw rest of panel while list is open

    # ── type-specific content ─────────────────────────────────────────────
    no_size = spawn_type in ('ship', 'delete', 'wormhole', 'binary')
    if no_size:
        hints = {
            'ship':    'Ship — no editable properties',
            'delete':  'Right-click a body to delete it',
            'wormhole':'Place two to create a linked pair',
            'binary':  'Place two bodies — auto-sets mutual orbit',
        }
        screen.blit(font_sm.render(hints.get(spawn_type, ''), True, (153,221,255)), (ox, PANEL_Y+58))
    else:
        screen.blit(font_xs.render('Size', True, (80,80,100)), (ox, PANEL_Y+48))
        if spawn_type == 'bh':
            m_val, mult = bh_spawn_mass(spawn_size)
            m_str = f'x{mult}  m={m_val:.2e}'
        elif spawn_type == 'star':
            m_str = f'r={spawn_size}   m={size_to_star_mass(spawn_size):,}'
        elif spawn_type == 'neutron':
            m_str = f'r={spawn_size//3}   m={SM*3:,}'
        elif spawn_type == 'nebula':
            m_str = f'cloud r={spawn_size*6}'
        else:
            m_str = f'r={spawn_size}   m={size_to_mass(spawn_size):,}'
        screen.blit(font_sm.render(m_str, True, (153,221,255)), (ox, PANEL_Y+66))

        pygame.draw.rect(screen, (35,35,55), (SL_X, SL_Y-3, SL_W, 6), border_radius=3)
        fill_w = max(0, slider_hx()-SL_X)
        if fill_w:
            pygame.draw.rect(screen, (50,130,220), (SL_X, SL_Y-3, fill_w, 6), border_radius=3)
        pygame.draw.circle(screen, (68,170,255), (slider_hx(), SL_Y), 11)
        pygame.draw.circle(screen, (200,228,255), (slider_hx(), SL_Y), 11, 2)
        screen.blit(font_xs.render('[ ] nudge size', True, (50,50,68)), (ox, PANEL_Y+134))

        no_col = spawn_type in ('bh', 'neutron', 'wormhole', 'nebula')
        if not no_col:
            screen.blit(font_xs.render('Color', True, (80,80,100)), (ox, PANEL_Y+166))
            for i, col in enumerate(COLS):
                cx = SWATCH_X0 + i*SWATCH_GAP
                pygame.draw.circle(screen, col, (cx, SWATCH_Y), SWATCH_R)
                if i == spawn_col_idx:
                    pygame.draw.circle(screen, (255,255,255), (cx, SWATCH_Y), SWATCH_R, 2)

    # ── action buttons ────────────────────────────────────────────────────
    btn_y = PANEL_Y + 258
    _btn_clone_rect = pygame.Rect(PANEL_X+20,  btn_y, 88, 24)
    _btn_belt_rect  = pygame.Rect(PANEL_X+116, btn_y, 88, 24)
    _btn_rnd_rect   = pygame.Rect(PANEL_X+212, btn_y, 88, 24)
    for bx, bg, fg, label in [
        (PANEL_X+20,  (45,70,45), (80,170,80),  'Clone'),
        (PANEL_X+116, (40,50,75), (80,120,200), 'Belt'),
        (PANEL_X+212, (70,45,75), (180,90,200), 'Rnd'),
    ]:
        r = pygame.Rect(bx, btn_y, 88, 24)
        pygame.draw.rect(screen, bg, r, border_radius=4)
        pygame.draw.rect(screen, fg, r, 1, border_radius=4)
        t = font_xs.render(label, True, fg)
        screen.blit(t, (bx+(88-t.get_width())//2, btn_y+(24-t.get_height())//2))

    screen.blit(font_xs.render('right-click to spawn', True, (50,50,68)), (ox, PANEL_Y+290))


def draw_landing_prompt():
    if player_ship is None or player_ship not in bodies:
        return
    b = player_ship
    px, py = to_screen(b['x'], b['y'])

    # faint approach-zone ring around the target planet
    if _approach_target is not None and _approach_target in bodies:
        tpx, tpy = to_screen(_approach_target['x'], _approach_target['y'])
        ring_r = int(_approach_target['rad'] * 5.0 * cam['zoom'])
        if ring_r > 4:
            _overlay.fill((0, 0, 0, 0))
            pygame.draw.circle(_overlay, (80, 200, 120, 35), (int(tpx), int(tpy)), ring_r)
            pygame.draw.circle(_overlay, (80, 200, 120, 70), (int(tpx), int(tpy)), ring_r, 1)
            screen.blit(_overlay, (0, 0))

    if landed_on is not None and landed_on in bodies:
        lbl = font_xs.render(f'LANDED: {landed_on["name"]}  [L] launch  [WASD] thrust off', True, (120, 255, 160))
        screen.blit(lbl, (int(px) - lbl.get_width()//2, int(py) - 28))
    elif _land_candidate is not None:
        lbl = font_xs.render(f'[L] Land on {_land_candidate["name"]}', True, (255, 220, 80))
        screen.blit(lbl, (int(px) - lbl.get_width()//2, int(py) - 28))
    elif _approach_target is not None:
        lbl = font_xs.render(f'Approach assist: {_approach_target["name"]}', True, (80, 180, 120))
        screen.blit(lbl, (int(px) - lbl.get_width()//2, int(py) - 28))


def draw_ship_trajectory(keys):
    if player_ship is None or player_ship not in bodies:
        return
    b = player_ship
    # only preview when thrust keys held
    if not (keys[pygame.K_w] or keys[pygame.K_s]):
        return
    # approximate initial velocity change from holding thrust for a short time
    mass = max(1.0, b['mass'])
    thrust_force = 120000.0
    preview_time = 0.6
    dv = (thrust_force / mass) * preview_time
    ang = b.get('angle', 0.0)
    if keys[pygame.K_w]:
        init_vx = b['vx'] + math.cos(ang) * dv
        init_vy = b['vy'] + math.sin(ang) * dv
        col = (80, 220, 255, 170)
    else:
        init_vx = b['vx'] - math.cos(ang) * dv
        init_vy = b['vy'] - math.sin(ang) * dv
        col = (255, 160, 120, 170)

    global _ship_traj_key, _ship_traj_val
    traj_dt = 0.05 / max(0.05, cam['zoom'])
    key = (round(b['x'], 1), round(b['y'], 1), round(init_vx, 2), round(init_vy, 2), round(traj_dt, 4))
    if key != _ship_traj_key:
        try:
            raw_pts = predict_trajectory(b['x'], b['y'], init_vx, init_vy, steps=700, dt=traj_dt, sample=1, max_bodies=12)
            _ship_traj_val = smooth_points(raw_pts, window=7) if raw_pts else []
        except (OverflowError, ZeroDivisionError, ValueError):
            _ship_traj_val = []
        _ship_traj_key = key
    pts = _ship_traj_val
    if not pts:
        return
    spts = [to_screen(x, y) for x, y in pts]
    _overlay.fill((0, 0, 0, 0))
    try:
        pygame.draw.aalines(_overlay, col, False, spts)
    except (TypeError, ValueError):
        for i in range(len(spts)-1):
            pygame.draw.line(_overlay, col, (int(spts[i][0]), int(spts[i][1])), (int(spts[i+1][0]), int(spts[i+1][1])), 2)
    # fading dots
    tot = sum(math.hypot(pts[i][0]-pts[i-1][0], pts[i][1]-pts[i-1][1]) for i in range(1, len(pts))) or 1.0
    run = 0.0
    for i, (sx, sy) in enumerate(spts):
        if i > 0:
            run += math.hypot(pts[i][0]-pts[i-1][0], pts[i][1]-pts[i-1][1])
        a = int(200 * (1.0 - min(1.0, run / tot)))
        pygame.draw.circle(_overlay, (col[0], col[1], col[2], a), (int(sx), int(sy)), 2)
    screen.blit(_overlay, (0, 0))


_ap_traj_key = None
_ap_traj_val = []

def draw_autopilot_trajectory():
    global _ap_traj_key, _ap_traj_val
    if autopilot_mode is None or player_ship is None or player_ship not in bodies:
        return
    b = player_ship

    # resolve which body the autopilot is targeting (mirrors physics logic)
    if ap_locked_target is not None and ap_locked_target in bodies and not ap_locked_target.get('ship'):
        tgt = ap_locked_target
    else:
        tgt = None;  best = float('inf')
        for ob in bodies:
            if ob is b or ob.get('ship'):
                continue
            d = math.hypot(b['x']-ob['x'], b['y']-ob['y'])
            if d < best:
                best = d;  tgt = ob
    if tgt is None:
        return

    traj_dt = 0.05 / max(0.05, cam['zoom'])
    key = (round(b['x'], 1), round(b['y'], 1),
           round(b['vx'], 2), round(b['vy'], 2),
           round(traj_dt, 4), id(tgt))
    if key != _ap_traj_key:
        try:
            raw_pts = predict_trajectory(b['x'], b['y'], b['vx'], b['vy'],
                                         steps=900, dt=traj_dt, sample=1, max_bodies=14)
            _ap_traj_val = smooth_points(raw_pts, window=7) if raw_pts else []
        except (OverflowError, ZeroDivisionError, ValueError):
            _ap_traj_val = []
        _ap_traj_key = key

    pts = _ap_traj_val
    if not pts:
        return

    spts = [to_screen(x, y) for x, y in pts]
    col = (255, 220, 60) if autopilot_mode == 'orbit' else (255, 120, 60)
    _overlay.fill((0, 0, 0, 0))
    try:
        pygame.draw.aalines(_overlay, (*col, 160), False, spts)
    except (TypeError, ValueError):
        for i in range(len(spts)-1):
            pygame.draw.line(_overlay, (*col, 160),
                             (int(spts[i][0]), int(spts[i][1])),
                             (int(spts[i+1][0]), int(spts[i+1][1])), 1)

    # fading dots
    tot = sum(math.hypot(pts[i][0]-pts[i-1][0], pts[i][1]-pts[i-1][1])
              for i in range(1, len(pts))) or 1.0
    run = 0.0
    for i, (sx, sy) in enumerate(spts):
        if i > 0:
            run += math.hypot(pts[i][0]-pts[i-1][0], pts[i][1]-pts[i-1][1])
        a = int(180 * (1.0 - min(1.0, run / tot)))
        pygame.draw.circle(_overlay, (*col, a), (int(sx), int(sy)), 2)

    # draw a small diamond marker at the target body
    tx, ty = to_screen(tgt['x'], tgt['y'])
    dm = 7
    pygame.draw.polygon(_overlay, (*col, 200),
                        [(tx, ty-dm), (tx+dm, ty), (tx, ty+dm), (tx-dm, ty)])

    screen.blit(_overlay, (0, 0))


def draw_all_trajectories():
    global show_all_trajs
    if not show_all_trajs:
        return
    if not bodies:
        return
    traj_dt = 0.06 / max(0.05, cam['zoom'])
    _overlay.fill((0,0,0,0))
    # draw predicted paths for non-fixed bodies (sampled to limit cost)
    for b in bodies:
        if b.get('fixed'):
            continue
        try:
            raw_pts = predict_trajectory(b['x'], b['y'], b['vx'], b['vy'], steps=1200, dt=traj_dt, sample=3, max_bodies=12)
            pts = smooth_points(raw_pts, window=5) if raw_pts else []
        except (OverflowError, ZeroDivisionError, ValueError):
            pts = []
        if not pts:
            continue
        spts = [to_screen(x,y) for x,y in pts]
        col = b.get('col', (180,180,220))
        col4 = (col[0], col[1], col[2], 90)
        try:
            pygame.draw.aalines(_overlay, col4, False, spts)
        except Exception:
            for i in range(len(spts)-1):
                pygame.draw.line(_overlay, col4, (int(spts[i][0]), int(spts[i][1])), (int(spts[i+1][0]), int(spts[i+1][1])), 1)
        tot = sum(math.hypot(pts[i][0]-pts[i-1][0], pts[i][1]-pts[i-1][1]) for i in range(1, len(pts))) or 1.0
        run = 0.0
        for i,(sx,sy) in enumerate(spts):
            if i>0:
                run += math.hypot(pts[i][0]-pts[i-1][0], pts[i][1]-pts[i-1][1])
            a = int(120*(1.0 - min(1.0, run / tot)))
            pygame.draw.circle(_overlay, (col[0], col[1], col[2], a), (int(sx), int(sy)), 1)
    screen.blit(_overlay, (0, 0))



def draw_minimap():

    _minimap_surf.fill((6, 6, 16, 215))
    screen.blit(_minimap_surf, (MM_X, MM_Y))
    for pos in star_mm:
        screen.set_at(pos, (46, 46, 60))
    for b in bodies:
        mx = MM_X + int((b['x']-WORLD_X0)*MM_SX)
        my = MM_Y + int((b['y']-WORLD_Y0)*MM_SY)
        br = max(3, int(b['rad']*MM_SX*50))
        c  = (0, 0, 5) if b.get('bh') else b['col']
        pygame.draw.circle(screen, c, (mx, my), br)
    hw  = (W/2)/cam['zoom'];  hh  = (H/2)/cam['zoom']
    vx1 = MM_X+int((cam['x']-hw-WORLD_X0)*MM_SX);  vy1 = MM_Y+int((cam['y']-hh-WORLD_Y0)*MM_SY)
    vx2 = MM_X+int((cam['x']+hw-WORLD_X0)*MM_SX);  vy2 = MM_Y+int((cam['y']+hh-WORLD_Y0)*MM_SY)
    rx  = max(MM_X, vx1);  ry  = max(MM_Y, vy1)
    rw  = min(MM_X+MM_W, vx2)-rx;  rh  = min(MM_Y+MM_H, vy2)-ry
    if rw > 0 and rh > 0:
        pygame.draw.rect(screen, (80,200,255), (rx,ry,rw,rh), 1)
    pygame.draw.rect(screen, (35,35,55), (MM_X,MM_Y,MM_W,MM_H), 1)
    screen.blit(font_xs.render('MAP', True, (40,40,56)), (MM_X+4, MM_Y+4))


def draw_rename_input():
    if renaming_body is None:
        return
    px, py   = to_screen(renaming_body['x'], renaming_body['y'])
    r        = max(int(renaming_body['rad'] * cam['zoom']), 3)
    cursor   = '|' if (pygame.time.get_ticks()//500)%2==0 else ''
    display  = rename_text + cursor
    box_w    = max(190, font_sm.size(display)[0]+24)
    box_h    = 34
    bx = max(4, min(W-box_w-4, int(px)+r+10))
    by = max(4, min(H-box_h-22, int(py)-box_h//2))
    # label above
    screen.blit(font_xs.render('RENAME  (Enter/Esc)', True, (50,80,130)), (bx, by-18))
    # box
    _rename_surf.fill((0, 0, 0, 0))
    pygame.draw.rect(_rename_surf, (8, 8, 22, 235), (0, 0, box_w, box_h))
    screen.blit(_rename_surf, (bx, by), (0, 0, box_w, box_h))
    pygame.draw.rect(screen, (80,150,255), (bx, by, box_w, box_h), 1, border_radius=4)
    txt = font_sm.render(display, True, (180,220,255))
    screen.blit(txt, (bx+8, by+(box_h-txt.get_height())//2))


def draw_props_panel():
    global _props_slider_rects, _props_lock_btn_rect
    if follow_target is None or follow_target not in bodies:
        _props_slider_rects = [];  _props_lock_btn_rect = None
        return
    b = follow_target
    _props_slider_rects = []

    _props_surf.fill((0, 0, 0, 0))
    pygame.draw.rect(_props_surf, (6, 6, 16, 245),   (0, 0, PROPS_W, PROPS_H), border_radius=8)
    pygame.draw.rect(_props_surf, (28, 28, 44, 255), (0, 0, PROPS_W, PROPS_H), 1, border_radius=8)
    screen.blit(_props_surf, (PROPS_X, PROPS_Y))

    # title + type tag
    title_s = font_sm.render(b['name'], True, (160, 200, 255))
    screen.blit(title_s, (PROPS_X + 12, PROPS_Y + 10))
    tag_col = (180,180,255) if b.get('bh') else (255,220,80) if b.get('glow') else \
              (160,240,255) if b.get('neutron') else (200,200,255) if b.get('ship') else (70,70,100)
    tag_txt = 'BH' if b.get('bh') else 'Star' if b.get('glow') else \
              'Neutron' if b.get('neutron') else 'Ship' if b.get('ship') else 'Body'
    tag_s = font_xs.render(tag_txt, True, tag_col)
    screen.blit(tag_s, (PROPS_X + PROPS_W - tag_s.get_width() - 12, PROPS_Y + 13))

    # lock toggle button
    lk_x = PROPS_X + 8;  lk_y = PROPS_Y + 36;  lk_w = PROPS_W - 16;  lk_h = 22
    _props_lock_btn_rect = pygame.Rect(lk_x, lk_y, lk_w, lk_h)
    pygame.draw.rect(screen, (18,45,18) if _props_lock_mass_rad else (18,18,30), _props_lock_btn_rect, border_radius=4)
    pygame.draw.rect(screen, (60,180,60) if _props_lock_mass_rad else (38,38,62), _props_lock_btn_rect, 1, border_radius=4)
    lk_txt = '[*] Mass <-> Radius  LOCKED' if _props_lock_mass_rad else '[ ] Lock Mass <-> Radius'
    lk_s   = font_xs.render(lk_txt, True, (80,210,80) if _props_lock_mass_rad else (60,60,100))
    screen.blit(lk_s, (lk_x + (lk_w - lk_s.get_width()) // 2, lk_y + (lk_h - lk_s.get_height()) // 2))

    # sliders
    bar_x = PROPS_X + 10;  bar_w = PROPS_W - 20;  fy = PROPS_Y + 68
    for key, label, lo, hi, log_scale in _PROP_SLIDERS:
        val = b.get(key, 0)
        t   = _val_to_t(val, lo, hi, log_scale)

        lbl_s = font_xs.render(label, True, (80, 80, 115))
        val_s = font_xs.render(_fmt_prop(key, val), True, (195, 220, 255))
        screen.blit(lbl_s, (bar_x, fy))
        screen.blit(val_s, (bar_x + bar_w - val_s.get_width(), fy))

        by = fy + lbl_s.get_height() + 4
        pygame.draw.rect(screen, (25, 25, 42), (bar_x, by, bar_w, 10), border_radius=5)
        fw = max(0, int(t * bar_w))
        if fw:
            pygame.draw.rect(screen, (40, 90, 180), (bar_x, by, fw, 10), border_radius=5)
        tx = bar_x + int(t * bar_w)
        pygame.draw.circle(screen, (90, 170, 255), (tx, by + 5), 7)
        pygame.draw.circle(screen, (200, 230, 255), (tx, by + 5), 7, 2)

        hit = pygame.Rect(bar_x - 2, by - 6, bar_w + 4, 22)
        _props_slider_rects.append((hit, bar_x, bar_w, key, lo, hi, log_scale))
        fy += PROPS_ROW_H


def draw_ui():
    global _warp_left_rect, _warp_right_rect

    # ── top-left: time warp with clickable buttons ────────────────────────
    y = 14
    bw, bh = 22, 22
    lbl = font_xs.render('Time ', True, (70, 70, 90))
    warp_surf = font.render(f'{warp}x', True, (200, 200, 200))
    screen.blit(lbl, (18, y + (bh - lbl.get_height()) // 2))
    xc = 18 + lbl.get_width() + 2

    _warp_left_rect = pygame.Rect(xc, y, bw, bh)
    pygame.draw.rect(screen, (24, 24, 38), _warp_left_rect, border_radius=4)
    pygame.draw.rect(screen, (55, 55, 85), _warp_left_rect, 1, border_radius=4)
    la = font_sm.render('<', True, (140, 160, 210))
    screen.blit(la, (xc + (bw - la.get_width()) // 2, y + (bh - la.get_height()) // 2))
    xc += bw + 5

    screen.blit(warp_surf, (xc, y + (bh - warp_surf.get_height()) // 2))
    xc += warp_surf.get_width() + 5

    _warp_right_rect = pygame.Rect(xc, y, bw, bh)
    pygame.draw.rect(screen, (24, 24, 38), _warp_right_rect, border_radius=4)
    pygame.draw.rect(screen, (55, 55, 85), _warp_right_rect, 1, border_radius=4)
    ra = font_sm.render('>', True, (140, 160, 210))
    screen.blit(ra, (xc + (bw - ra.get_width()) // 2, y + (bh - ra.get_height()) // 2))
    y += bh + 8

    # ── music ─────────────────────────────────────────────────────────────
    if music_files:
        mus_col = (100, 200, 100) if music_playing else (100, 100, 100)
        ms = font_xs.render(
            f"♫ {music_files[current_track_idx]} ({current_track_idx+1}/{len(music_files)})",
            True, mus_col)
        screen.blit(ms, (18, y));  y += ms.get_height() + 4
        vs_v = font_xs.render(f'Vol: {int(music_volume*100)}%', True, (100, 100, 150))
        screen.blit(vs_v, (18, y));  y += vs_v.get_height() + 6

    # ── reset button ──────────────────────────────────────────────────────
    RESET_RECT.y = y + 2
    pygame.draw.rect(screen, (30, 18, 42), RESET_RECT, border_radius=4)
    pygame.draw.rect(screen, (85, 50, 110), RESET_RECT, 1, border_radius=4)
    rl = font_xs.render('R — RESET', True, (150, 100, 180))
    screen.blit(rl, (RESET_RECT.x + (RESET_RECT.w - rl.get_width()) // 2,
                     RESET_RECT.y + (RESET_RECT.h - rl.get_height()) // 2))

    # ── top-right hints ───────────────────────────────────────────────────
    cy = 18
    for cl in ['scroll — zoom', 'drag — pan', 'T — trajectories',
               'right-click — spawn', 'SHIFT — orbit lock',
               'dbl-click — rename', 'O — orbit AP  |  E — escape AP']:
        s = font_xs.render(cl, True, (42, 42, 42))
        screen.blit(s, (W - s.get_width() - 18, cy));  cy += 20

    # ── above minimap: traj status + autopilot ────────────────────────────
    hy = MM_Y - 6
    traj_col = (100, 200, 100) if show_all_trajs else (60, 60, 80)
    traj_s = font_xs.render('T  Traj: ' + ('ON' if show_all_trajs else 'OFF'), True, traj_col)
    hy -= traj_s.get_height()
    screen.blit(traj_s, (MM_X, hy))
    if landed_on is not None and landed_on in bodies:
        ld_s = font_xs.render(f'LANDED: {landed_on["name"]}', True, (120, 255, 160))
        hy -= ld_s.get_height() + 4
        screen.blit(ld_s, (MM_X, hy))
    elif autopilot_mode is not None:
        ap_col = (80, 255, 160) if autopilot_mode == 'orbit' else (255, 160, 80)
        _ap_tgt_name = (ap_locked_target['name'] + ' [lock]') if (ap_locked_target is not None and ap_locked_target in bodies) else 'nearest'
        ap_s = font_xs.render(f'AP: {autopilot_mode.upper()} → {_ap_tgt_name}  [O/E]', True, ap_col)
        hy -= ap_s.get_height() + 4
        screen.blit(ap_s, (MM_X, hy))

    # ── shared panels ─────────────────────────────────────────────────────
    draw_object_finder()
    draw_spawn_panel()
    draw_minimap()
    draw_rename_input()
    draw_props_panel()

    if note_alpha > 0:
        ns = font_sm.render(note_text, True, (255, 170, 0))
        ns.set_alpha(int(note_alpha * 255))
        screen.blit(ns, (W // 2 - ns.get_width() // 2, H - 64))


def _build_tutorial_surf():
    surf = pygame.Surface((W, H), pygame.SRCALPHA)
    pygame.draw.rect(surf, (5, 5, 12, 232), (55, 45, W-110, H-90), border_radius=10)
    pygame.draw.rect(surf, (38, 38, 68, 200), (55, 45, W-110, H-90), 1, border_radius=10)

    surf.blit(font.render('Space Simulator', True, (210, 220, 255)), (95, 60))
    hint_s = font_xs.render('Click anywhere  or  F10  to close', True, (55, 55, 85))
    surf.blit(hint_s, (W - hint_s.get_width() - 95, 70))

    COL1 = 95
    COL2 = W // 2 + 55
    Y0   = 112
    SPC  = 21

    def hdr(x, y, txt):
        s = font_sm.render(txt, True, (120, 170, 255))
        surf.blit(s, (x, y))
        pygame.draw.line(surf, (38, 58, 115), (x, y+s.get_height()+1), (x+s.get_width(), y+s.get_height()+1))
        return y + s.get_height() + 7

    def row(x, y, txt, col=(170, 195, 228)):
        surf.blit(font_xs.render(txt, True, col), (x, y))
        return y + SPC

    def gap(y):
        return y + 10

    # ── LEFT COLUMN ──────────────────────────────────────────────────────────
    y = Y0

    y = hdr(COL1, y, 'NAVIGATION')
    y = row(COL1, y, '  Scroll wheel          Zoom in / out')
    y = row(COL1, y, '  Left-drag             Pan camera freely')
    y = row(COL1, y, '  Click minimap         Jump camera to that spot')
    y = row(COL1, y, '  Top object bar        Browse, select and rename bodies')
    y = gap(y)

    y = hdr(COL1, y, 'SPAWNER  (bottom-right panel)')
    y = row(COL1, y, '  Right-click + drag    Draw velocity arrow, release to spawn')
    y = row(COL1, y, '  SHIFT while dragging  Auto-set exact orbital speed')
    y = row(COL1, y, '  LMB while dragging    Cancel spawn')
    y = row(COL1, y, '  Dropdown              Choose object type')
    y = row(COL1, y, '  Size slider           Adjust radius / mass')
    y = row(COL1, y, '  Colour swatches       Pick body colour')
    y = row(COL1, y, '  Clone                 Duplicate selected body')
    y = row(COL1, y, '  Belt                  Spawn asteroid ring around selected body')
    y = row(COL1, y, '  Rnd                   Randomise type and size')
    y = gap(y)

    y = hdr(COL1, y, 'SHIP CONTROLS')
    y = row(COL1, y, '  A / D                 Rotate ship left / right')
    y = row(COL1, y, '  W / S                 Thrust forward / brake')
    y = row(COL1, y, '  SHIFT                 Boost thrust')
    y = row(COL1, y, '  L                     Land on / launch from nearby planet')
    y = row(COL1, y, '  O                     Autopilot: enter orbit around nearest body')
    y = row(COL1, y, '  E                     Autopilot: escape from nearest body')
    y = row(COL1, y, '  (hold W/S)            Shows predicted trajectory')
    y = gap(y)

    y = hdr(COL1, y, 'SIMULATION')
    y = row(COL1, y, '  < / >                 Time warp slower / faster  (0.25x – 10x)')
    y = row(COL1, y, '  T                     Toggle trajectory previews for all bodies')
    y = row(COL1, y, '  R                     Reset simulation to default world')
    y = row(COL1, y, '  Ctrl+S                Save current world to file')
    y = row(COL1, y, '  Ctrl+L                Load world from file')
    y = row(COL1, y, '  F10                   Open / close this screen')
    y = gap(y)

    y = hdr(COL1, y, 'MUSIC PLAYER')
    y = row(COL1, y, '  M                     Play / pause')
    y = row(COL1, y, '  N / P                 Next / previous track')
    y = row(COL1, y, '  + / -                 Volume up / down')
    y = row(COL1, y, '  (place .mp3/.ogg files in the music/ folder)')

    # ── RIGHT COLUMN ─────────────────────────────────────────────────────────
    y = Y0

    y = hdr(COL2, y, 'OBJECT TYPES')
    y = row(COL2, y, '  Planet       Orbits stars; affected by gravity and tidal forces')
    y = row(COL2, y, '  Star         Glowing; habitable zone ring; can trigger supernova')
    y = row(COL2, y, '  Black Hole   Immense gravity; visually bends background stars')
    y = row(COL2, y, '  Neutron Star Ultra-dense remnant; fast spin; twin pulsar beams')
    y = row(COL2, y, '  Comet        Light icy body; tail always points away from star')
    y = row(COL2, y, '  Binary Pair  Place two — auto-adjusted to mutual orbit')
    y = row(COL2, y, '  Nebula       Gas cloud; drags and slows bodies flying through it')
    y = row(COL2, y, '  Wormhole     Place two — entering one exits the other instantly')
    y = row(COL2, y, '  Ship         Your vessel; only one active at a time')
    y = gap(y)

    y = hdr(COL2, y, 'PROPERTIES PANEL  (appears when a body is selected)')
    y = row(COL2, y, '  Click any body or its icon in the top bar to select it')
    y = row(COL2, y, '  Mass slider       Drag to change mass live  (logarithmic scale)')
    y = row(COL2, y, '  Radius slider     Drag to change size live')
    y = row(COL2, y, '  Vel X / Vel Y     Drag to change velocity components live')
    y = row(COL2, y, '  Lock toggle       Links mass and radius — changing one updates both')
    y = row(COL2, y, '  Mass label        Shown below every body name in the world')
    y = gap(y)

    y = hdr(COL2, y, 'PHYSICS & EVENTS')
    y = row(COL2, y, '  Two stars collide    Supernova: becomes Black Hole + shockwave')
    y = row(COL2, y, '  Body absorbed        Shockwave radiates outward, kicks nearby bodies')
    y = row(COL2, y, '  Tidal forces         Body too close to star/BH sheds debris chunks')
    y = row(COL2, y, '  Gravity waves        Visual ripple emitted on large-mass merges')
    y = row(COL2, y, '  Ship collision       Ship always bounces off — it cannot be destroyed')
    y = row(COL2, y, '  Glancing blow        Partial mass transfer + elastic rebound')
    y = gap(y)

    y = hdr(COL2, y, 'OBJECT FINDER  (top-centre bar)')
    y = row(COL2, y, '  Filter tabs          All / Stars / Planets / BH / Ship / Other')
    y = row(COL2, y, '  Click icon           Follow / select that body')
    y = row(COL2, y, '  Double-click icon    Rename it inline')
    y = row(COL2, y, '  Scroll arrows        Browse when many bodies are in the list')
    y = gap(y)

    y = hdr(COL2, y, 'DEFAULT WORLD')
    y = row(COL2, y, '  Central Black Hole (Sagittarius) with 6 orbiting star systems')
    y = row(COL2, y, '  Binary pair (Kastor & Pollux), neutron star (Nexar)')
    y = row(COL2, y, '  3 nebulae: Crimson Veil, Cerulean Drift, Ember Cloud')
    y = row(COL2, y, '  Wormhole pair: Gate-alpha  <-->  Gate-beta')

    return surf

_tutorial_surf = _build_tutorial_surf()

def draw_tutorial():
    screen.blit(_tutorial_surf, (0, 0))


# ── title screen ──────────────────────────────────────────────────────────────

def draw_star_shape(surf, cx, cy, outer, inner, col):
    pts = []
    for i in range(10):
        r = outer if i % 2 == 0 else inner
        a = math.pi / 2 + math.pi * i / 5
        pts.append((cx + math.cos(a) * r, cy - math.sin(a) * r))
    pygame.draw.polygon(surf, col, pts)


def draw_title_screen():
    global _title_blink_t
    _title_blink_t += 0.016

    WHITE = (240, 240, 240)

    # subtle dark overlay — lets the star field show through
    ov = pygame.Surface((W, H), pygame.SRCALPHA)
    ov.fill((0, 0, 0, 130))
    screen.blit(ov, (0, 0))

    title_str = 'KOSMOSIM'
    CY = H // 2 - 90

    # render base glyph to get dimensions
    base_lbl = font_title.render(title_str, True, WHITE)
    bw, bh   = base_lbl.get_size()
    bx       = W // 2 - bw // 2

    # glow: blit scaled-up low-alpha copies behind the title
    for gi in range(7, 0, -1):
        spread = gi * 7
        gs = pygame.transform.smoothscale(base_lbl, (bw + spread * 2, bh + spread))
        gs.set_alpha(8 + gi * 3)
        screen.blit(gs, (bx - spread, CY - spread // 2))

    # sharp title text
    screen.blit(base_lbl, (bx, CY))

    # large flanking stars beside the title
    draw_star_shape(screen, bx - 60,      CY + bh // 2, 46, 19, WHITE)
    draw_star_shape(screen, bx + bw + 60, CY + bh // 2, 46, 19, WHITE)

    # tagline
    tag = font_title2.render('SPACE EXPLORATION SIMULATOR', True, (150, 150, 160))
    screen.blit(tag, (W // 2 - tag.get_width() // 2, CY + bh + 24))

    # blinking press-any-key prompt
    if int(_title_blink_t * 1.5) % 2 == 0:
        prompt = font_title2.render('— PRESS ANY KEY —', True, (195, 195, 205))
        screen.blit(prompt, (W // 2 - prompt.get_width() // 2, CY + bh + 76))


# ── save / load ───────────────────────────────────────────────────────────────

def save_game(path):
    data = {
        'bodies':      [],
        'cam':         dict(cam),
        'warp_idx':    warp_idx,
        'player_ship': player_ship['name'] if (player_ship and player_ship in bodies) else None,
    }
    for b in bodies:
        bd = {}
        for k, v in b.items():
            if k in _SAVE_SKIP:
                continue
            if k in _SAVE_REFS:
                bd[k] = v['name'] if v is not None else None
            elif isinstance(v, tuple):
                bd[k] = list(v)
            else:
                bd[k] = v
        data['bodies'].append(bd)
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        set_note('Game saved!')
    except Exception:
        set_note('Save failed!')


def load_game(path):
    global bodies, follow_target, warp_idx, warp, player_ship
    global gravity_waves, shockwaves, wormhole_pending, binary_pending
    global landed_on, autopilot_mode, ap_locked_target, tractor_active
    global ship_delta_v, _ship_prev_vx, _ship_prev_vy, _roche_cooldown
    global _obj_scroll, _obj_filter
    global panning, spawning, slider_dragging, renaming_body, rename_text
    global _props_slider_dragging, _spawn_dropdown_open

    with open(path, encoding='utf-8') as f:
        data = json.load(f)

    # first pass: create bodies without ref links
    new_bodies = []
    for bd in data['bodies']:
        b = {}
        for k, v in bd.items():
            if k in _SAVE_REFS:
                continue
            b[k] = tuple(v) if k == 'col' else v
        tmax = b.get('tmax', 500)
        b['trail'] = deque(maxlen=tmax or None)
        new_bodies.append(b)

    # second pass: reconnect wormhole/binary references by name
    name_map = {b['name']: b for b in new_bodies}
    for b, bd in zip(new_bodies, data['bodies']):
        for rk in _SAVE_REFS:
            if rk in bd:
                b[rk] = name_map.get(bd[rk]) if bd[rk] else None

    bodies        = new_bodies
    cam.update(data['cam'])
    wi            = data.get('warp_idx', 3)
    warp_idx      = max(0, min(wi, len(WARPS) - 1))
    warp          = WARPS[warp_idx]
    pname         = data.get('player_ship')
    player_ship   = name_map.get(pname) if pname else None
    follow_target = player_ship

    gravity_waves = [];  shockwaves = [];  _roche_cooldown = 0.0
    wormhole_pending = None;  binary_pending = None
    landed_on = None;  autopilot_mode = None;  ap_locked_target = None
    tractor_active = False
    ship_delta_v = 0.0;  _ship_prev_vx = 0.0;  _ship_prev_vy = 0.0
    _obj_scroll = 0;  _obj_filter = 'all'
    panning = False;  spawning = False;  slider_dragging = False
    renaming_body = None;  rename_text = '';  _spawn_dropdown_open = False
    _props_slider_dragging = None
    _glow_cache.clear();  _bh_glow_cache.clear()
    set_note('Game loaded!')


def spawn_asteroid_belt(center_body, n=20):
    global _spawn_count
    if center_body is None:
        set_note('Select a body first (click to follow)')
        return
    r_min = center_body['rad'] * 5
    r_max = center_body['rad'] * 14
    for _ in range(n):
        angle = random.uniform(0, 2 * math.pi)
        dist  = random.uniform(r_min, r_max)
        ax = center_body['x'] + math.cos(angle) * dist
        ay = center_body['y'] + math.sin(angle) * dist
        spd = circ(dist, center_body['mass'])
        avx = center_body['vx'] - math.sin(angle) * spd
        avy = center_body['vy'] + math.cos(angle) * spd
        sz  = random.randint(4, 10)
        col = random.choice([(180,160,140),(200,180,160),(165,150,140),(190,170,150)])
        _spawn_count += 1
        b = mk_body(f'A{_spawn_count}', col, ax, ay, avx, avy, size_to_mass(sz), sz, 15000)
        b['spin_rate'] = random.uniform(0.3, 1.8)
        bodies.append(b)
    set_note(f'Asteroid belt spawned around {center_body["name"]} ({n} rocks)')

def clone_body(src):
    global _spawn_count
    if src is None:
        set_note('Select a body first (click to follow)')
        return
    _spawn_count += 1
    off = src['rad'] * 3
    b = mk_body(f'{src["name"]}\'', src['col'],
                src['x'] + off, src['y'] + off,
                src['vx'], src['vy'],
                src['mass'], src['rad'],
                src.get('tmax', 500),
                src.get('glow', False), False, src.get('bh', False))
    for flag in ('comet', 'neutron', 'wormhole', 'nebula', 'ship'):
        if src.get(flag):
            b[flag] = True
    b['spin_rate'] = src.get('spin_rate', 0.0)
    b['has_rings']  = src.get('has_rings', False)
    b['cloud_rad']  = src.get('cloud_rad', 0)
    if b.get('nebula'):
        gen_nebula_particles(b)
    bodies.append(b)
    set_note(f'Cloned {src["name"]} → {b["name"]}')

def randomize_spawn():
    global spawn_size, spawn_col_idx, spawn_type
    spawn_type    = random.choice(['planet', 'star', 'comet', 'nebula', 'neutron'])
    spawn_size    = random.randint(SL_MIN, SL_MAX)
    spawn_col_idx = random.randint(0, len(COLS) - 1)
    set_note(f'Randomized: {spawn_type.upper()} r={spawn_size}')


def do_spawn(rx, ry):
    global _spawn_count, wormhole_pending, binary_pending
    global player_ship, follow_target
    mods  = pygame.key.get_mods()
    shift = bool(mods & pygame.KMOD_SHIFT)

    wx, wy   = to_world(spawn_sx, spawn_sy)
    sdx = rx-spawn_sx;  sdy = ry-spawn_sy
    drag_len = math.hypot(sdx, sdy) or 1

    if shift:
        vx, vy = orbit_velocity(wx, wy, sdx, sdy, override_body=follow_target)
    else:
        speed  = drag_to_speed(drag_len)
        nx, ny = sdx/drag_len, sdy/drag_len
        vx, vy = nx*speed, ny*speed

    _spawn_count += 1
    col = COLS[spawn_col_idx]

    if spawn_type == 'bh':
        name      = f'BH{_spawn_count}'
        mass, _   = bh_spawn_mass(spawn_size)
        rad       = max(45, spawn_size * 2)
        b         = mk_body(name, (5,5,12), wx, wy, vx, vy, mass, rad, 500, bh=True)
        bodies.append(b)
        _bh_glow_cache.clear()
    elif spawn_type == 'star':
        name = f'S{_spawn_count}'
        mass = size_to_star_mass(spawn_size)
        b    = mk_body(name, col, wx, wy, vx, vy, mass, spawn_size, 30000, glow=True)
        bodies.append(b)
        _glow_cache.clear()
    elif spawn_type == 'planet':
        name = f'P{_spawn_count}'
        mass = size_to_mass(spawn_size)
        bodies.append(mk_body(name, col, wx, wy, vx, vy, mass, spawn_size, 30000))
    elif spawn_type == 'ship':
        for ob in list(bodies):
            if ob.get('ship'):
                if follow_target is ob:
                    follow_target = None
                bodies.remove(ob)
        player_ship = None
        name = f'Ship{_spawn_count}'
        ship_mass = 500.0
        ship_rad  = 1
        b = mk_body(name, (200, 200, 255), wx, wy, vx, vy, ship_mass, ship_rad, 500)
        b['ship'] = True
        b['angle'] = math.atan2(vy, vx) if (vx or vy) else 0.0
        b['thrusting'] = False
        bodies.append(b)
        player_ship = b
        follow_target = b

    elif spawn_type == 'binary':
        name = f'B{_spawn_count}'
        # size >= 20 → star, otherwise planet
        if spawn_size >= 20:
            mass = size_to_star_mass(spawn_size)
            b    = mk_body(name, col, wx, wy, vx, vy, mass, spawn_size, 30000, glow=True)
            b['spin_rate'] = random.uniform(0.05, 0.3)
            _glow_cache.clear()
        else:
            mass = size_to_mass(spawn_size)
            b    = mk_body(name, col, wx, wy, vx, vy, mass, spawn_size, 30000)
            b['spin_rate'] = random.uniform(0.1, 0.6)
        bodies.append(b)

        if binary_pending is not None and binary_pending in bodies:
            b1 = binary_pending;  b2 = b
            m1 = b1['mass'];  m2 = b2['mass'];  tot = m1 + m2
            com_vx = (m1*b1['vx'] + m2*b2['vx']) / tot
            com_vy = (m1*b1['vy'] + m2*b2['vy']) / tot
            sep    = math.hypot(b2['x']-b1['x'], b2['y']-b1['y']) or 100
            v_orb  = math.sqrt(G * tot / sep)
            dx12   = b2['x']-b1['x'];  dy12 = b2['y']-b1['y']
            px = -dy12/sep;  py = dx12/sep          # CCW perp unit vec
            b1['vx'] = com_vx - px*v_orb*(m2/tot)
            b1['vy'] = com_vy - py*v_orb*(m2/tot)
            b2['vx'] = com_vx + px*v_orb*(m1/tot)
            b2['vy'] = com_vy + py*v_orb*(m1/tot)
            b1['binary_partner'] = b2;  b2['binary_partner'] = b1
            set_note(f'Binary pair: {b1["name"]} ↔ {name}')
            binary_pending = None
        else:
            binary_pending = b
            set_note(f'{name} placed — place partner to complete binary')
        return

    elif spawn_type == 'comet':
        name = f'C{_spawn_count}'
        sz   = max(4, spawn_size // 2)
        b    = mk_body(name, (200, 225, 255), wx, wy, vx, vy, size_to_mass(sz), sz, 30000)
        b['comet'] = True;  b['spin_rate'] = random.uniform(0.4, 1.4)
        bodies.append(b)

    elif spawn_type == 'neutron':
        name = f'NS{_spawn_count}'
        b    = mk_body(name, (200, 240, 255), wx, wy, vx, vy, SM * 3, max(6, spawn_size // 3), 30000)
        b['neutron'] = True;  b['spin_rate'] = random.uniform(30.0, 100.0)
        bodies.append(b)
        _glow_cache.clear()

    elif spawn_type == 'wormhole':
        name = f'WH{_spawn_count}'
        b    = mk_body(name, (160, 80, 255), wx, wy, 0, 0, 1, spawn_size, 0, fixed=True)
        b['wormhole'] = True;  b['tmax'] = 0
        bodies.append(b)
        if wormhole_pending is not None and wormhole_pending in bodies:
            b['partner']               = wormhole_pending
            wormhole_pending['partner'] = b
            set_note(f'Linked {wormhole_pending["name"]} ↔ {name}')
            wormhole_pending = None
        else:
            wormhole_pending = b
            set_note(f'{name} placed — place second wormhole to link')
        return

    elif spawn_type == 'nebula':
        name = f'NB{_spawn_count}'
        b    = mk_body(name, col, wx, wy, 0, 0, 1, spawn_size, 0, fixed=True)
        b['nebula'] = True;  b['cloud_rad'] = spawn_size * 6;  b['tmax'] = 0
        gen_nebula_particles(b)
        bodies.append(b)

    elif spawn_type == 'delete':
        target = None;  min_d = float('inf')
        for bd in bodies:
            bx_s, by_s = to_screen(bd['x'], bd['y'])
            d = math.hypot(spawn_sx - bx_s, spawn_sy - by_s)
            if d < min_d:
                min_d = d;  target = bd
        if target is not None and min_d < 80:
            if follow_target is target:
                follow_target = None
            if player_ship is target:
                player_ship = None
            bodies.remove(target)
            set_note(f'{target["name"]} deleted')
        return

    set_note(f'Spawned {name}')


# ── main loop ─────────────────────────────────────────────────────────────────

acc       = 0.0
last_time = pygame.time.get_ticks() / 1000.0
running   = True

while running:
    now = pygame.time.get_ticks() / 1000.0
    raw = min(now - last_time, 0.08)
    last_time = now

    # autoplay first music track on startup
    if not music_autoplay_done and music_files:
        play_music(0)
        music_autoplay_done = True

    if note_alpha > 0 and now > note_end_time:
        note_alpha = max(0.0, note_alpha - raw / 0.4)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        # title screen: any key or click dismisses it and shows tutorial
        if title_visible:
            if event.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
                title_visible    = False
                tutorial_visible = True
            continue

        # while tutorial visible, allow dismissal by LMB or toggle by F10; ignore other inputs
        if tutorial_visible:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                tutorial_visible = False
                continue
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F10:
                tutorial_visible = False
                continue
            # ignore all other events while tutorial is up
            continue

        elif event.type == pygame.WINDOWLEAVE:
            if spawning:
                do_spawn(mouse_sx, mouse_sy);  spawning = False
            panning = False

        elif event.type == pygame.KEYDOWN:
            if renaming_body is not None:
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    if rename_text.strip():
                        renaming_body['name'] = rename_text.strip()[:18]
                    renaming_body = None
                elif event.key == pygame.K_ESCAPE:
                    renaming_body = None
                elif event.key == pygame.K_BACKSPACE:
                    rename_text = rename_text[:-1]
                else:
                    ch = event.unicode
                    if ch and ch.isprintable() and len(rename_text) < 18:
                        rename_text += ch
            else:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_t:
                    show_all_trajs = not show_all_trajs
                    set_note(f"Trajectories {'ON' if show_all_trajs else 'OFF'}")
                elif event.key == pygame.K_COMMA:
                    warp_idx = (warp_idx-1) % len(WARPS);  warp = WARPS[warp_idx]
                    set_note(f'Warp {warp}x')
                elif event.key == pygame.K_PERIOD:
                    warp_idx = (warp_idx+1) % len(WARPS);  warp = WARPS[warp_idx]
                    set_note(f'Warp {warp}x')
                elif event.key == pygame.K_r:
                    do_reset()
                elif event.key == pygame.K_s and (event.mod & pygame.KMOD_CTRL):
                    save_game(SAVE_PATH)
                elif event.key == pygame.K_s:
                    spawn_type = SPAWN_TYPES[(SPAWN_TYPES.index(spawn_type)+1) % len(SPAWN_TYPES)]
                    set_note(f'Spawn: {spawn_type.upper()}')
                elif event.key == pygame.K_LEFTBRACKET:
                    spawn_size = max(SL_MIN, spawn_size-1)
                elif event.key == pygame.K_RIGHTBRACKET:
                    spawn_size = min(SL_MAX, spawn_size+1)
                elif pygame.K_1 <= event.key <= pygame.K_8:
                    spawn_col_idx = event.key - pygame.K_1
                elif event.key == pygame.K_F10:
                    # show tutorial overlay
                    tutorial_visible = True
                elif event.key == pygame.K_m:
                    # toggle music
                    toggle_music()
                elif event.key == pygame.K_n:
                    # next track
                    next_track()
                elif event.key == pygame.K_p:
                    # previous track
                    prev_track()
                elif event.key == pygame.K_EQUALS or event.key == pygame.K_PLUS:
                    change_volume(0.05)
                elif event.key == pygame.K_MINUS or event.key == pygame.K_UNDERSCORE:
                    change_volume(-0.05)
                elif event.key == pygame.K_l and (event.mod & pygame.KMOD_CTRL):
                    try:
                        load_game(SAVE_PATH)
                    except Exception:
                        set_note('Load failed — no save file?')
                elif event.key == pygame.K_l:
                    if player_ship is not None and player_ship in bodies:
                        if landed_on is not None:
                            landed_on = None
                            set_note('Launched!')
                        elif _land_candidate is not None:
                            landed_on = _land_candidate
                            land_offset_x = player_ship['x'] - _land_candidate['x']
                            land_offset_y = player_ship['y'] - _land_candidate['y']
                            autopilot_mode = None;  ap_locked_target = None
                            set_note(f'Landed on {_land_candidate["name"]}')
                        else:
                            set_note('Too fast or too far to land')
                    else:
                        set_note('No ship — spawn one first')
                elif event.key == pygame.K_o:
                    if player_ship is not None and player_ship in bodies:
                        if autopilot_mode == 'orbit':
                            autopilot_mode = None;  ap_locked_target = None
                            set_note('Autopilot: OFF')
                        else:
                            autopilot_mode = 'orbit'
                            # lock onto selected body if valid, else nearest
                            if follow_target is not None and follow_target in bodies and not follow_target.get('ship'):
                                ap_locked_target = follow_target
                                set_note(f'Autopilot: ORBIT → {follow_target["name"]} [locked]')
                            else:
                                ap_locked_target = None
                                set_note('Autopilot: ORBIT nearest')
                    else:
                        set_note('No ship — spawn one first')
                elif event.key == pygame.K_e:
                    if player_ship is not None and player_ship in bodies:
                        if autopilot_mode == 'escape':
                            autopilot_mode = None;  ap_locked_target = None
                            set_note('Autopilot: OFF')
                        else:
                            autopilot_mode = 'escape'
                            if follow_target is not None and follow_target in bodies and not follow_target.get('ship'):
                                ap_locked_target = follow_target
                                set_note(f'Autopilot: ESCAPE from {follow_target["name"]} [locked]')
                            else:
                                ap_locked_target = None
                                set_note('Autopilot: ESCAPE nearest')
                    else:
                        set_note('No ship — spawn one first')

        elif event.type == pygame.MOUSEBUTTONDOWN:
            # allow cancelling an active right-click spawn by left-click
            if event.button == 1 and spawning:
                spawning = False
                set_note('Spawn cancelled')
                continue

            if event.button == 3:
                spawning = True
                spawn_sx, spawn_sy = event.pos;  mouse_sx, mouse_sy = event.pos
                set_note('Drag to aim  |  SHIFT = orbit lock')

            elif event.button == 1:
                pos = event.pos
                if RESET_RECT.collidepoint(pos):
                    do_reset()
                elif _warp_left_rect and _warp_left_rect.collidepoint(pos):
                    warp_idx = (warp_idx - 1) % len(WARPS);  warp = WARPS[warp_idx]
                    set_note(f'Warp {warp}x')
                elif _warp_right_rect and _warp_right_rect.collidepoint(pos):
                    warp_idx = (warp_idx + 1) % len(WARPS);  warp = WARPS[warp_idx]
                    set_note(f'Warp {warp}x')
                elif obj_panel_hit(pos):
                    hit = obj_icon_at(pos)
                    flt = obj_filter_at(pos)
                    if hit is not None:
                        now_t = pygame.time.get_ticks() / 1000.0
                        if hit is _last_click_body and now_t - _last_click_time < 0.45:
                            renaming_body = hit;  rename_text = hit['name']
                        else:
                            follow_target = None if follow_target is hit else hit
                        _last_click_body = hit;  _last_click_time = now_t
                    elif flt is not None:
                        _obj_filter = flt;  _obj_scroll = 0
                    elif pos[0] < OBJ_X + _OBJ_ARROW_W and pos[1] > OBJ_Y + OBJ_FILTER_H:
                        _obj_scroll = max(0, _obj_scroll - 1)
                    elif pos[0] > OBJ_X + OBJ_W - _OBJ_ARROW_W and pos[1] > OBJ_Y + OBJ_FILTER_H:
                        _obj_scroll += 1
                elif _spawn_dropdown_open:
                    # close dropdown; select item if clicked
                    _spawn_dropdown_open = False
                    for item_rect, key in _spawn_dropdown_rects:
                        if item_rect.collidepoint(pos):
                            spawn_type = key
                            set_note(f'Spawn: {key.upper()}')
                            break
                elif panel_hit(pos):
                    if _spawn_type_btn_rect and _spawn_type_btn_rect.collidepoint(pos):
                        _spawn_dropdown_open = not _spawn_dropdown_open
                    elif _btn_clone_rect and _btn_clone_rect.collidepoint(pos):
                        if follow_target is not None and follow_target in bodies:
                            clone_body(follow_target)
                        else:
                            set_note('Select a body to clone')
                    elif _btn_belt_rect and _btn_belt_rect.collidepoint(pos):
                        if follow_target is not None and follow_target in bodies:
                            spawn_asteroid_belt(follow_target)
                        else:
                            set_note('Select a body for Belt')
                    elif _btn_rnd_rect and _btn_rnd_rect.collidepoint(pos):
                        randomize_spawn()
                    elif slider_hit(pos):
                        slider_dragging = True;  update_slider(pos)
                    else:
                        si = swatch_at(pos)
                        if si >= 0:
                            spawn_col_idx = si
                elif props_panel_hit(pos):
                    if _props_lock_btn_rect and _props_lock_btn_rect.collidepoint(pos):
                        _props_lock_mass_rad = not _props_lock_mass_rad
                    else:
                        for hit, bx, bw, key, lo, hi, log_s in _props_slider_rects:
                            if hit.collidepoint(pos):
                                t = max(0.0, min(1.0, (pos[0] - bx) / bw))
                                if follow_target is not None and follow_target in bodies:
                                    _apply_props_slider(follow_target, key, t, lo, hi, log_s)
                                _props_slider_dragging = (bx, bw, key, lo, hi, log_s)
                                break
                else:
                        clicked = None;  z = cam['zoom']
                        for b in bodies:
                            bx, by = to_screen(b['x'], b['y'])
                            if math.hypot(pos[0]-bx, pos[1]-by) < max(int(b['rad']*z), 18):
                                clicked = b;  break
                        if clicked:
                            now_t = pygame.time.get_ticks() / 1000.0
                            if clicked is _last_click_body and now_t - _last_click_time < 0.45:
                                renaming_body = clicked;  rename_text = clicked['name']
                            else:
                                follow_target = None if follow_target is clicked else clicked
                            _last_click_body = clicked;  _last_click_time = now_t
                        else:
                            if MM_X <= pos[0] <= MM_X+MM_W and MM_Y <= pos[1] <= MM_Y+MM_H:
                                mm_local_x = pos[0] - MM_X
                                mm_local_y = pos[1] - MM_Y
                                cam['x'] = WORLD_X0 + mm_local_x / MM_SX
                                cam['y'] = WORLD_Y0 + mm_local_y / MM_SY
                                clamp_cam()
                                follow_target = None
                            else:
                                if renaming_body is not None:
                                    renaming_body = None
                                panning = True;  pan_mx, pan_my = pos;  follow_target = None

            elif event.button == 4:
                if obj_panel_hit(event.pos):
                    _obj_scroll = max(0, _obj_scroll - 1)
                else:
                    cam['zoom'] = min(30.0, cam['zoom']*1.12);  clamp_cam()
            elif event.button == 5:
                if obj_panel_hit(event.pos):
                    _obj_scroll += 1
                else:
                    cam['zoom'] = max(0.0125, cam['zoom']*0.89);  clamp_cam()

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 3 and spawning:
                do_spawn(*event.pos);  spawning = False
            elif event.button == 1:
                panning = False;  slider_dragging = False;  _props_slider_dragging = None

        elif event.type == pygame.MOUSEMOTION:
            mouse_sx, mouse_sy = event.pos
            if panning:
                cam['x'] -= (event.pos[0]-pan_mx) / cam['zoom']
                cam['y'] -= (event.pos[1]-pan_my) / cam['zoom']
                pan_mx, pan_my = event.pos;  clamp_cam()
            if slider_dragging:
                update_slider(event.pos)
            if _props_slider_dragging is not None and follow_target is not None and follow_target in bodies:
                bx, bw, key, lo, hi, log_s = _props_slider_dragging
                t = max(0.0, min(1.0, (event.pos[0] - bx) / bw))
                _apply_props_slider(follow_target, key, t, lo, hi, log_s)

    acc  += raw * warp;  steps = 0
    while acc >= FDT and steps < 12:
        grav_step(FDT);  acc -= FDT;  steps += 1

    check_collisions()
    despawn_oob()
    update_shockwaves(raw * warp)
    update_spin(raw * warp)
    update_tidal_heating(raw * warp)
    check_roche_limit()
    update_wormholes()
    update_nebulae(raw * warp)
    update_gravity_waves(raw * warp)

    # player ship controls (A/D rotate, W/S thrust) or autopilot
    keys = pygame.key.get_pressed()
    if player_ship is not None and player_ship in bodies:
        b = player_ship
        thrust_force = 120000.0
        rot_speed    = 3.0
        fwd = back = False

        # ── landing: lock ship to planet surface ──────────────────────────
        if landed_on is not None:
            if landed_on not in bodies:
                # planet was destroyed — eject ship
                landed_on = None
            else:
                if keys[pygame.K_w] or keys[pygame.K_s] or keys[pygame.K_a] or keys[pygame.K_d]:
                    # thrust breaks landing
                    landed_on = None
                    set_note('Launched!')
                else:
                    b['x']  = landed_on['x'] + land_offset_x
                    b['y']  = landed_on['y'] + land_offset_y
                    b['vx'] = landed_on['vx']
                    b['vy'] = landed_on['vy']
                    b['thrust_fwd'] = False;  b['thrust_back'] = False;  b['thrusting'] = False
                    # keep angle pointing away from planet centre
                    b['angle'] = math.atan2(land_offset_y, land_offset_x)

        # ── approach assist + landing candidate ───────────────────────────
        _land_candidate = None
        _approach_target = None   # body currently being assisted toward
        if landed_on is None:
            ASSIST_ZONE = 10.0    # multiples of planet radius where assist starts
            LAND_ZONE   = 5.0     # multiples where [L] prompt appears
            manual_override = keys[pygame.K_w] or keys[pygame.K_s]
            for ob in bodies:
                if ob is b or ob.get('ship') or ob.get('bh') or ob.get('wormhole') or ob.get('nebula'):
                    continue
                dist = math.hypot(b['x']-ob['x'], b['y']-ob['y'])
                if dist < ob['rad'] * ASSIST_ZONE:
                    _approach_target = ob
                    if not manual_override:
                        # proportional drag toward planet velocity — stronger when closer
                        t = 1.0 - dist / (ob['rad'] * ASSIST_ZONE)   # 0 at edge, 1 at surface
                        strength = t * t * 0.55 * raw * warp
                        b['vx'] -= (b['vx'] - ob['vx']) * strength
                        b['vy'] -= (b['vy'] - ob['vy']) * strength
                    if dist < ob['rad'] * LAND_ZONE:
                        _land_candidate = ob
                    break

        if landed_on is not None:
            b['thrust_fwd'] = False;  b['thrust_back'] = False;  b['thrusting'] = False
        elif autopilot_mode is not None:
            # use locked target if valid, else fall back to nearest non-ship body
            if ap_locked_target is not None and ap_locked_target in bodies and not ap_locked_target.get('ship'):
                ap_target = ap_locked_target
            else:
                ap_target = None;  ap_dist = float('inf')
                for ob in bodies:
                    if ob is b or ob.get('ship'):
                        continue
                    d = math.hypot(b['x']-ob['x'], b['y']-ob['y'])
                    if d < ap_dist:
                        ap_dist = d;  ap_target = ob

            if ap_target is not None:
                if autopilot_mode == 'orbit':
                    dx_ = b['x']-ap_target['x'];  dy_ = b['y']-ap_target['y']
                    dist_ = math.hypot(dx_, dy_) or 1
                    v_orb = math.sqrt(G * ap_target['mass'] / dist_)
                    # desired velocity: CCW tangent + target's own drift
                    want_vx = -dy_/dist_ * v_orb + ap_target['vx']
                    want_vy =  dx_/dist_ * v_orb + ap_target['vy']
                    dv_x = want_vx - b['vx'];  dv_y = want_vy - b['vy']
                    dv_mag = math.hypot(dv_x, dv_y)
                    if dv_mag > 1.5:
                        heading = math.atan2(dv_y, dv_x)
                    else:
                        heading = b['angle']   # close enough — hold heading
                elif autopilot_mode == 'escape':
                    dx_ = b['x']-ap_target['x'];  dy_ = b['y']-ap_target['y']
                    heading = math.atan2(dy_, dx_)   # point directly away
                    dv_mag  = 9999
                else:
                    heading = b['angle'];  dv_mag = 0

                # steer toward heading
                diff = ((heading - b['angle']) + math.pi) % (2*math.pi) - math.pi
                if abs(diff) > 0.08:
                    b['angle'] += math.copysign(rot_speed * raw * warp, diff)
                elif dv_mag > 1.5:
                    dv = (thrust_force / max(1.0, b['mass'])) * raw * warp
                    b['vx'] += math.cos(b['angle']) * dv
                    b['vy'] += math.sin(b['angle']) * dv
                    fwd = True
                    if autopilot_mode == 'orbit' and dv_mag < 1.5:
                        autopilot_mode = None   # target reached

            # manual override cancels autopilot
            if keys[pygame.K_w] or keys[pygame.K_s] or keys[pygame.K_a] or keys[pygame.K_d]:
                autopilot_mode = None
        else:
            # manual controls
            if keys[pygame.K_a]:
                b['angle'] -= rot_speed * raw * warp
            if keys[pygame.K_d]:
                b['angle'] += rot_speed * raw * warp
            boost      = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
            boost_mult = 3.0 if boost else 1.0
            if keys[pygame.K_w]:
                dv = (thrust_force * boost_mult / max(1.0, b['mass'])) * raw * warp
                b['vx'] += math.cos(b['angle']) * dv
                b['vy'] += math.sin(b['angle']) * dv
                fwd = True
            if keys[pygame.K_s]:
                dv = (thrust_force * 0.5 * boost_mult / max(1.0, b['mass'])) * raw * warp
                b['vx'] -= math.cos(b['angle']) * dv
                b['vy'] -= math.sin(b['angle']) * dv
                back = True
        b['thrust_fwd']  = fwd
        b['thrust_back'] = back
        b['thrusting']   = fwd or back

    # arrow key camera pan (breaks follow lock)
    _arrow_spd = 400 / cam['zoom']
    _moved_cam = False
    if keys[pygame.K_LEFT]:  cam['x'] -= _arrow_spd * raw;  _moved_cam = True
    if keys[pygame.K_RIGHT]: cam['x'] += _arrow_spd * raw;  _moved_cam = True
    if keys[pygame.K_UP]:    cam['y'] -= _arrow_spd * raw;  _moved_cam = True
    if keys[pygame.K_DOWN]:  cam['y'] += _arrow_spd * raw;  _moved_cam = True
    if _moved_cam:
        follow_target = None;  clamp_cam()

    if follow_target is not None:
        cam['x'] = follow_target['x'];  cam['y'] = follow_target['y'];  clamp_cam()

    screen.fill((0, 0, 0))
    draw_stars()
    if title_visible:
        draw_title_screen()
    else:
        draw_world_border()
        for b in bodies:
            draw_trail(b['trail'], b['col'])
        draw_shockwaves()
        draw_gravity_waves()
        draw_binary_links()
        draw_bodies()
        draw_landing_prompt()
        draw_ship_trajectory(keys)
        draw_autopilot_trajectory()
        draw_all_trajectories()
        draw_spawn_preview()
        draw_ui()
        if tutorial_visible:
            draw_tutorial()

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()
