export type Team = { id: number; name: string; club_id?: number; code: string };
export type Player = {
  id: number;
  name: string;
  team_id: number;
  club_id?: number;
  membership: string;
  eligible?: number;
  source_ref?: string;
  version?: number;
  revision?: number;
};
type Issue = {
  source_id: number;
  name: string;
  reasons: string[];
  league_ids: number[];
};
export type Event = {
  id: number;
  event_key: string;
  source_id: number;
  version: number;
  payload: string;
  status: string;
  attempts: number;
  last_error: string | null;
  next_attempt: number;
  created_at: string;
};
export type State = {
  clubs: { id: number; name: string }[];
  club_teams: Team[];
  league_teams: Team[];
  club_players: Player[];
  league_players: Player[];
  reconciliation: {
    mismatch_count: number;
    issues: Issue[];
    club_count: number;
    league_count: number;
  };
  worker_enabled: boolean;
  sync: {
    workflow: "baseline" | "reliable";
    failure_budget: number;
    counts: {
      pending: number;
      failed: number;
      delivered: number;
      conflict: number;
    };
    events: Event[];
    audit: {
      id: number;
      event_id: number | null;
      action: string;
      detail: string;
      created_at: string;
    }[];
    identity_map: {
      source_id: number;
      target_id: number;
      last_version: number;
      expected_revision: number;
    }[];
    team_map: { source_id: number; target_id: number }[];
  };
};
