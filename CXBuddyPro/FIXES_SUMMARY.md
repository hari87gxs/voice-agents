# CXBuddyPro Fixes - Nov 30, 2025

## Issues Fixed

### 1. Login Page Not Showing
**Problem**: Direct URL access showed the post-login Hari agent page instead of login

**Solution**:
- Created `landing.html` - a landing page with two options:
  - Talk to Riley (no login required)
  - Login & Talk to Hari (requires authentication)
- Updated server.py root route to serve landing.html instead of index.html
- Added explicit /index.html route for voice agent page

**User Flow Now**:
1. Visit https://cxbuddypro-708533464468.us-central1.run.app → Landing page
2. Click "Talk to Riley" → index.html (Riley - no auth)
3. Click "Login & Talk to Hari" → mock_gxs_app.html → Login → index.html?jwt=... (Hari - authenticated)

### 2. Handoff Call Disconnection
**Problem**: During agent handoff, the call would disconnect instead of smoothly transitioning

**Solution** in client.js `handleAgentHandoff()`:
- Removed hard-coded port numbers (8003, 8005) for cloud compatibility
- Fixed URL structure to use relative paths:
  - Riley → Hari (no JWT): redirects to `mock_gxs_app.html`
  - Riley → Hari (has JWT): redirects to `index.html?jwt=...&handoff=true`
  - Hari → Riley: redirects to `index.html?handoff=true` (clears JWT)
- Added proper cleanup sequence:
  1. Send goodbye message to server
  2. Stop audio playback
  3. Stop microphone
  4. Disconnect audio worklet
  5. Wait for hold tone to finish (2.5s)
  6. Close WebSocket
  7. Redirect to new page with handoff=true flag
- Auto-start call on handoff (when URL has `handoff=true` parameter)

**Handoff Flow Now**:
1. Riley says "Let me transfer you to Hari" → function call triggers
2. Browser plays hold tone
3. Clean disconnect of current session
4. Redirect to target agent page
5. New page auto-starts call (because of `handoff=true` in URL)
6. Smooth continuation of conversation

## Files Modified

1. `landing.html` - NEW: Landing page with Riley/Hari options
2. `server.py` - Updated root route to serve landing.html
3. `client.js` - Fixed handleAgentHandoff() function
4. `mock_gxs_app.html` - Already correctly redirects to index.html?jwt=...

## Testing Checklist

- [ ] Visit root URL → Should show landing page
- [ ] Click "Talk to Riley" → Should start Riley agent (no login)
- [ ] Click "Login & Talk to Hari" → Should show login page
- [ ] Login as John Doe → Should redirect to Hari agent with JWT
- [ ] Ask Riley to handoff to Hari → Should smoothly transition (with login if needed)
- [ ] Ask Hari to handoff to Riley → Should smoothly transition and clear JWT
- [ ] Refresh page after login → Should remember JWT and show Hari

## Deployment Commands

```bash
# Build and push Docker image
gcloud builds submit --tag gcr.io/vernac-479217/cxbuddypro --project vernac-479217 --quiet

# Deploy to Cloud Run
gcloud run deploy cxbuddypro \
  --image gcr.io/vernac-479217/cxbuddypro \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --set-env-vars GXS_API_BASE=https://gxs-mock-api-708533464468.us-central1.run.app \
  --project vernac-479217 \
  --quiet
```
