# music.py – procedural cyberpunk track, stdlib + pygame only, no numpy
import array
import io
import math
import wave
import pygame

SR   = 11025   # sample rate – lo-fi retro feel, generates fast
BPM  = 118
BARS = 4       # bars per loop (≈ 8 seconds)


# ── Wave primitives ───────────────────────────────────────────────────────────
def _saw(t, f):
    return 2.0 * ((t * f) % 1.0) - 1.0

def _square(t, f, duty=0.45):
    return 1.0 if (t * f) % 1.0 < duty else -1.0

def _sine(t, f):
    return math.sin(2.0 * math.pi * t * f)

def _note(semis):
    """Semitones from A4 (440 Hz) → frequency."""
    return 440.0 * (2.0 ** (semis / 12.0))


# ── Note table (A-minor feel) ─────────────────────────────────────────────────
A2 = _note(-24); E2 = _note(-17); F2 = _note(-16); G2 = _note(-14)
A3 = _note(-12); C4 = _note(-9);  E4 = _note(-5);  G4 = _note(-2)
A4 = _note(0);   C5 = _note(3);   E5 = _note(7)

# Bass: 4-bar chord cycle (one note per beat)
_BASS = [A2, E2, F2, G2,   A2, G2, F2, E2,
         A2, E2, C4/4, G2,  A2, E2, F2, G2]   # /4 for sub-octave C

# Arpeggio 16th-note sequence (repeating)
_ARP  = [A4, C5, E5, A4, G4, E5, C5, A4]

# Pad (sustained Am7 chord)
_PAD  = [A3, C4, E4, G4]


def _generate() -> io.BytesIO:
    beat    = 60.0 / BPM
    bar     = beat * 4
    total   = int(BARS * bar * SR)
    sixteenth = beat / 4.0

    buf = array.array('h', [0] * total)

    for i in range(total):
        t          = i / SR
        t_in_bar   = t % bar
        beat_idx   = int(t_in_bar / beat)
        t_in_beat  = t_in_bar % beat
        a16_idx    = int(t_in_bar / sixteenth) % len(_ARP)
        t_in_16    = t_in_bar % sixteenth

        # Bass
        bass_f  = _BASS[(int(t / beat)) % len(_BASS)]
        b_env   = max(0.0, 1.0 - t_in_beat / (beat * 0.80))
        bass    = (_saw(t, bass_f) * 0.38
                   + _square(t, bass_f * 2, 0.25) * 0.10) * b_env

        # Arpeggio
        a_env   = max(0.0, 1.0 - t_in_16 / (sixteenth * 0.55))
        arp     = _square(t, _ARP[a16_idx]) * 0.22 * a_env

        # Subtle pad
        pad = sum(_sine(t, f) * 0.025 for f in _PAD)

        # Noise hi-hat on every 8th note (adds rhythm texture)
        eighth = beat / 2.0
        t_in_8 = t_in_bar % eighth
        hat_env = max(0.0, 0.04 - t_in_8 / eighth) * 25
        # cheap pseudo-noise via high-freq square beating
        hat = _square(t, 8000.0) * _square(t, 7993.0) * hat_env * 0.15

        v = bass + arp + pad + hat
        buf[i] = int(max(-32767.0, min(32767.0, v * 28000.0)))

    out = io.BytesIO()
    with wave.open(out, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(buf.tobytes())
    out.seek(0)
    return out


# ── Public API ────────────────────────────────────────────────────────────────
_cached: io.BytesIO | None = None


def pre_init():
    """Call BEFORE pygame.init() to set mixer format."""
    pygame.mixer.pre_init(SR, -16, 1, 512)


def play(volume: float = 0.6):
    """Generate (first call only) and loop the track."""
    global _cached
    if _cached is None:
        _cached = _generate()
    else:
        _cached.seek(0)
    try:
        pygame.mixer.music.load(_cached)
        pygame.mixer.music.set_volume(max(0.0, min(1.0, volume)))
        pygame.mixer.music.play(loops=-1)
    except Exception as e:
        print(f"[music] playback error: {e}")


def stop():
    try:
        pygame.mixer.music.stop()
    except Exception:
        pass


def set_volume(vol: float):
    try:
        pygame.mixer.music.set_volume(max(0.0, min(1.0, vol)))
    except Exception:
        pass
