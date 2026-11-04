#!/usr/bin/env node
'use strict';
const fs = require('fs').promises;
const path = require('path');
const { classifyPost, platformsRemaining, recordResult } = require('./scheduler');

// This script performs REAL social API calls. Never invoke it from tests.
const POSTS_FILE = path.join(__dirname, '..', 'posts.json');
const facebook = require('./publishers/facebook');
const linkedin = require('./publishers/linkedin');

const publishers = Object.freeze({
  facebook_personal: facebook.postToPersonalProfile,
  facebook_page: facebook.postToPage,
  linkedin_personal: linkedin.postToPersonalProfile,
  linkedin_company: linkedin.postToCompanyPage
});

async function writeState(posts) {
  // A temporary local file limits partial JSON corruption within a run.
  // GitHub push remains an independent action and is NOT an exactly-once guarantee.
  const temp = POSTS_FILE + '.tmp';
  await fs.writeFile(temp, JSON.stringify(posts, null, 2));
  await fs.rename(temp, POSTS_FILE);
}

async function main() {
  const now = new Date();
  console.log('Autopilot Publisher', now.toISOString());
  const posts = JSON.parse(await fs.readFile(POSTS_FILE, 'utf8'));
  if (!Array.isArray(posts)) throw new Error('posts.json must be an array');

  const due = [];
  const stale = [];
  const invalid = [];
  for (const post of posts) {
    const status = classifyPost(post, now);
    if (status === 'due') due.push(post);
    if (status === 'stale') stale.push(post.id);
    if (status === 'invalid') invalid.push(post.id);
  }
  if (stale.length) console.warn('HOLD: stale unsent posts need manual review:', stale);
  if (invalid.length) console.error('HOLD: invalid schedule/target:', invalid);
  console.log('Due posts:', due.length, 'stale:', stale.length, 'invalid:', invalid.length);

  for (const post of due) {
    console.log('Publishing eligible post ID', post.id);
    for (const platform of platformsRemaining(post)) {
      const publish = publishers[platform];
      if (!publish) {
        recordResult(post, { platform, success: false, error: 'UNSUPPORTED_PLATFORM' });
        console.error('Unknown publishing target:', platform);
        await writeState(posts);
        continue;
      }
      try {
        const result = await publish(post.content);
        if (!result || !result.id) throw new Error('Missing provider post ID; manual reconciliation required');
        recordResult(post, { platform, success: true, id: result.id });
        console.log('Confirmed platform:', platform, 'remote ID:', result.id);
      } catch (err) {
        recordResult(post, { platform, success: false, error: err?.message || String(err) });
        console.error('Failed:', platform, err?.message || err);
      }
      // Preserve partial successful platforms locally after every provider call;
      // the workflow must still commit state before a new run. Provider API
      // ambiguity/crash before push cannot guarantee exactly once.
      await writeState(posts);
    }
  }

  const incomplete = due.filter(post => !post.published).length;
  console.log('Finished; incomplete due posts:', incomplete, 'stale held:', stale.length);
  if (incomplete || invalid.length) process.exitCode = 1;
}

if (require.main === module) {
  main().catch(error => {
    console.error('Autopilot Publisher fatal:', error?.message || error);
    process.exitCode = 1;
  });
}

module.exports = { main };
