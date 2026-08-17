import { useEffect, useState } from "react";
import { api } from "../api";
import type { HealthResponse } from "../types";

export interface HealthState {
  health: HealthResponse | null;
  connected: boolean;
  checking: boolean;
  error: string | null;
}

export function useHealth(pollMs = 10000): HealthState {
  const [state, setState] = useState<HealthState>({
    health: null,
    connected: false,
    checking: true,
    error: null,
  });

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setInterval> | undefined;

    async function check() {
      try {
        const health = await api.health();
        if (!cancelled) setState({ health, connected: true, checking: false, error: null });
      } catch (e) {
        if (!cancelled) {
          setState({
            health: null,
            connected: false,
            checking: false,
            error: e instanceof Error ? e.message : "Unable to reach backend",
          });
        }
      }
    }

    check();
    timer = setInterval(check, pollMs);
    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
    };
  }, [pollMs]);

  return state;
}
