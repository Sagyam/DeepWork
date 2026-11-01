//! Privilege-escalation hook, run by `pam_exec` and the polkit rule.
//!
//! Exit status 0 means **deny**; anything else allows. The PAM stack only
//! reaches `pam_deny` on a clean 0, so a missing binary, a crash, a timeout or
//! an unreachable daemon all leave sudo working. Root is never gated.
//!
//!     deepwork-pam-gate                   from pam_exec (reads PAM_SERVICE)
//!     deepwork-pam-gate polkit <action>   from the polkit rule

use std::process::ExitCode;
use std::time::Duration;

use deepwork_proto::{Request, Response};

const TIMEOUT: Duration = Duration::from_secs(2);

fn real_uid() -> Option<u32> {
    let status = std::fs::read_to_string("/proc/self/status").ok()?;
    let line = status.lines().find_map(|l| l.strip_prefix("Uid:"))?;
    line.split_whitespace().next()?.parse().ok()
}

fn main() -> ExitCode {
    const ALLOW: u8 = 1;
    let args: Vec<String> = std::env::args().skip(1).collect();
    let (service, uid) = match args.as_slice() {
        [kind, action] if kind == "polkit" => (format!("polkit {action}"), None),
        [] => {
            let Some(uid) = real_uid() else {
                return ExitCode::from(ALLOW);
            };
            if uid == 0 {
                return ExitCode::from(ALLOW);
            }
            let service = std::env::var("PAM_SERVICE").unwrap_or_else(|_| "pam".into());
            let stage = std::env::var("PAM_TYPE").unwrap_or_default();
            (format!("{service} {stage}").trim().to_string(), Some(uid))
        }
        _ => return ExitCode::from(ALLOW),
    };
    // Fixed at build time: a runtime override would let the caller point the
    // gate at a socket that always says "allow".
    let socket = option_env!("DEEPWORK_GATE_SOCKET").unwrap_or(deepwork_proto::DEFAULT_SOCKET);
    let socket = std::path::Path::new(socket);
    match deepwork_proto::request_timeout(socket, &Request::Gate { service, uid }, TIMEOUT) {
        Ok(Response::Gate {
            allow: false,
            message,
        }) => {
            println!("{message}");
            ExitCode::SUCCESS
        }
        _ => ExitCode::from(ALLOW),
    }
}
