import { useState } from "react";
import "./operations.css";
import { ArrowRight, RefreshCw, Zap, ShieldAlert } from "lucide-react";
import { api } from "./api";
import type { State, Event } from "./types";

type Act = (fn: () => Promise<unknown>, message: string) => Promise<void>;
type Props = { state: State; busy: boolean; act: Act };

export function SyncPanel({
  state,
  busy,
  act,
  playerId,
}: Props & { playerId: number }) {
  const mapped = state.sync.identity_map.find((m) => m.source_id === playerId);
  const target = state.league_players.find((p) => p.id === mapped?.target_id);
  return (
    <section className="panel" id="deliveries">
      <div className="section-heading">
        <div>
          <div className="eyebrow">DELIVERY CONTROL ROOM</div>
          <h2>Every change has a trace</h2>
        </div>
        <span className="pill green">
          {state.sync.identity_map.length} MAPPED IDENTITIES
        </span>
      </div>
      <div className="queue-toolbar">
        <button
          disabled={busy}
          onClick={() =>
            act(
              () => api("/sync/process", {}),
              "Due jobs processed. Review their status below.",
            )
          }
        >
          <RefreshCw size={15} /> Process queue
        </button>
        <button
          className="secondary"
          disabled={busy}
          onClick={() =>
            act(
              () => api("/sync/failure", { attempts: 1 }),
              "Temporary failure armed. The next delivery attempt will fail safely.",
            )
          }
        >
          <Zap size={15} /> Fail next delivery
        </button>
        <button
          className="secondary"
          disabled={busy || !target}
          onClick={() =>
            act(
              () =>
                api(
                  `/league/players/${target!.id}/local-edit`,
                  {
                    name: "Synthetic League Review",
                    expected_revision: target!.revision,
                  },
                  "PATCH",
                ),
              "League name edited locally. Transfer this player to expose the conflict.",
            )
          }
        >
          <ShieldAlert size={15} /> Simulate conflicting name
        </button>
        <span>{state.sync.failure_budget} failure(s) armed</span>
      </div>
      <p className="help">
        Automatic retries: 3 total attempts, with exponential delay. A manual
        retry retains the previous attempts and audit history. Simulation
        controls affect this local synthetic lab only.
      </p>
      {!state.sync.events.length ? (
        <div className="empty">
          <RefreshCw size={25} />
          <div>
            <strong>The queue is ready.</strong>
            <p>Save a Club transfer to produce the first event.</p>
          </div>
        </div>
      ) : (
        <div className="table-wrap">
          <table className="events-table">
            <thead>
              <tr>
                <th>Event / created UTC</th>
                <th>State</th>
                <th>Attempts</th>
                <th>Delivery detail</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {state.sync.events.map((event) => (
                <EventRow
                  key={event.id}
                  event={event}
                  state={state}
                  busy={busy}
                  act={act}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
      <details className="audit-details" open={state.sync.audit.length > 1}>
        <summary>
          Audit trail · latest {state.sync.audit.length} entries
        </summary>
        <div className="audit-list">
          {state.sync.audit.map((a) => (
            <div className="audit-entry" key={a.id}>
              <span className="audit-time">
                {a.created_at.replace("T", " ").replace("Z", "")}
              </span>
              <span className="audit-action">
                {a.action.replaceAll("_", " ")}
              </span>
              <span>
                {a.event_id ? `Event #${a.event_id} · ` : ""}
                {a.detail}
              </span>
            </div>
          ))}
        </div>
      </details>
    </section>
  );
}

function EventRow({ event, state, busy, act }: { event: Event } & Props) {
  const [reason, setReason] = useState("");
  const mapping = state.sync.identity_map.find(
    (m) => m.source_id === event.source_id,
  );
  const target = state.league_players.find((p) => p.id === mapping?.target_id);
  const incoming = JSON.parse(event.payload);
  const missing = event.last_error?.startsWith("Missing team mapping");
  return (
    <tr>
      <td>
        <code>{event.event_key}</code>
        <span>{event.created_at.replace("T", " ").replace("Z", "")}</span>
      </td>
      <td>
        <span
          className={`badge ${event.status === "delivered" ? "green" : "amber"}`}
        >
          {event.status}
        </span>
      </td>
      <td>{event.attempts}</td>
      <td className="event-detail">
        {event.last_error || "Versioned Club snapshot; eligibility preserved."}
        {event.status === "failed" && event.attempts < 3 && (
          <small>Automatic retry scheduled; or retry now.</small>
        )}
        {event.status === "failed" && event.attempts >= 3 && (
          <small>Automatic attempts exhausted. Investigate, then retry.</small>
        )}
        {event.status === "conflict" && target && !missing && (
          <details>
            <summary>Review conflict & approve authority</summary>
            <p>
              Club snapshot: {incoming.name}; membership {incoming.membership};
              Club team #{incoming.team_id}.
            </p>
            <p>
              League record #{target.id}: {target.name}; membership{" "}
              {target.membership}; League team #{target.team_id}; revision{" "}
              {target.revision}. Eligibility stays{" "}
              {target.eligible ? "eligible" : "on hold"}.
            </p>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                act(
                  () =>
                    api(`/sync/events/${event.id}/resolve`, {
                      expected_revision: target.revision,
                      reason,
                    }),
                  "Club authority approved and recorded. Event queued for delivery.",
                );
              }}
            >
              <label>
                Reason for approving Club fields
                <input
                  required
                  minLength={8}
                  maxLength={240}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Explain your review decision"
                />
              </label>
              <button disabled={busy} className="secondary">
                Approve Club fields
              </button>
            </form>
          </details>
        )}
      </td>
      <td>
        {event.status === "delivered" ? (
          <button
            className="secondary compact"
            disabled={busy}
            onClick={() =>
              act(
                () => api(`/sync/events/${event.id}/replay`, {}),
                "Same event queued again; version guard will avoid another write.",
              )
            }
          >
            Replay
          </button>
        ) : event.status === "failed" ? (
          <button
            className="secondary compact"
            disabled={busy}
            onClick={() =>
              act(
                () => api(`/sync/events/${event.id}/retry`, {}),
                "Retry queued. Audit history preserved.",
              )
            }
          >
            Retry
          </button>
        ) : event.status === "conflict" ? (
          <span className="subtle">
            {missing ? "Map team below" : "Review required"}
          </span>
        ) : (
          <span className="subtle">Awaiting worker</span>
        )}
      </td>
    </tr>
  );
}

export function TeamManager({ state, busy, act }: Props) {
  const [portal, setPortal] = useState("club");
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [club, setClub] = useState(1);
  const unmapped = state.club_teams.filter(
    (t) => !state.sync.team_map.some((m) => m.source_id === t.id),
  );
  const targets = state.league_teams.filter(
    (t) => !state.sync.team_map.some((m) => m.target_id === t.id),
  );
  return (
    <details>
      <summary>Manage teams & explicit mappings</summary>
      <div className="team-management">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            act(
              () =>
                api(`/${portal}/teams`, {
                  name,
                  code,
                  ...(portal === "club" ? { club_id: club } : {}),
                }),
              "Team created. Reliable delivery needs an explicit team mapping.",
            );
          }}
        >
          <h3>Add a team</h3>
          <div className="team-fields">
            <label>
              Portal
              <select
                value={portal}
                onChange={(e) => setPortal(e.target.value)}
              >
                <option value="club">Club</option>
                <option value="league">League</option>
              </select>
            </label>
            {portal === "club" && (
              <label>
                Club
                <select
                  value={club}
                  onChange={(e) => setClub(Number(e.target.value))}
                >
                  {state.clubs.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <label>
              Team name
              <input
                required
                maxLength={80}
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </label>
            <label>
              Unique code
              <input
                required
                pattern="[A-Z][A-Z0-9]{1,7}"
                value={code}
                maxLength={8}
                onChange={(e) => setCode(e.target.value.toUpperCase())}
                placeholder="CX"
              />
            </label>
            <button disabled={busy}>Create team</button>
          </div>
        </form>
        {state.sync.workflow === "reliable" && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const data = new FormData(e.currentTarget);
              act(
                () =>
                  api("/sync/team-map", {
                    source_id: Number(data.get("source")),
                    target_id: Number(data.get("target")),
                  }),
                "Explicit mapping recorded; affected jobs are queued again.",
              );
            }}
          >
            <h3>Connect an unmapped team</h3>
            <div className="team-fields">
              <label>
                Club team
                <select name="source" required disabled={!unmapped.length}>
                  {unmapped.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name} · #{t.id}
                    </option>
                  ))}
                </select>
              </label>
              <ArrowRight size={16} />
              <label>
                League team
                <select name="target" required disabled={!targets.length}>
                  {targets.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name} · #{t.id}
                    </option>
                  ))}
                </select>
              </label>
              <button disabled={busy || !unmapped.length || !targets.length}>
                Save mapping
              </button>
            </div>
          </form>
        )}
        <div className="mapping-list">
          {state.sync.team_map.map((m) => (
            <span key={m.source_id}>
              Club #{m.source_id} → League #{m.target_id}
            </span>
          ))}
        </div>
      </div>
    </details>
  );
}
