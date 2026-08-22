# C7 — does activation restart a systemd USER service?
#
# Three questions, in order of value:
#   1. does switch-to-configuration visit the user scope at all?
#   2. does a changed config.yaml -- carried into the unit as
#      X-Restart-Triggers -- restart the user service in the same activation?
#   3. what does the developer see when the restart does NOT happen?
#
# Question 3 is built by hand so the answer is on record whichever way 2 comes
# out: generation B's config.yaml is installed underneath a server that was
# started on generation A's, which is exactly the state an activation that
# skips the restart leaves behind.

import re


def sep(title):
    machine.log("")
    machine.log("=" * 70)
    machine.log("C7 :: " + title)
    machine.log("=" * 70)


ENV = (
    "XDG_RUNTIME_DIR=/run/user/1000 "
    "DAGU_HOME=/home/tester/.local/share/dagu "
)


def u(cmd):
    return machine.succeed("su tester -c '" + ENV + cmd + "' 2>&1")


def try_u(cmd):
    rc, out = machine.execute("su tester -c '" + ENV + cmd + "' 2>&1")
    return "rc=%d\n%s" % (rc, out)


machine.start()
machine.wait_for_unit("multi-user.target")

sep("0. the user manager is running and logind lists the user")
machine.wait_for_unit("user@1000.service")
machine.log(machine.succeed("loginctl list-users"))
machine.wait_until_succeeds(
    "su tester -c 'XDG_RUNTIME_DIR=/run/user/1000 systemctl --user is-active dagu.service'",
    timeout=90,
)

sep("1. generation A")
unit_a = machine.succeed("cat /etc/systemd/user/dagu.service")
machine.log(unit_a)
m = re.search(r"X-Restart-Triggers=(.*)", unit_a)
trig_a = m.group(1) if m else "<ABSENT>"
machine.log("X-Restart-Triggers (A) = " + trig_a)

cfg_a = u("cat ~/.local/share/dagu/config.yaml")
machine.log("--- config.yaml, generation A:\n" + cfg_a)

inv_a = u("systemctl --user show dagu.service -p InvocationID --value").strip()
pid_a = u("systemctl --user show dagu.service -p MainPID --value").strip()
machine.log("dagu InvocationID (A) = %s   MainPID (A) = %s" % (inv_a, pid_a))

sep("2. activate generation B — the queues change, nothing else does")
sw = machine.succeed(
    "/run/current-system/specialisation/newqueues/bin/switch-to-configuration test 2>&1"
)
machine.log("--- switch-to-configuration output, verbatim:\n" + sw)
machine.log("--- lines mentioning the user scope or dagu:")
for line in sw.splitlines():
    if "user" in line.lower() or "dagu" in line.lower():
        machine.log("    >> " + line)

sep("3. did the unit change, and did the service restart?")
unit_b = machine.succeed("cat /etc/systemd/user/dagu.service")
m = re.search(r"X-Restart-Triggers=(.*)", unit_b)
trig_b = m.group(1) if m else "<ABSENT>"
machine.log("X-Restart-Triggers (B) = " + trig_b)
machine.log("unit file changed : " + str(unit_a != unit_b))
machine.log("trigger changed   : " + str(trig_a != trig_b))

inv_b = u("systemctl --user show dagu.service -p InvocationID --value").strip()
pid_b = u("systemctl --user show dagu.service -p MainPID --value").strip()
machine.log("dagu InvocationID (B) = %s   MainPID (B) = %s" % (inv_b, pid_b))
machine.log(">>> RESTARTED IN THE SAME ACTIVATION: " + str(inv_a != inv_b))

cfg_b = u("cat ~/.local/share/dagu/config.yaml")
machine.log("--- config.yaml after activation:\n" + cfg_b)
machine.log("config.yaml rewritten: " + str(cfg_a != cfg_b))

sep("4. the divergence: generation B's config.yaml under a generation A server")
# Reproduce the state an activation that skips the restart would leave, using
# the real generated files rather than hand-written YAML. Generation A's
# config is the first store path in generation A's X-Restart-Triggers;
# generation B's is the first in B's.
# X-Restart-Triggers points at a file whose contents are the triggering store
# paths, space separated: config.yaml first, base.yaml second.
cfg_path_a = machine.succeed("cat " + trig_a).split()[0]
cfg_path_b = machine.succeed("cat " + trig_b).split()[0]
machine.log("generation A config: " + cfg_path_a)
machine.log("generation B config: " + cfg_path_b)

u("systemctl --user stop dagu.service")
machine.succeed("install -m 0644 %s /home/tester/.local/share/dagu/config.yaml" % cfg_path_a)
machine.succeed("chown tester /home/tester/.local/share/dagu/config.yaml")
# Start the server WITHOUT the unit's ExecStartPre, so the file we put there
# survives. This is the running server of generation A.
machine.succeed(
    "su tester -c '" + ENV + "setsid dagu start-all >/tmp/dagu-a.log 2>&1 &'"
)
machine.sleep(8)
machine.log("--- server started on generation A's config:")
machine.log(try_u("dagu ls"))

machine.log("--- now install generation B's config.yaml underneath it, no restart")
machine.succeed("install -m 0644 %s /home/tester/.local/share/dagu/config.yaml" % cfg_path_b)
machine.succeed("chown tester /home/tester/.local/share/dagu/config.yaml")

machine.succeed("mkdir -p /home/tester/.local/share/dagu/dags")
machine.succeed(
    "cat > /home/tester/.local/share/dagu/dags/c7probe.yaml <<'EOF'\n"
    "queue: light\n"
    "steps:\n"
    "  - name: hello\n"
    "    command: sleep 30\n"
    "EOF"
)
machine.succeed("chown -R tester /home/tester/.local/share/dagu/dags")

machine.log("--- generation B config.yaml:\n" + machine.succeed("cat " + cfg_path_b))
machine.log("--- generation A config.yaml (what the server is running):\n" + machine.succeed("cat " + cfg_path_a))

machine.log("--- what the CLI says, reading the NEW config.yaml:")
machine.log(try_u("dagu enqueue c7probe --run-id c7run1"))
machine.sleep(10)
machine.log("--- dagu status:")
machine.log(try_u("dagu status c7probe"))
machine.log("--- dagu ps:")
machine.log(try_u("dagu ps"))
machine.log("--- the server's own log while this happened:")
machine.log(machine.succeed("tail -40 /tmp/dagu-a.log || true"))

sep("5. after a restart, which is what §5.2 says activation must do")
machine.execute("pkill -f 'dagu start-all'")
machine.sleep(3)
machine.succeed(
    "su tester -c '" + ENV + "setsid dagu start-all >/tmp/dagu-b.log 2>&1 &'"
)
machine.sleep(8)
machine.log(try_u("dagu enqueue c7probe --run-id c7run2"))
machine.sleep(10)
machine.log(try_u("dagu status c7probe"))
machine.log(try_u("dagu ps"))
machine.log(machine.succeed("tail -40 /tmp/dagu-b.log || true"))

sep("done")
