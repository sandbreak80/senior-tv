/* Senior TV - Broadcast-Style Audio Normalization

   Design based on broadcast audio processing (EBU R128 / CALM Act):
   NO feedback loops. NO adaptive gain measurement. Just a fixed chain
   that makes everything sound the same volume.

   Chain:
   1. Voice Boost EQ — cuts rumble, boosts dialogue clarity (configurable)
   2. Slow Compressor (AGC) — evens out overall level differences between
      content. Long time constants prevent pumping. A quiet indie film and
      a loud commercial both come out at roughly the same level.
   3. Makeup Gain — fixed boost to bring compressed signal up to target
      level. Configurable via admin ("Target Volume Level").
   4. Fast Limiter — brick-wall ceiling prevents anything from exceeding
      max output. Catches transients the compressor misses.

   With external speakers (Sonos soundbar, etc.), set the speaker volume
   to a comfortable level once. This chain keeps ALL content at the same
   consistent level — movies, live TV, YouTube, music, alerts.

   Uses Web Audio API — runs in real-time, no transcoding needed. */

// Voice boost EQ presets (highpass freq, presence boost dB, mud cut dB)
var VOICE_BOOST_PRESETS = {
    "off":    { highpass: 0,   presence: 0,  mudcut: 0  },
    "mild":   { highpass: 80,  presence: 3,  mudcut: -2 },
    "strong": { highpass: 120, presence: 6,  mudcut: -4 }
};

var _voiceBoostLevel = "mild";
var _makeupGainValue = 6;  // default ~+15.5dB, maps to -14 LUFS target
var _audioProcessingEnabled = false;  // disabled by default (beta)

// Map LUFS target to fixed makeup gain multiplier.
// The AGC compressor outputs roughly -30dB for typical content.
// Makeup gain bridges the gap to the target level.
function _targetToMakeupGain(targetLUFS) {
    // With AGC threshold=-30, ratio=8, typical content compresses to about -30 to -33dB.
    // Makeup gain = 10^((target - compressedOutput) / 20)
    // AGC with threshold=-30, ratio=8, typical content at -20 to -25dB input
    // compresses to roughly -24 to -28dB. Limiter at -3dB catches peaks.
    var compressedAvg = -24;
    var makeupDB = targetLUFS - compressedAvg;
    return Math.pow(10, makeupDB / 20);
}

function _loadAudioSettings() {
    fetch("/api/tv-settings")
        .then(function(r) { return r.json(); })
        .then(function(data) {
            _audioProcessingEnabled = !!data.audio_processing;
            if (data.voice_boost && VOICE_BOOST_PRESETS[data.voice_boost]) {
                _voiceBoostLevel = data.voice_boost;
                if (window._audioNorm && window._audioNorm._applyVoiceBoost) {
                    window._audioNorm._applyVoiceBoost(_voiceBoostLevel);
                }
            }
            if (data.audio_target != null) {
                var t = parseInt(data.audio_target, 10);
                if (t >= -30 && t <= -5) {
                    _makeupGainValue = _targetToMakeupGain(t);
                    // Update makeup gain in real-time if already running
                    if (window._audioNorm && window._audioNorm.makeupGain) {
                        window._audioNorm.makeupGain.gain.setTargetAtTime(
                            _makeupGainValue, window._audioNorm.ctx.currentTime, 0.5
                        );
                    }
                }
            }
        })
        .catch(function() {});
}
_loadAudioSettings();

function initAudioNormalizer(mediaElement) {
    if (!mediaElement || mediaElement._audioNormalized) return null;
    if (!_audioProcessingEnabled) return null;  // Disabled in admin (beta)
    try {
        // Request low-latency audio processing to minimize A/V desync.
        // 'interactive' requests the smallest buffer the system supports.
        var AudioCtx = window.AudioContext || window.webkitAudioContext;
        var ctx = new AudioCtx({ latencyHint: "interactive" });
        var source = ctx.createMediaElementSource(mediaElement);

        // === Stage 1: Voice Boost EQ ===
        var highpass = ctx.createBiquadFilter();
        highpass.type = "highpass";
        highpass.frequency.value = 1;
        highpass.Q.value = 0.7;

        var presence = ctx.createBiquadFilter();
        presence.type = "peaking";
        presence.frequency.value = 3000;
        presence.Q.value = 1.0;
        presence.gain.value = 0;

        var mudcut = ctx.createBiquadFilter();
        mudcut.type = "peaking";
        mudcut.frequency.value = 300;
        mudcut.Q.value = 0.8;
        mudcut.gain.value = 0;

        function applyVoiceBoost(level) {
            var preset = VOICE_BOOST_PRESETS[level] || VOICE_BOOST_PRESETS["off"];
            if (preset.highpass > 0) {
                highpass.frequency.setTargetAtTime(preset.highpass, ctx.currentTime, 0.3);
            } else {
                highpass.frequency.setTargetAtTime(1, ctx.currentTime, 0.3);
            }
            presence.gain.setTargetAtTime(preset.presence, ctx.currentTime, 0.3);
            mudcut.gain.setTargetAtTime(preset.mudcut, ctx.currentTime, 0.3);
        }
        applyVoiceBoost(_voiceBoostLevel);

        // === Stage 2: Slow Compressor (AGC) ===
        // Long time constants = no pumping. Evens out level differences
        // between content without reacting to individual transients.
        var compressor = ctx.createDynamicsCompressor();
        compressor.threshold.value = -30;  // Compress everything above -30dB
        compressor.knee.value = 20;        // Soft knee for natural sound
        compressor.ratio.value = 8;        // Heavy but not crushing
        compressor.attack.value = 0.1;     // 100ms — ignore transients, respond to sustained level
        compressor.release.value = 1.0;    // 1 second — slow release prevents pumping

        // === Stage 3: Fixed Makeup Gain ===
        // Brings compressed signal up to target level. NO feedback loop.
        // Value set by admin "Target Volume Level" setting.
        var makeupGain = ctx.createGain();
        makeupGain.gain.value = 0.01;  // Start silent
        makeupGain.gain.setTargetAtTime(_makeupGainValue, ctx.currentTime + 0.1, 0.8);  // Ramp up over ~2s

        // === Stage 4: Fast Limiter ===
        // Brick-wall ceiling. Catches any peaks that exceed output ceiling.
        // Short attack = instant catch. This is what prevents loud moments.
        var limiter = ctx.createDynamicsCompressor();
        limiter.threshold.value = -3;    // Only limit peaks near max output
        limiter.knee.value = 0;          // Hard knee = brick wall
        limiter.ratio.value = 20;        // Near-infinite ratio = true limiting
        limiter.attack.value = 0.001;    // 1ms — catch everything
        limiter.release.value = 0.1;     // 100ms — fast recovery after peak

        // Analyser for diagnostics only (NOT used for gain control)
        var analyser = ctx.createAnalyser();
        analyser.fftSize = 2048;
        analyser.smoothingTimeConstant = 0.8;

        // Chain: source → EQ → AGC → makeup gain → limiter → analyser → speakers
        source.connect(highpass);
        highpass.connect(presence);
        presence.connect(mudcut);
        mudcut.connect(compressor);
        compressor.connect(makeupGain);
        makeupGain.connect(limiter);
        limiter.connect(analyser);
        analyser.connect(ctx.destination);

        // Resume AudioContext (Chrome autoplay policy)
        if (ctx.state === "suspended") {
            ctx.resume().catch(function() {});
            document.addEventListener("keydown", function resumeAudio() {
                ctx.resume();
                document.removeEventListener("keydown", resumeAudio);
            }, { once: true });
        }

        mediaElement._audioNormalized = true;

        // === A/V Sync Compensation ===
        // createMediaElementSource() takes over the audio path from Chrome.
        // Chrome can no longer auto-compensate for system audio latency.
        // We measure the total latency and skip the video forward to match.
        var totalLatency = ctx.baseLatency + (ctx.outputLatency || 0);
        var syncApplied = false;
        if (totalLatency > 0.02 && mediaElement.tagName === "VIDEO") {
            // Wait a moment for playback to stabilize, then nudge video forward
            setTimeout(function() {
                try {
                    if (!mediaElement.paused && mediaElement.currentTime > 1) {
                        mediaElement.currentTime += totalLatency;
                        syncApplied = true;
                    }
                } catch (e) {
                    // Some streams (live HLS) may not support seeking
                }
            }, 500);
        }

        // Diagnostics (read-only, no control)
        var dataArray = new Float32Array(analyser.fftSize);
        window._audioNorm = {
            ctx: ctx, makeupGain: makeupGain, compressor: compressor,
            limiter: limiter, analyser: analyser, source: source,
            highpass: highpass, presence: presence, mudcut: mudcut,
            _applyVoiceBoost: applyVoiceBoost,
            getStats: function() {
                analyser.getFloatTimeDomainData(dataArray);
                var sum = 0;
                for (var i = 0; i < dataArray.length; i++) sum += dataArray[i] * dataArray[i];
                var rms = Math.sqrt(sum / dataArray.length);
                var db = rms > 0.0001 ? 20 * Math.log10(rms) : -60;
                var preset = VOICE_BOOST_PRESETS[_voiceBoostLevel] || {};
                return {
                    outputDB: Math.round(db * 10) / 10,
                    makeupGain: Math.round(makeupGain.gain.value * 100) / 100,
                    makeupDB: Math.round(20 * Math.log10(makeupGain.gain.value || 0.01) * 10) / 10,
                    compressorReduction: Math.round(compressor.reduction * 10) / 10,
                    limiterReduction: Math.round(limiter.reduction * 10) / 10,
                    voiceBoost: _voiceBoostLevel,
                    presenceBoostDB: preset.presence || 0,
                    baseLatencyMs: Math.round(ctx.baseLatency * 1000 * 10) / 10,
                    outputLatencyMs: Math.round((ctx.outputLatency || 0) * 1000 * 10) / 10,
                    totalLatencyMs: Math.round((ctx.baseLatency + (ctx.outputLatency || 0)) * 1000 * 10) / 10,
                    syncCompensated: syncApplied
                };
            }
        };

        return window._audioNorm;
    } catch (e) {
        return null;
    }
}

// Auto-attach to #video-player ONLY after it starts playing.
// createMediaElementSource before data loads breaks HLS.js playback.
(function() {
    var video = document.getElementById("video-player");
    if (video) {
        video.addEventListener("playing", function() {
            initAudioNormalizer(video);
        }, { once: true });
    }
})();
