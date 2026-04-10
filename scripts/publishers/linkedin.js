const fetch = require('node-fetch');

const LINKEDIN_API_BASE = 'https://api.linkedin.com/v2';

/**
 * Post to Ahmad's personal LinkedIn profile
 */
async function postToPersonalProfile(content) {
  const accessToken = process.env.LINKEDIN_ACCESS_TOKEN;
  const personUrn = process.env.LINKEDIN_PERSON_URN;
  
  if (!accessToken) {
    throw new Error('LINKEDIN_ACCESS_TOKEN not configured');
  }
  
  if (!personUrn) {
    throw new Error('LINKEDIN_PERSON_URN not configured');
  }
  
  const url = `${LINKEDIN_API_BASE}/ugcPosts`;
  
  const postData = {
    author: personUrn,
    lifecycleState: 'PUBLISHED',
    specificContent: {
      'com.linkedin.ugc.ShareContent': {
        shareCommentary: {
          text: content
        },
        shareMediaCategory: 'NONE'
      }
    },
    visibility: {
      'com.linkedin.ugc.MemberNetworkVisibility': 'PUBLIC'
    }
  };
  
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
      'X-Restli-Protocol-Version': '2.0.0'
    },
    body: JSON.stringify(postData)
  });
  
  const data = await response.json();
  
  if (!response.ok) {
    throw new Error(`LinkedIn API Error: ${data.message || 'Unknown error'}`);
  }
  
  return { id: data.id };
}

/**
 * Post to Ajax LinkedIn Company Page
 */
async function postToCompanyPage(content) {
  const accessToken = process.env.LINKEDIN_ACCESS_TOKEN;
  const organizationUrn = process.env.LINKEDIN_ORGANIZATION_URN;
  
  if (!accessToken) {
    throw new Error('LINKEDIN_ACCESS_TOKEN not configured');
  }
  
  if (!organizationUrn) {
    throw new Error('LINKEDIN_ORGANIZATION_URN not configured');
  }
  
  const url = `${LINKEDIN_API_BASE}/ugcPosts`;
  
  const postData = {
    author: organizationUrn,
    lifecycleState: 'PUBLISHED',
    specificContent: {
      'com.linkedin.ugc.ShareContent': {
        shareCommentary: {
          text: content
        },
        shareMediaCategory: 'NONE'
      }
    },
    visibility: {
      'com.linkedin.ugc.MemberNetworkVisibility': 'PUBLIC'
    }
  };
  
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
      'X-Restli-Protocol-Version': '2.0.0'
    },
    body: JSON.stringify(postData)
  });
  
  const data = await response.json();
  
  if (!response.ok) {
    throw new Error(`LinkedIn API Error: ${data.message || 'Unknown error'}`);
  }
  
  return { id: data.id };
}

module.exports = {
  postToPersonalProfile,
  postToCompanyPage
};
