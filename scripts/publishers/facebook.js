const fetch = require('node-fetch');

const FACEBOOK_API_VERSION = 'v18.0';
const FACEBOOK_API_BASE = `https://graph.facebook.com/${FACEBOOK_API_VERSION}`;

// Ahmad's Facebook IDs (these will be configured via secrets)
const PERSONAL_USER_ID = 'me'; // Uses the token owner's ID
const PAGE_ID = process.env.FACEBOOK_PAGE_ID || ''; // Set in GitHub Secrets

/**
 * Post to Ahmad's personal Facebook profile
 */
async function postToPersonalProfile(content) {
  const accessToken = process.env.FACEBOOK_USER_ACCESS_TOKEN;
  
  if (!accessToken) {
    throw new Error('FACEBOOK_USER_ACCESS_TOKEN not configured');
  }
  
  const url = `${FACEBOOK_API_BASE}/${PERSONAL_USER_ID}/feed`;
  
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message: content,
      access_token: accessToken
    })
  });
  
  const data = await response.json();
  
  if (!response.ok) {
    throw new Error(`Facebook API Error: ${data.error?.message || 'Unknown error'}`);
  }
  
  return { id: data.id };
}

/**
 * Post to Ajax Facebook Page
 */
async function postToPage(content) {
  const accessToken = process.env.FACEBOOK_PAGE_ACCESS_TOKEN;
  
  if (!accessToken) {
    throw new Error('FACEBOOK_PAGE_ACCESS_TOKEN not configured');
  }
  
  if (!PAGE_ID) {
    throw new Error('FACEBOOK_PAGE_ID not configured');
  }
  
  const url = `${FACEBOOK_API_BASE}/${PAGE_ID}/feed`;
  
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message: content,
      access_token: accessToken
    })
  });
  
  const data = await response.json();
  
  if (!response.ok) {
    throw new Error(`Facebook API Error: ${data.error?.message || 'Unknown error'}`);
  }
  
  return { id: data.id };
}

module.exports = {
  postToPersonalProfile,
  postToPage
};
