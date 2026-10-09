# Alexa Integration: User Setup Guide

## Quick Setup (2 Actions)

Connecting your Amazon Echo device to ALFRED requires only two simple steps:

### Step 1: Click "CONNECT ALEXA"
1. In ALFRED, open **Tactical Controls** (bottom drawer) and click **API Connections / Setup API Backends**.
2. Select the **🎙 ALEXA** tab.
3. Click the cyan **CONNECT ALEXA** button.

### Step 2: Enable & Link the Skill
1. ALFRED will automatically open your default browser to the ALFRED Skill Linking page (or display a copyable link / QR code).
2. Sign in or confirm your ALFRED account.
3. Tap **Link Account** to grant permission.

Once confirmed, ALFRED's status badge will update to **CONNECTED**. You are now ready to issue voice directives to ALFRED through any Echo device connected to your Amazon account.

---

## Approved Voice Directives

Use standard Alexa invocation phrasing:

- *"Alexa, ask Alfred for status."*  
  *(Replies with CPU load and memory utilization.)*
- *"Alexa, ask Alfred to start focus mode for twenty-five minutes."*  
  *(Engages Sentry Focus mode on your desktop.)*
- *"Alexa, ask Alfred to stop focus mode."*  
  *(Concludes active focus session.)*
- *"Alexa, ask Alfred for my internet speed."*  
  *(Acknowledges immediately and runs the speed test in ALFRED.)*
- *"Alexa, tell Alfred to pause playback."*  
  *(Pauses media in Spotify or Audio Core.)*
- *"Alexa, tell Alfred to resume playback."*  
  *(Resumes media.)*
- *"Alexa, ask Alfred what is on my schedule."*  
  *(Summarizes schedule status without reading private message bodies.)*

---

## Managing Permissions
To disable or re-enable specific capabilities at any time:
1. Open the **🎙 ALEXA** tab in API Connections.
2. Click **MANAGE PERMISSIONS**.
3. Toggle any capability checkbox on or off, or click **RESET TO SAFE DEFAULTS**.
4. Click **SAVE PERMISSIONS**. Changes take effect immediately without reconnecting.

## Disconnecting
To revoke access, open the **🎙 ALEXA** tab and click **DISCONNECT**. This revokes only Alexa credentials; your Spotify, Gmail, and Tavily settings remain untouched.
