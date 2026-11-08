const environmentBase = import.meta.env.VITE_API_BASE_URL ?? '';
export const configuredApiBase = environmentBase === '/' ? '/' : environmentBase.replace(/\/+$/, '');

export function apiUrl(path: string, base = configuredApiBase): string {
  if (base === '/') return `/api/${path}`;
  if (!base) {
    if (import.meta.env.PROD) throw new Error('Backend connection required. Open API connection and enter the HTTPS URL of your hosted Python backend.');
    return `/api/${path}`;
  }
  const url = new URL(base);
  const local = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname);
  if (url.protocol !== 'https:' && !(local && url.protocol === 'http:')) throw new Error('Backend URL must use HTTPS (HTTP is allowed only for local development).');
  if (url.username || url.password || url.search || url.hash) throw new Error('Backend URL must not contain credentials, query parameters, or a fragment.');
  return `${base.replace(/\/+$/, '').replace(/\/api$/, '')}/api/${path}`;
}
