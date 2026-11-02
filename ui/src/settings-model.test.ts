import { describe, expect, test } from "bun:test";
import { cleanDomain, defaultProfileName, putPath } from "./settings-model";
import type { Config, Profile } from "./proto";

const profile = (): Profile => ({
  mode: "block_list",
  throttle: { rtt_ms: 400, jitter_ms: 50, rate_kbit: 256, loss_pct: 0 },
  block_quic: true,
  inspect_sni: true,
  lock_docker: false,
  rules: [],
  escalation: [],
});

const config = (): Config => ({
  dns: {
    port: 5454,
    upstreams: [],
    forward: [],
    manage_resolved: true,
    container_dns: null,
  },
  session: { default_profile: "deep", stopwatch_min_secs: 600, surrender_wait_secs: 600 },
  schedule: { heads_up_secs: 300, skip_tokens_per_week: 2 },
  nudge: { enabled: true, days: [], from: "09:00", until: "21:00", after_mins: 30, repeat_mins: 15 },
  inverted: { enabled: false, profile: null, free_mins_per_hour: 12, max_bank_mins: 120 },
  routines: [],
  profiles: { deep: profile(), trial: profile() },
});

describe("cleanDomain", () => {
  test("takes a pasted URL down to a rule domain", () => {
    expect(cleanDomain("https://www.YouTube.com/watch?v=1")).toBe("www.youtube.com");
    expect(cleanDomain("example.com/path?q=1")).toBe("example.com");
    expect(cleanDomain("example.com:443")).toBe("example.com");
    expect(cleanDomain("  Example.COM.  ")).toBe("example.com");
  });

  test("leaves a plain domain alone", () => {
    expect(cleanDomain("music.youtube.com")).toBe("music.youtube.com");
    expect(cleanDomain("*.reddit.com")).toBe("reddit.com");
  });
});

describe("putPath", () => {
  test("writes a nested field", () => {
    const c = config();
    putPath(c, "profiles.deep.throttle.rate_kbit", 128);
    putPath(c, "profiles.deep.mode", "allow_only");
    expect(c.profiles.deep.throttle.rate_kbit).toBe(128);
    expect(c.profiles.deep.mode).toBe("allow_only");
  });

  test("writes an array element", () => {
    const c = config();
    c.routines.push({ name: "morning", days: [], start: "09:00", duration_mins: 50, profile: null });
    putPath(c, "routines.0.duration_mins", 90);
    expect(c.routines[0].duration_mins).toBe(90);
  });
});

describe("defaultProfileName", () => {
  test("prefers the configured default", () => {
    expect(defaultProfileName(config())).toBe("deep");
  });

  test("falls back to the first profile when the default is gone", () => {
    const c = config();
    c.session.default_profile = "missing";
    expect(defaultProfileName(c)).toBe("deep");
  });
});
