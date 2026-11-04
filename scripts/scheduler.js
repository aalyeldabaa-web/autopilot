'use strict';

// Pure scheduling/state helpers; no social/API calls and no clock dependence.
const MAX_LATE_MS = 2 * 60 * 60 * 1000;

function classifyPost(post, now = new Date(), maxLateMs = MAX_LATE_MS) {
  if (!post || post.published === true) return 'complete';
  if (!Array.isArray(post.platforms) || post.platforms.length === 0) return 'invalid';
  if (typeof post.scheduledTime !== 'string') return 'invalid';
  const timestamp = Date.parse(post.scheduledTime);
  const current = now.getTime();
  if (!Number.isFinite(timestamp) || !Number.isFinite(current)) return 'invalid';
  if (timestamp > current) return 'future'; // Never publish ahead of schedule.
  if (timestamp < current - maxLateMs) return 'stale'; // Never surprise-publish old queue.
  return 'due';
}

function successfulPlatforms(post) {
  return new Set(
    (Array.isArray(post?.publishResults) ? post.publishResults : [])
      .filter(x => x && x.success === true && typeof x.platform === 'string')
      .map(x => x.platform)
  );
}

function platformsRemaining(post) {
  const done = successfulPlatforms(post);
  return Array.isArray(post?.platforms) ? [...new Set(post.platforms)].filter(p => !done.has(p)) : [];
}

function recordResult(post, result) {
  if (!post || !result || typeof result.platform !== 'string') throw new Error('Invalid result');
  const previous = Array.isArray(post.publishResults) ? post.publishResults : [];
  // Successful external effects are sticky: never retry a previously confirmed platform.
  if (previous.some(p => p.platform === result.platform && p.success === true)) return post;
  post.publishResults = previous.filter(p => p.platform !== result.platform).concat(result);
  const uniquePlatforms = [...new Set(Array.isArray(post.platforms) ? post.platforms : [])];
  post.published = uniquePlatforms.length > 0 &&
    uniquePlatforms.every(p => successfulPlatforms(post).has(p));
  if (post.published && !post.publishedAt) post.publishedAt = new Date().toISOString();
  return post;
}

module.exports = { MAX_LATE_MS, classifyPost, successfulPlatforms, platformsRemaining, recordResult };
