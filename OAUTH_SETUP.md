# OAuth Setup Guide - Fix 403 Error

## Quick Fix Steps

### 1. Configure OAuth Consent Screen
Go to: https://console.cloud.google.com/apis/credentials/consent

**Required Settings:**
- **User Type**: External (or Internal if you have Google Workspace)
- **App Name**: YouTube Auto Uploader (or any name)
- **User Support Email**: Your email address
- **Developer Contact**: Your email address

### 2. Add Required Scopes
In the Scopes section, add:
- `https://www.googleapis.com/auth/youtube.upload`

### 3. Add Test Users (If App is in Testing Mode)
If your app is in "Testing" status:
- Go to "Test users" section
- Click "Add Users"
- Add your Google account email address
- Click "Add"

### 4. Publish App (Optional but Recommended)
For personal use, you can keep it in Testing mode with your email as a test user.
For production, click "Publish App" (may require verification).

## Common Issues

### Issue: "Access Denied" Error
**Solution**: Make sure:
1. Your email is added as a test user (if app is in Testing mode)
2. The scope `youtube.upload` is added to the consent screen
3. You're signing in with the correct Google account

### Issue: "App Not Verified" Warning
**Solution**: 
- For personal use: Click "Advanced" → "Go to [App Name] (unsafe)"
- This is safe for your own personal use

## After Configuration

1. Delete any existing OAuth token file:
   ```bash
   rm youtube-oauth2.json
   ```

2. Run the script again:
   ```bash
   python3 main.py --dry-run
   ```

3. When browser opens, sign in with the Google account that owns your "Content Thats Now" channel

4. Grant permissions when prompted

## Still Having Issues?

If you still get errors:
1. Make sure you're using the Google account that owns the YouTube channel
2. Check that YouTube Data API v3 is enabled in your project
3. Verify the OAuth consent screen is fully configured
4. Try deleting `youtube-oauth2.json` and re-authenticating

