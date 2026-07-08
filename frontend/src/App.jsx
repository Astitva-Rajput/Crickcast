import { useEffect, useState } from "react";
import { getMatches } from "./api";
import MatchPicker from "./components/MatchPicker";
import Replay from "./components/Replay";
import LoadingMark from "./components/LoadingMark";

export default function App() {
  const [matches, setMatches] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [matchId, setMatchId] = useState(null);

  useEffect(() => {
    getMatches().then(setMatches).catch((e) => setLoadError(e.message));
  }, []);

  return (
    <div className="app">
      <header className="app-header">
        <button className="brand" onClick={() => setMatchId(null)}>
          <svg className="brand-mark" width="20" height="16" viewBox="0 0 20 16">
            <rect className="bar" x="0" y="6" width="4" height="10" rx="1" fill="var(--signal)" />
            <rect className="bar" x="8" y="2" width="4" height="14" rx="1" fill="var(--signal)" />
            <rect className="bar" x="16" y="9" width="4" height="7" rx="1" fill="var(--signal)" />
          </svg>
          <h1>Crick<span>Cast</span></h1>
        </button>
        <p>ball-by-ball win probability, replayed over by over — men's T20Is</p>
      </header>

      {loadError && (
        <div className="replay-error">
          can't reach the API ({loadError}) — it might be waking up, try refreshing in a moment.
        </div>
      )}

      {!loadError && matches === null && (
        <div className="replay-loading">
          <LoadingMark />
          waking up the server, this can take a bit on the first load…
        </div>
      )}

      {!loadError && matches !== null && matchId === null && (
        <MatchPicker matches={matches} onPick={setMatchId} />
      )}

      {matchId !== null && (
        <Replay matchId={matchId} onBack={() => setMatchId(null)} />
      )}

      <footer className="app-footer">
        CrickCast · ball-by-ball data via cricsheet.org · win probability from a calibrated xgboost model
      </footer>
    </div>
  );
}
