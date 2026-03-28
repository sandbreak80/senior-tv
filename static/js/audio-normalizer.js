/* Senior TV - Audio Normalization for Hearing-Impaired Viewers

   Two-stage processing chain:
   1. DynamicsCompressor — squashes dynamic range within a video
      (boosts dialogue, tames explosions/music)
   2. Auto-gain with loudness metering — measures actual output loudness
      and adjusts gain to hit a consistent target across different videos.
      A quiet indie film and a loud action movie will play at the same level.

   Target: -14 LUFS (broadcast standard, comfortable for TV listening)
   Uses Web Audio API — runs in real-time, no transcoding needed. */

var TARGET_LOUDNESS = -14;  // LUFS — broadcast standard
var GAIN_ADJUST_INTERVAL = 2000;  // Adjust gain every 2 seconds
var GAIN_SMOOTHING = 0.3;  // How fast to adjust (0=instant, 1=never)

function initAudioNormalizer(mediaElement) {
    if (!mediaElement || mediaElement._audioNormalized) return null;
    try {
        var ctx = new (window.AudioContext || window.webkitAudioContext)();
        var source = ctx.createMediaElementSource(mediaElement);

        // Stage 1: Compressor — squash dynamic range
        var compressor = ctx.createDynamicsCompressor();
        compressor.threshold.value = -35;   // Compress anything above -35dB
        compressor.knee.value = 20;          // Moderate knee
        compressor.ratio.value = 10;         // Heavy compression
        compressor.attack.value = 0.003;     // Fast attack — catch sudden loud sounds
        compressor.release.value = 0.25;     // Moderate release

        // Stage 2: Auto-gain — adjusts level to hit target loudness
        var gain = ctx.createGain();
        gain.gain.value = 1.5;  // Start with moderate boost

        // Loudness analyzer — measures RMS of output to estimate loudness
        var analyser = ctx.createAnalyser();
        analyser.fftSize = 2048;
        analyser.smoothingTimeConstant = 0.8;

        // Chain: media → compressor → gain → analyser → speakers
        source.connect(compressor);
        compressor.connect(gain);
        gain.connect(analyser);
        analyser.connect(ctx.destination);

        // Resume AudioContext (Chrome autoplay policy)
        if (ctx.state === "suspended") {
            ctx.resume().catch(function() {});
            document.addEventListener("keydown", function resumeAudio() {
                ctx.resume();
                document.removeEventListener("keydown", resumeAudio);
            }, { once: true });
        }

        // Auto-gain loop: measure loudness, adjust gain toward target
        var dataArray = new Float32Array(analyser.fftSize);
        var currentGain = gain.gain.value;

        var gainInterval = setInterval(function() {
            if (mediaElement.paused || mediaElement.ended) return;

            analyser.getFloatTimeDomainData(dataArray);

            // Calculate RMS (root mean square) loudness
            var sumSquares = 0;
            for (var i = 0; i < dataArray.length; i++) {
                sumSquares += dataArray[i] * dataArray[i];
            }
            var rms = Math.sqrt(sumSquares / dataArray.length);

            // Convert to dB (approximate LUFS)
            var loudnessDB = rms > 0.0001 ? 20 * Math.log10(rms) : -60;

            // Skip adjustment during silence (scene changes, pauses)
            if (loudnessDB < -50) return;

            // Calculate how far off we are from target
            var error = TARGET_LOUDNESS - loudnessDB;

            // Convert dB error to gain multiplier adjustment
            var gainAdjust = Math.pow(10, error / 20);

            // Smooth the adjustment to avoid pumping
            currentGain = currentGain * GAIN_SMOOTHING + (currentGain * gainAdjust) * (1 - GAIN_SMOOTHING);

            // Clamp gain to safe range (0.5x to 4x)
            currentGain = Math.max(0.5, Math.min(4.0, currentGain));

            gain.gain.setTargetAtTime(currentGain, ctx.currentTime, 0.5);
        }, GAIN_ADJUST_INTERVAL);

        mediaElement._audioNormalized = true;

        // Store refs globally for diagnostics
        window._audioNorm = {
            ctx: ctx, gain: gain, compressor: compressor,
            analyser: analyser, source: source,
            getStats: function() {
                analyser.getFloatTimeDomainData(dataArray);
                var sum = 0;
                for (var i = 0; i < dataArray.length; i++) sum += dataArray[i] * dataArray[i];
                var rms = Math.sqrt(sum / dataArray.length);
                var db = rms > 0.0001 ? 20 * Math.log10(rms) : -60;
                return {
                    loudnessDB: Math.round(db * 10) / 10,
                    currentGain: Math.round(currentGain * 100) / 100,
                    compressorReduction: Math.round(compressor.reduction * 10) / 10,
                    targetLUFS: TARGET_LOUDNESS
                };
            }
        };

        // Cleanup on page unload
        window.addEventListener("beforeunload", function() {
            clearInterval(gainInterval);
        });

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
