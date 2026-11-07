import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowRight,
  ArrowUpRight,
  Check,
  Download,
  Upload,
  RefreshCw,
  Users,
  Layers,
  Activity,
  ShieldCheck,
} from "lucide-react";
import "./styles.css";
import { SyncPanel, TeamManager } from "./operations";

import type { State, Team, Player } from "./types";
import { api } from "./api";

function App() {
  const [state, setState] = useState<State>();
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [player, setPlayer] = useState(1);
  const [team, setTeam] = useState(2);
  const [name, setName] = useState("");
  const [registrationTeam, setRegistrationTeam] = useState(1);
  const load = async () => setState(await api("/state"));
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    if (busy) return;
    const timer = setInterval(
      () => load().catch((e) => setError(e.message)),
      1500,
    );
    return () => clearInterval(timer);
  }, [busy]);
  async function act(fn: () => Promise<unknown>, message: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
      await load();
      setNotice(message);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const selected = state?.club_players.find((p) => p.id === player);
  const choices =
    state?.club_teams.filter(
      (t) => t.club_id === selected?.club_id && t.id !== selected?.team_id,
    ) || [];
  useEffect(() => {
    if (choices.length && !choices.some((t) => t.id === team))
      setTeam(choices[0].id);
  }, [player, state]);
  if (!state)
    return (
      <main className="loading">
        <h1>League Sync</h1>
        <p role="status">{error || "Connecting to the local lab…"}</p>
        <button onClick={() => load().catch((e) => setError(e.message))}>
          Reconnect
        </button>
      </main>
    );
  const reliable = state.sync.workflow === "reliable";
  const teamName = (id: number, teams: Team[]) =>
    teams.find((t) => t.id === id)?.name || "Unmapped";
  return (
    <div className="app">
      <aside className="sidebar">
        <a className="brand" href="/">
          <Layers size={27} />
          <span>
            league<span className="brand-light">sync</span>
            <small>INTEGRATION RELIABILITY LAB</small>
          </span>
        </a>
        <div className="workspace">
          WORKSPACE <span>LOCAL DEMO</span>
        </div>
        <nav>
          <a className="active" href="#overview">
            <Activity size={18} /> Integration overview
          </a>
          <a href="#rosters">
            <Users size={18} /> Club & League rosters
          </a>
          <a href="#reconciliation">
            <ShieldCheck size={18} /> Reconciliation{" "}
            <b>{state.reconciliation.mismatch_count}</b>
          </a>
        </nav>
        <div className="sidebar-bottom">
          <span className="dot" /> Synthetic data only
          <p>
            Independent engineering case study.
            <br />
            No external systems connected.
          </p>
          <code>CLUB → LEAGUE / LAB 01</code>
        </div>
      </aside>
      <main id="overview">
        <header>
          <span>
            WORKSPACE <span className="slash">/</span>{" "}
            <strong>Integration overview</strong>
          </span>
          <span className="local">
            <span className="dot" /> Local environment
          </span>
        </header>
        <section className="page-heading">
          <div>
            <div className="eyebrow">OPERATIONS / ROSTER INTEGRATION</div>
            <h1>Two systems. One reliable roster.</h1>
            <p>
              Follow a roster change from the Club Portal to the League Portal.
            </p>
          </div>
          <button
            className="secondary"
            disabled={busy}
            onClick={() => act(load, "Live data refreshed.")}
          >
            <RefreshCw size={16} /> Refresh
          </button>
        </section>
        <div className="workflow">
          <div>
            <span className="step-label">WORKFLOW</span>
            <h2>Compare the operating model</h2>
          </div>
          <div className="segmented">
            <button
              className={!reliable ? "selected" : ""}
              disabled={busy}
              onClick={() =>
                act(
                  () => api("/workflow", { workflow: "baseline" }),
                  "Manual CSV workflow selected.",
                )
              }
              aria-pressed={!reliable}
            >
              01 <span>Manual CSV</span>
            </button>
            <button
              className={reliable ? "selected" : ""}
              disabled={busy}
              onClick={() =>
                act(
                  () => api("/workflow", { workflow: "reliable" }),
                  "Reliable synchronization enabled. Club changes now enter the outbox.",
                )
              }
              aria-pressed={reliable}
            >
              02 <span>Reliable sync</span>
            </button>
          </div>
        </div>
        <section className="context">
          <div className="context-icon">
            {reliable ? <ShieldCheck size={22} /> : <Upload size={22} />}
          </div>
          <div>
            <strong>
              {reliable
                ? "Changes travel with a delivery record"
                : "The original workflow"}
            </strong>
            <p>
              {reliable
                ? "Club changes enter a durable queue. Stable identity mappings update the existing League record; retries and conflicts stay visible."
                : "Export the club roster, upload it to League, then inspect discrepancies. Team-scoped imports preserve old assignments after a transfer."}
            </p>
          </div>
          <span className={`pill ${reliable ? "green" : "amber"}`}>
            {reliable ? "DURABLE OUTBOX" : "MANUAL HANDOFF"}
          </span>
        </section>
        <section className="metrics">
          <Metric
            label="Club registrations"
            value={state.club_players.length}
            note="Source of roster truth"
          />
          <Metric
            label="League records"
            value={state.league_players.length}
            note="Independent identifiers"
          />
          <Metric
            label="Reconciliation mismatches"
            value={state.reconciliation.mismatch_count}
            note="Players needing attention"
            warning={state.reconciliation.mismatch_count > 0}
          />
          {reliable ? (
            <Metric
              label="Pending / blocked jobs"
              value={
                state.sync.counts.pending +
                state.sync.counts.failed +
                state.sync.counts.conflict
              }
              note={`${state.sync.counts.delivered} delivered · ${state.sync.counts.failed} failed · ${state.sync.counts.conflict} conflicts`}
            />
          ) : (
            <Metric
              label="Manual handoff steps"
              value={3}
              note="Export → upload → inspect · defined workflow"
            />
          )}
        </section>
        {error && (
          <div className="alert error" role="alert">
            {error}
          </div>
        )}
        {notice && (
          <div className="alert success" role="status">
            <Check size={17} />
            {notice}
          </div>
        )}
        <div className="operation-grid">
          <section className="panel">
            <div className="panel-title">
              <span className="number">01</span>
              <div>
                <h2>Make a club-side change</h2>
                <p>Club owns registration, membership and assignment.</p>
              </div>
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                act(
                  () =>
                    api(`/club/players/${player}/transfer`, { team_id: team }),
                  "Transfer saved in Club. Check the League copy.",
                );
              }}
            >
              <label>
                Player
                <select
                  value={player}
                  onChange={(e) => setPlayer(Number(e.target.value))}
                >
                  {state.club_players.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} · {teamName(p.team_id, state.club_teams)}
                    </option>
                  ))}
                </select>
              </label>
              <div className="form-row">
                <label>
                  Transfer to
                  <select
                    value={team}
                    onChange={(e) => setTeam(Number(e.target.value))}
                  >
                    {choices.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name}
                      </option>
                    ))}
                  </select>
                </label>
                <button disabled={busy || !choices.length} type="submit">
                  Save transfer <ArrowRight size={16} />
                </button>
              </div>
            </form>
            <details>
              <summary>Register a synthetic player</summary>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  act(
                    () =>
                      api("/club/players", { name, team_id: registrationTeam }),
                    "Registration saved.",
                  );
                  setName("");
                }}
              >
                <label>
                  Display name
                  <input
                    required
                    maxLength={80}
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Synthetic Player 21"
                  />
                </label>
                <div className="form-row">
                  <label>
                    Team
                    <select
                      value={registrationTeam}
                      onChange={(e) =>
                        setRegistrationTeam(Number(e.target.value))
                      }
                    >
                      {state.club_teams.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button disabled={busy}>Register</button>
                </div>
              </form>
            </details>
          </section>
          {reliable ? (
            <section className="panel">
              <div className="panel-title">
                <span className="number">02</span>
                <div>
                  <h2>Observe automatic delivery</h2>
                  <p>
                    {state.worker_enabled
                      ? "Worker checks the queue every 0.5 seconds."
                      : "Test mode: use Process queue to advance deliveries."}
                  </p>
                </div>
              </div>
              <div className="delivery-path">
                <span>Club write</span>
                <ArrowRight size={15} />
                <span>Outbox</span>
                <ArrowRight size={15} />
                <span>League</span>
              </div>
              <div className="note">
                <ShieldCheck size={18} />
                <p>
                  Name, membership and team belong to Club. League keeps
                  eligibility. Conflicts require an explicit, audited approval.
                </p>
              </div>
              <p className="cutover-note">
                For a clean before/after comparison, reset the lab between
                workflows. Activation requires aligned rosters.
              </p>
            </section>
          ) : (
            <section className="panel">
              <div className="panel-title">
                <span className="number">02</span>
                <div>
                  <h2>Move the roster manually</h2>
                  <p>Each upload is a snapshot, scoped to each team.</p>
                </div>
              </div>
              <div className="csv-actions">
                <a
                  className="button secondary"
                  href="/api/baseline/export"
                  download="club-roster.csv"
                >
                  <Download size={17} /> Export club CSV{" "}
                  <ArrowUpRight size={15} />
                </a>
                <label className={`button upload ${busy ? "disabled" : ""}`}>
                  <Upload size={17} /> Upload CSV to League
                  <input
                    type="file"
                    accept=".csv,text/csv"
                    aria-label="Upload roster CSV"
                    disabled={busy}
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f)
                        act(
                          async () =>
                            api("/baseline/import", { csv: await f.text() }),
                          "CSV imported. Review reconciliation below.",
                        );
                      e.target.value = "";
                    }}
                  />
                </label>
              </div>
              <div className="note">
                <ShieldCheck size={18} />
                <p>
                  League eligibility is owned by League. CSV imports preserve
                  that decision.
                </p>
              </div>
            </section>
          )}
        </div>
        {reliable && (
          <SyncPanel state={state} busy={busy} act={act} playerId={player} />
        )}
        <section className="panel" id="rosters">
          <div className="section-heading">
            <div>
              <div className="eyebrow">SYSTEM BOUNDARIES</div>
              <h2>Same players, separate records</h2>
            </div>
            <span className="subtle">
              Independent local IDs · synthetic seed
            </span>
          </div>
          <div className="roster-grid">
            <Roster
              title="Club Portal"
              players={state.club_players}
              teams={state.club_teams}
            />
            <Roster
              title="League Portal"
              players={state.league_players}
              teams={state.league_teams}
              onEligibility={(p) =>
                act(
                  () =>
                    api(
                      `/league/players/${p.id}/eligibility`,
                      { eligible: !p.eligible },
                      "PATCH",
                    ),
                  "League eligibility updated.",
                )
              }
            />
          </div>
          <TeamManager state={state} busy={busy} act={act} />
        </section>
        <section className="panel" id="reconciliation">
          <div className="section-heading">
            <div>
              <div className="eyebrow">VERIFY THE OUTCOME</div>
              <h2>Reconciliation report</h2>
            </div>
            <span
              className={`pill ${state.reconciliation.mismatch_count ? "amber" : "green"}`}
            >
              {state.reconciliation.mismatch_count
                ? "ATTENTION NEEDED"
                : "ROSTERS ALIGNED"}
            </span>
          </div>
          {!state.reconciliation.issues.length ? (
            <div className="empty">
              <ShieldCheck size={29} />
              <div>
                <strong>
                  Every registration has a matching League record.
                </strong>
                <p>Transfer a player to see how the two workflows behave.</p>
              </div>
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Player</th>
                    <th>Discrepancy</th>
                    <th>League record IDs</th>
                  </tr>
                </thead>
                <tbody>
                  {state.reconciliation.issues.map((i) => (
                    <tr key={i.source_id}>
                      <td>{i.name}</td>
                      <td>{i.reasons.join(" · ")}</td>
                      <td>{i.league_ids.join(", ") || "None"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
        <footer>
          LEAGUE SYNC RELIABILITY LAB{" "}
          <span>
            Independent, synthetic, portfolio-company-inspired demonstration
          </span>
        </footer>
      </main>
    </div>
  );
}
function Metric({
  label,
  value,
  note,
  warning = false,
}: {
  label: string;
  value: number;
  note: string;
  warning?: boolean;
}) {
  return (
    <article className="metric">
      <span>{label}</span>
      <strong className={warning ? "warning" : ""}>
        {value.toString().padStart(2, "0")}
      </strong>
      <small>{note}</small>
    </article>
  );
}
function Roster({
  title,
  players,
  teams,
  onEligibility,
}: {
  title: string;
  players: Player[];
  teams: Team[];
  onEligibility?: (p: Player) => void;
}) {
  return (
    <div className="roster">
      <h3>
        <span className="dot" />
        {title}
        <span>{players.length} records</span>
      </h3>
      <div className="table-wrap roster-scroll">
        <table>
          <thead>
            <tr>
              <th>ID / player</th>
              <th>Assignment</th>
              <th>{onEligibility ? "Eligibility" : "Membership"}</th>
            </tr>
          </thead>
          <tbody>
            {players.map((p) => (
              <tr key={p.id}>
                <td>
                  <code>#{p.id}</code>
                  <span>{p.name}</span>
                </td>
                <td>{teams.find((t) => t.id === p.team_id)?.name}</td>
                <td>
                  {onEligibility ? (
                    <button
                      className={`badge ${p.eligible ? "green" : "amber"}`}
                      onClick={() => onEligibility(p)}
                      aria-label={`Toggle eligibility for ${p.name}`}
                    >
                      {p.eligible ? "Eligible" : "On hold"}
                    </button>
                  ) : (
                    <span className="badge green">{p.membership}</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
