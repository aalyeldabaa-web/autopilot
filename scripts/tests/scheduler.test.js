'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { classifyPost, platformsRemaining, recordResult, successfulPlatforms } = require('../scheduler');
const now = new Date('2026-11-04T20:00:00.000Z');
const sample = (scheduledTime, extra = {}) => ({
  id: 'p1', scheduledTime, platforms: ['linkedin_personal', 'facebook_page'], published: false, ...extra
});

test('never publishes before its scheduled timestamp', () => {
  assert.equal(classifyPost(sample('2026-11-04T20:01:00Z'), now), 'future');
});
test('publishes when overdue within a bounded 2h operational window', () => {
  assert.equal(classifyPost(sample('2026-11-04T19:30:00Z'), now), 'due');
});
test('ancient overdue items are held for manual review', () => {
  assert.equal(classifyPost(sample('2026-04-11T22:50:00Z'), now), 'stale');
});
test('invalid and already published posts do not publish', () => {
  assert.equal(classifyPost(sample('invalid'), now), 'invalid');
  assert.equal(classifyPost(sample('2026-11-04T19:00:00Z', { published: true }), now), 'complete');
  assert.equal(classifyPost(sample('2026-11-04T19:00:00Z', { platforms: [] }), now), 'invalid');
});
test('partial success is not a fully published post; failed platform is retryable', () => {
  const post = sample('2026-11-04T19:30:00Z');
  recordResult(post, { platform: 'linkedin_personal', success: true, id: 'remote-abc' });
  recordResult(post, { platform: 'facebook_page', success: false, error: 'API unavailable' });
  assert.equal(post.published, false);
  assert.deepEqual(platformsRemaining(post), ['facebook_page']);
  assert.equal(successfulPlatforms(post).has('linkedin_personal'), true);
});
test('successful platforms stay successful even on repeated result updates', () => {
  const post = sample('2026-11-04T19:30:00Z');
  recordResult(post, { platform: 'linkedin_personal', success: true, id: 'a' });
  recordResult(post, { platform: 'linkedin_personal', success: false, error: 'unexpected retry' });
  assert.deepEqual(platformsRemaining(post), ['facebook_page']);
  assert.equal(post.publishResults.find(p => p.platform === 'linkedin_personal').id, 'a');
});
test('publishes only after every requested platform succeeded', () => {
  const post = sample('2026-11-04T19:30:00Z');
  recordResult(post, { platform: 'linkedin_personal', success: true, id: 'a' });
  recordResult(post, { platform: 'facebook_page', success: true, id: 'b' });
  assert.equal(post.published, true);
  assert.ok(post.publishedAt);
  assert.deepEqual(platformsRemaining(post), []);
});
test('keeps unknown platforms pending instead of silently claiming success', () => {
  const post = sample('2026-11-04T19:30:00Z', { platforms: ['unknown_platform'] });
  assert.deepEqual(platformsRemaining(post), ['unknown_platform']);
  assert.equal(post.published, false);
});
