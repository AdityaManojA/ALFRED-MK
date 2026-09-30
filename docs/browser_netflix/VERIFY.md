# Live Verification Checklist: Browser Suite & Netflix Pilot

This checklist outlines the manual live verification procedures across Windows, macOS, and Linux for the Browser Suite tab control and Netflix Pilot.

---

## 1. Browser Tab Management ("Close Tab" Fix)

### Test 1.1: Chrome Active Tab Close
1. Open Google Chrome with multiple tabs (e.g. Tab 1: `wikipedia.org`, Tab 2: `github.com`).
2. Focus Tab 2 (`github.com`).
3. Speak or trigger: *"close tab"* or *"close this tab"*.
4. **Expected:**
   - Tab 2 closes immediately.
   - ALFRED responds: *"Tab closed, sir."*
   - HUD displays status toast: `[Browser] Tab closed`.
   - **Crucial:** No blank window or `about:blank` page is opened.

### Test 1.2: Microsoft Edge Active Tab Close
1. Open Microsoft Edge with two tabs.
2. Focus the active tab.
3. Speak: *"shut this tab"* or *"kill tab"*.
4. **Expected:**
   - Active tab closes cleanly.
   - No background Playwright instances spawn.

### Test 1.3: Brave Browser Active Tab Close
1. Open Brave Browser.
2. Speak: *"close tab"*.
3. **Expected:**
   - Foreground tab closes cleanly.

### Test 1.4: Tab Reopen & New Tab
1. With browser focused, speak: *"reopen tab"* or *"undo close tab"*.
2. **Expected:** Closed tab reopens (`Ctrl+Shift+T` / `Cmd+Shift+T`).
3. Speak: *"new tab"*.
4. **Expected:** Blank new tab opens in the frontmost browser (`Ctrl+T` / `Cmd+T`).

---

## 2. Netflix State Detection & Profile Gate

### Test 2.1: Logged-in Session with Profile Gate ("Who's watching?")
1. Navigate to Netflix (`netflix.com`) on an account with multiple profiles so the "Who's watching?" screen is visible.
2. Speak: *"open Netflix"* or trigger state check.
3. **Expected:**
   - ALFRED detects `NetflixState.PROFILE_GATE` in < 1.5s.
   - ALFRED prompts: *"Which profile shall I select, sir?"*
   - Single-utterance AnswerWindow opens (mic is active without requiring "Hey Alfred").
4. User speaks profile name (e.g. *"Aditya"*) or ordinal (e.g. *"first"* / *"second"*).
5. **Expected:**
   - ALFRED speaks: *"Accessing [Profile], sir."*
   - HUD displays status toast: `[Netflix] Profile: <Name>`.
   - Profile avatar is clicked or activated via keyboard.
   - Netflix transitions to Browse Home.

### Test 2.2: Non-Logged-In Session
1. Open an incognito/private browser window to `https://www.netflix.com` (showing the "Sign In" / "Unlimited movies" landing page).
2. Speak: *"open Netflix"*.
3. **Expected:**
   - ALFRED detects `NetflixState.NOT_LOGGED_IN`.
   - ALFRED speaks: *"Netflix is not logged in on this browser, sir."*
   - No credential entry is attempted. System exits cleanly without crashing.

---

## 3. Netflix Search & Playback Automation

### Test 3.1: Voice Search
1. With Netflix open on Browse Home, speak: *"search Netflix for Interstellar"*.
2. **Expected:**
   - ALFRED speaks: *"Searching Netflix for 'Interstellar', sir."*
   - HUD toast: `[Netflix] Searching: Interstellar`.
   - Search box is focused and typed with 25ms humanized delays.
   - Search results grid is displayed.

### Test 3.2: Instant Play
1. Speak: *"play Dune on Netflix"*.
2. **Expected:**
   - ALFRED speaks: *"Searching Netflix for 'Dune', sir."* followed by *"Playing 'Dune', sir."*
   - HUD toast: `[Netflix] Playing: Dune`.
   - First video card in the search grid is targeted and activated.

### Test 3.3: Category / Genre Browse
1. Speak: *"browse Sci-Fi on Netflix"*.
2. **Expected:**
   - ALFRED speaks: *"Browsing Sci-fi on Netflix, sir."*
   - Browser navigates to `https://www.netflix.com/browse/genre/1492`.

---

## 4. Collision Guards Verification

| Voice Command | Verified Destination | Negative Collision Confirmed |
| :--- | :--- | :--- |
| *"play Inception on Netflix"* | Netflix Pilot (Browser) | NOT Visual HUD video player; NOT Spotify |
| *"play Inception trailer"* | Visual HUD video player | NOT Spotify |
| *"play Inception soundtrack"* | Spotify | NOT Visual HUD; NOT Netflix |
| *"close tab"* | Browser Controller | NOT OS Screen lock; NOT Window close; NOT Visual HUD stop |
| *"close the visual hud"* | Visual HUD player | Browser tabs remain open |
