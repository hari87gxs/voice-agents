#!/bin/bash

# Fix 1: Update mock_gxs_app.html to use correct URL structure
# The Hari link should point to index.html with JWT parameter

sed -i '' 's|const hariUrl = `${window.location.protocol}//${window.location.hostname}?jwt=${encodeURIComponent(jwt)}`;|const hariUrl = `index.html?jwt=${encodeURIComponent(jwt)}`;|' mock_gxs_app.html

# Fix 2: Update client.js handoff logic to use correct URLs for cloud deployment
# When deployed on Cloud Run, both apps are on the same domain/service

# First, let's create a backup
cp client.js client.js.backup

# Update the handoff logic to work in both local and cloud environments
cat > client_handoff_fix.txt << 'HANDOFF_FIX'
    /**
     * Handle agent handoff
     * @param {string} targetAgent - 'hari' or 'riley'
     */
    async handleAgentHandoff(targetAgent) {
        this.log(`🔄 Switching to ${targetAgent}...`, 'info');
        this.updateStatus(`⏳ Transferring to ${targetAgent.toUpperCase()}... Please wait.`, false, false);
        
        // Play hold tone
        this.playHoldTone();

        // Clean up current connection (but don't end the session completely)
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.close();
        }
        
        // Stop audio playback
        this.stopAllAudio();
        
        // Stop microphone
        if (this.micStream) {
            this.micStream.getTracks().forEach(track => track.stop());
        }

        // Wait for hold tone to play
        await new Promise(resolve => setTimeout(resolve, 2000));

        let targetUrl;

        if (targetAgent === 'hari') {
            const hasJwt = sessionStorage.getItem('gxs_jwt');
            if (!hasJwt) {
                // No JWT - redirect to login page
                this.log('Hari requires authentication - redirecting to login', 'info');
                targetUrl = `mock_gxs_app.html`;
            } else {
                // Has JWT - go directly to authenticated Hari agent
                targetUrl = `index.html?jwt=${encodeURIComponent(hasJwt)}&handoff=true`;
            }
        } else {
            // Going to Riley - clear JWT and redirect to Riley's page
            sessionStorage.removeItem('gxs_jwt');
            sessionStorage.removeItem('gxs_user');
            this.jwtToken = null;
            // For now, just reload the current page (which should show Riley for non-authenticated)
            targetUrl = `index.html?handoff=true`;
        }

        this.log(`Redirecting to ${targetAgent}...`, 'info');
        window.location.href = targetUrl;
    }
HANDOFF_FIX

echo "✅ Fixes prepared"
