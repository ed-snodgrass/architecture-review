#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
fake_bin="$scratch/bin"
fake_home="$scratch/home"
mkdir -p "$fake_bin" "$fake_home"

fake() {
  local name="$1" body="$2"
  printf '#!/usr/bin/env bash\n%s\n' "$body" >"$fake_bin/$name"
  chmod +x "$fake_bin/$name"
}

for tool in npm git claude codex; do
  fake "$tool" 'case "$1 ${2-}" in *status*) exit 1 ;; *) echo "fake 1.0" ;; esac'
done
fake pi '
if [[ "$1 ${2-} ${3-}" == "auth check --help" ]]; then exit 0; fi
if [[ "$1 ${2-}" == "auth check" ]]; then
  [[ "${PI_AUTH_RESULT-fail}" == ready ]] && { printf "{\\"status\\":\\"ready\\"}\\n"; exit 0; }
  printf "{\\"status\\":\\"not_ready\\"}\\n"
  exit 1
fi
echo "fake 1.0"'

run_doctor() {
  env -u ANTHROPIC_API_KEY -u OPENAI_API_KEY -u GEMINI_API_KEY -u XAI_API_KEY -u OPENROUTER_API_KEY \
    PATH="$fake_bin:$PATH" HOME="$fake_home" NO_COLOR=1 \
    PI_AUTH_RESULT="${PI_AUTH_RESULT-fail}" OPENAI_API_KEY="${DOCTOR_TEST_OPENAI_KEY-}" \
    /bin/bash "$repo_root/bin/doctor" "$@"
}

if run_doctor --agent nope >/dev/null 2>&1; then
  echo 'expected invalid agent to fail' >&2
  exit 1
fi
if run_doctor --agent pi >/dev/null 2>&1; then
  echo 'expected selected unconfigured agent to fail' >&2
  exit 1
fi
if run_doctor >/dev/null 2>&1; then
  echo 'expected no configured agents to fail' >&2
  exit 1
fi

if ! DOCTOR_TEST_OPENAI_KEY=present PI_AUTH_RESULT=ready run_doctor --agent pi >/dev/null; then
  echo 'expected Pi native ready check to pass for an environment-key provider' >&2
  exit 1
fi
if ! DOCTOR_TEST_OPENAI_KEY=present PI_AUTH_RESULT=ready run_doctor >/dev/null; then
  echo 'expected default mode to pass with one configured agent' >&2
  exit 1
fi
if DOCTOR_TEST_OPENAI_KEY=present PI_AUTH_RESULT=ready run_doctor --agent all >/dev/null 2>&1; then
  echo 'expected --agent all to require every configured agent' >&2
  exit 1
fi

mkdir -p "$fake_home/.pi/agent"
printf '%s\n' '{"anthropic":{"type":"api_key","key":"test-secret"}}' >"$fake_home/.pi/agent/auth.json"
if ! PI_AUTH_RESULT=ready run_doctor --agent pi >/dev/null; then
  echo 'expected Pi native ready check to pass for a stored provider' >&2
  exit 1
fi
if stale_output=$(PI_AUTH_RESULT=fail run_doctor --agent pi); then
  echo 'expected stale Pi credentials to fail the native check' >&2
  exit 1
fi
if [[ "$stale_output" == *test-secret* || "$stale_output" != *'not ready for anthropic'* ]]; then
  echo 'expected stale Pi output to be redacted and actionable' >&2
  exit 1
fi
rm -rf "$fake_home/.pi"
if unknown_output=$(PI_AUTH_RESULT=ready run_doctor --agent pi); then
  echo 'expected Pi with no identifiable provider to remain unknown' >&2
  exit 1
fi
if [[ "$unknown_output" != *'readiness is unknown'* ]]; then
  echo 'expected an unknown Pi configuration warning' >&2
  exit 1
fi

fake claude 'case "$1 ${2-}" in *auth\ status*) exit 0 ;; *) echo "fake 1.0" ;; esac'
if ! run_doctor --agent claude >/dev/null; then
  echo 'expected Claude configured state to pass' >&2
  exit 1
fi

fake codex 'case "$1 ${2-}" in *login\ status*) exit 0 ;; *) echo "fake 1.0" ;; esac'
if ! run_doctor --agent codex >/dev/null; then
  echo 'expected Codex configured state to pass' >&2
  exit 1
fi

printf 'doctor tests passed\n'
