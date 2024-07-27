ass-ask-zsh() {
  local transform=(
    command ass ask --instructions "$ASS_ASK_ZSH_INSTRUCTIONS" --result
    $ASS_ASK_ZSH_TOOLS
  )
  if [[ -n "$BUFFER" ]]
  then out="$(mktemp)"
       BUFFER="$("${transform[@]}" <<< "$BUFFER" 2>"$out")"
       CURSOR=0
       zle -M "$(cat "$out")"
       rm "$out"
  fi
}

zle -N ass-ask-zsh
