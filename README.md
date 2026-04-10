# Autopilot 🚀

**Fully automated social media publishing system for Facebook & LinkedIn**

Built by Ahmad Aly Eldabaa with Claude - April 2026

---

## What is Autopilot?

Autopilot is a zero-cost, fully automated content scheduling and publishing system that posts to your social media accounts on schedule.

### Features

✅ **Web Interface** - Schedule posts from any device  
✅ **Multi-Platform** - Facebook (personal + pages) + LinkedIn (personal + company)  
✅ **Fully Automated** - GitHub Actions runs every hour (free tier)  
✅ **Zero Cost** - No subscriptions, no API fees, no servers  
✅ **Secure** - OAuth tokens encrypted in GitHub Secrets  
✅ **Simple** - Create content in Claude, paste, schedule, done  

---

## Quick Start

1. **Access the interface**: https://aalyeldabaa-web.github.io/autopilot/
2. **Schedule a post**: Paste content, select platforms, set time
3. **Let it run**: Autopilot publishes automatically

---

## Architecture

```
Claude Chat (Content Creation)
    ↓
Autopilot Web Interface (Scheduling)
    ↓
GitHub Repo (Storage: posts.json)
    ↓
GitHub Actions (Runs hourly)
    ↓
Social Media APIs (Publishing)
```

---

## Setup

See **[SETUP.md](docs/SETUP.md)** for complete step-by-step configuration guide.

**One-time setup (~45 minutes):**
1. Create GitHub repo
2. Configure Facebook & LinkedIn apps
3. Add OAuth tokens to GitHub Secrets
4. Deploy GitHub Pages

---

## Platforms Supported

| Platform | Account Type | Configuration |
|----------|-------------|---------------|
| Facebook | Personal Profile | ✅ Your timeline |
| Facebook | Ajax Business Solutions Page | ✅ Company page |
| LinkedIn | Personal Profile | ✅ ahmad-eldabaa |
| LinkedIn | Ajax Business Solutions Company | ✅ ajax-business-solutions |

---

## Usage

### From Claude Chat:
1. Create content using your skills (appm-content-factory, etc.)
2. Copy the generated post
3. Open Autopilot
4. Paste, schedule, done

### From Autopilot Interface:
- **Schedule Post**: + button
- **Edit Post**: Click any scheduled post
- **View Queue**: See all upcoming posts
- **Track Published**: Posts marked with ✓

---

## How It Works

1. **You schedule** posts via the web interface
2. **Posts save** to `posts.json` in GitHub repo
3. **GitHub Actions** runs every hour at :00
4. **Script checks** for posts scheduled in current hour
5. **API calls** post to selected platforms
6. **Database updates** to mark posts as published
7. **You get notified** via GitHub Actions logs

---

## Files Structure

```
autopilot/
├── .github/workflows/
│   └── publish.yml          # GitHub Actions workflow
├── public/
│   ├── index.html           # Web interface
│   └── app.js               # Frontend logic
├── scripts/
│   ├── publishers/
│   │   ├── facebook.js      # Facebook API integration
│   │   └── linkedin.js      # LinkedIn API integration
│   ├── package.json
│   └── publish.js           # Main publishing engine
├── docs/
│   └── SETUP.md             # Complete setup guide
├── posts.json               # Posts database
└── README.md
```

---

## Security

✅ **OAuth tokens** encrypted in GitHub Secrets  
✅ **No API keys** in code  
✅ **Private repo** option available  
✅ **HTTPS only** for web interface  

---

## Maintenance

**Monthly Tasks:**
- Regenerate Facebook access tokens (60-day expiration)
- Check GitHub Actions logs for any errors

**As Needed:**
- Update LinkedIn access token if expired
- Refresh GitHub Personal Access Token

---

## Troubleshooting

**Posts not publishing?**
- Check GitHub Actions logs (Actions tab)
- Verify tokens in Secrets are current
- Test tokens in Facebook/LinkedIn developer tools

**Can't schedule posts?**
- Verify GitHub Personal Access Token is valid
- Check browser console for errors
- Refresh the page

**Need help?**
- See [SETUP.md](docs/SETUP.md) for detailed guide
- Check GitHub Actions logs for specific errors
- Ask Claude with error messages

---

## Tech Stack

- **Frontend**: Vanilla JavaScript, no frameworks
- **Backend**: GitHub Actions (Node.js)
- **APIs**: Facebook Graph API v18.0, LinkedIn v2
- **Storage**: JSON file in GitHub repo
- **Hosting**: GitHub Pages (free)

---

## Cost Breakdown

| Service | Cost | Notes |
|---------|------|-------|
| GitHub Actions | $0 | 2000 min/month free (way more than needed) |
| GitHub Pages | $0 | Free hosting |
| Facebook API | $0 | Free tier |
| LinkedIn API | $0 | Free tier |
| **TOTAL** | **$0/month** | Zero cost! |

---

## Roadmap

Future enhancements:
- 📸 Image upload support
- 📊 Analytics dashboard
- 🔄 Content recycling
- 📱 Mobile app
- 🤖 AI content suggestions
- 📅 Calendar view

---

## Support

Built with ❤️ by Ahmad Aly Eldabaa

- 🌐 Website: https://ajaxsolutions.net
- 💼 LinkedIn: https://www.linkedin.com/in/ahmad-eldabaa
- 📧 Email: ahmad.eldabaa@ajaxsolutions.net

---

**Version 1.0 - April 2026**
**License: MIT**
