# Bash integration
#
# To install, run the following command:
#
# eval "$(ass bash)"

ASS_ASK_BASH_INSTRUCTIONS="You are a shell command generator.
Whenever you are ask something, you will only output a valid shell (bash)
expression (no markdown fencing) which will be directly inserted into the users
readline buffer for review and potential submission to an interactive shell."

function ass_ask_bash {
  local transform=(
    ass ask --instructions "$ASS_ASK_BASH_INSTRUCTIONS" --comment
  )
  if [[ -n "$READLINE_LINE" ]]
  then READLINE_LINE="$("${transform[@]}" <<< "$READLINE_LINE")"
       READLINE_POINT=0
  fi
}

# And bind the function to a sequence of your liking:
#
# bind -x '"\C-xa": ass_ask_bash'
