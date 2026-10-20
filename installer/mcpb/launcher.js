#!/usr/bin/env node
// 숏템 연결기(launcher) — Claude Desktop(.mcpb)과 Claude Code(플러그인) 공용. 한 벌만 둔다.
// 하는 일: 설치팩이 깐 폴더에서 server/index.js 를 찾아 동봉 node 로 실행(stdio 그대로 연결).
// 설치 폴더가 없으면: "설치팩을 먼저 설치하세요" 도구 1개만 내는 최소 MCP 서버로 돈다.
// 규칙: 서버 응답·인자 문자열을 실행 파일 경로로 쓰지 않는다(경로는 아래 고정 규칙으로만 정한다).
'use strict';
const fs = require('fs');
const path = require('path');
const os = require('os');
const { spawn } = require('child_process');

const LAUNCHER_VERSION = '1.0.0';

function installHome() {
  // 1) 설치 프로그램이 등록한 환경변수(윈도: 사용자 환경변수, 맥: postinstall 이 남김)
  //    ★SHORTEM_HOME 은 서버 쪽 '사용자 자료 폴더(~/.shortem)' 이름이라 설치 폴더에는 SHORTEM_INSTALL 을 쓴다
  const fromEnv = process.env.SHORTEM_INSTALL;
  if (fromEnv && fs.existsSync(manifestPath(fromEnv))) return fromEnv;
  // 2) 기본 설치 경로(설계 §3-2 · §3-4)
  if (process.platform === 'win32') {
    const base = process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local');
    return path.join(base, 'Shortem');
  }
  if (process.platform === 'darwin') {
    return path.join(os.homedir(), 'Library', 'Application Support', 'Shortem');
  }
  return path.join(os.homedir(), '.local', 'share', 'Shortem');
}

function manifestPath(home) {
  return path.join(home, 'tools', 'tools.manifest.json');
}

function nodeExe(home) {
  return process.platform === 'win32'
    ? path.join(home, 'tools', 'node', 'node.exe')
    : path.join(home, 'tools', 'node', 'bin', 'node');
}

function readInstallInfo(home) {
  try { return JSON.parse(fs.readFileSync(path.join(home, 'install.json'), 'utf8')); } catch (_) { return null; }
}

function problem(home) {
  const server = path.join(home, 'server', 'index.js');
  const node = nodeExe(home);
  if (!fs.existsSync(manifestPath(home))) return 'not_installed';
  if (!fs.existsSync(server)) return 'server_missing';
  if (!fs.existsSync(node)) return 'node_missing';
  const info = readInstallInfo(home);
  if (process.platform === 'darwin' && info && info.arch && info.arch !== process.arch && info.arch === 'arm64') {
    // arm64 설치팩을 Intel 맥에 깐 경우(반대 방향 x64→Apple Silicon 은 Rosetta 로 돈다)
    if (os.cpus().every((c) => !/Apple/i.test(c.model))) return 'arch_mismatch';
  }
  return null;
}

const MESSAGES = {
  not_installed: '숏템 설치팩이 이 컴퓨터에 아직 없습니다. 숏템메이커 \'클로드형\' 페이지에서 설치팩(윈도 exe / 맥 pkg)을 내려받아 먼저 설치한 뒤, Claude 를 완전히 껐다 켜 주세요.',
  server_missing: '숏템 설치 폴더가 손상됐습니다(서버 파일 없음). 설치팩을 다시 실행해 주세요.',
  node_missing: '숏템 설치 폴더가 손상됐습니다(실행 도구 없음). 설치팩을 다시 실행해 주세요.',
  arch_mismatch: '이 맥(Intel)과 다른 종류(Apple Silicon용) 설치팩이 깔렸습니다. 페이지에서 \'맥 Intel(x64)\' 설치팩을 받아 다시 설치해 주세요.',
};

function runServer(home) {
  // 서버 계약(shortem_client/server/tools_paths.js): 실행 도구 폴더 = SHORTEM_TOOLS, 그 안 tools.manifest.json
  const env = Object.assign({}, process.env, {
    SHORTEM_INSTALL: home,
    SHORTEM_TOOLS: path.join(home, 'tools'),
    SHORTEM_LAUNCHER: LAUNCHER_VERSION,
  });
  const child = spawn(nodeExe(home), [path.join(home, 'server', 'index.js')], {
    stdio: 'inherit',
    env,
    windowsHide: true,
  });
  const forward = (sig) => { try { child.kill(sig); } catch (_) { /* 이미 끝남 */ } };
  process.on('SIGINT', () => forward('SIGINT'));
  process.on('SIGTERM', () => forward('SIGTERM'));
  child.on('error', (err) => {
    process.stderr.write(`[shortem-launcher] 서버 시작 실패: ${err.code || err.message}\n`);
    process.exit(1);
  });
  child.on('exit', (code, signal) => {
    if (signal) process.exit(1);
    process.exit(code == null ? 1 : code);
  });
}

// ── 설치 전용 최소 MCP(stdio, 줄 단위 JSON-RPC) ───────────────────────────
function runFallback(reason, home) {
  const msg = MESSAGES[reason] || MESSAGES.not_installed;
  const tool = {
    name: 'shortem_setup',
    title: '숏템 준비 점검',
    description: '숏템 준비 상태를 점검합니다. 지금은 설치팩이 없어 설치 안내만 돌려줍니다.',
    inputSchema: { type: 'object', properties: { selftest: { type: 'boolean' } }, additionalProperties: false },
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
  };
  const send = (obj) => process.stdout.write(JSON.stringify(obj) + '\n');
  const reply = (id, result) => send({ jsonrpc: '2.0', id, result });
  const error = (id, code, message) => send({ jsonrpc: '2.0', id, error: { code, message } });
  process.stderr.write(`[shortem-launcher] 설치팩 없음(${reason}) — 안내 전용으로 동작. 찾은 경로: ${home}\n`);

  let buf = '';
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', (chunk) => {
    buf += chunk;
    let nl;
    while ((nl = buf.indexOf('\n')) >= 0) {
      const line = buf.slice(0, nl).trim();
      buf = buf.slice(nl + 1);
      if (!line) continue;
      let req;
      try { req = JSON.parse(line); } catch (_) { error(null, -32700, 'Parse error'); continue; }
      const { id, method, params } = req;
      if (id === undefined || id === null) continue; // 알림은 답하지 않는다
      if (method === 'initialize') {
        reply(id, {
          protocolVersion: (params && params.protocolVersion) || '2025-06-18',
          capabilities: { tools: { listChanged: false } },
          serverInfo: { name: 'shortem', title: '숏템', version: LAUNCHER_VERSION },
          instructions: msg,
        });
      } else if (method === 'ping') {
        reply(id, {});
      } else if (method === 'tools/list') {
        reply(id, { tools: [tool] });
      } else if (method === 'tools/call') {
        const name = params && params.name;
        if (name !== 'shortem_setup') { error(id, -32602, `알 수 없는 도구: ${name}`); continue; }
        reply(id, {
          content: [{ type: 'text', text: msg }],
          structuredContent: { ok: false, fail: { where: '설치', why: msg, fix: '설치팩 설치 후 Claude 다시 시작', retry_ok: true } },
          isError: true,
        });
      } else if (method === 'resources/list') {
        reply(id, { resources: [] });
      } else if (method === 'prompts/list') {
        reply(id, { prompts: [] });
      } else {
        error(id, -32601, `Method not found: ${method}`);
      }
    }
  });
  process.stdin.on('end', () => process.exit(0));
}

function main() {
  const home = installHome();
  if (process.argv.includes('--where')) {
    process.stdout.write(JSON.stringify({ home, node: nodeExe(home), problem: problem(home) }) + '\n');
    return;
  }
  const p = problem(home);
  if (p) runFallback(p, home);
  else runServer(home);
}

main();
