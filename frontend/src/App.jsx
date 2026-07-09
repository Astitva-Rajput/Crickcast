import { useEffect, useState } from "react";
import { getMatches, getLiveMatches } from "./api";
import MatchPicker from "./components/MatchPicker";
import Replay from "./components/Replay";
import Live from "./components/Live";
import LoadingMark from "./components/LoadingMark";

export default function App() {
  const [matches, setMatches] = useState(null);
  const [liveMatches, setLiveMatches] = useState([]);
  const [loadError, setLoadError] = useState(null);
  const [matchId, setMatchId] = useState(null);
  const [liveId, setLiveId] = useState(null);

  useEffect(() => {
    getMatches().then(setMatches).catch((e) => setLoadError(e.message));
    // live section just doesn't show if the tracker isn't reachable -
    // the replay side of the app shouldn't care
    getLiveMatches().then(setLiveMatches).catch(() => setLiveMatches([]));
  }, []);

  const goHome = () => { setMatchId(null); setLiveId(null); };
  const picking = matchId === null && liveId === null;

  return (
    <div className="app">
      <header className="app-header">
        <button className="brand" onClick={goHome}>
          <svg className="brand-mark" width="20" height="16" viewBox="0 0 20 16">
            <rect className="bar" x="0" y="6" width="4" height="10" rx="1" fill="var(--signal)" />
            <rect className="bar" x="8" y="2" width="4" height="14" rx="1" fill="var(--signal)" />
            <rect className="bar" x="16" y="9" width="4" height="7" rx="1" fill="var(--signal)" />
          </svg>
          <h1>Crick<span>Cast</span></h1>
        </button>
        <p>ball-by-ball win probability, live and replayed over by over</p>
      </header>

      {loadError && (
        <div className="replay-error">
          can't reach the API ({loadError}) — it might be waking up, try refreshing in a moment.
        </div>
      )}

      {!loadError && matches === null && picking && (
        <div className="replay-loading">
          <LoadingMark />
          waking up the server, this can take a bit on the first load…
        </div>
      )}

      {picking && liveMatches.length > 0 && (
        <div className="live-strip">
          <div className="live-strip-label">
            <span className="live-dot" />
            live now
          </div>
          <ul className="live-list">
            {liveMatches.map((m) => (
              <li key={m.id}>
                <button className="picker-row live-row" onClick={() => setLiveId(m.id)}>
                  <span className="picker-teams">{m.teams.join(" v ")}</span>
                  <span className="picker-meta">{m.format} · {m.venue}</span>
                  <span className="picker-winner">{m.status}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {!loadError && matches !== null && picking && (
        <MatchPicker matches={matches} onPick={setMatchId} />
      )}

      {matchId !== null && (
        <Replay matchId={matchId} onBack={goHome} />
      )}

      {liveId !== null && (
        <Live matchId={liveId} onBack={goHome} />
      )}

      <footer className="app-footer">
        CrickCast · ball-by-ball data via cricsheet.org · win probability from a calibrated xgboost model
      </footer>
    </div>
  );
}
