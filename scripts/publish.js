#!/usr/bin/env node

const fs = require('fs').promises;
const path = require('path');

// Configuration
const POSTS_FILE = path.join(__dirname, '..', 'posts.json');

// Platform Publishers
const facebook = require('./publishers/facebook');
const linkedin = require('./publishers/linkedin');

async function main() {
  try {
    console.log('🚀 Autopilot Publisher Started');
    console.log(`⏰ Current Time: ${new Date().toISOString()}`);
    
    // Load posts
    const postsData = await fs.readFile(POSTS_FILE, 'utf-8');
    const posts = JSON.parse(postsData);
    
    console.log(`📊 Total posts in database: ${posts.length}`);
    
    // Filter posts that need to be published
    const now = new Date();
    const oneHourFromNow = new Date(now.getTime() + 60 * 60 * 1000);
    
    const postsToPublish = posts.filter(post => {
      if (post.published) return false;
      
      const scheduledTime = new Date(post.scheduledTime);
      return scheduledTime <= oneHourFromNow && scheduledTime >= now;
    });
    
    console.log(`📝 Posts scheduled for this hour: ${postsToPublish.length}`);
    
    if (postsToPublish.length === 0) {
      console.log('✅ No posts to publish at this time');
      return;
    }
    
    // Publish each post
    for (const post of postsToPublish) {
      console.log(`\n📤 Publishing post ${post.id}...`);
      console.log(`   Scheduled: ${post.scheduledTime}`);
      console.log(`   Platforms: ${post.platforms.join(', ')}`);
      
      const results = [];
      
      for (const platform of post.platforms) {
        try {
          let result;
          
          switch (platform) {
            case 'facebook_personal':
              result = await facebook.postToPersonalProfile(post.content);
              break;
            
            case 'facebook_page':
              result = await facebook.postToPage(post.content);
              break;
            
            case 'linkedin_personal':
              result = await linkedin.postToPersonalProfile(post.content);
              break;
            
            case 'linkedin_company':
              result = await linkedin.postToCompanyPage(post.content);
              break;
            
            default:
              console.log(`   ⚠️  Unknown platform: ${platform}`);
              continue;
          }
          
          console.log(`   ✅ ${platform}: ${result.id || 'Success'}`);
          results.push({ platform, success: true, id: result.id });
          
        } catch (error) {
          console.error(`   ❌ ${platform}: ${error.message}`);
          results.push({ platform, success: false, error: error.message });
        }
      }
      
      // Mark as published if at least one platform succeeded
      const anySuccess = results.some(r => r.success);
      if (anySuccess) {
        post.published = true;
        post.publishedAt = new Date().toISOString();
        post.publishResults = results;
        console.log(`   🎉 Post marked as published`);
      } else {
        console.log(`   ⚠️  All platforms failed - will retry next hour`);
      }
    }
    
    // Save updated posts
    await fs.writeFile(POSTS_FILE, JSON.stringify(posts, null, 2));
    console.log('\n💾 Posts database updated');
    
    // Summary
    const publishedCount = postsToPublish.filter(p => p.published).length;
    console.log(`\n✨ Summary:`);
    console.log(`   Published: ${publishedCount}/${postsToPublish.length}`);
    console.log(`   Total in queue: ${posts.filter(p => !p.published).length}`);
    
  } catch (error) {
    console.error('💥 Fatal Error:', error);
    process.exit(1);
  }
}

// Run
main().then(() => {
  console.log('\n🏁 Autopilot Publisher Finished');
  process.exit(0);
}).catch(error => {
  console.error('💥 Unhandled Error:', error);
  process.exit(1);
});
