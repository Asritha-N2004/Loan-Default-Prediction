import {describe, expect, it} from 'vitest';
import {apiUrl} from './api';

describe('cloud API routing',()=>{
  it('routes to the persistent backend rather than the Vercel SPA',()=>{
    expect(apiUrl('data/datasets','/')).toBe('/api/data/datasets');
    expect(apiUrl('prediction/train','https://backend.example')).toBe('https://backend.example/api/prediction/train');
    expect(apiUrl('reports','https://backend.example/api/')).toBe('https://backend.example/api/reports');
  });
  it('rejects insecure remote URLs and credentials in URLs',()=>{
    expect(()=>apiUrl('data/datasets','http://backend.example')).toThrow('HTTPS');
    expect(()=>apiUrl('data/datasets','https://user:password@backend.example')).toThrow('credentials');
    expect(()=>apiUrl('data/datasets','https://backend.example?key=secret')).toThrow('credentials');
  });
  it('retains local development routing',()=>{
    expect(apiUrl('reports','http://127.0.0.1:8000')).toBe('http://127.0.0.1:8000/api/reports');
    expect(apiUrl('reports','')).toBe('/api/reports');
  });
});
