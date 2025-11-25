<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Newsletter Integration Script</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
            background: linear-gradient(135deg, #1a1a3e 0%, #16213e 50%, #0f3460 100%);
            color: #fff;
        }
        .container {
            background: rgba(26, 26, 64, 0.95);
            border: 2px solid #00d4ff;
            border-radius: 15px;
            padding: 2rem;
        }
        h1 {
            color: #00d4ff;
            margin-bottom: 1rem;
        }
        .code-block {
            background: #1a1a40;
            border: 1px solid #444;
            border-radius: 8px;
            padding: 1.5rem;
            margin: 1rem 0;
            overflow-x: auto;
            position: relative;
        }
        .code-block pre {
            margin: 0;
            color: #b0b8c1;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            line-height: 1.6;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
        .copy-btn {
            position: absolute;
            top: 10px;
            right: 10px;
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s;
        }
        .copy-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4);
        }
        .instructions {
            background: rgba(16, 185, 129, 0.1);
            border: 2px solid #10b981;
            border-radius: 10px;
            padding: 1.5rem;
            margin: 1.5rem 0;
        }
        .step {
            margin: 1rem 0;
            padding-left: 2rem;
        }
        .step strong {
            color: #00d4ff;
        }
        .warning {
            background: rgba(245, 158, 11, 0.1);
            border: 2px solid #f59e0b;
            border-radius: 10px;
            padding: 1rem;
            margin: 1rem 0;
        }
        .success-msg {
            display: none;
            background: rgba(16, 185, 129, 0.2);
            border: 1px solid #10b981;
            padding: 1rem;
            border-radius: 6px;
            margin-top: 1rem;
            text-align: center;
            color: #10b981;
            font-weight: 600;
        }
        .success-msg.show {
            display: block;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📰 Newsletter Integration Script</h1>
        
        <div class="instructions">
            <h2>📋 Installation Instructions</h2>
            <div class="step">
                <strong>Step 1:</strong> Click "Copy Script" button below
            </div>
            <div class="step">
                <strong>Step 2:</strong> Create a new file named <code>newsletter-integration.js</code> in your <strong>frontend/</strong> folder
            </div>
            <div class="step">
                <strong>Step 3:</strong> Paste the complete script into that file
            </div>
            <div class="step">
                <strong>Step 4:</strong> Save the file
            </div>
            <div class="step">
                <strong>Step 5:</strong> Add this line to your index.html before <code>&lt;/body&gt;</code>:<br>
                <code>&lt;script src="./newsletter-integration.js"&gt;&lt;/script&gt;</code>
            </div>
        </div>

        <div class="warning">
            ⚠️ <strong>Important:</strong> Make sure your backend URL is correct. Currently set to:<br>
            <code>https://elite-trading-with-exclusive-ip.onrender.com</code>
        </div>

        <div class="code-block">
            <button class="copy-btn" onclick="copyScript()">📋 Copy Script</button>
            <pre id="scriptCode">/**
 * Elite Trading Newsletter Integration
 * Adds newsletter generation functionality to Market Brief page only
 * 
 * Usage: Add this script to your index.html before closing &lt;/body&gt; tag
 * Place newsletter button ONLY on the Market Brief page section
 */

(function() {
    'use strict';
    
    // Configuration
    const CONFIG = {
        BACKEND_URL: 'https://elite-trading-with-exclusive-ip.onrender.com', // Update this with your actual backend URL
        TIMEOUT: 120000, // 2 minutes
        POLL_INTERVAL: 500 // Check every 500ms
    };
    
    // Initialize newsletter functionality when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initNewsletterFeature);
    } else {
        initNewsletterFeature();
    }
    
    /**
     * Initialize newsletter button and handlers
     */
    function initNewsletterFeature() {
        console.log('📰 Initializing Newsletter Feature...');
        
        // Find newsletter button - ONLY on Market Brief section
        const generateBtn = document.getElementById('generateNewsletterBtn');
        
        if (!generateBtn) {
            console.log('⚠ Newsletter button not found. Skipping initialization.');
            return;
        }
        
        console.log('✅ Newsletter button found. Attaching handlers...');
        
        // Add event listeners
        generateBtn.addEventListener('click', handleGenerateNewsletter);
        
        // Check system status on load
        checkNewsletterStatus();
    }
    
    /**
     * Check newsletter system status
     */
    async function checkNewsletterStatus() {
        try {
            const response = await fetch(`${CONFIG.BACKEND_URL}/api/newsletter/status`, {
                method: 'GET',
                timeout: 5000
            });
            
            if (response.ok) {
                const data = await response.json();
                console.log('✅ Newsletter system status:', data);
                updateStatusIndicator(data.status);
            }
        } catch (error) {
            console.log('⚠ Could not check newsletter status:', error.message);
            updateStatusIndicator('offline');
        }
    }
    
    /**
     * Update status indicator UI
     */
    function updateStatusIndicator(status) {
        const statusDiv = document.getElementById('newsletterStatus');
        if (!statusDiv) return;
        
        statusDiv.className = 'status-message';
        statusDiv.style.display = 'block';
        
        if (status === 'operational') {
            statusDiv.innerHTML = '✅ Newsletter system is ready';
            statusDiv.classList.add('success');
        } else if (status === 'degraded') {
            statusDiv.innerHTML = '⚠ Newsletter system partially available';
            statusDiv.classList.add('warning');
        } else {
            statusDiv.innerHTML = '❌ Newsletter system offline';
            statusDiv.classList.add('error');
        }
    }
    
    /**
     * Handle newsletter generation request
     */
    async function handleGenerateNewsletter(event) {
        event.preventDefault();
        
        const btn = event.target;
        const statusDiv = document.getElementById('newsletterStatus');
        
        if (!btn || !statusDiv) {
            console.error('❌ Required elements not found');
            return;
        }
        
        // Disable button and show loading state
        btn.disabled = true;
        const originalText = btn.textContent;
        btn.textContent = '⏳ Generating...';
        btn.style.opacity = '0.7';
        
        // Show loading status
        statusDiv.style.display = 'block';
        statusDiv.className = 'status-message loading';
        statusDiv.innerHTML = '⏳ Generating newsletter with real-time data...';
        
        try {
            console.log('🚀 Generating newsletter...');
            
            // Call backend API
            const response = await fetch(`${CONFIG.BACKEND_URL}/api/newsletter/generate`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ format: 'markdown' })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            // Handle file download
            const blob = await response.blob();
            
            if (blob.size === 0) {
                throw new Error('Received empty response from server');
            }
            
            // Create download link
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `newsletter_${new Date().toISOString().split('T')[0]}.md`;
            
            // Trigger download
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            window.URL.revokeObjectURL(url);
            
            // Show success message
            statusDiv.className = 'status-message success';
            statusDiv.innerHTML = '✅ Newsletter downloaded successfully! Check your downloads folder.';
            
            console.log('✅ Newsletter generated and downloaded');
            
        } catch (error) {
            console.error('❌ Newsletter generation error:', error);
            
            // Show error message
            statusDiv.className = 'status-message error';
            statusDiv.style.display = 'block';
            
            if (error.message.includes('Failed to fetch')) {
                statusDiv.innerHTML = '❌ Cannot connect to server. Check your internet connection and verify backend URL.';
            } else if (error.message.includes('timeout') || error.message.includes('Timeout')) {
                statusDiv.innerHTML = '❌ Request timed out. Server took too long to respond. Try again.';
            } else if (error.message.includes('empty')) {
                statusDiv.innerHTML = '❌ Server returned no data. Try again or check backend logs.';
            } else {
                statusDiv.innerHTML = `❌ Error: ${error.message}`;
            }
        } finally {
            // Re-enable button
            btn.disabled = false;
            btn.textContent = originalText;
            btn.style.opacity = '1';
            
            // Clear status after 8 seconds
            setTimeout(() => {
                statusDiv.classList.remove('success', 'error', 'loading', 'warning');
            }, 8000);
        }
    }
    
    // Expose for manual testing in console
    window.newsletterAPI = {
        generateNewsletter: handleGenerateNewsletter,
        checkStatus: checkNewsletterStatus,
        config: CONFIG
    };
    
    console.log('📰 Newsletter feature initialized. Use window.newsletterAPI for manual control.');
})();</pre>
        </div>

        <div class="success-msg" id="successMsg">
            ✅ Script copied to clipboard! Now paste it into your newsletter-integration.js file.
        </div>
    </div>

    <script>
        function copyScript() {
            const scriptCode = document.getElementById('scriptCode').textContent;
            navigator.clipboard.writeText(scriptCode).then(() => {
                const successMsg = document.getElementById('successMsg');
                successMsg.classList.add('show');
                
                // Update button text
                const btn = event.target;
                const originalText = btn.textContent;
                btn.textContent = '✅ Copied!';
                btn.style.background = 'linear-gradient(135deg, #10b981 0%, #059669 100%)';
                
                setTimeout(() => {
                    btn.textContent = originalText;
                    btn.style.background = 'linear-gradient(135deg, #10b981 0%, #059669 100%)';
                    successMsg.classList.remove('show');
                }, 3000);
            }).catch(err => {
                alert('Failed to copy. Please manually select and copy the code.');
                console.error('Copy failed:', err);
            });
        }
    </script>
</body>
</html>
