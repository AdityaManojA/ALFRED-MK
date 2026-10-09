# Alexa Integration: Developer Setup Guide

## 1. Prerequisites
- Amazon Developer Account ([developer.amazon.com](https://developer.amazon.com))
- Alexa Developer Console access
- Publicly accessible HTTPS domain or reverse proxy (e.g. Cloudflare Tunnel, ngrok, or AWS EC2) for the relay endpoint

---

## 2. Deploying the ALFRED Relay Server

The relay server resides in `server/alexa/` and runs as a standalone FastAPI service.

### Local Development / Quick Start:
```bash
# Run the relay server locally on port 8000
python -m uvicorn server.alexa.endpoint:create_alexa_app --factory --port 8000
```

### Environment Variables:
- `ALEXA_SKILL_ID`: Your Amazon Custom Skill ID (`amzn1.ask.skill.xxxx-xxxx`)
- `ALEXA_SKIP_SIGNATURE`: Set to `1` only during local offline unit testing; must be `0` in production.
- `ALEXA_RELAY_PORT`: Ingress port (default `8000`).

---

## 3. Creating the Amazon Alexa Custom Skill

1. Open the [Alexa Developer Console](https://developer.amazon.com/alexa/console/ask).
2. Click **Create Skill**.
3. Set Skill Name to **ALFRED**.
4. Choose **Custom** model and select **Provision your own** hosting.
5. In **Invocation Name**, set Skill Invocation Name to `alfred`.

### Importing the Interaction Model:
1. Navigate to **Interaction Model** -> **JSON Editor**.
2. Run the helper to generate the model or paste the output from:
   ```python
   from core.integrations.alexa.skill_model import export_interaction_model
   import json
   print(json.dumps(export_interaction_model("alfred"), indent=2))
   ```
3. Click **Save Model** and **Build Model**.

---

## 4. Configuring the HTTPS Endpoint

1. In the Alexa Developer Console, click **Endpoint**.
2. Select **HTTPS**.
3. Under **Default Region**, enter your relay HTTPS URL:
   `https://<your-domain>/api/alexa/skill`
4. Under **SSL Certificate Type**, select:
   *My development endpoint has a Certificate from a trusted Certificate Authority.*
5. Save Endpoints.

---

## 5. Account Linking Configuration

1. In the Alexa Developer Console, select **TOOLS** -> **Account Linking**.
2. Enable **Do you allow users to create an account or link to an existing account...**.
3. Select **Auth Code Grant**.
4. Set:
   - **Authorization URI**: `https://<your-domain>/api/alexa/link`
   - **Access Token URI**: `https://<your-domain>/api/alexa/token`
   - **Client ID**: Your configured ALFRED OAuth Client ID.
   - **Client Secret**: Your configured ALFRED OAuth Client Secret.
   - **Client Authentication Scheme**: `HTTP Basic (Recommended)`.
5. Note the Amazon **Redirect URLs** (e.g. `https://pitangui.amazon.com/api/moderator/z2/saveAuthCode`) and add them to ALFRED Developer Configuration in the **🎙 ALEXA** tab.

---

## 6. Testing & Beta Distribution

### Alexa Simulator Testing:
1. Go to the **Test** tab in the Alexa Developer Console.
2. Set test stage to **Development**.
3. Type or speak: *"ask alfred for status"* or *"tell alfred to start focus mode"*.

### Beta Testing / Real Echo Devices:
1. Under **Distribution** -> **Availability**, invite your Amazon account email to the skill beta.
2. Accept the invitation in your email on your phone.
3. Open the Alexa App -> **Skills & Games** -> **Your Skills** -> **Beta** to enable and link ALFRED.

---

## 7. Certification & Public Publishing Considerations
- **Privacy Policy**: A public custom skill requires a valid Privacy Policy URL and Terms of Service.
- **Proactive Events**: If you intend to announce alerts proactively on Echo devices without user invocation, apply for the Proactive Events permission under **Permissions** -> **Alexa Notifications**.
- During personal development and beta testing, certification is **not** required.
