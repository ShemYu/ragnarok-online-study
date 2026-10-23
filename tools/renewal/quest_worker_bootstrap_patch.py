"""Pure T10.005 controller-source correction after the T10.005.003 plan review.

The input is the exact pinned UNBOUND source. This module performs no filesystem,
process, network or supplied-source execution. Root owns binding and execution.
The finite replacements preserve all other bytes and have an exact inverse.

Claude supplied the startup-pause and real-response join direction. Root fixes
the retained waiting flag, enable/resume readiness race and observation fence.
This transform alone does not qualify installed CDP behavior or quest content.
"""
import hashlib

SOURCE_PIN = (44509, 'a951b3a7956a0a402b1b616743eba369a87dc919b849e7f1acaeb6bb8a934a45')
GROWTH_CAP = 4096
EDITS = (
    (
        b'let worker=null,workerReady=false,pageReady=false,workerDetached=false,cleanupAck=false,cleanupTimer,stopTimer,setupTimer;',
        b'let worker=null,workerReady=false,workerResumeAcknowledged=false,pageReady=false,workerDetached=false,cleanupAck=false,cleanupTimer,stopTimer,setupTimer;',
    ),
    (
        b'let bootstrapKey=null,navigationIssued=false,navigationAck=false,discoveryAttempted=false,discoveryAck=false;',
        b'let bootstrapKey=null,bootstrapWorkerKey=null,navigationIssued=false,navigationAck=false,discoveryAttempted=false,discoveryAck=false;',
    ),
    (
        b'result.worker=worker;result.workerReady=workerReady;result.pageReady=pageReady;',
        b'result.worker=worker;result.workerReady=workerReady;result.workerResumeAcknowledged=workerResumeAcknowledged;result.pageReady=pageReady;',
    ),
    (
        b'      grantVerified&&discoveryAck&&cleanupAck&&workerDetached&&pageDetached',
        b'      grantVerified&&workerResumeAcknowledged&&discoveryAck&&cleanupAck&&workerDetached&&pageDetached',
    ),
    (
        b'if(!navigationAck||!pageReady||!workerReady||!worker||!result.nativeWorkerBootstrapQualified',
        b'if(!navigationAck||!pageReady||!workerReady||!workerResumeAcknowledged||!worker||!result.nativeWorkerBootstrapQualified',
    ),
    (
        b"  need(p.targetInfo?.type==='worker'&&p.targetInfo.url===workerURL&&safeId(p.sessionId)&&safeId(p.targetInfo.targetId)&&p.waitingForDebugger===false,'Worker association');\n"
        b"  worker={sessionId:p.sessionId,targetId:p.targetInfo.targetId,type:'worker',url:p.targetInfo.url,parentSessionId:pageSessionId};retain({method:'Target.attachedToTarget',...worker,waitingForDebugger:false});\n"
        b"  await call('Network.enable',{},worker.sessionId);controlCheck();workerReady=true;\n"
        b"  workerReadyPin=write('READY_WORKER.json',{schema:result.schema,sourceHash,inputHash,attemptId:cfg.attemptId,marker:cfg.ownedMarker,worker,networkEnableAcknowledged:true});",
        b"  need(p.targetInfo?.type==='worker'&&p.targetInfo.url===workerURL&&safeId(p.sessionId)&&p.sessionId!==pageSessionId&&safeId(p.targetInfo.targetId)&&p.targetInfo.targetId!==expectedTargetId&&p.waitingForDebugger===true,'Worker association');\n"
        b"  worker={sessionId:p.sessionId,targetId:p.targetInfo.targetId,type:'worker',url:p.targetInfo.url,parentSessionId:pageSessionId};retain({method:'Target.attachedToTarget',...worker,waitingForDebugger:p.waitingForDebugger});\n"
        b"  await call('Network.enable',{},worker.sessionId);controlCheck();workerReady=true;\n"
        b"  await call('Runtime.runIfWaitingForDebugger',{},worker.sessionId);controlCheck();workerResumeAcknowledged=true;\n"
        b"  workerReadyPin=write('READY_WORKER.json',{schema:result.schema,sourceHash,inputHash,attemptId:cfg.attemptId,marker:cfg.ownedMarker,worker,networkEnableAcknowledged:true,resumeAcknowledged:true});completionCheck();",
    ),
    (
        b"  const key=JSON.stringify([sid,p.requestId]);need(safeId(p.requestId)&&Number.isFinite(p.timestamp),'network identity');let row={method,sessionId:sid,requestId:p.requestId,timestamp:p.timestamp};",
        b"  const rawKey=JSON.stringify([sid,p.requestId]);need(safeId(p.requestId)&&Number.isFinite(p.timestamp),'network identity');let key=rawKey,joiningBootstrap=false,row={method,sessionId:sid,requestId:p.requestId,timestamp:p.timestamp};",
    ),
    (
        b"  if(method==='Network.requestWillBeSent'){\n    const u=p.request?.url,verb=p.request?.method;",
        b"  if(method==='Network.requestWillBeSent'){\n"
        b"    need(!(worker&&sid===worker.sessionId&&p.requestId===worker.targetId&&bootstrapKey===JSON.stringify([pageSessionId,worker.targetId])),'bootstrap Worker request token reserved');\n"
        b"    const u=p.request?.url,verb=p.request?.method;",
    ),
    (
        b"  }else{\n    need(requests.has(key)&&!terminals.has(key),'unmatched/duplicate terminal chain');\n    if(method==='Network.responseReceived'){",
        b"  }else{\n"
        b"    if(bootstrapWorkerKey!==null){\n"
        b"      if(rawKey===bootstrapWorkerKey){controlCheck();need(workerReady&&sid===worker?.sessionId&&p.requestId===worker.targetId,'bootstrap emitting identity');key=bootstrapKey;}\n"
        b"      else need(rawKey!==bootstrapKey,'conflicting bootstrap response/terminal producer');\n"
        b"    }else if(!requests.has(rawKey)&&worker&&sid===worker.sessionId&&p.requestId===worker.targetId){\n"
        b"      controlCheck();const original=requests.get(bootstrapKey);\n"
        b"      need(method==='Network.responseReceived'&&workerReady&&original?.sid===pageSessionId&&original.role==='page'&&original.url===workerURL&&original.method==='GET'&&bootstrapKey===JSON.stringify([pageSessionId,worker.targetId])&&!responses.has(bootstrapKey)&&!terminals.has(bootstrapKey),'unqualified bootstrap association');\n"
        b"      key=bootstrapKey;joiningBootstrap=true;\n"
        b"    }\n"
        b"    need(requests.has(key)&&!terminals.has(key),'unmatched/duplicate terminal chain');\n"
        b"    if(method==='Network.responseReceived'){",
    ),
    (
        b'      row.status=p.response.status;row.mimeType=p.response.mimeType;row.protocol=p.response.protocol;responses.add(key);responseStatuses.set(key,p.response.status);',
        b"      if(joiningBootstrap){need(p.response.status===200,'bootstrap admitted response200');bootstrapWorkerKey=rawKey;result.nativeWorkerBootstrapAssociation={requestKey:bootstrapKey,responseEmittingKey:rawKey,pageSessionId,workerSessionId:worker.sessionId,requestId:p.requestId,evidence:'real Worker response200; raw emitting session retained'};}\n"
        b'      row.status=p.response.status;row.mimeType=p.response.mimeType;row.protocol=p.response.protocol;responses.add(key);responseStatuses.set(key,p.response.status);',
    ),
    (
        b"  retain(row);if(method==='Network.loadingFinished'||method==='Network.loadingFailed'){terminals.add(key);terminalMethods.set(key,method);}",
        b"  if(rawKey!==key)row.canonicalBootstrapRequestKey=key;\n"
        b"  retain(row);if(method==='Network.loadingFinished'||method==='Network.loadingFailed'){terminals.add(key);terminalMethods.set(key,method);}",
    ),
    (
        b"autoAttachAttempted=true;await call('Target.setAutoAttach',{autoAttach:true,waitForDebuggerOnStart:false,flatten:true},pageSessionId);",
        b"autoAttachAttempted=true;await call('Target.setAutoAttach',{autoAttach:true,waitForDebuggerOnStart:true,flatten:true},pageSessionId);",
    ),
)


def _refuse(code):
    raise ValueError('T10.005 Worker correction refused: ' + code)


def inverse_worker_bootstrap_patch(patched):
    """Undo exactly this edit surface; this is not an input trust validator."""
    if type(patched) is not bytes:
        raise TypeError('patched source must be bytes')
    restored = patched
    for old, new in reversed(EDITS):
        if restored.count(new) != 1:
            _refuse('inverse edit surface')
        restored = restored.replace(new, old, 1)
    return restored


def apply_worker_bootstrap_patch(source):
    """Return corrected UNBOUND source bytes, refusing any source drift."""
    if type(source) is not bytes:
        raise TypeError('source must be bytes')
    if (len(source), hashlib.sha256(source).hexdigest()) != SOURCE_PIN:
        _refuse('source pin')
    out = source
    for old, new in EDITS:
        if out.count(old) != 1 or new in out:
            _refuse('nonunique or foreign edit surface')
        out = out.replace(old, new, 1)
    if not 0 < len(out) - len(source) <= GROWTH_CAP:
        _refuse('growth cap')
    if inverse_worker_bootstrap_patch(out) != source:
        _refuse('inverse mismatch')
    return out
