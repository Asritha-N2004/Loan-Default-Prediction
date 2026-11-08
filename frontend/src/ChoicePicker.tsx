import React, {useEffect, useId, useRef, useState} from 'react';
import {Check, ChevronDown} from 'lucide-react';

type Option = {value:string; label:string};

/** An in-page list keeps choices visible inside embedded and mobile browsers. */
export function ChoicePicker({label,value,options,onChange,placeholder,emptyHint,disabled=false}:{
  label:string; value:string; options:Option[]; onChange:(value:string)=>void;
  placeholder:string; emptyHint:string; disabled?:boolean;
}){
  const id=useId();
  const [open,setOpen]=useState(false), [active,setActive]=useState(0);
  const root=useRef<HTMLDivElement>(null), trigger=useRef<HTMLButtonElement>(null);
  const choices=useRef<(HTMLButtonElement|null)[]>([]);
  const selected=options.find(o=>o.value===value);
  useEffect(()=>{
    const outside=(e:PointerEvent)=>{if(!root.current?.contains(e.target as Node))setOpen(false)};
    document.addEventListener('pointerdown',outside);
    return()=>document.removeEventListener('pointerdown',outside);
  },[]);
  useEffect(()=>{if(open)choices.current[active]?.focus()},[open,active]);
  useEffect(()=>{setOpen(false)},[disabled]);
  function show(){setActive(Math.max(0,options.findIndex(o=>o.value===value)));setOpen(true)}
  function choose(next:string){onChange(next);setOpen(false);trigger.current?.focus()}
  return <div className="picker-field" ref={root}>
    <span id={`${id}-label`}>{label}</span>
    <button ref={trigger} type="button" className="picker-trigger" aria-labelledby={`${id}-label ${id}-value`}
      aria-haspopup="listbox" aria-expanded={open} aria-controls={`${id}-list`} disabled={disabled}
      onClick={()=>open?setOpen(false):show()}
      onKeyDown={e=>{if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();show()}if(e.key==='Escape')setOpen(false)}}>
      <span id={`${id}-value`}>{selected?.label??placeholder}</span><ChevronDown size={16}/>
    </button>
    {open&&<div className="picker-options" id={`${id}-list`} role="listbox" aria-labelledby={`${id}-label`}
      onKeyDown={e=>{
        if(e.key==='Escape'){e.preventDefault();setOpen(false);trigger.current?.focus()}
        if(e.key==='ArrowDown'){e.preventDefault();setActive(i=>Math.min(i+1,options.length-1))}
        if(e.key==='ArrowUp'){e.preventDefault();setActive(i=>Math.max(i-1,0))}
        if(e.key==='Home'){e.preventDefault();setActive(0)}
        if(e.key==='End'){e.preventDefault();setActive(Math.max(options.length-1,0))}
        if(e.key==='Tab')setOpen(false);
      }}>
      {options.length?options.map((option,i)=><button type="button" role="option" key={option.value}
        ref={el=>{choices.current[i]=el}} aria-selected={option.value===value} tabIndex={i===active?0:-1}
        onClick={()=>choose(option.value)}><span>{option.label}</span>{option.value===value&&<Check size={16}/>}</button>)
        :<p className="picker-empty">{emptyHint}</p>}
    </div>}
    {!options.length&&!open&&<small className="picker-hint">{emptyHint}</small>}
  </div>
}
