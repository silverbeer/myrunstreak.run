# Your Month, Planned. Your Plan, Alive.

**MyRunStreak Adaptive Planning** turns the goals in your head into a plan that
tells you exactly what to do today — and quietly rewrites itself the moment life
gets in the way.

You set the goals. It builds the month. You run. It keeps you honest, keeps you
moving, and tells you the truth about where you stand — with a little push when
you need one.

> *This is a user guide written as the feature ships (P2). The visual month-grid
> walkthrough and screenshots land with the frontend (P3); for now this is the
> CLI + coaching story.*

---

## The idea in one breath

Most goal trackers show you a number and a percentage and leave the math to you.
"You're at 47%." Okay — so what do I run *today*?

Adaptive Planning answers that question every single morning. It takes your
monthly goals, lays them across the calendar, works around the trips and the
rough mornings you can't control, and hands you one thing: **today's plan.** When
you fall behind, it doesn't shame you with a red bar — it reshuffles the rest of
the month so the goal is still reachable, and shows you how.

---

## Set your goals

Tell MyRunStreak what the month is about. A real July:

- **Run every day** — the streak, never broken.
- **135 miles** total.
- **4 long runs** — over 5 miles each.
- **Push-ups** — at least 60, ten times.
- **Weigh in** — ten times.

These aren't five separate apps and five separate nags. They're one month, and
the planner holds all of them at once.

## Get your plan

```bash
stk plan show --period 2026-07
```

Out comes a day-by-day plan: an easy 4-miler here, a long 6 on Saturday, a rest
day with just your streak mile, push-up sessions and weigh-ins slotted in. Every
day has a job. You never have to do the math again.

Better yet, ask your assistant:

> **"How's my July plan looking?"**

and the `plan` skill reads your real plan and talks you through it — where you
stand, what today asks of you, whether you're ahead. Real numbers, plain
language, and a nudge in the right direction.

---

## Life happens. The plan adapts.

This is the part that makes it feel alive.

### You're traveling

You're in **Chicago, July 12–16**. Hotel treadmill, packed schedule — you can
keep the streak, but only a mile a day. Just say so:

> **"I'm in Chicago Thursday through Monday, can only get a mile in."**

The plan pins those five days at one mile, keeps your streak intact, and **moves
the missing miles into the rest of the month** — spread out safely, never dumped
on one brutal day. You left for a trip; you came back to a plan that already
handled it.

### You wake up rough

The plan says 5 miles. You slept badly and your legs feel like sandbags. You
don't have to white-knuckle it or blow up the month:

> **"Slept terrible, not feeling it today."**

Today softens to an easy effort, the load shifts forward, and you get told the
truth: *still on track for 135.* Feeling genuinely sick? Take the rest day — the
plan absorbs it, your streak survives on the floor mile, and nobody panics.

### You fall behind

It's the 28th and the miles didn't happen. Instead of finding out on July 31st
that it was hopeless, the plan flags **at risk** early — and shows you the
concrete catch-up, or tells you honestly when a goal needs to bend. No false
cheer. Just a clear call and the path forward.

---

## Why it actually motivates

- **One job a day.** The month stops being a vague 135 and becomes "today: an
  easy 4.5." Doable. Done. Streak intact.
- **The plan carries the worry, not you.** Travel, a bad night, a missed long
  run — it re-plans so you don't lie awake doing mileage arithmetic.
- **It tells the truth, kindly.** Ahead of pace? You'll hear it. At risk? You'll
  hear that too — early, with a way out, never sugar-coated.
- **Every number is real.** The coaching never makes up a mileage to sound
  encouraging. What it tells you is exactly what the plan says.

---

## The commands behind it

The coaching assistant drives these for you, but they're yours to run directly:

```bash
stk plan show --period 2026-07          # see the month
stk plan recompute                      # rebuild from the latest reality
stk constraint add --metric running_distance \
  --from 2026-07-12 --to 2026-07-16 \
  --cap 1mi --floor 1mi --reason "Chicago travel"
stk readiness set --status tired        # tell it how you feel; it re-plans
```

And every night, while you sleep, the plan recomputes on its own — so the
version waiting for you in the morning already knows about yesterday's run.

---

*Set the goals. Run the miles. Let the plan handle the rest.*
