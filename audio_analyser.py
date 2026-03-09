"""
audio_analyser.py
─────────────────
PAB Audio Analysis Module — Phase 2
"""

import numpy as np
import warnings
warnings.filterwarnings("ignore")

try:
    import librosa
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False
    print("⚠️  librosa not installed. Run: pip install librosa soundfile")

# ── Tuning thresholds ─────────────────────────────────────────────────────────
# ── Tuning thresholds ─────────────────────────────────────────────────────────
SILENCE_RMS_THRESHOLD       = 0.004   
LABOURED_ZCR_THRESHOLD      = 0.09    
RAPID_BREATH_RATE_THRESHOLD = 30      
WEAK_VOICE_RMS_THRESHOLD    = 0.015
SCREAM_F0_THRESHOLD         = 600
SLUR_MFCC_VARIANCE_THRESH   = 120
DISTRESSED_PITCH_STD_THRESH = 95
DISTRESSED_ZCR_THRESHOLD    = 0.082
DISTRESSED_RMS_CV_THRESHOLD = 0.60
ALARM_FREQ_LOW              = 2800
ALARM_FREQ_HIGH             = 3200
IMPACT_ONSET_THRESHOLD      = 0.85
WATER_ZCR_THRESHOLD         = 0.12
CARER_PRESENT_THRESHOLD     = 35.0    
VOICE_ACTIVITY_MAX_FOR_BREATH = 0.55


# ── Main entry point ──────────────────────────────────────────────────────────
def analyse_audio(audio_path: str) -> dict:
    if not LIBROSA_AVAILABLE:
        print("⚠️  librosa unavailable — returning safe defaults")
        return _safe_defaults()

    try:
        y, sr = librosa.load(audio_path, sr=16000, mono=True)

        if not _check_audio_present(y):
            return {
                "audio_present":   False,
                "breathing_state": "absent",
                "vocal_tone":      "calm",
                "background_cues": ["silence"],
            }

        breathing_state = _detect_breathing(y, sr)
        vocal_tone      = _detect_vocal_tone(y, sr)
        background_cues = _detect_background_cues(y, sr)

        result = {
            "audio_present":   True,
            "breathing_state": breathing_state,
            "vocal_tone":      vocal_tone,
            "background_cues": background_cues,
            "impact_event_count": _estimate_impact_events(y, sr),
        }

        print(f"   🎙 Audio analysis complete:")
        print(f"      Breathing : {breathing_state}")
        print(f"      Vocal tone: {vocal_tone}")
        print(f"      Background: {background_cues if background_cues else 'none'}")

        return result

    except Exception as e:
        print(f"⚠️  Audio analysis failed: {e} — using safe defaults")
        return _safe_defaults()


# ── STEP 1: Audio presence ────────────────────────────────────────────────────
def _check_audio_present(y: np.ndarray) -> bool:
    rms = float(np.sqrt(np.mean(y ** 2)))
    return rms > SILENCE_RMS_THRESHOLD


# ── STEP 2: Breathing pattern detection ──────────────────────────────────────
def _detect_breathing(y: np.ndarray, sr: int) -> str:

    # ── DEBUG — remove once thresholds are calibrated ─────────────
    zcr_debug          = librosa.feature.zero_crossing_rate(y)[0]
    rms_debug          = float(np.sqrt(np.mean(y ** 2)))
    oe_debug           = librosa.onset.onset_strength(y=y, sr=sr)
    of_debug           = librosa.onset.onset_detect(onset_envelope=oe_debug, sr=sr)
    duration_debug     = len(y) / sr
    breath_rate_debug  = (len(of_debug) / duration_debug) * 60 if duration_debug > 0 else 0
    print(f"   DEBUG — RMS: {rms_debug:.4f}  ZCR: {float(np.mean(zcr_debug)):.4f}  Onsets: {len(of_debug)}  Duration: {duration_debug:.1f}s  BreathRate: {breath_rate_debug:.1f}/min")
    if len(of_debug) > 2:
        iv  = np.diff(of_debug)
        irr = float(np.std(iv) / (np.mean(iv) + 1e-6))
        print(f"   DEBUG — Irregularity: {irr:.4f}")
    # ── END DEBUG ──────────────────────────────────────────────────

    onset_env    = librosa.onset.onset_strength(y=y, sr=sr)
    onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr)
    duration_sec = max(len(y) / sr, 0.001)
    rms          = float(np.sqrt(np.mean(y ** 2)))
    zcr          = librosa.feature.zero_crossing_rate(y)[0]
    mean_zcr     = float(np.mean(zcr))

    # Breathing-like envelope pulses (more robust than onset count for short clips)
    rms_env = librosa.feature.rms(y=y, frame_length=1024, hop_length=256)[0]
    env_threshold = float(np.mean(rms_env) + (0.35 * np.std(rms_env)))
    pulse_count = 0
    for i in range(1, len(rms_env) - 1):
        if rms_env[i] > env_threshold and rms_env[i] > rms_env[i - 1] and rms_env[i] > rms_env[i + 1]:
            pulse_count += 1
    pulse_rate = (pulse_count / duration_sec) * 60 if duration_sec > 0 else 0

    # Speech-heavy clips should not be mistaken for breathing emergencies.
    try:
        f0_track = librosa.yin(y, fmin=65, fmax=450, sr=sr)
        voiced_ratio = float(np.mean(np.isfinite(f0_track)))
    except Exception:
        voiced_ratio = 1.0

    # ── Agonal: very irregular sparse bursts ──────────────────────
    if len(onset_frames) > 2:
        intervals    = np.diff(onset_frames)
        irregularity = float(np.std(intervals) / (np.mean(intervals) + 1e-6))
        if irregularity > 1.5 and len(onset_frames) < 8:
            return "agonal"

    # ── Laboured: high ZCR = turbulent airflow ────────────────────
    if (
        voiced_ratio < VOICE_ACTIVITY_MAX_FOR_BREATH and
        (mean_zcr > LABOURED_ZCR_THRESHOLD or (rms > 0.02 and mean_zcr > 0.08 and pulse_count >= 4))
    ):
        return "laboured"

    # ── Rapid: only if recording > 3s (avoids speech false positives)
    if duration_sec > 3:
        breath_rate = (len(onset_frames) / duration_sec) * 60
        if voiced_ratio < VOICE_ACTIVITY_MAX_FOR_BREATH and (breath_rate > RAPID_BREATH_RATE_THRESHOLD or pulse_rate > 28):
            return "rapid"

    # ── Absent ────────────────────────────────────────────────────
    if rms < SILENCE_RMS_THRESHOLD * 2:
        return "absent"

    return "normal"


# ── STEP 3: Vocal tone detection ──────────────────────────────────────────────
def _detect_vocal_tone(y: np.ndarray, sr: int) -> str:

    # ── Weak voice ────────────────────────────────────────────────
    rms = float(np.sqrt(np.mean(y ** 2)))
    if rms < WEAK_VOICE_RMS_THRESHOLD:
        return "weak"

    # ── Screaming: high F0 ────────────────────────────────────────
    pitches, magnitudes = librosa.piptrack(y=y, sr=sr, threshold=0.1)
    pitch_values: list = []
    for t in range(pitches.shape[1]):
        index = int(magnitudes[:, t].argmax())
        pitch = pitches[index, t]
        if pitch > 0:
            pitch_values.append(float(pitch))

    if pitch_values:
        mean_f0 = float(np.mean(pitch_values))
        if mean_f0 > SCREAM_F0_THRESHOLD:
            return "screaming"

    # ── Slurred: low MFCC variance = monotone/poorly articulated ──
    mfccs         = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    mfcc_variance = float(np.mean(np.var(mfccs, axis=1)))
    if mfcc_variance < SLUR_MFCC_VARIANCE_THRESH:
        return "slurred"

    # ── Distressed: unstable pitch + turbulent/noisy/irregular energy ───────
    zcr = librosa.feature.zero_crossing_rate(y)[0]
    mean_zcr = float(np.mean(zcr))
    rms_env = librosa.feature.rms(y=y, frame_length=1024, hop_length=256)[0]
    rms_cv = float(np.std(rms_env) / (np.mean(rms_env) + 1e-6))

    if pitch_values and len(pitch_values) > 5:
        pitch_std = float(np.std(pitch_values))
        if pitch_std > 150 and rms > 0.06:   # was 80 and 0.04 — much stricter
            return "distressed"

    return "calm"


# ── STEP 5: Background sound detection ───────────────────────────────────────
def _detect_background_cues(y: np.ndarray, sr: int) -> list:
    cues: list = []

    # ── Impact / crash ────────────────────────────────────────────
    impact_events = _estimate_impact_events(y, sr)
    if impact_events >= 2:
        cues.append("impact")

    # ── Alarm tone ────────────────────────────────────────────────
    stft         = np.abs(librosa.stft(y))
    freqs        = librosa.fft_frequencies(sr=sr)
    alarm_mask   = (freqs >= ALARM_FREQ_LOW) & (freqs <= ALARM_FREQ_HIGH)
    alarm_energy = np.mean(stft[alarm_mask, :], axis=0)
    total_energy = np.mean(stft, axis=0) + 1e-6
    alarm_ratio_per_frame = alarm_energy / total_energy
    alarm_ratio_mean = float(np.mean(alarm_ratio_per_frame))
    alarm_ratio_std = float(np.std(alarm_ratio_per_frame))
    if alarm_ratio_mean > 0.62 and alarm_ratio_std < 0.22 and float(np.percentile(alarm_ratio_per_frame, 75)) > 0.65:
        cues.append("alarm")

    # ── Running water ─────────────────────────────────────────────
    zcr      = librosa.feature.zero_crossing_rate(y)[0]
    mean_zcr = float(np.mean(zcr))
    if mean_zcr > WATER_ZCR_THRESHOLD and "alarm" not in cues:
        cues.append("water")

    # ── Moaning ───────────────────────────────────────────────────
    centroid      = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    mean_centroid = float(np.mean(centroid))
    onset_frames  = librosa.onset.onset_detect(y=y, sr=sr)
    rms           = float(np.sqrt(np.mean(y ** 2)))
    if mean_centroid < 800 and len(onset_frames) < 5 and rms > SILENCE_RMS_THRESHOLD * 3:
        cues.append("moaning")

    # ── Carer / second voice ──────────────────────────────────────
    pitches, magnitudes      = librosa.piptrack(y=y, sr=sr)
    active_pitches_per_frame = []
    for t in range(pitches.shape[1]):
        active = int(np.sum(pitches[:, t] > 0))
        active_pitches_per_frame.append(active)
    if active_pitches_per_frame and float(np.mean(active_pitches_per_frame)) > CARER_PRESENT_THRESHOLD:
        cues.append("carer_present")

    return cues


# ── Safe fallback defaults ────────────────────────────────────────────────────
def _safe_defaults() -> dict:
    return {
        "audio_present":   True,
        "breathing_state": "normal",
        "vocal_tone":      "calm",
        "background_cues": [],
        "impact_event_count": 0,
    }


def _estimate_impact_events(y: np.ndarray, sr: int) -> int:
    """Estimate count of strong transient impacts."""
    # Use percussive component to reduce speech-driven false positives.
    _, y_perc = librosa.effects.hpss(y)
    onset_env = librosa.onset.onset_strength(y=y_perc, sr=sr)
    if len(onset_env) < 3:
        return 0

    med_onset = float(np.median(onset_env))
    std_onset = float(np.std(onset_env))
    p95_onset = float(np.percentile(onset_env, 95))
    # Strong threshold: robust against conversational consonant spikes
    strong_thr = max(IMPACT_ONSET_THRESHOLD * 2.0, med_onset + (3.5 * std_onset), p95_onset * 1.2)

    events = 0
    last_peak_idx = -10_000
    min_spacing = 10  # frames (~0.12s at default hop), avoids clustered speech peaks
    for i in range(1, len(onset_env) - 1):
        v = float(onset_env[i])
        if (
            v > strong_thr and
            v > float(onset_env[i - 1]) and
            v > float(onset_env[i + 1]) and
            (i - last_peak_idx) >= min_spacing
        ):
            events += 1
            last_peak_idx = i
    return events
