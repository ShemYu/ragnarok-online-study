// T07.007.014.012 finite model suffix; append after the unchanged compiled prefix.
// Derived from the T07.007.014.004 fixed diagnostic suffix: same deadline,
// SHA-256 and 8MiB no-truncation result bound, with the RSW/GAT/GND fetch body
// replaced by one host-handed standalone ArrayBuffer. It constructs one model
// and returns the unchanged summarizeModel output. It never fetches, enters
// FileManager/MapLoader, creates instances, compiles, decodes images or renders.
const ROOT_MODEL_LIMIT = 8 * 1024 * 1024;
const ROOT_MODEL_JOB = ROOT_MODEL_HOST.job;
const ROOT_MODEL_SUMMARIZE = ROOT_MODEL_HOST.summarizeModel;
const ROOT_MODEL_TAKE_BODY = ROOT_MODEL_HOST.takeBody;
let rootModelBusy = false;
self.onmessage = async event => {
  if (event.data?.type !== 'ROOT_MODEL_CONSTRUCT' || rootModelBusy) return;
  rootModelBusy = true;
  const deadline = performance.now() + 48000, started = performance.now();
  let phase = 'input';
  const check = () => {if (performance.now() >= deadline) throw new Error('worker deadline');};
  const need = (v,m) => {check();if(!v)throw new Error(m);};
  const sha = async value => {
    check();const b=await crypto.subtle.digest('SHA-256',value);check();
    return Array.from(new Uint8Array(b),x=>x.toString(16).padStart(2,'0')).join('');
  };
  const failure = (e,at) => {
    let name='Unknown',message='';
    try {name=String(e?.name||typeof e);} catch {}
    try {message=String(e?.message!==undefined?e.message:e);} catch {message='<unprintable>';}
    return {phase:at,name:name.slice(0,64),message:message.slice(0,1200),message_truncated:message.length>1200};
  };
  const result={schema:'t07-007-014-012-model-result-v1',model_index:ROOT_MODEL_JOB.model_index,
    outcome:null,constructor_returned:null,stages:[],input:null,input_postcheck:null,exception:null,
    summary:null,postcheck_error:null,observation_complete:false,qualification:false};
  let buffer=null;
  try {
    buffer=ROOT_MODEL_TAKE_BODY();
    need(buffer instanceof ArrayBuffer&&buffer.byteLength===ROOT_MODEL_JOB.bytes,'exact standalone body buffer');
    need(await sha(buffer)===ROOT_MODEL_JOB.sha256,'complete body pin');
    result.input={bytes:buffer.byteLength,sha256:ROOT_MODEL_JOB.sha256};result.stages.push(phase);
  } catch(e) {result.outcome='input_failure';result.exception=failure(e,phase);}
  let model;
  if(result.outcome===null) {
    phase='constructor';
    // The return fact is set as soon as new RSM returns and survives a later deadline.
    try {check();model=new RSM(buffer);result.constructor_returned=true;check();result.stages.push(phase);}
    catch(e) {result.constructor_returned=result.constructor_returned===true;result.outcome=String(e?.message)==='worker deadline'?'timeout':'constructor_exception';result.exception=failure(e,phase);}
  }
  if(result.outcome===null) {
    phase='summary';
    try {result.summary=ROOT_MODEL_SUMMARIZE(model);check();result.stages.push(phase);result.outcome='returned';}
    catch(e) {result.summary=null;result.outcome=e?.name==='SummaryLimitError'?'summary_limit':String(e?.message)==='worker deadline'?'timeout':'summary_error';result.exception=failure(e,phase);}
  }
  try {
    phase='input-postcheck';
    need(buffer instanceof ArrayBuffer,'body buffer missing');
    const actual={bytes:buffer.byteLength,sha256:await sha(buffer)};result.input_postcheck=actual;
    need(actual.bytes===ROOT_MODEL_JOB.bytes&&actual.sha256===ROOT_MODEL_JOB.sha256,'constructor input preservation');
  } catch(e) {result.postcheck_error=failure(e,phase);}
  result.observation_complete=result.outcome==='returned'&&result.postcheck_error===null;
  result.elapsed_milliseconds=performance.now()-started;
  let encoded;
  try {encoded=JSON.stringify(result);} catch(e) {
    encoded=JSON.stringify({schema:result.schema,model_index:result.model_index,outcome:'summary_error',
      constructor_returned:result.constructor_returned,exception:failure(e,'encode'),observation_complete:false,qualification:false});
  }
  if(new TextEncoder().encode(encoded).byteLength>ROOT_MODEL_LIMIT) {
    encoded=JSON.stringify({schema:result.schema,model_index:result.model_index,outcome:'result_limit',
      constructor_returned:result.constructor_returned,exception:{phase:'encode',name:'Limit',message:'8MiB result bound; no truncated summary accepted',message_truncated:false},
      observation_complete:false,qualification:false});
  }
  postMessage({type:'ROOT_MODEL_RESULT',encoded});
};
