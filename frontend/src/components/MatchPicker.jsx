import { useMemo, useState } from "react";

// initials for multi-word team names, first 3 letters otherwise
// (England -> ENG, West Indies -> WI)
function abbreviate(name) {
  const words = name.split(/\s+/).filter((w) => !/^(of|and)$/i.test(w));
  return words.length > 1
    ? words.map((w) => w[0]).join("")
    : name.slice(0, 3);
}

// "vs"/"v" show up in queries like "eng vs ind" but dont mean anything, drop them
const JOINERS = new Set(["vs", "v", "versus"]);

export default function MatchPicker({ matches, onPick }) {
  const [query, setQuery] = useState("");

  const indexed = useMemo(
    () =>
      matches.map((m) => ({
        match: m,
        // codes need an exact match, otherwise "ind" would also match
        // "West Indies" as a substring
        codes: new Set([abbreviate(m.team1), abbreviate(m.team2)].map((c) => c.toLowerCase())),
        haystack: [m.team1, m.team2, m.venue, m.season].join(" ").toLowerCase(),
      })),
    [matches]
  );

  const filtered = useMemo(() => {
    const tokens = query.trim().toLowerCase().split(/\s+/).filter((t) => t && !JOINERS.has(t));
    if (tokens.length === 0) return matches.slice(0, 60);

    return indexed
      .filter(({ codes, haystack }) =>
        tokens.every((t) => codes.has(t) || (t.length >= 4 && haystack.includes(t)))
      )
      .map(({ match }) => match)
      .slice(0, 60);
  }, [query, indexed, matches]);

  return (
    <div className="picker">
      <div className="picker-searchbar">
        <svg className="search-icon" width="15" height="15" viewBox="0 0 15 15" fill="none">
          <circle cx="6.5" cy="6.5" r="4.5" stroke="currentColor" strokeWidth="1.5" />
          <line x1="10" y1="10" x2="13.5" y2="13.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
        <input
          className="picker-search"
          placeholder="find a match — team, venue, season..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Escape") setQuery("");
            // enter just opens the top result, saves a click
            if (e.key === "Enter" && query && filtered.length > 0) onPick(filtered[0].match_id);
          }}
          autoFocus
        />
        {query && (
          <button className="search-clear" onClick={() => setQuery("")} aria-label="clear search">
            ×
          </button>
        )}
      </div>

      <div className="picker-count">
        {matches.length.toLocaleString()} matches on file
        {query && ` · ${filtered.length} match${filtered.length === 1 ? "" : "es"}`}
      </div>

      <ul className="picker-list">
        {filtered.map((m) => (
          <li key={m.match_id}>
            <button className="picker-row" onClick={() => onPick(m.match_id)}>
              <span className="picker-teams">{m.team1} v {m.team2}</span>
              <span className="picker-meta">{m.venue} · {m.season}</span>
              <span className="picker-winner">{m.winner} won</span>
            </button>
          </li>
        ))}
        {filtered.length === 0 && (
          <li className="picker-empty">nothing matches "{query}"</li>
        )}
      </ul>
    </div>
  );
}
