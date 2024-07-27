ass-ask-bash() {
  local transform=(
    ass ask --instructions "$ASS_ASK_BASH_INSTRUCTIONS" --result
    $ASS_ASK_BASH_TOOLS
  )
  if [[ -n "$READLINE_LINE" ]]
  then READLINE_LINE="$("${transform[@]}" <<< "$READLINE_LINE")"
       READLINE_POINT=0
  fi
}
