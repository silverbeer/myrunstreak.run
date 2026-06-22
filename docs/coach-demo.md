# Coach demo — Matthew builds + logs Gabe's workout

End-to-end walkthrough of the coach platform (SB-189): invite a coach, give
them an athlete, and have *them* build + log that athlete's training. Everything
below is CLI-driven (`stk`); the same flows back the future web UI.

## Roles in this demo
- **You** — owner/admin (seeded `admin` + `coach`).
- **Matthew** — the trainer; gets a `coach` account via an invite.
- **Gabe** — a managed athlete (14yo, no login).

## 1. Owner: invite Matthew as a coach
```bash
stk invite create --email matthew@example.com --role coach
#   Invite issued for matthew@example.com as coach (expires …)
#   link: https://myrunstreak.run/signup?invite=<token>
```
Text Matthew the link.

## 2. Matthew: redeem → he's a coach
Matthew opens the link, sets a password (web `/signup?invite=…`) — or, since
he's CLI-savvy:
```bash
stk invite redeem --token <token>     # creates his account + logs in
stk athlete whoami                     # roles: coach
```
The `--role coach` on the invite means he's a coach the moment he redeems — no
extra admin step.

## 3. Owner: create Gabe + hand him to Matthew
```bash
stk athlete add --name "Gabe" --birth-year 2011
stk athlete add-coach Gabe --email matthew@example.com
stk athlete coaches Gabe                # shows Matthew as an active coach
```
`add-coach` resolves Matthew by email, grants him `coach` (idempotent), and
links him to Gabe.

> Either the owner or Matthew can create Gabe; whoever does becomes a coach
> automatically. Shown here owner-side so Gabe pre-exists for Matthew.

## 4. Matthew: act as Gabe, build + log
```bash
stk athlete use Gabe                    # active athlete = Gabe
stk athlete whoami                      # active athlete: Gabe

# build Gabe's plan
stk workout add-template --file gabe-circuit.json
stk workout show <template-id>          # Gabe's card

# after the session, log it
stk workout log --file gabe-session.json
stk workout sessions                    # Gabe's sessions, not Matthew's
```
While "using" Gabe, every `stk workout …` call carries `X-Act-As-Athlete: <gabe>`
and is validated against Matthew's roster. Matthew's own workouts (if any) stay
separate — `stk athlete use` with no athlete, or clearing it, returns to self.

## 5. Changing coaches (history follows the athlete)
```bash
stk athlete add-coach Gabe --email newcoach@example.com   # add the new coach
# end the old link (owner or Matthew):
#   DELETE /athletes/<gabe>/coaches/<matthew-id>
```
Because workouts are **owned by the athlete**, the new coach immediately sees
Gabe's full history. The ex-coach loses roster access going forward.

## What's not here yet (roadmap)
- Teams + seasons + "who on my team got faster" (SB-196/197/200/201)
- Coach feedback on sessions (SB-199)
- Web athlete-switcher + coach dashboard (SB-202)
- Athlete/parent self-view via `linked_user_id` (SB-203)
