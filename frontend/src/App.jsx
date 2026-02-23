import { useEffect, useMemo, useState } from 'react';

const API_BASE = 'http://127.0.0.1:8000';

const navItems = [
  { key: 'discover', label: 'Discover' },
  { key: 'playlists', label: 'Playlists' },
  { key: 'upload', label: 'Artist Upload' },
  { key: 'review', label: 'Staff Review' },
  { key: 'account', label: 'Account' },
];

function api(path, options = {}, token = null) {
  const headers = {
    ...(options.headers || {}),
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return fetch(`${API_BASE}${path}`, { ...options, headers });
}


async function parseJsonSafe(response) {
  const contentType = response.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) {
    return null;
  }
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function extractErrorMessage(data, fallback) {
  if (!data) return fallback;
  if (typeof data.detail === 'string') return data.detail;
  if (Array.isArray(data.detail)) {
    const first = data.detail[0];
    if (first?.msg) {
      const location = Array.isArray(first.loc) ? first.loc.join('.') : 'field';
      return `${location}: ${first.msg}`;
    }
  }
  return fallback;
}

export default function App() {
  const [activeView, setActiveView] = useState('discover');
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem('user');
    return raw ? JSON.parse(raw) : null;
  });
  const [search, setSearch] = useState('');
  const [publications, setPublications] = useState([]);
  const [playlists, setPlaylists] = useState([]);
  const [message, setMessage] = useState('');

  async function refreshPublications() {
    const response = await api('/publications', {}, token);
    const data = await parseJsonSafe(response);
    setPublications(Array.isArray(data) ? data : []);
  }

  async function refreshPlaylists() {
    if (!token) {
      setPlaylists([]);
      return;
    }
    const response = await api('/playlists', {}, token);
    if (response.ok) {
      setPlaylists(await response.json());
    }
  }

  useEffect(() => {
    refreshPublications();
    refreshPlaylists();
  }, [token]);

  async function onLogin(formData, register = false) {
    const endpoint = register ? '/auth/register' : '/auth/login';
    const response = await api(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formData),
    });
    const data = await parseJsonSafe(response);
    if (!response.ok || !data) {
      setMessage(extractErrorMessage(data, 'Authentication failed'));
      return;
    }
    setToken(data.access_token);
    setUser(data.user);
    localStorage.setItem('token', data.access_token);
    localStorage.setItem('user', JSON.stringify(data.user));
    setActiveView('discover');
    setMessage(`Welcome ${data.user.username}`);
    refreshPublications();
    refreshPlaylists();
  }

  function onLogout() {
    setToken(null);
    setUser(null);
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setMessage('Logged out');
  }

  async function onCreatePlaylist(payload) {
    const response = await api('/playlists', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }, token);
    if (!response.ok) {
      setMessage('Failed to create playlist');
      return;
    }
    setMessage('Playlist created');
    refreshPlaylists();
  }

  async function onUploadArtist(formData) {
    const response = await api('/artist/upload', {
      method: 'POST',
      body: formData,
    }, token);
    if (!response.ok) {
      const err = await parseJsonSafe(response);
      setMessage(extractErrorMessage(err, 'Upload failed'));
      return;
    }
    setMessage('Upload submitted for review');
    refreshPublications();
  }

  async function onModerate(publicationId, status) {
    const response = await api(`/staff/publications/${publicationId}/status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    }, token);
    if (response.ok) {
      setMessage(`Publication ${status}`);
      refreshPublications();
    } else {
      setMessage('Unable to update publication');
    }
  }

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return publications;
    return publications.filter((entry) =>
      [entry.title, entry.genre, entry.artist_id].some((value) => String(value).toLowerCase().includes(q))
    );
  }, [search, publications]);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <h1>TuneForge</h1>
        {navItems.map((item) => {
          if (item.key === 'upload' && user?.role !== 'artist') return null;
          if (item.key === 'review' && user?.role !== 'staff') return null;
          return (
            <button key={item.key} className={activeView === item.key ? 'active' : ''} onClick={() => setActiveView(item.key)}>
              {item.label}
            </button>
          );
        })}
      </aside>

      <main className="content">
        <header>
          <input placeholder="Search by title, genre, artist" value={search} onChange={(e) => setSearch(e.target.value)} />
          {user ? (
            <div className="account-pill">
              {user.username} ({user.role}) <button onClick={onLogout}>Logout</button>
            </div>
          ) : (
            <span>Sign in to create playlists, upload tracks, or review artists.</span>
          )}
        </header>

        {message && <p className="message">{message}</p>}

        {activeView === 'discover' && <Discover publications={filtered} />}
        {activeView === 'playlists' && <Playlists user={user} playlists={playlists} onCreate={onCreatePlaylist} />}
        {activeView === 'upload' && <UploadView onUpload={onUploadArtist} />}
        {activeView === 'review' && <ReviewView publications={publications} onModerate={onModerate} />}
        {activeView === 'account' && <Account user={user} onAuth={onLogin} />}
      </main>
    </div>
  );
}

function Discover({ publications }) {
  return (
    <section>
      <h2>Discover music</h2>
      <div className="cards">
        {publications.map((item) => (
          <article className="card" key={item.publication_id}>
            <p><strong>{item.title}</strong></p>
            <p>Genre: {item.genre}</p>
            <p>Artist ID: {item.artist_id}</p>
            <p>Status: {item.status}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function Playlists({ user, playlists, onCreate }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  if (!user) {
    return <p>Please sign in to manage playlists.</p>;
  }

  return (
    <section>
      <h2>Your playlists</h2>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onCreate({ name, description });
          setName('');
          setDescription('');
        }}
      >
        <input required value={name} onChange={(e) => setName(e.target.value)} placeholder="Playlist name" />
        <textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Description" />
        <button type="submit">Create playlist</button>
      </form>
      <ul>
        {playlists.map((playlist) => (
          <li key={playlist.id}>{playlist.name} ({playlist.song_ids.length} songs)</li>
        ))}
      </ul>
    </section>
  );
}

function UploadView({ onUpload }) {
  return (
    <section>
      <h2>Upload release</h2>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const formData = new FormData(e.currentTarget);
          onUpload(formData);
        }}
      >
        <input name="title" required placeholder="Release title" />
        <input name="genre" required placeholder="Genre" />
        <textarea name="description" placeholder="Description" />
        <label>Cover image <input name="cover" type="file" accept="image/*" required /></label>
        <label>Songs <input name="songs" type="file" multiple required /></label>
        <button type="submit">Submit for approval</button>
      </form>
    </section>
  );
}

function ReviewView({ publications, onModerate }) {
  const pending = publications.filter((entry) => entry.status === 'pending');

  return (
    <section>
      <h2>Staff moderation</h2>
      {pending.length === 0 && <p>No pending releases.</p>}
      {pending.map((item) => (
        <article className="card" key={item.publication_id}>
          <p>{item.title} — {item.genre}</p>
          <p>Artist {item.artist_id}</p>
          <button onClick={() => onModerate(item.publication_id, 'approved')}>Approve</button>
          <button onClick={() => onModerate(item.publication_id, 'rejected')}>Reject</button>
        </article>
      ))}
    </section>
  );
}

function Account({ user, onAuth }) {
  const [registerMode, setRegisterMode] = useState(false);
  const [form, setForm] = useState({ username: '', email: '', password: '', role: 'listener' });

  if (user) {
    return <p>Signed in as {user.username} ({user.role}).</p>;
  }

  function update(key, value) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <section>
      <h2>{registerMode ? 'Create account' : 'Login'}</h2>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const payload = registerMode ? form : { username: form.username, password: form.password };
          onAuth(payload, registerMode);
        }}
      >
        <input required placeholder="Username" value={form.username} onChange={(e) => update('username', e.target.value)} />
        {registerMode && <input required placeholder="Email" type="email" value={form.email} onChange={(e) => update('email', e.target.value)} />}
        <input required placeholder="Password" type="password" value={form.password} onChange={(e) => update('password', e.target.value)} />
        {registerMode && (
          <select value={form.role} onChange={(e) => update('role', e.target.value)}>
            <option value="listener">Listener</option>
            <option value="artist">Artist</option>
            <option value="staff">Staff</option>
          </select>
        )}
        <button type="submit">{registerMode ? 'Register' : 'Login'}</button>
      </form>
      <button onClick={() => setRegisterMode((prev) => !prev)}>
        {registerMode ? 'Have an account? Login' : 'Need an account? Register'}
      </button>
    </section>
  );
}
