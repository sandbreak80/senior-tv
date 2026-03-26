/* Senior TV - TV UI Navigation
   Handles arrow key navigation for all page types, SSE pill reminders, and auto-refresh.

   Navigation model:
   - All navigable elements have class "navigable"
   - On home: vertical menu list
   - On browse pages: poster grid (2D), episode lists, channel lists
   - On all pages: Escape/Back returns home
*/

// Global activity logger — fire and forget
window.logActivity = function(type, title, itemType) {
    fetch("/api/log-activity", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({type: type, title: title, item_type: itemType})
    }).catch(function(){});
};

// Log page visit
window.logActivity("page_visit", document.title, window.location.pathname);

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

    // --- Initialization ---

    function init() {
        refreshNavItems();

        if (navItems.length > 0) {
            selectItem(0);
        }

        document.addEventListener("keydown", handleKeyDown);
        initSSE();
        startAutoRefresh();
        initIdleScreensaver();
        loadDailyDigest();
    }

    function refreshNavItems() {
        navItems = document.querySelectorAll(".navigable");
    }

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
                    } else if (data.type === "auto_play") {
                        // Auto-navigate to content (e.g. classical music)
                        if (data.url) window.quickNav(data.url);
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
                    dismissEl.textContent = "TV will be back in " + mins + ":" + String(secs).padStart(2, "0");
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
        }

        playChime();
    }

    function dismissReminder() {
        const overlay = document.getElementById("reminder-overlay");
        if (!overlay) return;

        if (blockCountdownInterval) {
            clearInterval(blockCountdownInterval);
            blockCountdownInterval = null;
        }
        reminderBlocked = false;

        overlay.classList.remove("active");
        reminderActive = false;

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

    function playChime() {
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();

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

        // Pause any playing video
        const mainVideo = document.getElementById("video-player");
        if (mainVideo) mainVideo.pause();

        // Play doorbell sound
        playDoorbell();

        // Auto-dismiss after 30 seconds
        setTimeout(() => {
            if (reminderActive) dismissReminder();
        }, 30000);
    }

    function playDoorbell() {
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
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

        // Play happy tune
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
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
        playChime();

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

        // Play gentle notification
        playChime();

        // On dismiss, navigate to the message
        currentReminderId = "__family_msg_" + (data.msg_id || "");
    }

    // Override dismiss to handle family message navigation
    const _origDismiss = dismissReminder;

    // --- Idle Screensaver ---

    let idleTimer = null;
    const IDLE_TIMEOUT = 10 * 60 * 1000; // 10 minutes

    function resetIdleTimer() {
        clearTimeout(idleTimer);
        idleTimer = setTimeout(() => {
            // Only activate screensaver from home page
            if (window.location.pathname === "/") {
                window.location.href = "/tv/photos?screensaver=1";
            }
        }, IDLE_TIMEOUT);
    }

    function initIdleScreensaver() {
        // Only enable on home page, and only if photos exist
        if (window.location.pathname !== "/") return;

        ["keydown", "mousemove", "mousedown", "touchstart"].forEach(evt => {
            document.addEventListener(evt, resetIdleTimer);
        });
        // Check if photos exist before enabling
        fetch("/api/has-photos")
            .then(r => r.json())
            .then(data => { if (data.has_photos) resetIdleTimer(); })
            .catch(() => {});
    }

    // --- Daily Digest ---

    function loadDailyDigest() {
        if (window.location.pathname !== "/") return;
        fetch("/api/daily-digest")
            .then(r => r.json())
            .then(data => {
                const digestEl = document.querySelector(".daily-digest");
                if (!digestEl) return;
                let html = "";
                if (data.quote) {
                    html += '<span class="digest-quote">"' + data.quote.text + '" — ' + data.quote.author + '</span>';
                }
                if (data.history) {
                    html += '<span class="digest-history">On this day in ' + data.history.year + ': ' + data.history.text.substring(0, 120) + '</span>';
                }
                if (html) digestEl.innerHTML = html;
            })
            .catch(() => {});
    }

    // --- Auto-refresh home data ---

    function startAutoRefresh() {
        if (window.location.pathname !== "/") return;

        setInterval(function () {
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
