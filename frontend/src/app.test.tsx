// @vitest-environment jsdom
import React from 'react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import {App} from './main';

const graph={nodes:['counseling','default'],edges:[['counseling','default']],assumptions:'Synthetic hypothesis'};
const dataset={id:'dataset-1',name:'Synthetic counseling benchmark',quality:{rows:2000},provenance:{synthetic:true}};
let calls:{path:string,body:any}[]=[];
beforeEach(()=>{
 calls=[];
 vi.stubGlobal('scrollTo',vi.fn());
 vi.stubGlobal('fetch',vi.fn(async(input:string, options:any)=>{
  const body=options?.body?JSON.parse(options.body):undefined;
  calls.push({path:input,body});
  const result=input.endsWith('/data/datasets')?[]:input.endsWith('/prediction/models')?[]:input.endsWith('/reports')?[]:input.endsWith('/graph/default')?graph:input.endsWith('/data/synthetic')?dataset:{};
  return {ok:true,json:async()=>result};
 }));
});
afterEach(()=>{cleanup();vi.unstubAllGlobals()});
describe('research workspace',()=>{
 it('renders an empty workspace without invented metrics',async()=>{
  render(<App/>);
  await screen.findByText('Load workspace complete');
  expect(screen.getByText('See risk. Understand evidence.')).toBeTruthy();
  expect(screen.getByText('Train the baselines to see measured holdout performance.')).toBeTruthy();
  expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(3);
 });
 it('calls the synthetic generator with a reproducible request',async()=>{
  render(<App/>);await screen.findByText('Load workspace complete');
  fireEvent.click(screen.getByRole('button',{name:'Create benchmark'}));
  await screen.findByText('Synthetic benchmark complete');
  expect(calls.find(c=>c.path.endsWith('/data/synthetic'))?.body).toEqual({n:2000,seed:42});
 });
 it('requires audit authorization and a model before running fairness',async()=>{
  render(<App/>);await screen.findByText('Load workspace complete');
  fireEvent.click(screen.getByRole('button',{name:'Fairness audit'}));
  const button=screen.getByRole('button',{name:'Evaluate disparities'}) as HTMLButtonElement;
  expect(button.disabled).toBe(true);
  fireEvent.click(screen.getByRole('checkbox'));
  expect(button.disabled).toBe(true);
 });
 it('displays backend errors rather than a successful state',async()=>{
  vi.stubGlobal('fetch',vi.fn(async()=>({ok:false,json:async()=>({detail:'Invalid API key'})})));
  render(<App/>);
  expect((await screen.findByRole('alert')).textContent).toContain('Invalid API key');
 });
 it('selects available data and keeps the model matched when changing datasets',async()=>{
  const data=[{...dataset,id:'d1',name:'First benchmark'},{...dataset,id:'d2',name:'Second benchmark'}];
  const models=[{id:'m1',dataset_id:'d1',selected:'logistic',models:{}},{id:'m2',dataset_id:'d2',selected:'logistic',models:{}}];
  vi.stubGlobal('fetch',vi.fn(async(input:string)=>({ok:true,json:async()=>
   input.endsWith('/data/datasets')?data:input.endsWith('/prediction/models')?models:input.endsWith('/reports')?[]:input.endsWith('/graph/default')?graph:{}})));
  render(<App/>);await screen.findByText('Load workspace complete');
  expect(screen.getByRole('button',{name:/Dataset First benchmark/})).toBeTruthy();
  expect(await screen.findByRole('button',{name:'Model version logistic · m1'})).toBeTruthy();
  fireEvent.click(screen.getByRole('button',{name:/Dataset First benchmark/}));
  fireEvent.click(screen.getByRole('option',{name:/Second benchmark/}));
  await screen.findByRole('button',{name:'Model version logistic · m2'});
  expect(screen.getByRole('button',{name:/Dataset Second benchmark/})).toBeTruthy();
 });
});
