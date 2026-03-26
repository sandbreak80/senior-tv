/* Senior TV - Built-in Video Player
   Controls: Enter=Play/Pause, Left/Right=Skip 30s, Escape=Back */

(function () {
    "use strict";

    const video = document.getElementById("video-player");
    const overlay = document.getElementById("player-overlay");
    const centerIcon = document.getElementById("player-center-icon");
    const progressFill = document.getElementById("player-progress-fill");
    const currentTimeEl = document.getElementById("player-current-time");
    const durationEl = document.getElementById("player-duration");

    let overlayTimeout = null;
    let iconTimeout = null;

    if (!video) return;

    // --- Activity Logging ---
    const container = document.getElementById("player-container");
    const logItemId = container ? container.dataset.itemId : "";
    const logItemTitle = container ? container.dataset.itemTitle : "";
    const logItemType = container ? container.dataset.itemType : "video";

    function logPlay() {
        fetch("/api/log-activity", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({type: "playback_start", item_id: logItemId, title: logItemTitle, item_type: logItemType})
        }).catch(function(){});
    }
    function logStop() {
        var dur = Math.floor(video.currentTime || 0);
        fetch("/api/log-activity", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({type: "playback_stop", item_id: logItemId, title: logItemTitle, item_type: logItemType, duration: dur})
        }).catch(function(){});
    }
    video.addEventListener("play", logPlay);
    video.addEventListener("ended", logStop);
    window.addEventListener("beforeunload", logStop);

    // --- Controls ---

    function togglePlayPause() {
        if (video.paused) {
            video.play();
            showCenterIcon("▶");
        } else {
            video.pause();
            showCenterIcon("⏸");
        }
        showOverlay();
    }

    function skip(seconds) {
        video.currentTime = Math.max(0, Math.min(video.duration || 0, video.currentTime + seconds));
        showCenterIcon(seconds > 0 ? "▶▶ 30s" : "◀◀ 30s");
        showOverlay();
    }

    function goBack() {
        video.pause();
        window.quickNav("back");
    }

    // --- Overlay visibility ---

    function showOverlay() {
        overlay.classList.add("visible");
        clearTimeout(overlayTimeout);
        overlayTimeout = setTimeout(() => {
            if (!video.paused) {
                overlay.classList.remove("visible");
            }
        }, 4000);
    }

    function showCenterIcon(text) {
        centerIcon.textContent = text;
        centerIcon.classList.add("visible");
        clearTimeout(iconTimeout);
        iconTimeout = setTimeout(() => {
            centerIcon.classList.remove("visible");
        }, 1000);
    }

    // --- Progress bar ---

    function updateProgress() {
        if (!video.duration) return;
        const pct = (video.currentTime / video.duration) * 100;
        progressFill.style.width = pct + "%";
        currentTimeEl.textContent = formatTime(video.currentTime);
        durationEl.textContent = formatTime(video.duration);
    }

    function formatTime(seconds) {
        if (isNaN(seconds)) return "0:00";
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = Math.floor(seconds % 60);
        if (h > 0) {
            return h + ":" + String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
        }
        return m + ":" + String(s).padStart(2, "0");
    }

    // --- Key handling (overrides tv.js for player page) ---

    document.addEventListener("keydown", function (e) {
        // Don't handle if reminder is active (tv.js handles that)
        const reminderOverlay = document.getElementById("reminder-overlay");
        if (reminderOverlay && reminderOverlay.classList.contains("active")) return;

        switch (e.key) {
            case "Enter":
            case " ":
                e.preventDefault();
                e.stopPropagation();
                togglePlayPause();
                break;
            case "ArrowLeft":
                e.preventDefault();
                e.stopPropagation();
                skip(-30);
                break;
            case "ArrowRight":
                e.preventDefault();
                e.stopPropagation();
                skip(30);
                break;
            case "ArrowUp":
                e.preventDefault();
                e.stopPropagation();
                // Volume up
                video.volume = Math.min(1, video.volume + 0.1);
                showCenterIcon("🔊 " + Math.round(video.volume * 100) + "%");
                showOverlay();
                break;
            case "ArrowDown":
                e.preventDefault();
                e.stopPropagation();
                // Volume down
                video.volume = Math.max(0, video.volume - 0.1);
                showCenterIcon("🔉 " + Math.round(video.volume * 100) + "%");
                showOverlay();
                break;
            case "Escape":
            case "Backspace":
            case "BrowserBack":
                e.preventDefault();
                e.stopPropagation();
                goBack();
                break;
        }
    }, true); // Use capture to override tv.js

    // --- Video events ---

    video.addEventListener("timeupdate", updateProgress);

    video.addEventListener("play", function () {
        showOverlay();
    });

    video.addEventListener("pause", function () {
        showOverlay();
    });

    video.addEventListener("ended", function () {
        logStop();
        showCenterIcon("Up Next...");
        showOverlay();
        // Auto-play next random content after 3 seconds
        fetch("/api/next-video")
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.url) {
                    setTimeout(function() { window.quickNav(data.url); }, 3000);
                } else {
                    showCenterIcon("✓ Finished");
                    setTimeout(goBack, 5000);
                }
            })
            .catch(function() {
                showCenterIcon("✓ Finished");
                setTimeout(goBack, 5000);
            });
    });

    var videoRetries = 0;
    video.addEventListener("error", function () {
        if (videoRetries < 2) {
            videoRetries++;
            showCenterIcon("Retrying...");
            setTimeout(function() { video.load(); video.play().catch(function(){}); }, 2000);
        } else {
            showCenterIcon("Unable to play — press BACK");
            overlay.classList.add("visible");
        }
    });

    // Show overlay initially
    showOverlay();
})();
