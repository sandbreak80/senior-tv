/* Senior TV - TV UI Navigation
   Handles arrow key navigation for all page types, SSE pill reminders, and auto-refresh.

   Navigation model:
   - All navigable elements have class "navigable"
   - On home: vertical menu list
   - On browse pages: poster grid (2D), episode lists, channel lists
   - On all pages: Escape/Back returns home
*/

// Global activity logger — fire and forget
window._pageLoadTime = Date.now();
window.logActivity = function(type, title, itemType, extra) {
    var payload = {type: type, title: title, item_type: itemType};
    if (extra) { for (var k in extra) payload[k] = extra[k]; }
    fetch("/api/log-activity", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
    }).catch(function(){});
};

// Log page visit on load
window.logActivity("page_visit", document.title, window.location.pathname);

// Log page leave with duration on unload
window.addEventListener("beforeunload", function() {
    var duration = Math.floor((Date.now() - window._pageLoadTime) / 1000);
    if (duration > 0) {
        navigator.sendBeacon("/api/log-activity", JSON.stringify({
            type: "page_leave", title: document.title,
            item_type: window.location.pathname, duration: duration
        }));
    }
});

// Global fast navigation — kills iframes, fades out, then navigates
window.quickNav = function(url) {
    // Kill iframes, videos, and in-flight image downloads
    document.querySelectorAll("iframe, video, img").forEach(function(el) {
        if (el.tagName === "IFRAME") el.src = "about:blank";
        else if (el.tagName === "VIDEO") { el.pause(); el.src = ""; }
        else el.src = "";
    });
    // Abort any pending fetch/XHR requests
    if (window._abortController) window._abortController.abort();
    document.body.style.transition = "opacity 0.12s";
    document.body.style.opacity = "0";
    if (url === "back") history.back();
    else window.location.href = url;
};

(function () {
    "use strict";

    // Block any navigation away from the Senior TV app
    window.addEventListener("beforeunload", function (e) {
        // Allow internal navigation (same origin)
        // Block external navigation (e.g. YouTube clicking through)
    });
    document.addEventListener("click", function (e) {
        const link = e.target.closest("a");
        if (link && link.href && !link.href.startsWith(window.location.origin) && !link.href.startsWith("/")) {
            e.preventDefault();
            e.stopPropagation();
        }
    }, true);

    // --- Network status monitoring ---
    function updateNetworkBanner() {
        var banner = document.getElementById("network-banner");
        if (!banner) {
            banner = document.createElement("div");
            banner.id = "network-banner";
            banner.style.cssText = "position:fixed;top:0;left:0;right:0;padding:12px;background:#c62828;" +
                "color:white;text-align:center;font-size:28px;z-index:99999;display:none;font-weight:bold;";
            document.body.prepend(banner);
        }
        if (!navigator.onLine) {
            banner.textContent = "No Internet Connection — Some features unavailable";
            banner.style.display = "block";
        } else {
            banner.style.display = "none";
        }
    }
    window.addEventListener("online", updateNetworkBanner);
    window.addEventListener("offline", updateNetworkBanner);
    updateNetworkBanner();

    let selectedIndex = 0;
    let navItems = [];
    let reminderActive = false;
    let reminderBlocked = false; // true during shower time — can't dismiss
    let blockCountdownInterval = null;
    let currentReminderId = null;
    var ttsEnabled = true;

    // --- Initialization ---

    function init() {
        refreshNavItems();

        // Fetch TTS setting from server
        fetch("/api/tv-settings")
            .then(function(r) { return r.json(); })
            .then(function(data) { ttsEnabled = !!data.tts_enabled; })
            .catch(function() {});

        if (navItems.length > 0) {
            var activeIdx = 0;
            for (var i = 0; i < navItems.length; i++) {
                if (navItems[i].classList.contains("active")) {
                    activeIdx = i;
                    break;
                }
            }
            selectItem(activeIdx);
        }

        document.addEventListener("keydown", handleKeyDown);
        initSSE();
        startAutoRefresh();
        initAutoPlay();
        loadDailyDigest();
        checkActiveBlockingReminder();
    }

    function checkActiveBlockingReminder() {
        fetch("/api/active-blocking-reminder")
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (!data.active) return;
                // Re-show the blocking reminder overlay
                var overlay = document.getElementById("reminder-overlay");
                if (!overlay) return;
                var iconEl = overlay.querySelector(".reminder-icon");
                var titleEl = overlay.querySelector(".reminder-title");
                if (iconEl) iconEl.textContent = data.icon || "\U0001f9d8";
                if (titleEl) {
                    if (data.icon === "\U0001f6bf") titleEl.textContent = "Shower Time!";
                    else titleEl.textContent = "Stretch Break!";
                }
                document.getElementById("reminder-name").textContent = data.name;
                document.getElementById("reminder-dosage").textContent = "";
                document.getElementById("reminder-message").textContent = data.instructions || "";
                var dismissEl = overlay.querySelector(".reminder-dismiss");
                overlay.classList.add("active");
                reminderActive = true;
                reminderBlocked = true;
                currentReminderId = data.reminder_id;
                muteAllMedia();
                // Live MM:SS countdown
                if (data.remaining_minutes > 0) {
                    var unlockMs = data.remaining_minutes * 60 * 1000;
                    function updateCountdown() {
                        var totalSecs = Math.ceil(unlockMs / 1000);
                        var m = Math.floor(totalSecs / 60);
                        var s = totalSecs % 60;
                        if (dismissEl) dismissEl.textContent = "TV Will Be Back In: " + m + ":" + String(s).padStart(2, "0");
                    }
                    updateCountdown();
                    blockCountdownInterval = setInterval(function() {
                        unlockMs -= 1000;
                        if (unlockMs <= 0) {
                            clearInterval(blockCountdownInterval);
                            blockCountdownInterval = null;
                            reminderBlocked = false;
                            if (dismissEl) dismissEl.textContent = "Press OK to continue";
                        } else {
                            updateCountdown();
                        }
                    }, 1000);
                }
            })
            .catch(function() {});
    }

    function refreshNavItems() {
        navItems = document.querySelectorAll(".navigable");
    }
    window.refreshNavItems = refreshNavItems;

    // --- Navigation ---

    function selectItem(index) {
        if (index < 0 || index >= navItems.length) return;
        navItems.forEach(item => item.classList.remove("selected"));
        selectedIndex = index;
        navItems[selectedIndex].classList.add("selected");
        navItems[selectedIndex].scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    function activateItem() {
        if (navItems.length === 0) return;
        const item = navItems[selectedIndex];
        // Check if this element has an AJAX handler (set by page-specific scripts)
        if (item._ajaxHandler) {
            item._ajaxHandler();
            return;
        }
        const url = item.getAttribute("data-url") || item.getAttribute("href");
        if (url) {
            window.quickNav(url);
        }
    }

    // --- Smart Navigation (row-aware) ---
    // Groups navigable items by their parent row/section.
    // Left/Right moves within a row. Up/Down jumps between rows,
    // landing on the closest item by horizontal position.

    function getRowOf(el) {
        // Walk up to find the containing row/section
        var p = el.parentElement;
        while (p && p !== document.body) {
            if (p.classList.contains("home-poster-row") ||
                p.classList.contains("poster-row") ||
                p.classList.contains("home-quick-menu") ||
                p.classList.contains("menu-list") ||
                p.classList.contains("poster-grid") ||
                p.classList.contains("category-tabs") ||
                p.classList.contains("content-body")) {
                return p;
            }
            p = p.parentElement;
        }
        return el.parentElement;
    }

    function getRows() {
        // Group navItems by their row container
        var rows = [];
        var rowMap = new Map();
        for (var i = 0; i < navItems.length; i++) {
            var row = getRowOf(navItems[i]);
            if (!rowMap.has(row)) {
                rowMap.set(row, rows.length);
                rows.push([]);
            }
            rows[rowMap.get(row)].push(i);
        }
        return rows;
    }

    function findCurrentRow(rows) {
        for (var r = 0; r < rows.length; r++) {
            if (rows[r].indexOf(selectedIndex) !== -1) return r;
        }
        return 0;
    }

    function moveUp() {
        var rows = getRows();
        var curRow = findCurrentRow(rows);
        if (curRow > 0) {
            // Jump to the closest item in the row above by horizontal position
            var curRect = navItems[selectedIndex].getBoundingClientRect();
            var targetRow = rows[curRow - 1];
            var best = targetRow[0];
            var bestDist = Infinity;
            for (var i = 0; i < targetRow.length; i++) {
                var rect = navItems[targetRow[i]].getBoundingClientRect();
                var dist = Math.abs(rect.left - curRect.left);
                if (dist < bestDist) { bestDist = dist; best = targetRow[i]; }
            }
            selectItem(best);
        }
    }

    function moveDown() {
        var rows = getRows();
        var curRow = findCurrentRow(rows);
        if (curRow < rows.length - 1) {
            var curRect = navItems[selectedIndex].getBoundingClientRect();
            var targetRow = rows[curRow + 1];
            var best = targetRow[0];
            var bestDist = Infinity;
            for (var i = 0; i < targetRow.length; i++) {
                var rect = navItems[targetRow[i]].getBoundingClientRect();
                var dist = Math.abs(rect.left - curRect.left);
                if (dist < bestDist) { bestDist = dist; best = targetRow[i]; }
            }
            selectItem(best);
        }
    }

    function moveLeft() {
        var rows = getRows();
        var curRow = findCurrentRow(rows);
        var rowItems = rows[curRow];
        var posInRow = rowItems.indexOf(selectedIndex);
        if (posInRow > 0) {
            selectItem(rowItems[posInRow - 1]);
        }
    }

    function moveRight() {
        var rows = getRows();
        var curRow = findCurrentRow(rows);
        var rowItems = rows[curRow];
        var posInRow = rowItems.indexOf(selectedIndex);
        if (posInRow < rowItems.length - 1) {
            selectItem(rowItems[posInRow + 1]);
        }
    }

    // --- Key Handling ---

    function handleKeyDown(e) {
        // If reminder is active, handle dismiss/action
        if (reminderActive) {
            if (!reminderBlocked) {
                if (e.key === "Enter" || e.key === " ") {
                    // For show alerts: Enter = Watch Now (navigate to channel)
                    if (showAlertChannelId) {
                        var chId = showAlertChannelId;
                        showAlertChannelId = null;
                        dismissReminder();
                        window.quickNav("/tv/live/play/" + chId);
                        e.preventDefault();
                        return;
                    }
                    dismissReminder();
                } else if ((e.key === "Escape" || e.key === "Backspace" || e.key === "BrowserBack" || e.key === "ArrowDown") && showAlertChannelId) {
                    // BACK or Down = just dismiss (don't watch)
                    showAlertChannelId = null;
                    dismissReminder();
                }
            }
            e.preventDefault();
            return;
        }

        switch (e.key) {
            case "ArrowUp":
                e.preventDefault();
                moveUp();
                break;

            case "ArrowDown":
                e.preventDefault();
                moveDown();
                break;

            case "ArrowLeft":
                e.preventDefault();
                moveLeft();
                break;

            case "ArrowRight":
                e.preventDefault();
                moveRight();
                break;

            case "Enter":
            case " ":
                e.preventDefault();
                activateItem();
                break;

            case "Escape":
            case "Backspace":
            case "BrowserBack":
                e.preventDefault();
                goBack();
                break;
        }
    }

    function goBack() {
        if (window.location.pathname === "/") return;
        const path = window.location.pathname;
        if (path.startsWith("/tv/plex/play/") || path.startsWith("/tv/plex/show/")) {
            window.quickNav("back");
        } else if (path.startsWith("/tv/plex/library/")) {
            window.quickNav("/tv/plex");
        } else if (path.startsWith("/tv/live/play/")) {
            window.quickNav("/tv/live");
        } else {
            window.quickNav("/");
        }
    }

    // --- SSE for Pill Reminders ---

    function initSSE() {
        function connectSSE() {
            const evtSource = new EventSource("/events");

            evtSource.onmessage = function (event) {
                try {
                    const data = JSON.parse(event.data);
                    if (data.type === "pill_reminder") {
                        showReminder(data);
                    } else if (data.type === "doorbell_alert") {
                        showDoorbellAlert(data);
                    } else if (data.type === "birthday_alert") {
                        showBirthdayAlert(data);
                    } else if (data.type === "show_alert") {
                        showShowAlert(data);
                    } else if (data.type === "family_message") {
                        showFamilyMessage(data);
                    } else if (data.type === "message_deleted") {
                        // Admin deleted a message — dismiss alert if it's for this message
                        if (reminderActive && currentReminderId === "__family_msg_" + data.msg_id) {
                            dismissReminder();
                        }
                    } else if (data.type === "auto_play") {
                        // Only auto-play if someone is watching (skip if room empty)
                        if (data.url && !window._roomEmpty) {
                            window.quickNav(data.url);
                        }
                    } else if (data.type === "presence_change") {
                        window._roomEmpty = !data.occupied;
                        if (!data.occupied) {
                            // Room empty — start screensaver after 15 minutes
                            // (bathroom trips, getting food, etc. — don't interrupt too quickly)
                            if (!window._presenceTimeout) {
                                window._presenceTimeout = setTimeout(function() {
                                    window.logActivity("screensaver_start", "Room empty — screensaver", window.location.pathname);
                                    window.quickNav("/tv/photos?screensaver=1");
                                }, 900000);
                            }
                        } else if (data.occupied) {
                            // Someone sat down — cancel screensaver timer
                            if (window._presenceTimeout) {
                                clearTimeout(window._presenceTimeout);
                                window._presenceTimeout = null;
                            }
                            // Wake from screensaver — go to home (which will auto-play content)
                            if (window.location.search.indexOf("screensaver") > -1) {
                                window.quickNav("/");
                            }
                        }
                    }
                } catch (e) {
                    console.error("SSE parse error:", e);
                }
            };

            evtSource.onerror = function () {
                evtSource.close();
                // Exponential backoff: 5s, 10s, 20s, 40s, max 60s
                sseDelay = Math.min(sseDelay * 2, 60000);
                console.log("SSE lost, reconnecting in " + (sseDelay/1000) + "s...");
                setTimeout(connectSSE, sseDelay);
            };

            evtSource.onopen = function () {
                sseDelay = 5000; // Reset on successful connection
            };
        }
        var sseDelay = 5000;
        connectSSE();
    }

    // --- Media Mute/Pause for Overlays ---

    var _mutedMedia = [];
    function muteAllMedia() {
        _mutedMedia = [];
        // Pause and mute all video/audio elements
        document.querySelectorAll("video, audio").forEach(function(el) {
            if (!el.paused || !el.muted) {
                _mutedMedia.push({ el: el, wasPaused: el.paused, wasMuted: el.muted });
                el.muted = true;
                if (!el.paused) el.pause();
            }
        });
        // Mute iframes by hiding them (can't control cross-origin audio)
        document.querySelectorAll("iframe").forEach(function(el) {
            el.style.visibility = "hidden";
        });
    }
    function unmuteAllMedia() {
        _mutedMedia.forEach(function(item) {
            item.el.muted = item.wasMuted;
            if (!item.wasPaused) item.el.play().catch(function() {});
        });
        _mutedMedia = [];
        document.querySelectorAll("iframe").forEach(function(el) {
            el.style.visibility = "";
        });
    }

    // --- Pill Reminder Display ---

    function showReminder(data) {
        const overlay = document.getElementById("reminder-overlay");
        if (!overlay) return;

        currentReminderId = data.reminder_id;

        // Set icon
        const iconEl = overlay.querySelector(".reminder-icon");
        if (iconEl) iconEl.textContent = data.icon || "💊";
        const titleEl = overlay.querySelector(".reminder-title");
        if (titleEl) {
            if (data.icon === "🚿") titleEl.textContent = "Shower Time!";
            else if (data.icon === "🧘") titleEl.textContent = "Stretch Break!";
            else titleEl.textContent = "Time For Your Medicine";
        }

        document.getElementById("reminder-name").textContent = data.name;
        document.getElementById("reminder-dosage").textContent = data.dosage || "";
        document.getElementById("reminder-message").textContent = data.reminder_message;

        const videoEl = document.getElementById("reminder-video");
        const imageEl = document.getElementById("reminder-image");
        videoEl.style.display = "none";
        imageEl.style.display = "none";

        if (data.reminder_type === "video" && data.reminder_media) {
            videoEl.src = "/static/media/" + data.reminder_media;
            videoEl.style.display = "block";
            videoEl.play().catch(() => {});
        } else if (data.reminder_type === "image" && data.reminder_media) {
            imageEl.src = "/static/media/" + data.reminder_media;
            imageEl.style.display = "block";
        }

        overlay.classList.add("active");
        reminderActive = true;
        muteAllMedia();

        // Pause any playing video
        const mainVideo = document.getElementById("video-player");
        if (mainVideo) mainVideo.pause();

        // Blocking reminder (shower time) — can't dismiss for N minutes
        const blockMinutes = data.block_minutes || 0;
        if (blockMinutes > 0) {
            reminderBlocked = true;
            let secondsLeft = blockMinutes * 60;
            const dismissEl = overlay.querySelector(".reminder-dismiss");

            blockCountdownInterval = setInterval(() => {
                secondsLeft--;
                const mins = Math.floor(secondsLeft / 60);
                const secs = secondsLeft % 60;
                if (dismissEl) {
                    dismissEl.textContent = "TV Will Be Back In: " + mins + ":" + String(secs).padStart(2, "0");
                }
                if (secondsLeft <= 0) {
                    clearInterval(blockCountdownInterval);
                    reminderBlocked = false;
                    if (dismissEl) dismissEl.textContent = "Press OK to continue";
                    dismissReminder();
                }
            }, 1000);

            // Safety: auto-unlock after 2x the block time in case countdown fails
            setTimeout(function() {
                if (reminderBlocked) {
                    reminderBlocked = false;
                    if (blockCountdownInterval) clearInterval(blockCountdownInterval);
                    dismissReminder();
                }
            }, blockMinutes * 120000);
        } else {
            reminderBlocked = false;
            // Auto-dismiss non-blocking reminders after 60 seconds
            // (they can't press OK without a remote)
            setTimeout(function() { if (reminderActive) dismissReminder(); }, 60000);
        }

        playChime();
        setTimeout(function() { speakAlert("pill_reminder", data); }, 1000);
    }

    function dismissReminder() {
        if (window.speechSynthesis) window.speechSynthesis.cancel();
        const overlay = document.getElementById("reminder-overlay");
        if (!overlay) return;

        if (blockCountdownInterval) {
            clearInterval(blockCountdownInterval);
            blockCountdownInterval = null;
        }
        reminderBlocked = false;

        overlay.classList.remove("active");
        reminderActive = false;
        unmuteAllMedia();

        // Reset dismiss text and icon
        const dismissEl = overlay.querySelector(".reminder-dismiss");
        if (dismissEl) dismissEl.textContent = "Press OK to dismiss";
        const resetIcon = overlay.querySelector(".reminder-icon");
        if (resetIcon) resetIcon.textContent = "💊";
        const resetTitle = overlay.querySelector(".reminder-title");
        if (resetTitle) resetTitle.textContent = "Time For Your Medicine";

        const videoEl = document.getElementById("reminder-video");
        videoEl.pause();
        videoEl.src = "";

        // Navigate to family message if that's what was showing
        if (currentReminderId && currentReminderId.startsWith("__family_msg_")) {
            const msgId = currentReminderId.replace("__family_msg_", "");
            currentReminderId = null;
            window.location.href = msgId ? "/tv/messages/" + msgId : "/tv/messages";
            return;
        }

        // Resume main video if on player page
        const mainVideo = document.getElementById("video-player");
        if (mainVideo) mainVideo.play().catch(() => {});

        if (currentReminderId) {
            fetch("/api/acknowledge", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ reminder_id: currentReminderId }),
            }).catch(() => {});
            currentReminderId = null;
        }
    }

    function _getAudioCtx() {
        if (!window._seniorTvAudioCtx) {
            window._seniorTvAudioCtx = new (window.AudioContext || window.webkitAudioContext)();
        }
        return window._seniorTvAudioCtx;
    }

    function playChime() {
        try {
            const ctx = _getAudioCtx();

            function playTone(freq, startTime, duration) {
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.type = "sine";
                osc.frequency.value = freq;
                gain.gain.setValueAtTime(0.3, startTime);
                gain.gain.exponentialRampToValueAtTime(0.01, startTime + duration);
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.start(startTime);
                osc.stop(startTime + duration);
            }

            const now = ctx.currentTime;
            playTone(523.25, now, 0.4);
            playTone(659.25, now + 0.2, 0.4);
            playTone(783.99, now + 0.4, 0.6);
        } catch (e) {
            console.log("Audio not available");
        }
    }

    function speakAlert(type, data) {
        if (!ttsEnabled || !window.speechSynthesis) return;
        window.speechSynthesis.cancel();

        var text = "";
        switch (type) {
            case "pill_reminder":
                if (data.icon === "\uD83D\uDEBF") {
                    text = "Shower Time! Time for your shower.";
                } else if (data.icon === "\uD83E\uDDD8") {
                    text = "Stretch Break! Time to stretch.";
                } else {
                    var parts = [];
                    if (data.name) parts.push(data.name);
                    if (data.dosage) parts.push(data.dosage);
                    if (data.reminder_message) parts.push(data.reminder_message);
                    text = parts.join(". ");
                }
                break;
            case "doorbell_alert":
                text = data.title || "Someone is at the front door!";
                break;
            case "birthday_alert":
                text = "Happy Birthday " + (data.name || "") + "! " + (data.age_str || "");
                break;
            case "show_alert":
                text = (data.show_name || "Your show") + " is on now!";
                break;
            case "family_message":
                text = "New message from " + (data.sender || "family");
                break;
        }
        if (!text) return;

        try {
            var utterance = new SpeechSynthesisUtterance(text);
            utterance.rate = 0.8;
            utterance.pitch = 1.0;
            utterance.volume = 1.0;
            window.speechSynthesis.speak(utterance);
        } catch (e) {
            console.log("TTS not available");
        }
    }

    // --- Doorbell Alert ---

    function showDoorbellAlert(data) {
        const overlay = document.getElementById("reminder-overlay");
        if (!overlay) return;

        document.getElementById("reminder-name").textContent = data.title || "Someone is at the door!";
        document.getElementById("reminder-dosage").textContent = data.timestamp || "";
        document.getElementById("reminder-message").textContent = "Press OK to dismiss";

        // Show camera snapshot
        const imageEl = document.getElementById("reminder-image");
        const videoEl = document.getElementById("reminder-video");
        videoEl.style.display = "none";
        if (data.snapshot_url) {
            imageEl.src = "/api/frigate-snapshot/" + data.snapshot_url.split("/api/")[1];
            imageEl.style.display = "block";
        } else {
            imageEl.style.display = "none";
        }

        // Change icon to doorbell
        const iconEl = overlay.querySelector(".reminder-icon");
        if (iconEl) iconEl.textContent = data.icon || "🚪";
        const titleEl = overlay.querySelector(".reminder-title");
        if (titleEl) titleEl.textContent = data.title || "Someone is at the Door!";

        overlay.classList.add("active");
        reminderActive = true;
        muteAllMedia();

        // Pause any playing video
        const mainVideo = document.getElementById("video-player");
        if (mainVideo) mainVideo.pause();

        // Play doorbell sound
        playDoorbell();
        setTimeout(function() { speakAlert("doorbell_alert", data); }, 1300);

        // Auto-dismiss after 30 seconds
        setTimeout(() => {
            if (reminderActive) dismissReminder();
        }, 30000);
    }

    function playDoorbell() {
        try {
            const ctx = _getAudioCtx();
            function playTone(freq, startTime, duration) {
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.type = "sine";
                osc.frequency.value = freq;
                gain.gain.setValueAtTime(0.4, startTime);
                gain.gain.exponentialRampToValueAtTime(0.01, startTime + duration);
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.start(startTime);
                osc.stop(startTime + duration);
            }
            const now = ctx.currentTime;
            // Ding-dong pattern
            playTone(880, now, 0.5);
            playTone(659, now + 0.5, 0.8);
        } catch (e) {}
    }

    // --- Birthday Alert ---

    function showBirthdayAlert(data) {
        const overlay = document.getElementById("reminder-overlay");
        if (!overlay) return;

        currentReminderId = data.reminder_id;

        const iconEl = overlay.querySelector(".reminder-icon");
        if (iconEl) iconEl.textContent = "🎂";
        const titleEl = overlay.querySelector(".reminder-title");
        if (titleEl) titleEl.textContent = "Happy Birthday!";

        document.getElementById("reminder-name").textContent = data.name + (data.age_str || "");
        document.getElementById("reminder-dosage").textContent = data.relationship || "";
        document.getElementById("reminder-message").textContent = data.message;

        const videoEl = document.getElementById("reminder-video");
        const imageEl = document.getElementById("reminder-image");
        videoEl.style.display = "none";
        imageEl.style.display = "none";

        overlay.classList.add("active");
        reminderActive = true;
        muteAllMedia();

        // Play happy tune
        try {
            const ctx = _getAudioCtx();
            function tone(freq, start, dur) {
                const o = ctx.createOscillator();
                const g = ctx.createGain();
                o.type = "sine"; o.frequency.value = freq;
                g.gain.setValueAtTime(0.3, start);
                g.gain.exponentialRampToValueAtTime(0.01, start + dur);
                o.connect(g); g.connect(ctx.destination);
                o.start(start); o.stop(start + dur);
            }
            const t = ctx.currentTime;
            // Happy Birthday melody fragment
            [262,262,294,262,349,330].forEach((f,i) => tone(f, t + i*0.25, 0.3));
        } catch(e) {}
        setTimeout(function() { speakAlert("birthday_alert", data); }, 1800);

        // Auto-dismiss after 60 seconds
        setTimeout(() => { if (reminderActive) dismissReminder(); }, 60000);
    }

    // --- Show Alert ---

    var showAlertChannelId = null;

    function showShowAlert(data) {
        const overlay = document.getElementById("reminder-overlay");
        if (!overlay) return;

        currentReminderId = data.reminder_id;
        showAlertChannelId = data.channel_id || null;

        const iconEl = overlay.querySelector(".reminder-icon");
        if (iconEl) iconEl.textContent = "📺";
        const titleEl = overlay.querySelector(".reminder-title");
        if (titleEl) titleEl.textContent = data.show_name + " is on now!";

        document.getElementById("reminder-name").textContent = data.channel_name;
        document.getElementById("reminder-dosage").textContent = "";
        document.getElementById("reminder-message").textContent = "";

        const videoEl = document.getElementById("reminder-video");
        const imageEl = document.getElementById("reminder-image");
        videoEl.style.display = "none";
        imageEl.style.display = "none";

        // Show clear action instructions
        const dismissEl = overlay.querySelector(".reminder-dismiss");
        if (dismissEl) dismissEl.innerHTML = '<span style="font-size:48px;display:block;margin-bottom:12px;">Press OK to Watch</span><span style="font-size:30px;opacity:0.6;">Press BACK to close</span>';

        overlay.classList.add("active");
        reminderActive = true;
        muteAllMedia();
        playChime();
        setTimeout(function() { speakAlert("show_alert", data); }, 1000);

        // Auto-dismiss after 30 seconds
        setTimeout(function() { if (reminderActive) dismissReminder(); }, 30000);
    }

    // --- Family Message Alert ---

    function showFamilyMessage(data) {
        const overlay = document.getElementById("reminder-overlay");
        if (!overlay) return;

        currentReminderId = null; // No server-side ack needed

        const iconEl = overlay.querySelector(".reminder-icon");
        if (iconEl) iconEl.textContent = "💌";
        const titleEl = overlay.querySelector(".reminder-title");
        if (titleEl) titleEl.textContent = "New Message from " + (data.sender || "Family") + "!";

        document.getElementById("reminder-name").textContent = data.message || "";
        document.getElementById("reminder-dosage").textContent = "";
        document.getElementById("reminder-message").textContent = "";

        const videoEl = document.getElementById("reminder-video");
        const imageEl = document.getElementById("reminder-image");
        videoEl.style.display = "none";
        imageEl.style.display = "none";

        const dismissEl = overlay.querySelector(".reminder-dismiss");
        if (dismissEl) dismissEl.textContent = "Press OK to view message";

        overlay.classList.add("active");
        reminderActive = true;
        muteAllMedia();

        // Play gentle notification
        playChime();
        setTimeout(function() { speakAlert("family_message", data); }, 1000);

        // On dismiss, navigate to the message
        currentReminderId = "__family_msg_" + (data.msg_id || "");

        // Auto-dismiss after 60 seconds
        setTimeout(function() {
            if (reminderActive && currentReminderId === "__family_msg_" + (data.msg_id || "")) {
                dismissReminder();
            }
        }, 60000);
    }

    // Override dismiss to handle family message navigation
    const _origDismiss = dismissReminder;

    // --- Auto-Play from Home Screen ---
    // Don & Colleen watch TV for hours without pressing buttons.
    // Screensaver is triggered ONLY by presence detection (room empty),
    // never by keyboard idle. After showing the home screen for 5 minutes
    // (weather, greeting, pills, family photo), auto-play genre-appropriate
    // content from Jellyfin based on time-of-day care plan.

    var autoPlayTimer = null;
    var AUTO_PLAY_DELAY = 45 * 1000; // 45 seconds on home before auto-play

    function initAutoPlay() {
        if (window.location.pathname !== "/") return;

        autoPlayTimer = setTimeout(function() {
            if (reminderActive) {
                // Reminder active — try again in 1 minute
                autoPlayTimer = setTimeout(arguments.callee, 60000);
                return;
            }
            // Try Jellyfin first (genre-matched to time of day)
            fetch("/api/next-video")
                .then(function(r) { return r.ok ? r.json() : null; })
                .then(function(data) {
                    if (data && data.url) {
                        window.logActivity("auto_play", data.title || "Auto-play", data.url, {item_id: data.id});
                        window.quickNav(data.url);
                    } else {
                        // Jellyfin unavailable — fall back to a time-appropriate Pluto channel
                        return fetch("/api/next-channel")
                            .then(function(r) { return r.ok ? r.json() : null; })
                            .then(function(ch) {
                                if (ch && ch.url) {
                                    window.logActivity("auto_play", ch.name || "Live TV", ch.url);
                                    window.quickNav(ch.url);
                                }
                            });
                    }
                })
                .catch(function() {
                    fetch("/api/next-channel")
                        .then(function(r) { return r.ok ? r.json() : null; })
                        .then(function(ch) {
                            if (ch && ch.url) {
                                window.logActivity("auto_play", ch.name || "Live TV", ch.url);
                                window.quickNav(ch.url);
                            }
                        })
                        .catch(function() {});
                });
        }, AUTO_PLAY_DELAY);

        // Cancel auto-play if user navigates manually
        document.addEventListener("keydown", function() {
            if (autoPlayTimer) {
                clearTimeout(autoPlayTimer);
                autoPlayTimer = null;
            }
        }, { once: true });
    }

    // --- Daily Digest ---

    function loadDailyDigest() {
        if (window.location.pathname !== "/") return;
        fetch("/api/daily-digest")
            .then(r => r.json())
            .then(data => {
                const digestEl = document.querySelector(".daily-digest");
                if (!digestEl) return;
                digestEl.textContent = "";
                if (data.quote) {
                    var q = document.createElement("span");
                    q.className = "digest-quote";
                    q.textContent = "\u201C" + data.quote.text + "\u201D \u2014 " + data.quote.author;
                    digestEl.appendChild(q);
                }
                if (data.history) {
                    var h = document.createElement("span");
                    h.className = "digest-history";
                    h.textContent = "On this day in " + data.history.year + ": " + data.history.text.substring(0, 120);
                    digestEl.appendChild(h);
                }
            })
            .catch(() => {});
    }

    // --- Auto-refresh home data ---

    var _homeRefreshInterval = null;
    function startAutoRefresh() {
        if (window.location.pathname !== "/") return;
        if (_homeRefreshInterval) clearInterval(_homeRefreshInterval);

        _homeRefreshInterval = setInterval(function () {
            fetch("/api/home-data")
                .then(r => r.json())
                .then(data => {
                    const greetEl = document.querySelector(".greeting");
                    const dateEl = document.querySelector(".date-text");
                    const weatherEl = document.querySelector(".weather-text");
                    const pillEl = document.querySelector(".pill-status");

                    if (greetEl) greetEl.textContent = data.greeting;
                    if (dateEl) dateEl.textContent = data.date;
                    if (weatherEl) {
                        weatherEl.textContent = data.weather.temp + " " + data.weather.condition;
                    }
                    if (pillEl && data.next_pill) {
                        pillEl.textContent = "💊 Next: " + data.next_pill.name + " at " + data.next_pill.time;
                        pillEl.classList.add("has-pill");
                    } else if (pillEl) {
                        pillEl.textContent = "✓ No pills due";
                        pillEl.classList.remove("has-pill");
                    }
                })
                .catch(() => {});
        }, 60000);
    }

    // --- Start ---

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
