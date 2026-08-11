#!/bin/bash
# PreToolUse hook on the Agent tool. Enforces AGENTS.md's Subagent Dispatch
# Policy: opus is reserved for the final-reviewer role; anything else
# requesting opus is silently downgraded to sonnet before dispatch.
jq -c '
  if (.tool_input.model == "opus") and (.tool_input.subagent_type != "final-reviewer") then
    {
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "allow",
        updatedInput: (.tool_input + {model: "sonnet"}),
        permissionDecisionReason: "Auto-downgraded opus to sonnet: opus is reserved for the final-reviewer role per AGENTS.md Subagent Dispatch Policy."
      },
      systemMessage: ("Subagent dispatch: opus→sonnet auto-downgrade (subagent_type=" + (.tool_input.subagent_type // "unspecified") + ")")
    }
  else
    {}
  end
'
