// falls back to the local FastAPI process when no build-time API URL is set
const API_BASE = `${import.meta.env.VITE_API_BASE || "http://127.0.0.1:8756"}/api`;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// free-tier render spins the api down when idle, so the first request after
// a while has to wait for it to cold-boot and sometimes drops before the
// container's even up. retrying a couple times covers that instead of
// making someone hit refresh themselves
async function get(path, attempt = 1) {
  try {
    const res = await fetch(`${API_BASE}${path}`);
    if (!res.ok) {
      throw new Error(`${path} -> ${res.status}`);
    }
    return await res.json();
  } catch (err) {
    if (attempt >= 3) throw err;
    await sleep(attempt * 4000);
    return get(path, attempt + 1);
  }
}

export function getMatches() {
  return get("/matches");
}

export function getReplay(matchId) {
  return get(`/matches/${matchId}/replay`);
}
