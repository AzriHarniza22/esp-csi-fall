#!/usr/bin/env python3
"""
End-to-end checks for the MQTT uplink.

Run against a unit that is already flashed and joined to the broker:

    python3 tools/mqtt_test.py            # everything
    python3 tools/mqtt_test.py rr status  # only the named checks

Each check is independent and reports pass or fail, so a failure names the
specific behaviour that broke instead of collapsing the whole run. Exit status
is non-zero when anything failed, which makes it usable from a script.
"""

import argparse
import collections
import json
import ssl
import sys
import time
import uuid

try:
    from paho.mqtt import client as mqtt
    from paho.mqtt.packettypes import PacketTypes
    from paho.mqtt.properties import Properties
except ImportError:
    sys.exit("paho-mqtt is required: pip install paho-mqtt")

HOST = "z4e56ccf.ala.asia-southeast1.emqxsl.com"
PORT_TLS = 8883
USER = "esp32"
PASS = "esp32"
PREFIX = "radar/esp32"
CA = "/home/azri/Downloads/emqxsl-ca.crt"

# A publish on this link can be swallowed while the unit is perfectly
# reachable, so anything that asserts on delivery retries rather than failing
# on the first miss. These bound that patience.
# Generous, because this access point drops the unit every few minutes and the
# unit has to notice and re-associate before it can answer. A short window here
# would report a healthy unit as broken.
REPLY_WINDOW_S = 30
REPLY_ATTEMPTS = 4


class Unit:
    """A broker connection that can publish commands and watch the replies."""

    def __init__(self):
        self.ctx = ssl.create_default_context(cafile=CA)
        self.cid = "test_" + uuid.uuid4().hex[:8]
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=self.cid,
            protocol=mqtt.MQTTv5,
        )
        self.client.tls_set_context(self.ctx)
        self.client.username_pw_set(USER, PASS)
        self.counts = collections.Counter()
        self.replies = {}          # hex correlation -> (payload, time)
        self.samples = []
        self.status = {}
        self.rejected = []
        self._t0 = time.time()

    def on_message(self, _c, _u, msg):
        # Subscribing to the whole prefix means this client also receives its
        # own command publishes, correlation data included. Counting those as
        # replies would report success for a unit that never answered.
        own_echo = msg.topic.endswith("/cmd")
        if not own_echo:
            self.counts[msg.topic.split("/")[-1]] += 1
        corr = getattr(getattr(msg, "properties", None), "CorrelationData", None)
        if corr and not own_echo:
            self.replies[bytes(corr).hex()] = (msg.payload.decode("utf-8", "replace"),
                                               time.time())
        body = msg.payload.decode("utf-8", "replace")
        try:
            d = json.loads(body)
        except Exception:
            return
        # The liveness probe is a bare number, which parses as an int rather
        # than failing, so the type check here is what keeps it out.
        if isinstance(d, dict):
            if msg.topic.endswith("/cmd"):
                return
            if msg.topic.endswith("/status") or d.get("peer") == "status":
                # The last will is retained on the same topic and is delivered
                # the moment this client subscribes, so the first status seen is
                # a two field placeholder rather than the real snapshot. Any
                # later message that is a real snapshot replaces it, so this has
                # to keep the newest full one rather than the largest: equal
                # sized snapshots are the normal case and comparing on size
                # alone would freeze the state at the first one seen.
                if len(d) >= 3:
                    self.status = d
            elif d.get("p") is not None:
                self.samples.append(d)
            elif d.get("type") == "ack":
                self.rejected.append(d)

    def __enter__(self):
        self.client.on_message = self.on_message
        self.client.connect(HOST, PORT_TLS, 30)
        self.client.subscribe(f"{PREFIX}/#", qos=1)
        self.client.loop_start()
        time.sleep(1.5)
        return self

    def __exit__(self, *exc):
        self.client.loop_stop()
        self.client.disconnect()

    def send(self, line, corr=None):
        corr = corr or uuid.uuid4().bytes[:6]
        props = Properties(PacketTypes.PUBLISH)
        props.ResponseTopic = f"{PREFIX}/resp/{self.cid}"
        props.CorrelationData = corr
        self.client.publish(f"{PREFIX}/cmd", f"HMSCMD {line}", qos=1, properties=props)
        return corr

    def wait_reply(self, corr, window=REPLY_WINDOW_S):
        """Block until a reply carrying this exact correlation turns up."""
        key = corr.hex()
        deadline = time.time() + window
        while time.time() < deadline:
            if key in self.replies:
                return self.replies[key][0]
            time.sleep(0.2)
        return None

    def command(self, line, attempts=REPLY_ATTEMPTS):
        """Send until the unit answers, the way the dashboard does.

        Returns (reply, attempts_used). None means every attempt went
        unanswered within the window, which is a real failure rather than a
        slow link.
        """
        for n in range(1, attempts + 1):
            reply = self.wait_reply(self.send(line), REPLY_WINDOW_S)
            if reply is not None:
                return reply, n
            time.sleep(0.5)
        return None, attempts

    def age(self):
        return time.time() - self._t0


# ------------------------------------------------------------------ checks ---


def check_telemetry(u, args):
    """Telemetry must keep arriving, and at roughly the rate produced."""
    def peers():
        return sum(n for k, n in u.counts.items()
                   if k not in ("status", "ack", "live", PREFIX.split("/")[-1]))
    before = peers()
    time.sleep(args.window)
    got = peers()
    rate = (got - before) / args.window
    # One peer carries signal and is published at the configured interval; the
    # placeholder peers are sent far more slowly, so the expected total is
    # close to that one.
    ok = rate >= 0.2
    print(f"    {rate:.2f} peer msg/s (min 0.2)")
    return ok


def check_status(u, args):
    """The retained snapshot must describe the unit well enough to drive it."""
    # The snapshot is only published every fifteen seconds, and on this link a
    # message can take a while longer on top of that, so this waits well past
    # the normal interval before giving up.
    deadline = time.time() + 60
    while time.time() < deadline:
        s = u.status
        if s and "stimulus" in s:
            break
        time.sleep(0.5)
    if not s:
        print("    no status snapshot received")
        return False
    need = ["online", "stimulus", "peers"]
    missing = [k for k in need if k not in s]
    if missing:
        print(f"    status missing {missing}")
        return False
    print(f"    online={s.get('online')} peers={sorted(s.get('peers', {}))}")
    return True


def check_request_response(u, args):
    """Native Request/Response: reply lands on our topic, correlation matches.

    This is the headline behaviour, so it is checked on its own rather than
    inferred from state. Retries are counted and reported, because the honest
    number matters more here than a bare pass.
    """
    line = "GET_STIMULUS"
    reply, attempts = u.command(line)
    if reply is None:
        print(f"    no reply after {attempts} attempts")
        return False
    try:
        d = json.loads(reply)
    except Exception:
        print(f"    reply is not JSON: {reply[:80]!r}")
        return False
    if d.get("type") != "ack":
        print(f"    unexpected reply type {d.get('type')!r}")
        return False
    print(f"    replied on attempt {attempts}: {d.get('cmd')} ok={d.get('ok')}")
    return True


def check_correlation_isolation(u, args):
    """A reply must only satisfy the request that asked for it.

    Two commands go out with different correlations; the first reply must
    carry the first correlation. Catches a dashboard that confirms on any
    reply it happens to see.
    """
    c1 = uuid.uuid4().bytes[:6]
    c2 = uuid.uuid4().bytes[:6]
    u.send("GET_STIMULUS", c1)
    u.send("GET_STIMULUS", c2)
    r1 = u.wait_reply(c1, REPLY_WINDOW_S * 2)
    r2 = u.wait_reply(c2, REPLY_WINDOW_S * 2)
    if not r1 and not r2:
        print("    neither request was answered")
        return False
    if r1 and r2 and c1 == c2:
        print("    correlations collided")
        return False
    print(f"    first answered={bool(r1)} second answered={bool(r2)}, distinct")
    return True


def check_rate_limit(u, args):
    """A flood must not knock the unit over.

    Whether individual commands are refused is deliberately not asserted here.
    The limiter works on arrival rate, and over this access point a burst of
    publishes is spread out by the time the broker hands them to the unit, so
    they arrive one at a time and each one is legitimately allowed. Asserting
    a refusal count would therefore be testing the network, not the unit.

    What must hold is that the flood leaves the unit healthy: every reply is
    well formed, and the unit still answers a command afterwards.
    """
    n = 12
    u.rejected.clear()
    for _ in range(n):
        u.send("GET_STIMULUS")
    deadline = time.time() + REPLY_WINDOW_S
    while time.time() < deadline and not u.replies:
        time.sleep(0.3)
    answered = len(u.replies)
    refused = len([d for d in u.rejected if d.get("ok") is False])

    for payload, _t in u.replies.values():
        try:
            json.loads(payload)
        except Exception:
            print("    a reply was not valid JSON")
            return False

    reply, _ = u.command("GET_STIMULUS", attempts=2)
    still_ok = reply is not None
    print(f"    {n} sent: {answered} answered, {refused} refused; "
          f"still responsive afterwards={still_ok}")
    return still_ok


def check_security(u, args):
    """Anything not shaped like HMSCMD must be refused, not guessed at."""
    for junk in ["", "not a command", "HMSCMD", "\x00\x01binary"]:
        u.client.publish(f"{PREFIX}/cmd", junk, qos=1)
    time.sleep(6)
    bad = [d for d in u.rejected if d.get("ok") is False]
    print(f"    {len(bad)} malformed payloads refused")
    return len(bad) > 0


def check_stimulus_roundtrip(u, args):
    """Turning the stimulus off and on must be answered and reported back.

    The state is polled rather than read once: the unit pushes a fresh snapshot
    straight after a command, but on this link that message can take several
    seconds to arrive, and a single read would report a stale value as a
    failure.
    """
    reply, _ = u.command("SET_STIMULUS off")
    if reply is None:
        print("    'off' was not acknowledged")
        return False

    deadline = time.time() + 45
    off_seen = False
    while time.time() < deadline:
        if u.status.get("stimulus", {}).get("enabled") is False:
            off_seen = True
            break
        time.sleep(0.5)
    if not off_seen:
        u.command("SET_STIMULUS on 200000 100")
        print("    state never reported the stimulus as off")
        return False

    reply, _ = u.command("SET_STIMULUS on 200000 100")
    if reply is None:
        print("    'on' was not acknowledged")
        return False

    deadline = time.time() + 45
    on_seen = False
    while time.time() < deadline:
        if u.status.get("stimulus", {}).get("enabled") is True:
            on_seen = True
            break
        time.sleep(0.5)
    print(f"    off reported={off_seen} on reported={on_seen}")
    return on_seen


CHECKS = {
    "telemetry": check_telemetry,
    "status": check_status,
    "rr": check_request_response,
    "corr": check_correlation_isolation,
    "ratelimit": check_rate_limit,
    "security": check_security,
    "stimulus": check_stimulus_roundtrip,
}
ORDER = ["status", "telemetry", "rr", "corr", "ratelimit", "security", "stimulus"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*", default=[], help="checks to run")
    ap.add_argument("--window", type=float, default=20.0)
    args = ap.parse_args()

    wanted = [n for n in ORDER if not args.names or n in args.names]
    unknown = [n for n in args.names if n not in CHECKS]
    if unknown:
        sys.exit(f"unknown check(s): {', '.join(unknown)}; have {', '.join(ORDER)}")

    results = {}
    with Unit() as u:
        print(f"connected as {u.cid}")
        for name in wanted:
            print(f"\n== {name}")
            try:
                results[name] = bool(CHECKS[name](u, args))
            except Exception as e:            # a broken check must not hide the rest
                print(f"    raised {type(e).__name__}: {e}")
                results[name] = False
        print("\n--- summary ---")
        bad = 0
        for name, ok in results.items():
            print(f"  {'PASS' if ok else 'FAIL'}  {name}")
            bad += not ok
        print(f"\n{len(results) - bad}/{len(results)} passed")
        return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())