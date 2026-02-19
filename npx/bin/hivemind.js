#!/usr/bin/env node
// hivemind-mcp: stdio-to-HTTP proxy for HiveMind MCP server via mcp-remote
//
// NOTE: Before publishing to npm, verify package name availability:
//   npm info hivemind-mcp
// If taken, consider a scoped package: @your-org/hivemind-mcp

'use strict';

const { spawn } = require('child_process');

// ---------------------------------------------------------------------------
// Argument and environment variable parsing
// ---------------------------------------------------------------------------

// HIVEMIND_URL: required — the base URL of the HiveMind server
// HIVEMIND_API_KEY: optional — API key for authenticated requests
const url = process.env.HIVEMIND_URL || process.argv[2];
const apiKey = process.env.HIVEMIND_API_KEY || process.argv[3];

// ---------------------------------------------------------------------------
// Usage validation
// ---------------------------------------------------------------------------

if (!url) {
  process.stderr.write(
    `Usage: npx hivemind-mcp <url> [api-key]\n\n` +
    `Or set environment variables:\n` +
    `  HIVEMIND_URL=https://your-hivemind-instance.com\n` +
    `  HIVEMIND_API_KEY=your-api-key\n\n` +
    `Then: npx hivemind-mcp\n`
  );
  process.exit(1);
}

// ---------------------------------------------------------------------------
// Build mcp-remote args
// ---------------------------------------------------------------------------

// mcp-remote proxies stdio <-> HTTP/SSE for MCP clients that only support stdio.
// We append /mcp to the base URL to reach the Streamable HTTP MCP endpoint.
const mcpArgs = ['mcp-remote', url.replace(/\/$/, '') + '/mcp'];

if (apiKey) {
  mcpArgs.push('--header', `X-API-Key:${apiKey}`);
}

// ---------------------------------------------------------------------------
// Spawn mcp-remote and forward stdio
// ---------------------------------------------------------------------------

const child = spawn('npx', ['-y', ...mcpArgs], {
  stdio: 'inherit',
  env: process.env,
});

// Forward exit code from mcp-remote to the parent process
child.on('exit', (code) => {
  process.exit(code ?? 0);
});

child.on('error', (err) => {
  process.stderr.write(`hivemind-mcp: failed to start mcp-remote: ${err.message}\n`);
  process.exit(1);
});

// ---------------------------------------------------------------------------
// Signal forwarding — clean shutdown on Ctrl+C or SIGTERM
// ---------------------------------------------------------------------------

function forwardSignal(signal) {
  if (child && !child.killed) {
    child.kill(signal);
  }
}

process.on('SIGINT', () => forwardSignal('SIGINT'));
process.on('SIGTERM', () => forwardSignal('SIGTERM'));
