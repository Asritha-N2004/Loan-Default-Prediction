// @vitest-environment jsdom
import React from 'react';
import {afterEach, describe, expect, it, vi} from 'vitest';
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {AuthGate,AuthPage} from './AuthGate';

afterEach(()=>{cleanup();vi.unstubAllGlobals()});
const user={id:'user-1',email:'researcher@example.test',email_verified:false};
describe('account login and automatic workspace preparation',()=>{
 it('shows a login page when no account session exists',async()=>{
  vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,json:async()=>({authenticated:false})})));
  render(<AuthGate>{()=> <div>Dashboard</div>}</AuthGate>);
  expect(await screen.findByRole('heading',{name:'Sign in to your workspace'})).toBeTruthy();
  expect(screen.queryByText('Dashboard')).toBeNull();
 });
 it('loads the saved session and initializes the workspace automatically',async()=>{
  const paths:string[]=[];
  vi.stubGlobal('fetch',vi.fn(async(path:string)=>{paths.push(path);return{ok:true,json:async()=>path.endsWith('/session')?{authenticated:true,user}:{dataset_id:'dataset-1',model_id:'model-1'}}}));
  render(<AuthGate>{(account,_,starter)=><div>{account.email} {starter.model_id}</div>}</AuthGate>);
  expect(await screen.findByText('researcher@example.test model-1')).toBeTruthy();
  expect(paths).toEqual(['/api/auth/session','/api/workspace/initialize']);
 });
 it('creates an account through the API and checks confirmation first',async()=>{
  const fetch=vi.fn(async(_path:string,_options?:unknown)=>({ok:true,json:async()=>({authenticated:true,user})}));vi.stubGlobal('fetch',fetch);
  const done=vi.fn(async()=>{});render(<AuthPage onAuthenticated={done}/>);
  fireEvent.click(screen.getByRole('tab',{name:'Create account'}));
  fireEvent.change(screen.getByLabelText('Email address'),{target:{value:user.email}});
  fireEvent.change(screen.getByLabelText('Password',{exact:true}),{target:{value:'A synthetic test passphrase'}});
  fireEvent.change(screen.getByLabelText('Confirm password'),{target:{value:'different passphrase'}});
  fireEvent.click(screen.getByRole('button',{name:'Create account'}));
  expect(await screen.findByRole('alert')).toBeTruthy();expect(fetch).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText('Confirm password'),{target:{value:'A synthetic test passphrase'}});
  fireEvent.click(screen.getByRole('button',{name:'Create account'}));
  await waitFor(()=>expect(done).toHaveBeenCalledWith(user));
  expect(fetch.mock.calls[0][0]).toBe('/api/auth/register');
 });
 it('returns to login when the dashboard reports an expired session',async()=>{
  vi.stubGlobal('fetch',vi.fn(async(path:string)=>({ok:true,json:async()=>path.endsWith('/session')?{authenticated:true,user}:{dataset_id:'d',model_id:'m'}})));
  render(<AuthGate>{()=> <div>Private dashboard</div>}</AuthGate>);
  await screen.findByText('Private dashboard');
  window.dispatchEvent(new Event('causallens:session-expired'));
  expect(await screen.findByRole('heading',{name:'Sign in to your workspace'})).toBeTruthy();
  expect(screen.queryByText('Private dashboard')).toBeNull();
 });
});
