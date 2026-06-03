import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { api } from '../lib/apiClient';

export default function Login() {
  const { login } = useAuth();
  const navigate  = useNavigate();

  const [username,  setUsername]  = useState('');
  const [password,  setPassword]  = useState('');
  const [empresaId, setEmpresaId] = useState('');
  const [empresas,  setEmpresas]  = useState([]);
  const [error,     setError]     = useState('');
  const [loading,   setLoading]   = useState(false);

  // Cargar lista de empresas al montar
  useEffect(() => {
    api.get('/api/auth/empresas')
      .then((list) => {
        setEmpresas(list);
        if (list.length > 0) setEmpresaId(list[0].id);
      })
      .catch((err) => console.error('[Login] cargar empresas:', err));
  }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(username, password, empresaId);
      navigate('/panel', { replace: true });
    } catch (err) {
      setError(err.message ?? 'Credenciales incorrectas');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={handleSubmit}>
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <img src="/logo.svg" alt="LOGOS" style={{ width: 64, height: 64, display: 'block', margin: '0 auto 12px' }} />
          <h1 style={{
            fontFamily: "'Plus Jakarta Sans', sans-serif",
            fontWeight: 500,
            fontSize: '22px',
            letterSpacing: '5px',
            color: '#1E40AF',
            margin: 0
          }}>LOGOS</h1>
          <p style={{ color: '#64748B', fontSize: '13px', marginTop: 6 }}>Sistema de gestión</p>
        </div>

        {empresas.length > 1 && (
          <div style={{ marginBottom: 14 }}>
            <label className="label">Empresa</label>
            <select
              className="input"
              value={empresaId}
              onChange={(e) => setEmpresaId(e.target.value)}
            >
              {empresas.map((em) => (
                <option key={em.id} value={em.id}>{em.nombre}</option>
              ))}
            </select>
          </div>
        )}

        <div style={{ marginBottom: 14 }}>
          <label className="label">Usuario</label>
          <input
            className="input"
            type="text"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </div>

        <div style={{ marginBottom: 20 }}>
          <label className="label">Contraseña</label>
          <input
            className="input"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>

        {error && <div className="login-error">{error}</div>}

        <button
          className="btn btn-primary"
          type="submit"
          disabled={loading}
          style={{ width: '100%', marginTop: 8, padding: '9px 14px' }}
        >
          {loading ? 'Ingresando…' : 'Ingresar'}
        </button>
      </form>
    </div>
  );
}
