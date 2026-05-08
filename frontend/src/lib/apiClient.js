const BASE = import.meta.env.VITE_API_URL ?? '';

function getToken() {
  return sessionStorage.getItem('clf_token');
}

async function request(method, path, body) {
  const token = getToken();
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401) {
    sessionStorage.removeItem('clf_token');
    sessionStorage.removeItem('clf_user');
    window.location.href = '/login';
    throw new Error('No autorizado');
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Error del servidor');
  }

  return res.json();
}

async function upload(path, formData) {
  const token = getToken();
  const headers = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${BASE}${path}`, { method: 'POST', headers, body: formData });
  if (res.status === 401) {
    sessionStorage.removeItem('clf_token');
    sessionStorage.removeItem('clf_user');
    window.location.href = '/login';
    throw new Error('No autorizado');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Error del servidor');
  }
  return res.json();
}

export const api = {
  get:    (path)         => request('GET',    path),
  post:   (path, body)   => request('POST',   path, body),
  put:    (path, body)   => request('PUT',    path, body),
  patch:  (path, body)   => request('PATCH',  path, body),
  delete: (path)         => request('DELETE', path),
  upload: (path, form)   => upload(path, form),
};
