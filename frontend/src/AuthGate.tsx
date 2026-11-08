import React, {useEffect, useState} from 'react';
import {ArrowRight, Check, GitBranch, LoaderCircle, ShieldCheck} from 'lucide-react';

export type Account = {id:string; email:string; email_verified:boolean};
type Starter = {dataset_id:string; model_id:string};

async function authRequest(path:string,body?:unknown){
  const response=await fetch(`/api/${path}`,{method:body===undefined?'GET':'POST',credentials:'same-origin',
    headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});
  const value=await response.json();
  if(!response.ok){const error=new Error(typeof value.detail==='string'?value.detail:'Check your details and try again.');
    Object.assign(error,{status:response.status});throw error;}
  return value;
}

export function AuthGate({children}:{children:(user:Account,signOut:()=>Promise<void>,starter:Starter)=>React.ReactNode}){
  const [user,setUser]=useState<Account|null>(null), [starter,setStarter]=useState<Starter|null>(null);
  const [phase,setPhase]=useState<'checking'|'login'|'preparing'|'ready'|'error'>('checking');
  const [error,setError]=useState('');
  async function initialize(account:Account){
    setUser(account);setPhase('preparing');setError('');
    try{
      for(let retry=0;retry<25;retry++){
        try{const value=await authRequest('workspace/initialize',{});setStarter(value);setPhase('ready');return}
        catch(e){if((e as {status?:number}).status===409&&retry<24){await new Promise(resolve=>setTimeout(resolve,1500));continue}throw e}
      }
    }catch(e){if((e as {status?:number}).status===401){setUser(null);setPhase('login')}else{setError(String(e));setPhase('error')}}
  }
  async function checkSession(){
    setPhase('checking');setError('');
    try{const session=await authRequest('auth/session');if(session.authenticated)await initialize(session.user);else setPhase('login')}
    catch(e){setError(String(e));setPhase('error')}
  }
  useEffect(()=>{checkSession();const expired=()=>{setUser(null);setStarter(null);setPhase('login')};
    window.addEventListener('causallens:session-expired',expired);
    return()=>window.removeEventListener('causallens:session-expired',expired);
  },[]);
  async function signOut(){await authRequest('auth/logout',{});setUser(null);setStarter(null);setPhase('login')}
  if(phase==='login')return <AuthPage onAuthenticated={initialize}/>;
  if(phase==='ready'&&user&&starter)return <>{children(user,signOut,starter)}</>;
  return <div className="auth-loading"><div className="auth-brand"><GitBranch/>CausalLens</div>
    {phase==='error'?<><h1>Workspace preparation paused</h1><p role="alert">{error}</p><button className="primary" onClick={()=>user?initialize(user):checkSession()}>Try again</button></>
      :<><LoaderCircle className="spinner-icon"/><h1>{phase==='checking'?'Opening your workspace':'Preparing your research workspace'}</h1>
      <p>{phase==='checking'?'Checking your secure session.':'Creating or loading your synthetic benchmark and four calibrated models. First setup may take a short while.'}</p>
      {phase==='preparing'&&<p>Your existing datasets and models will be reused on future visits.</p>}</>}
  </div>
}

export function AuthPage({onAuthenticated}:{onAuthenticated:(user:Account)=>Promise<void>}){
  const [mode,setMode]=useState<'login'|'register'>('login');
  const [email,setEmail]=useState(''), [password,setPassword]=useState(''), [confirm,setConfirm]=useState('');
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  async function submit(event:React.FormEvent){
    event.preventDefault();setError('');
    if(mode==='register'&&password!==confirm){setError('Passwords do not match.');return}
    setBusy(true);
    try{const session=await authRequest(`auth/${mode}`,{email,password});setPassword('');setConfirm('');await onAuthenticated(session.user)}
    catch(e){setError(e instanceof Error?e.message:String(e));setPassword('');setConfirm('')}
    finally{setBusy(false)}
  }
  return <main className="auth-layout"><section className="auth-intro"><div className="auth-brand"><GitBranch/>CausalLens</div>
    <div className="auth-intro-content"><div className="eyebrow">CAUSALITY-AWARE LOAN RISK RESEARCH</div><h1>Your evidence. <br/>Your workspace. <br/>Ready when you are.</h1>
    <p>Explore the difference between a prediction, an explanation, and a causal finding—with a reproducible research workspace.</p>
    <ul>{['Synthetic benchmark prepared automatically','Four calibrated prediction models','Private, account-linked analysis history','The same workspace across browsers'].map(text=><li key={text}><Check size={17}/>{text}</li>)}</ul></div>
    <div className="auth-research-note"><ShieldCheck size={20}/><span>Synthetic research demo. No automated lending decisions.</span></div>
  </section><section className="auth-panel"><div className="auth-form-card"><div className="eyebrow">WELCOME TO CAUSALLENS</div>
    <h2>{mode==='login'?'Sign in to your workspace':'Create your account'}</h2><p>{mode==='login'?'Your benchmark, models, and saved analyses will load automatically.':'We’ll prepare your synthetic benchmark and train the models after you sign up.'}</p>
    <div className="auth-tabs" role="tablist" aria-label="Account access"><button type="button" role="tab" aria-selected={mode==='login'} disabled={busy} onClick={()=>{setMode('login');setError('');setPassword('');setConfirm('')}}>Sign in</button><button type="button" role="tab" aria-selected={mode==='register'} disabled={busy} onClick={()=>{setMode('register');setError('');setPassword('');setConfirm('')}}>Create account</button></div>
    <form onSubmit={submit}><label>Email address<input type="email" autoComplete="email" maxLength={254} required value={email} onChange={e=>setEmail(e.target.value)}/></label>
    <label>Password<input type="password" autoComplete={mode==='register'?'new-password':'current-password'} minLength={mode==='register'?15:1} maxLength={128} required value={password} onChange={e=>setPassword(e.target.value)}/></label>
    {mode==='register'&&<><small>Use at least 15 characters. A memorable passphrase works well.</small><label>Confirm password<input type="password" autoComplete="new-password" required value={confirm} onChange={e=>setConfirm(e.target.value)}/></label></>}
    {error&&<div className="message error" role="alert">{error}</div>}
    <button className="primary auth-submit" disabled={busy}>{busy?<><LoaderCircle className="spinner-icon" size={17}/>Please wait…</>:<>{mode==='login'?'Sign in':'Create account'}<ArrowRight size={17}/></>}</button>
    </form><p className="auth-footer-note">Your password is hashed and your session is kept in a secure cookie. This research demo does not yet support email verification or password recovery.</p>
    </div></section></main>
}
