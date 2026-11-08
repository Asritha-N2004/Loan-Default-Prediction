// @vitest-environment jsdom
import React from 'react';
import {afterEach, describe, expect, it, vi} from 'vitest';
import {cleanup, fireEvent, render, screen} from '@testing-library/react';
import {ChoicePicker} from './ChoicePicker';

afterEach(cleanup);
const options=[{value:'first',label:'Benchmark 1 · 2000 rows'},{value:'second',label:'Benchmark 2 · 1000 rows'}];
function picker(onChange=vi.fn(),value=''){
 render(<ChoicePicker label="Dataset" value={value} options={options} onChange={onChange} placeholder="Select a dataset" emptyHint="Create a benchmark first"/>);
 return onChange;
}
describe('in-page dataset selection',()=>{
 it('shows choices on the page and selects with a click',()=>{
  const change=picker();
  fireEvent.click(screen.getByRole('button',{name:'Dataset Select a dataset'}));
  expect(screen.getByRole('listbox',{name:'Dataset'})).toBeTruthy();
  fireEvent.click(screen.getByRole('option',{name:'Benchmark 2 · 1000 rows'}));
  expect(change).toHaveBeenCalledWith('second');
  expect(screen.queryByRole('listbox')).toBeNull();
 });
 it('supports keyboard navigation and escape',()=>{
  picker(undefined,'first');
  const trigger=screen.getByRole('button',{name:'Dataset Benchmark 1 · 2000 rows'});
  fireEvent.keyDown(trigger,{key:'ArrowDown'});
  expect(document.activeElement).toBe(screen.getByRole('option',{name:options[0].label}));
  fireEvent.keyDown(screen.getByRole('listbox'),{key:'ArrowDown'});
  expect(document.activeElement).toBe(screen.getByRole('option',{name:options[1].label}));
  fireEvent.keyDown(screen.getByRole('listbox'),{key:'Escape'});
  expect(screen.queryByRole('listbox')).toBeNull();
  expect(document.activeElement).toBe(trigger);
 });
 it('explains empty datasets instead of presenting an unusable dropdown',()=>{
  render(<ChoicePicker label="Dataset" value="" options={[]} onChange={vi.fn()} placeholder="Select a dataset" emptyHint="Create a benchmark first"/>);
  expect(screen.getByText('Create a benchmark first')).toBeTruthy();
  fireEvent.click(screen.getByRole('button',{name:'Dataset Select a dataset'}));
  expect(screen.getByRole('listbox').textContent).toContain('Create a benchmark first');
 });
 it('closes when clicking elsewhere',()=>{
  picker();fireEvent.click(screen.getByRole('button',{name:'Dataset Select a dataset'}));
  fireEvent.pointerDown(document.body);
  expect(screen.queryByRole('listbox')).toBeNull();
 });
});
