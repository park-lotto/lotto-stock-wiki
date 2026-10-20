// 라이선스 키·기기 지문(계약 §0, 설계 §7-2·§7-10).
//   키: env SHORTEM_LICENSE 또는 ~/.shortem/license (0600). 값은 어디에도 출력·기록하지 않는다(지문 12자만).
//   기기 지문 = sha256(machine id + "|" + os user). machine id 는 고정 명령(절대 경로)으로만 읽는다.
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { homeDir, writeFileIn } from './paths.js';
import { toolsDir } from './tools_paths.js';

// 설치 판 = 설치 폴더 app_version.json(빌드·자동 업데이트가 쓴다) — 없으면 코드 기본값(개발)
function appVersion() {
  try {
    const v = JSON.parse(fs.readFileSync(path.join(toolsDir(), '..', 'app_version.json'), 'utf8')).version;
    if (/^\d+\.\d+\.\d+$/.test(String(v))) return String(v);
  } catch { /* 개발 PC */ }
  return '1.0.0';
}
export const ENGINE_VERSION = appVersion();
const KEY_RE = /^SHORTEM-L1\.\d{1,12}\.\d{1,12}\.\d{1,6}\.[0-9a-f]{32}$/;

export const keyPrint = v => crypto.createHash('sha256').update(String(v)).digest('hex').slice(0, 12);

export function validKeyShape(k) { return KEY_RE.test(String(k || '').trim()); }

export function readLicense() {
  const env = String(process.env.SHORTEM_LICENSE || '').trim();
  if (env) return env;
  try { return fs.readFileSync(path.join(homeDir(), 'license'), 'utf8').trim(); } catch { return ''; }
}

export function saveLicense(key) {
  const k = String(key || '').trim();
  if (!validKeyShape(k)) { const e = new Error('라이선스 키 모양이 아닙니다'); e.code = 'bad_key'; throw e; }
  writeFileIn(homeDir(), 'license', k, 0o600);
  return keyPrint(k);
}

function machineId() {
  if (process.env.SHORTEM_MACHINE_ID) return process.env.SHORTEM_MACHINE_ID;   // 시험용(두 기기 흉내)
  try {
    if (process.platform === 'win32') {
      const reg = path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'reg.exe');
      const out = execFileSync(reg, ['query', 'HKLM\\SOFTWARE\\Microsoft\\Cryptography', '/v', 'MachineGuid'], { encoding: 'utf8', windowsHide: true, timeout: 10000 });
      const m = out.match(/MachineGuid\s+REG_SZ\s+([0-9a-fA-F-]{20,})/);
      if (m) return m[1].toLowerCase();
    } else if (process.platform === 'darwin') {
      const out = execFileSync('/usr/sbin/ioreg', ['-rd1', '-c', 'IOPlatformExpertDevice'], { encoding: 'utf8', timeout: 10000 });
      const m = out.match(/"IOPlatformUUID"\s*=\s*"([^"]+)"/);
      if (m) return m[1].toLowerCase();
    } else {
      for (const f of ['/etc/machine-id', '/var/lib/dbus/machine-id']) {
        try { const v = fs.readFileSync(f, 'utf8').trim(); if (v) return v; } catch { /* 다음 */ }
      }
    }
  } catch { /* 아래로 */ }
  return 'host:' + os.hostname();
}

let fp = null;
export function deviceFingerprint() {
  if (fp && !process.env.SHORTEM_MACHINE_ID) return fp;
  let user = '';
  try { user = os.userInfo().username; } catch { user = process.env.USERNAME || process.env.USER || ''; }
  if (process.env.SHORTEM_MACHINE_ID && process.env.SHORTEM_OS_USER) user = process.env.SHORTEM_OS_USER;   // 시험용(기기 지문 흉내) — 둘 다 줄 때만
  const v = crypto.createHash('sha256').update(machineId() + '|' + user).digest('hex');
  if (!process.env.SHORTEM_MACHINE_ID) fp = v;
  return v;
}

export function deviceName() {
  const n = (process.env.SHORTEM_DEVICE_NAME || os.hostname() || '내 PC').replace(/[\r\n\t]/g, ' ').trim();
  return n.slice(0, 40);
}
