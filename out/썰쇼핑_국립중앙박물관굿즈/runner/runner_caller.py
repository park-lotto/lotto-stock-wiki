"""작업 폴더 밖의 공용 runner/ 에서 떠 있는 옛 실행기를 찾는다 — 자동 설치(FP1)가 그 폴더도 함께 바꿔도 되는지 (2026-10-05 · Z ②).

■ 왜 — 한 공용 runner 로 여러 작업 폴더를 돌리는 사람은 새 작업을 시작할 때마다 «새 실행기는 <wd>/runner 에 있습니다. 그런데 이
  요청을 보낸 실행기 프로세스는 다른 코드입니다» 로 멈췄다(10-05 24시간 38건·15명 · 사람마다 건수 = 작업 폴더 수). 설치는 작업
  폴더에만 했고 공용 폴더는 영영 옛 판이라 다음 작업도 같은 자리에서 멈춘다.
■ 누가 부르나 — 서버가 내려보내는 설치기(`volcano_runner_migration` 의 INSTALL_SCRIPT)가 **새 팩**에서 이 모듈을 읽어 부른다.
  설치기 글자에 넣지 않은 이유: 직접 MCP 응답(글자+구조 두 벌)이 25,000 토큰 벽 아래여야 한다(검사 50,000자).
■ 바꿔도 되는 때(하나라도 아니면 (None, 사람이 읽을 이유)):
  · 설치기를 띄운 옛 실행기 프로세스 명령줄에 절대경로 volcano_drive.py — 그 폴더가 작업 폴더 runner/ 와 다르다.
    진행 기록 모드(--background)·실행 일꾼처럼 실행기가 스스로 띄운 `python -c` 일꾼은 그 코드가 volcano_drive 를 읽는 폴더(_bootstrap_folder).
    옛 실행기는 부모이거나, 사이에 런처(윈도우 py -3 · venv Scripts\\python.exe 리디렉터 · POSIX exec 없는 셸 래퍼)가 낀
    조상이다(깊이 LAUNCHER_DEPTH 까지 · 런처가 아닌 프로세스가 끼면 거슬러 오르지 않는다).
  · 링크·정션이 아닌 보통 폴더(연결이면 공용 원본이다 — 바꾸지 않는다는 기존 원칙)
  · 그 폴더의 식별값 = 요청을 보낸 실행기(헛짚지 않았다)
  · 편집 엔진 다섯 파일이 새 팩과 바이트까지 같다(그 폴더로 도는 고정 편집 작업의 엔진이 안 바뀐다)
  · 그 폴더 경로가 명령줄에 든 다른 프로세스가 없다(조상 프로세스 — py 런처·셸 — 는 뺀다). 돌고 있는 다른 작업은 이미 올린
    모듈과 나중에 읽을 새 모듈이 섞일 수 있다. 명령줄의 volcano_drive.py 는 실경로(링크·정션·별칭을 푼 것)로 견주고, 상대경로면
    그 프로세스의 현재 폴더로 푼다(리눅스 /proc · 맥 lsof · 윈도우 PEB) — 현재 폴더를 못 읽으면(권한 · 비트 수가 다른 프로세스)
    쓰는 것으로 보고 바꾸지 않는다.
■ 프로세스 표: 윈도우 = Toolhelp 스냅샷(부모) + NtQueryInformationProcess(ProcessCommandLineInformation=60, 8.1+) +
  CommandLineToArgvW · 리눅스 = /proc · 맥 = ps(pid·ppid) + sysctl KERN_PROCARGS2(argv). 못 읽으면 None(바꾸지 않는다).
■ 윈도우 현재 폴더 (2026-10-06 win-01 실기) — 예전에는 윈도우에서 다른 프로세스의 현재 폴더를 «모름» 으로 두었다. 그러면
  상대경로 실행기(작업 폴더에서 `python runner/volcano_drive.py …` — 클로드 코드가 흔히 띄우는 모양)가 이 PC 어디서든 하나라도
  돌면 그 폴더와 무관해도 «확인하지 못했습니다» 로 공용 폴더를 영영 못 바꿨다. 실측: win-01 에서 다른 세션의 진짜 실행기
  (venv 리디렉터 + `runner/volcano_drive.py` · 제 작업 폴더가 현재 폴더)가 떠 있는 동안 test_runner_shared_caller 13개 중 5개가
  모두 그 한 프로세스 때문에 멈췄다. 지금은 psutil 과 같은 길로 읽는다 — NtQueryInformationProcess(ProcessBasicInformation) 의
  PEB → ProcessParameters → CurrentDirectory.DosPath(ReadProcessMemory). 비트 수가 다른 짝(32비트 파이썬 ↔ 64비트 프로세스 ·
  WOW64)은 구조 배치가 달라 읽지 않는다(모름 → 쓰는 것으로 본다).
■ 남는 위험 — 이 판정이 **못 보는** 두 가지 (2026-10-06 · Z 검토 3회차 minor · 오케스트레이터 결정: 이번 판은 코드로 막지 않고 적는다)
  ① 명령줄에 그 폴더 경로가 없는 프로세스. «다른 프로세스» 판정(`_uses_folder`)은 명령줄만 본다 — 그 폴더의 절대경로(또는 실경로)
     글자, 또는 volcano_drive.py 인자(상대경로면 그 프로세스의 현재 폴더로 푼다). `runner_note` 가 직접 가르치는 방식(작업 폴더를
     현재 폴더로 두고 `sys.path.insert(0, 'runner')` 뒤 `import volcano_run`)으로 그 폴더의 모듈을 쓰는 파이썬은 둘 다 없어
     «안 쓴다» 로 판정된다. 검토 실험 r8/exp_shared_relimport.py: 그런 프로세스가 살아 있는 동안 자동 설치가 공용 폴더를 새 판으로
     바꿨다(식별값 b24a5c9c25a9→a55e1646aa1a). 열린 파일 목록으로도 안 보인다 — 맥 실측(10-06): 그 프로세스가 살아 있을 때
     `lsof +D <그 폴더>` 0건(파이썬은 import 한 소스 파일을 열어 두지 않고, 현재 폴더는 그 폴더의 부모다).
  ② 확인과 교체 사이(TOCTOU). 프로세스 표는 판정할 때 한 번 읽는다 — 그 뒤 설치기가 파일을 바꾸는 동안(파일 단위 교체) 그 폴더로
     새로 뜨는 프로세스는 못 본다.
  영향: 그런 프로세스는 이미 읽은 모듈은 옛 판 그대로 쓰고, 교체 뒤에 처음 읽는 모듈은 새 판에서 읽는다 — 한 프로세스 안에서 판이
     섞일 수 있다(②는 그 틈에 뜬 짧은 일회성 프로세스가 반쯤 바뀐 폴더를 읽는 경우). 섞인 뒤 오류로 멈추는지 조용히 다른 결과를
     내는지는 재지 않았다(실측 없음 · 대기 보고 쪽의 같은 위험은 서버 `volcano_receipt_wait.feedback_meta` 머리말).
  막으려면 필요한 것(이번 판은 안 한다):
     · 잠금 — 실행기가 그 폴더에 공유 잠금을 쥐고 설치기가 배타 잠금을 시도하는 방식은 그 잠금을 아는 판끼리만 지킨다. 지금 나가
       있는 옛 판 실행기·사용자 스크립트는 잠금을 잡지 않으므로 잠금만으로는 ①②를 못 막는다.
     · 현재 폴더 확인 — «그 폴더나 그 부모를 현재 폴더로 둔 파이썬» 까지 쓰는 것으로 보면 ①의 모양은 걸린다. 현재 폴더는 이 모듈
       `process_cwd` 가 이미 읽는다(리눅스 /proc/<pid>/cwd · 맥 lsof -d cwd · 윈도우 PEB — 10-06 부터, 권한·비트 수가 다르면 «모름»).
       다만 그 부모를 현재 폴더로 둔 무관한 파이썬도 «쓰는 것» 이 되어 함께 설치가 줄어든다(공용 멈춤이 남는다).
     · ②는 확인을 아무리 넓혀도 닫히지 않는다 — 교체 동안 새 프로세스가 못 뜨게 하는 장치(위 잠금)가 있어야 하고, 그것도 옛 판은
       안 지킨다.
"""
import ast
import ntpath
import os
import subprocess
import sys
from pathlib import Path


def process_table():
    # 이 PC 의 {pid: (ppid, argv)} — 못 읽으면 None. 호출한 실행기가 사는 공용 폴더를 함께 바꿔도 되는지 볼 때만 쓴다(Z ②).
    table={}
    try:
        import ctypes
        if os.name=='nt':
            from ctypes import wintypes
            k32=ctypes.WinDLL('kernel32',use_last_error=True)
            ntdll=ctypes.WinDLL('ntdll')
            shell=ctypes.WinDLL('shell32')
            class ENTRY(ctypes.Structure):
                _fields_=[('dwSize',wintypes.DWORD),('cntUsage',wintypes.DWORD),('th32ProcessID',wintypes.DWORD),
                          ('th32DefaultHeapID',ctypes.c_void_p),('th32ModuleID',wintypes.DWORD),('cntThreads',wintypes.DWORD),
                          ('th32ParentProcessID',wintypes.DWORD),('pcPriClassBase',ctypes.c_long),('dwFlags',wintypes.DWORD),
                          ('szExeFile',ctypes.c_wchar*260)]
            class TEXT(ctypes.Structure):
                _fields_=[('Length',ctypes.c_ushort),('MaximumLength',ctypes.c_ushort),('Buffer',ctypes.c_void_p)]
            k32.CreateToolhelp32Snapshot.restype=ctypes.c_void_p
            k32.CreateToolhelp32Snapshot.argtypes=(wintypes.DWORD,wintypes.DWORD)
            k32.Process32FirstW.argtypes=k32.Process32NextW.argtypes=(ctypes.c_void_p,ctypes.POINTER(ENTRY))
            k32.OpenProcess.restype=ctypes.c_void_p
            k32.OpenProcess.argtypes=(wintypes.DWORD,wintypes.BOOL,wintypes.DWORD)
            k32.CloseHandle.argtypes=(ctypes.c_void_p,)
            k32.LocalFree.argtypes=(ctypes.c_void_p,)
            ntdll.NtQueryInformationProcess.restype=ctypes.c_long
            ntdll.NtQueryInformationProcess.argtypes=(ctypes.c_void_p,ctypes.c_ulong,ctypes.c_void_p,ctypes.c_ulong,ctypes.POINTER(ctypes.c_ulong))
            shell.CommandLineToArgvW.restype=ctypes.POINTER(ctypes.c_wchar_p)
            shell.CommandLineToArgvW.argtypes=(ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_int))
            snap=k32.CreateToolhelp32Snapshot(2,0)
            if not snap or snap==ctypes.c_void_p(-1).value:
                return None
            try:
                entry=ENTRY()
                entry.dwSize=ctypes.sizeof(ENTRY)
                more=k32.Process32FirstW(snap,ctypes.byref(entry))
                while more:
                    table[int(entry.th32ProcessID)]=(int(entry.th32ParentProcessID),None)
                    more=k32.Process32NextW(snap,ctypes.byref(entry))
            finally:
                k32.CloseHandle(snap)
            for pid in list(table):
                handle=k32.OpenProcess(0x1000,False,pid)
                if not handle:
                    continue
                try:
                    size=ctypes.c_ulong(0)
                    ntdll.NtQueryInformationProcess(handle,60,None,0,ctypes.byref(size))
                    if not size.value:
                        continue
                    buffer=ctypes.create_string_buffer(size.value)
                    if ntdll.NtQueryInformationProcess(handle,60,buffer,size,ctypes.byref(size))!=0:
                        continue
                    text=TEXT.from_buffer(buffer)
                    line=ctypes.wstring_at(text.Buffer,text.Length//2) if text.Buffer and text.Length else ''
                finally:
                    k32.CloseHandle(handle)
                if not line:
                    continue
                count=ctypes.c_int(0)
                parts=shell.CommandLineToArgvW(line,ctypes.byref(count))
                if parts:
                    try:
                        table[pid]=(table[pid][0],[parts[i] for i in range(count.value)])
                    finally:
                        k32.LocalFree(parts)
            return table
        if os.path.isdir('/proc/self'):
            for name in os.listdir('/proc'):
                if not name.isdigit():
                    continue
                try:
                    with open('/proc/'+name+'/stat','rb') as handle:
                        ppid=int(handle.read().rsplit(b')',1)[1].split()[1])
                    with open('/proc/'+name+'/cmdline','rb') as handle:
                        argv=[os.fsdecode(part) for part in handle.read().split(b'\0') if part]
                except (OSError,ValueError,IndexError):
                    continue
                table[int(name)]=(ppid,argv or None)
            return table
        listed=subprocess.run(['ps','-axo','pid=,ppid='],capture_output=True,timeout=20)
        if listed.returncode:
            return None
        libc=ctypes.CDLL(None)
        for row in listed.stdout.decode('ascii','replace').splitlines():
            fields=row.split()
            if len(fields)!=2:
                continue
            pid,ppid=int(fields[0]),int(fields[1])
            mib=(ctypes.c_int*3)(1,49,pid)
            size=ctypes.c_size_t(0)
            argv=None
            if libc.sysctl(mib,3,None,ctypes.byref(size),None,0)==0 and size.value>4:
                buffer=ctypes.create_string_buffer(size.value)
                if libc.sysctl(mib,3,buffer,ctypes.byref(size),None,0)==0:
                    raw=buffer.raw[:size.value]
                    count=int.from_bytes(raw[:4],sys.byteorder)
                    rest=raw[4:]
                    rest=rest[rest.find(b'\0'):].lstrip(b'\0')
                    argv=[os.fsdecode(part) for part in rest.split(b'\0')[:count]]
            table[pid]=(ppid,argv)
        return table
    except (OSError,ValueError,AttributeError,TypeError,ImportError,subprocess.SubprocessError):
        # SubprocessError: ps 가 20초를 넘기면(TimeoutExpired) 설치기가 트레이스백으로 죽지 않고 «못 읽음» 으로 간다(Z 검토 minor).
        return None

def _win_cwd(pid):
    # 윈도우: 그 프로세스의 PEB → RTL_USER_PROCESS_PARAMETERS.CurrentDirectory.DosPath (psutil 과 같은 길 · 10-06 win-01 실기).
    # 배치(포인터 크기 P): PROCESS_BASIC_INFORMATION 둘째 칸 = PEB · PEB+4P = ProcessParameters · 그 +16+5P = CurrentDirectory
    # (UNICODE_STRING: Length 2바이트 · 버퍼 주소는 +P). 비트 수가 다른 짝(WOW64)은 배치가 달라 읽지 않는다 → None(모름).
    import ctypes
    from ctypes import wintypes
    k32=ctypes.WinDLL('kernel32',use_last_error=True)
    ntdll=ctypes.WinDLL('ntdll')
    k32.OpenProcess.restype=ctypes.c_void_p
    k32.OpenProcess.argtypes=(wintypes.DWORD,wintypes.BOOL,wintypes.DWORD)
    k32.CloseHandle.argtypes=(ctypes.c_void_p,)
    k32.GetCurrentProcess.restype=ctypes.c_void_p
    k32.IsWow64Process.argtypes=(ctypes.c_void_p,ctypes.POINTER(wintypes.BOOL))
    k32.ReadProcessMemory.argtypes=(ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.POINTER(ctypes.c_size_t))
    ntdll.NtQueryInformationProcess.restype=ctypes.c_long
    ntdll.NtQueryInformationProcess.argtypes=(ctypes.c_void_p,ctypes.c_ulong,ctypes.c_void_p,ctypes.c_ulong,ctypes.POINTER(ctypes.c_ulong))
    # PROCESS_QUERY_INFORMATION | PROCESS_VM_READ — 같은 사용자·같은 권한 수준의 프로세스면 열린다(관리자 프로세스 등은 못 연다 → 모름).
    handle=k32.OpenProcess(0x0410,False,int(pid))
    if not handle:
        return None
    try:
        mine,theirs=wintypes.BOOL(),wintypes.BOOL()
        if (not k32.IsWow64Process(k32.GetCurrentProcess(),ctypes.byref(mine)) or not k32.IsWow64Process(handle,ctypes.byref(theirs))
                or bool(mine.value)!=bool(theirs.value)):
            return None
        size=ctypes.sizeof(ctypes.c_void_p)
        basic=(ctypes.c_void_p*6)()
        if ntdll.NtQueryInformationProcess(handle,0,basic,ctypes.sizeof(basic),ctypes.byref(ctypes.c_ulong(0)))!=0 or not basic[1]:
            return None

        def read(address,length):
            buffer=ctypes.create_string_buffer(length)
            done=ctypes.c_size_t(0)
            if not k32.ReadProcessMemory(handle,address,buffer,length,ctypes.byref(done)) or done.value!=length:
                return None
            return buffer.raw[:length]
        params=read(basic[1]+4*size,size)
        params=int.from_bytes(params,sys.byteorder) if params else 0
        text=read(params+16+5*size,2*size) if params else None
        if not text:
            return None
        length,address=int.from_bytes(text[:2],sys.byteorder),int.from_bytes(text[size:2*size],sys.byteorder)
        body=read(address,length) if address and length and not length%2 else None
        if not body:
            return None
        path=body.decode('utf-16-le')
        # 긴 경로 접두(\\?\ · \\?\UNC\)는 걷어 일반 경로로 — 명령줄 인자(/ 섞임)와 이어 붙여 실경로를 풀 수 있게.
        if path.startswith('\\\\?\\UNC\\'):
            path='\\\\'+path[8:]
        elif path.startswith('\\\\?\\'):
            path=path[4:]
        return path
    finally:
        k32.CloseHandle(handle)

def process_cwd(pid):
    # 그 프로세스의 현재 폴더 — 못 읽으면 None(모름 = 그 폴더를 쓰는 것으로 본다). 윈도우는 PEB(_win_cwd · 10-06).
    try:
        if os.name=='nt':
            import ctypes
            try:
                return _win_cwd(pid)
            except (OSError,ValueError,AttributeError,TypeError,ctypes.ArgumentError):
                return None
        if os.path.isdir('/proc/self'):
            return os.readlink('/proc/'+str(int(pid))+'/cwd')
        if sys.platform=='darwin':
            out=subprocess.run(['lsof','-a','-p',str(int(pid)),'-d','cwd','-Fn'],capture_output=True,timeout=10)
            for line in out.stdout.decode('utf-8','surrogateescape').splitlines():
                if line.startswith('n/'):
                    return line[1:]
    except (OSError,ValueError,ImportError,subprocess.SubprocessError):
        return None
    return None

def _uses_folder(pid,args,marks,real):
    # 그 프로세스가 이 폴더의 실행기를 쓰는가 — True · 모르면 None · 아니면 False (Z 검토 minor: 상대경로·별칭 경로).
    if any(mark in os.path.normcase(' '.join(args)) for mark in marks):
        return True
    unknown=False
    for part in _drive_paths(args):
        if os.path.isabs(part):
            path=part
        else:
            cwd=process_cwd(pid)
            if not cwd:
                unknown=True
                continue
            path=os.path.join(cwd,part)
        # 링크·정션·대소문자 별칭도 같은 폴더로 본다.
        if os.path.normcase(os.path.realpath(os.path.dirname(path)))==real:
            return True
    return None if unknown else False

_PY_OPTION_VALUE=frozenset(('-W','-X','--check-hash-based-pycs'))   # 값을 다음 인자로 받는 파이썬 옵션(CPython Python/initconfig.c)

def _bootstrap_folder(argv):
    # 실행기가 스스로 띄운 `python [옵션…] -c <코드> [인자…]` 의 실행기 폴더 — 아니면 None (2026-10-19 #210 A · win-01 실측).
    # 진행 기록 모드(--background · volcano_drive._logged_bootstrap)의 일꾼은 `sys.path.insert(0,'<실행기 폴더>');import volcano_drive
    # as D;D._logged_child([…])` 를 떼어 띄우고 띄운 프로세스는 바로 끝난다 — 명령줄에 volcano_drive.py 가 따로 없고 부모도 표에
    # 없어 판정이 늘 «찾지 못했습니다» 였다(win-01: 실제 _logged_bootstrap 글로 띄운 일꾼 아래 설치기 → 사슬 py · python -u -c · 표에
    # 없음). 실행 일꾼(_execution_worker)은 `sys.path.insert(0,sys.argv[1])` + 폴더 인자다. 코드는 실행하지 않고 구문만 읽는다(ast) —
    # 윈도우 경로는 코드 안에서 repr 로 역슬래시가 겹쳐 있어 글자 비교로는 그 폴더와 맞지 않는다.
    k=1
    while k<len(argv) and argv[k]!='-c':
        if argv[k] in _PY_OPTION_VALUE:
            k+=2
        elif argv[k].startswith('-') and argv[k]!='-':
            k+=1
        else:
            return None   # 스크립트·`-`(표준 입력) — -c 일꾼이 아니다
    if k+1>=len(argv):
        return None
    try:
        tree=ast.parse(argv[k+1])
    except (SyntaxError,ValueError):
        return None
    folder,imports=None,False
    for node in ast.walk(tree):
        if isinstance(node,ast.Import) and any(alias.name=='volcano_drive' for alias in node.names):
            imports=True
        elif (isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='insert'
              and ast.unparse(node.func.value)=='sys.path' and len(node.args)==2):
            where=node.args[1]
            if isinstance(where,ast.Constant) and isinstance(where.value,str):
                folder=where.value
            elif ast.unparse(where)=='sys.argv[1]' and k+2<len(argv):
                folder=argv[k+2]
    return folder if imports and folder else None

def _drive_paths(argv):
    # 그 명령줄이 돌리는 volcano_drive.py — 인자로 준 것(`python …/volcano_drive.py`) + 실행기가 스스로 띄운 -c 일꾼의 폴더.
    # 설치기를 띄운 실행기 찾기(_driver_script)와 «그 폴더를 쓰는 다른 프로세스» 판정(_uses_folder)이 같은 자로 본다 —
    # 한쪽만 알아보면 여러 작업을 한 공용 폴더의 진행 기록 일꾼으로 돌리는 사람의 다른 작업이 «안 쓴다» 로 보여 돌던 중에 바뀐다.
    paths=[part for part in argv[1:] if os.path.basename(part.replace('\\','/')).lower()=='volcano_drive.py']
    folder=_bootstrap_folder(argv)
    if folder:
        paths.append(os.path.join(folder,'volcano_drive.py'))
    return paths

LAUNCHER_DEPTH=4
_SHELLS=frozenset(('sh','bash','zsh','dash','ksh'))

def _launcher(argv):
    # 실행기와 설치기 사이에 낄 수 있는 «띄우기만 하는» 프로세스인가 — 윈도우 py 런처(py -3) · venv 의 Scripts\python.exe
    # 리디렉터(CPython PC/venvlauncher.c: CreateProcessW 로 진짜 python.exe 를 띄우고 WaitForSingleObjectEx 로 기다린다) ·
    # POSIX 의 exec 없는 셸 래퍼. 이름만 본다(py* · 셸) — 그 밖의 프로세스면 거슬러 올라가지 않는다.
    if not argv:
        return False
    name=os.path.basename(argv[0].replace('\\','/')).lower()
    if name.endswith('.exe'):
        name=name[:-4]
    return name.startswith('py') or name in _SHELLS

def _driver_script(table,pid):
    # 설치기의 부모부터 거슬러 올라가 volcano_drive.py 를 돌리는 가장 가까운 조상의 그 경로 — (경로, None) · 못 찾으면 (None, None) ·
    # 사이에 런처가 아닌 프로세스가 끼었거나 명령줄을 못 읽으면 (None, 이유) (Z 검토 2회차 major ①: 윈도우 21명 중 대부분이
    # py 런처·venv 리디렉터 아래에서 설치기를 띄워 직계 부모만 보던 판정이 늘 «찾지 못했습니다» 였다).
    seen=set()
    for _depth in range(LAUNCHER_DEPTH):
        if pid in seen or pid not in table:
            return None,None
        seen.add(pid)
        ppid,argv=table[pid]
        script=next(iter(_drive_paths(argv or [])),None)
        if script:
            if os.path.isabs(script) or ntpath.isabs(script):   # 윈도우 모양(D:\…)은 어느 OS 에서 표를 읽어도 절대경로다
                return script,None
            # 상대경로로 띄운 실행기(«python runner\volcano_drive.py») — 그 프로세스의 현재 폴더(OS 가 아는 사실)로 푼다.
            # 예전에는 절대경로만 인정해 공용 폴더가 영영 안 바뀌고 새 작업 폴더마다 같은 멈춤이 되풀이됐다(신고 #53).
            # 실행기는 설치 컷오버 동안만 잠깐 폴더를 옮기고 같은 자리로 돌아온다(volcano_drive · 그 사이엔 설치기가 안 돈다).
            cwd=process_cwd(pid)
            if not cwd:
                return None,'실행기(pid '+str(pid)+')를 상대경로로 띄웠는데 그 프로세스의 현재 폴더를 읽지 못했습니다'
            return os.path.normpath(os.path.join(cwd,script)),None
        if argv is None:
            return None,'실행기와 설치기 사이 프로세스(pid '+str(pid)+')의 명령줄을 읽지 못했습니다'
        if not _launcher(argv):
            return None,None
        pid=ppid
    return None,None

# 못박힌 옛 편집기(2026-10-07) — 새 팩에 있으면 그 폴더 film_editor.py 와 견준다. LEGACY_SAFE_DIFF: 그 바이트가 같을 때 달라도 되는 엔진 파일.
LEGACY_ENGINE='film_editor_legacy.py'
LEGACY_SAFE_DIFF=('film_editor.py','film_continuity.py')


def caller_runner(target,from_id,engine_files,pack_link,identity_of,io_path=lambda p:p):
    # 이 설치를 부른 옛 실행기가 작업 폴더 밖의 공용 폴더에서 떠 있으면 그 폴더 — (Path, None) · 바꾸면 안 되면 (None, 이유).
    # 바꾸는 조건: 설치기를 띄운 옛 실행기(부모 · 런처가 끼면 조상) 명령줄에 절대경로 volcano_drive.py · 링크가 아닌 보통 폴더 · 그 폴더의 식별값이 호출자와 같다 ·
    # 편집 엔진 다섯 파일이 새 팩과 같다(그 폴더로 도는 다른 작업의 고정 엔진이 안 바뀐다) · 그 폴더를 쓰는 다른 프로세스가 없다.
    table=process_table()
    if not table:
        return None,'프로세스 목록을 읽지 못했습니다'
    script,why=_driver_script(table,os.getppid())
    if why:
        return None,why
    if not script or not os.path.isabs(script):
        return None,'실행기 명령줄에서 실행기 폴더를 찾지 못했습니다'
    folder=os.path.dirname(script)
    if os.path.normcase(os.path.realpath(folder))==os.path.normcase(os.path.realpath(str(target))):
        return None,'같은 폴더'
    if not os.path.isdir(folder) or pack_link(folder):
        return None,'그 폴더가 공용 연결(링크·정션)입니다'
    if identity_of(folder)[0]!=from_id:
        return None,'그 폴더의 실행기가 이 요청을 보낸 실행기와 다릅니다'
    engine_files=dict(engine_files)
    legacy=engine_files.pop(LEGACY_ENGINE,None)
    old={}
    for name in engine_files:
        path=Path(io_path(os.path.join(folder,name)))
        try:
            old[name]=path.read_bytes() if path.is_file() else None
        except OSError:
            # 윈도우 백신·동기화가 그 파일을 쥐면 읽기가 실패한다 — 설치기 트레이스백이 아니라 바꾸지 않는 쪽으로(Z 검토 2회차 minor).
            return None,'그 폴더의 편집 엔진('+name+')을 읽지 못했습니다'
    # 이야기 카드가 아닌 작업의 못박힌 엔진 = 그 폴더 film_editor.py 의 바이트. 새 팩이 그 바이트를 film_editor_legacy.py 로
    # 그대로 싣고 있으면 그 작업은 새 팩에서도 같은 엔진(같은 지문)으로 돈다(film_editor.run). 그때 새 팩의 film_continuity.py 는
    # 이야기 카드에서만 쓰는 함수만 다르다(검사 tests/test_film_editor_legacy_freeze.py 가 함수 단위로 잰다). 이야기 카드 작업은
    # 엔진이 바뀌면 서버가 재준비로 잇는다(engine_update_required → prepare · 유료 음성 보존).
    frozen=legacy is not None and old.get('film_editor.py')==legacy
    for name,body in engine_files.items():
        same=body is not None and old[name]==body
        if not same and not (frozen and name in LEGACY_SAFE_DIFF):
            return None,'그 폴더의 편집 엔진이 새 실행기와 달라 그 폴더로 도는 편집 작업이 깨질 수 있습니다'
    ancestors,pid=set(),os.getpid()
    while pid in table and pid not in ancestors:
        ancestors.add(pid)
        pid=table[pid][0]
    real=os.path.normcase(os.path.realpath(folder))
    marks={os.path.normcase(os.path.abspath(folder)),real}
    for pid,(_ppid,args) in table.items():
        if pid in ancestors or not args:
            continue
        used=_uses_folder(pid,args,marks,real)
        if used:
            return None,'그 폴더의 실행기로 도는 다른 프로세스(pid '+str(pid)+')가 있습니다'
        if used is None:
            return None,'다른 실행기 프로세스(pid '+str(pid)+')가 상대경로로 떠 있어 그 폴더를 쓰는지 확인하지 못했습니다'
    return Path(folder),None

