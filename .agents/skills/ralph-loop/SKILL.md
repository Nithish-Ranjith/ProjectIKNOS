---
name: ralph-loop
description: Ralph Loop plugin for continuous evaluation, multi-step planning, and recursive checking.
---

# Ralph Loop

When activated, operate in a recursive loop:
1. **Plan**: Before writing any code for a complex task, output a step-by-step plan.
2. **Execute**: Execute the current step of the plan.
3. **Verify**: Test or verify the outcome of the step.
4. **Loop**: Move to the next step. If verification fails, adjust the plan and loop back.
5. **No Halting**: Do not stop until the entire loop is complete and the final objective is verified.
