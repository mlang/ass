# Bash integration
#
# To install, run the following command:
#
# eval "$(ass bash)"
#
# And bind the function to a sequence of your liking:
#
# bind -x '"\C-xa": ass_ask_bash'

ASS_ASK_BASH_INSTRUCTIONS="You are a shell command generator.
Whatever you are asked, you will always provide a shell command via the result function tool.
Everything else you say will be echoed to the users screen.
Only return the result via the result function, never display it
using markdown fencing.  Be brief with comments, don't waste the users time."

function ass_ask_bash {
  local transform=(
    ass ask --instructions "$ASS_ASK_BASH_INSTRUCTIONS" --result
  )
  if [[ -n "$READLINE_LINE" ]]
  then READLINE_LINE="$("${transform[@]}" <<< "$READLINE_LINE")"
       READLINE_POINT=0
  fi
}
