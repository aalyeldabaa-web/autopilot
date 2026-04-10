# Autopilot Setup Guide
## Social Media Automation System - Complete Configuration

This guide will walk you through setting up Autopilot to automatically post to your Facebook and LinkedIn accounts. **Estimated setup time: 45-60 minutes** (one-time configuration).

---

## 📋 What You're Building

**Autopilot** is a fully automated social media publishing system that:
1. **Web Interface** - Schedule posts from any device
2. **GitHub Actions** - Runs every hour automatically (free)
3. **API Integration** - Posts to Facebook & LinkedIn
4. **Zero Cost** - Uses GitHub's free tier

---

## PART 1: Create GitHub Repository (5 minutes)

### Step 1: Create New Repository

1. Go to https://github.com/new
2. **Repository name**: `autopilot`
3. **Description**: "Automated social media publishing system"
4. **Visibility**: Private (recommended) or Public
5. **Initialize**: ✅ Check "Add a README file"
6. Click **Create repository**

### Step 2: Upload Autopilot Files

1. Download all Autopilot files from Claude (they're in `/home/claude/autopilot/`)
2. On your computer, create this structure:
   ```
   autopilot/
   ├── .github/
   │   └── workflows/
   │       └── publish.yml
   ├── public/
   │   ├── index.html
   │   └── app.js
   ├── scripts/
   │   ├── publishers/
   │   │   ├── facebook.js
   │   │   └── linkedin.js
   │   ├── package.json
   │   └── publish.js
   ├── posts.json
   └── README.md
   ```

3. Go to your GitHub repo → **Add file** → **Upload files**
4. Drag all files/folders and commit

### Step 3: Enable GitHub Pages

1. Go to **Settings** → **Pages**
2. **Source**: Deploy from a branch
3. **Branch**: main
4. **Folder**: /public
5. Click **Save**
6. Wait 2 minutes, then visit: `https://aalyeldabaa-web.github.io/autopilot/`

✅ **Checkpoint**: You should see the Autopilot interface

---

## PART 2: Facebook Setup (15 minutes)

### Step 1: Create Facebook App

1. Go to https://developers.facebook.com/apps/create/
2. **App Type**: Business
3. **App Name**: "Autopilot Social Publisher"
4. **App Purpose**: Select "Yourself or your own business"
5. Click **Create App**

### Step 2: Configure App Settings

1. Go to **Settings** → **Basic**
2. **App Domains**: `github.io`
3. **Privacy Policy URL**: (use your Ajax website or create simple page)
4. **Category**: Business
5. Save changes

### Step 3: Add Products

1. From dashboard, click **Add Product**
2. Find **Facebook Login** → Click **Set Up**
3. Choose **Web**
4. **Site URL**: `https://aalyeldabaa-web.github.io/autopilot/`
5. Save

### Step 4: Get Facebook Page ID

1. Go to your Ajax Facebook Page: https://www.facebook.com/Ajax.Business.Solutions
2. Click **About** → Scroll to bottom
3. Find **Page ID** (it's a long number like 123456789012345)
4. **Save this number** - you'll need it

### Step 5: Get Access Tokens

**For Personal Profile:**
1. Go to https://developers.facebook.com/tools/explorer/
2. **User or Page**: Select "User Token"
3. **Permissions**: Add these permissions:
   - `pages_show_list`
   - `pages_read_engagement`
   - `pages_manage_posts`
   - `publish_to_groups` (if posting to personal timeline)
4. Click **Generate Access Token**
5. **Save this token** (starts with `EAAG...`)

**For Page:**
1. In Graph API Explorer, change to "Get Page Access Token"
2. Select your Ajax page
3. **Permissions**: 
   - `pages_manage_posts`
   - `pages_read_engagement`
4. Click **Generate Access Token**
5. **Save this token** (different from user token)

**Make Tokens Long-Lived:**
1. Go to https://developers.facebook.com/tools/accesstoken/
2. Click **Extend Access Token** for both tokens
3. **Save the new extended tokens** (last 60 days, can be renewed)

---

## PART 3: LinkedIn Setup (15 minutes)

### Step 1: Create LinkedIn App

1. Go to https://www.linkedin.com/developers/apps/new
2. **App name**: "Autopilot Publisher"
3. **LinkedIn Page**: Select "Ajax Business Solutions" page
4. **App logo**: Upload Ajax logo
5. **Privacy Policy**: Your Ajax website privacy page
6. Click **Create app**

### Step 2: Request API Access

1. Go to **Products** tab
2. Request access to:
   - **Share on LinkedIn**
   - **Sign In with LinkedIn**
3. Fill out the forms (usually approved instantly for pages you own)

### Step 3: Configure OAuth Settings

1. Go to **Auth** tab
2. **Redirect URLs**: Add:
   - `https://aalyeldabaa-web.github.io/autopilot/callback`
   - `https://localhost:3000/callback` (for testing)
3. Save

### Step 4: Get Client Credentials

1. Still in **Auth** tab
2. **Save these values:**
   - Client ID: `(long string)`
   - Client Secret: `(click Show, then copy)`

### Step 5: Get Person URN

1. Go to https://www.linkedin.com/developers/tools/oauth/token-generator
2. **Client ID**: Paste from previous step
3. **Client Secret**: Paste from previous step
4. **Scopes**: Select:
   - `r_liteprofile`
   - `r_emailaddress`
   - `w_member_social`
   - `w_organization_social`
5. Click **Request Access Token**
6. **Save the access token**
7. To get your Person URN, run this in browser console on LinkedIn:
   ```javascript
   fetch('https://api.linkedin.com/v2/me', {
     headers: { 'Authorization': 'Bearer YOUR_ACCESS_TOKEN' }
   }).then(r => r.json()).then(console.log)
   ```
8. Look for `"id": "urn:li:person:XXXXXXXXX"` - **save the full URN**

### Step 6: Get Organization URN

1. Run this:
   ```javascript
   fetch('https://api.linkedin.com/v2/organizationalEntityAcls?q=roleAssignee', {
     headers: { 'Authorization': 'Bearer YOUR_ACCESS_TOKEN' }
   }).then(r => r.json()).then(console.log)
   ```
2. Find your Ajax company page in the results
3. Copy the full organization URN: `urn:li:organization:XXXXXXX`

---

## PART 4: Configure GitHub Secrets (10 minutes)

### Add All Secrets

1. Go to your GitHub repo → **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret** for each:

| Secret Name | Value | Example |
|-------------|-------|---------|
| `FACEBOOK_PAGE_ACCESS_TOKEN` | Your page token | `EAAG...` |
| `FACEBOOK_USER_ACCESS_TOKEN` | Your personal token | `EAAG...` |
| `FACEBOOK_PAGE_ID` | Your page ID | `123456789012345` |
| `LINKEDIN_ACCESS_TOKEN` | LinkedIn OAuth token | `AQV...` |
| `LINKEDIN_PERSON_URN` | Your person URN | `urn:li:person:abc123` |
| `LINKEDIN_ORGANIZATION_URN` | Ajax company URN | `urn:li:organization:xyz789` |

✅ **Checkpoint**: You should have 6 secrets configured

---

## PART 5: Test the System (10 minutes)

### Test 1: Web Interface

1. Go to `https://aalyeldabaa-web.github.io/autopilot/`
2. Click **Setup GitHub Token** (first time only)
3. Generate a Personal Access Token:
   - Go to https://github.com/settings/tokens
   - **Generate new token (classic)**
   - **Scopes**: Select `repo` (full control)
   - **Expiration**: No expiration
   - Generate and copy
4. Paste into Autopilot
5. Click **+ Schedule Post**
6. Paste any test content
7. Select platforms
8. Set time to 5 minutes from now
9. Click **Schedule**

### Test 2: Manual Publish

1. Go to GitHub repo → **Actions** tab
2. Click **Autopilot - Social Media Publisher**
3. Click **Run workflow** → **Run workflow**
4. Wait 1-2 minutes
5. Check your Facebook/LinkedIn - post should appear!

### Test 3: Automatic Publish

1. Schedule a post for next hour
2. Wait for the hour to pass
3. GitHub Actions will run automatically
4. Check your social accounts

---

## 🚀 You're Live!

Your Autopilot system is now fully operational:

- ✅ Web interface accessible from anywhere
- ✅ Posts sync to GitHub automatically
- ✅ GitHub Actions runs every hour
- ✅ Auto-posts to Facebook & LinkedIn
- ✅ Zero ongoing costs

---

## Daily Usage

1. **Create content in Claude** (using your content skills)
2. **Open Autopilot**: https://aalyeldabaa-web.github.io/autopilot/
3. **Paste content** and schedule
4. **Forget it** - Autopilot handles the rest

---

## Troubleshooting

### "Post failed to publish"
- Check GitHub Actions logs for errors
- Verify access tokens are still valid
- Facebook/LinkedIn tokens expire - regenerate monthly

### "Can't save to GitHub"
- Check your Personal Access Token is still valid
- Go to https://github.com/settings/tokens and regenerate if needed

### "GitHub Actions not running"
- Check **.github/workflows/publish.yml** is in the right folder
- Verify Actions are enabled in repo settings

---

## Security Notes

✅ **What's Secure:**
- All tokens stored as GitHub Secrets (encrypted)
- Autopilot never exposes credentials
- Private repo keeps everything locked down

⚠️ **Best Practices:**
- Regenerate Facebook/LinkedIn tokens every 60 days
- Don't share your GitHub Personal Access Token
- Keep repo private if possible

---

## Need Help?

If something doesn't work:
1. Check GitHub Actions logs (detailed error messages)
2. Verify all 6 secrets are set correctly
3. Test tokens in Graph API Explorer / LinkedIn tools
4. Ask Claude for help - include error messages

---

**Built by Ahmad Aly Eldabaa with Claude**
**Version 1.0 - April 2026**
